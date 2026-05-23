-- =============================================================================
-- Migracja 0001 - inicjalizacja bazy agenta naborow
-- Wykonaj w Supabase SQL Editor (lub przez `supabase db push` jesli uzywasz CLI).
-- =============================================================================

-- Wlacz rozszerzenia
create extension if not exists "uuid-ossp";
create extension if not exists "pg_trgm";

-- =============================================================================
-- ENUM-y
-- =============================================================================

do $$ begin
    create type call_status as enum ('draft', 'published', 'rejected');
exception
    when duplicate_object then null;
end $$;

do $$ begin
    create type fetcher_type as enum ('http', 'playwright', 'rss', 'pdf');
exception
    when duplicate_object then null;
end $$;

do $$ begin
    create type beneficiary_type as enum ('msp', 'ngo', 'samorzad', 'startup', 'duza_firma', 'rolnictwo', 'osoba_fizyczna', 'inne');
exception
    when duplicate_object then null;
end $$;

-- =============================================================================
-- Tabela: sources
-- =============================================================================

create table if not exists public.sources (
    id              uuid primary key default uuid_generate_v4(),
    name            text not null unique,
    url             text not null,
    fetcher         fetcher_type not null,
    extractor       text not null default 'css',
    config          jsonb not null default '{}'::jsonb,
    active          boolean not null default true,
    last_run_at     timestamptz,
    last_status     text,
    last_error      text,
    notes           text,
    created_at      timestamptz not null default now(),
    updated_at      timestamptz not null default now()
);

create index if not exists idx_sources_active on public.sources(active);

-- =============================================================================
-- Tabela: calls (nabory)
-- =============================================================================

create table if not exists public.calls (
    id                      uuid primary key default uuid_generate_v4(),
    source_id               uuid references public.sources(id) on delete set null,
    external_id_hash        text not null unique,
    title                   text not null,
    url                     text not null,
    deadline                date,
    deadline_text           text,
    region                  text,
    beneficiary             beneficiary_type,
    program                 text,
    amount_min              numeric,
    amount_max              numeric,
    amount_currency         text default 'PLN',
    summary                 text,
    raw_text                text,
    profile_match_score     int check (profile_match_score >= 0 and profile_match_score <= 100),
    profile_match_reason    text,
    status                  call_status not null default 'draft',
    published_at            timestamptz,
    created_at              timestamptz not null default now(),
    updated_at              timestamptz not null default now()
);

create index if not exists idx_calls_status on public.calls(status);
create index if not exists idx_calls_deadline on public.calls(deadline);
create index if not exists idx_calls_match_score on public.calls(profile_match_score desc);
create index if not exists idx_calls_created_at on public.calls(created_at desc);
create index if not exists idx_calls_source_id on public.calls(source_id);
create index if not exists idx_calls_title_trgm on public.calls using gin (title gin_trgm_ops);

-- =============================================================================
-- Tabele: tags + call_tags
-- =============================================================================

create table if not exists public.tags (
    id          uuid primary key default uuid_generate_v4(),
    slug        text not null unique,
    label       text not null,
    category    text,
    created_at  timestamptz not null default now()
);

create index if not exists idx_tags_category on public.tags(category);

create table if not exists public.call_tags (
    call_id     uuid not null references public.calls(id) on delete cascade,
    tag_id      uuid not null references public.tags(id) on delete cascade,
    primary key (call_id, tag_id)
);

create index if not exists idx_call_tags_tag on public.call_tags(tag_id);

-- =============================================================================
-- Tabela: subscribers (Etap 5 - newsletter klientow)
-- =============================================================================

create table if not exists public.subscribers (
    id                  uuid primary key default uuid_generate_v4(),
    email               text not null unique,
    name                text,
    company             text,
    interest_ue         boolean not null default false,
    interest_kpo        boolean not null default false,
    interest_regional   boolean not null default false,
    confirmed_at        timestamptz,
    unsubscribe_token   text not null default encode(gen_random_bytes(24), 'hex'),
    unsubscribed_at     timestamptz,
    created_at          timestamptz not null default now()
);

create index if not exists idx_subscribers_confirmed on public.subscribers(confirmed_at) where unsubscribed_at is null;

-- =============================================================================
-- Tabela: audit_log
-- =============================================================================

create table if not exists public.audit_log (
    id          uuid primary key default uuid_generate_v4(),
    actor       text not null,
    action      text not null,
    entity      text not null,
    entity_id   uuid,
    details     jsonb,
    created_at  timestamptz not null default now()
);

create index if not exists idx_audit_log_entity on public.audit_log(entity, entity_id);
create index if not exists idx_audit_log_created on public.audit_log(created_at desc);

-- =============================================================================
-- Tabela: run_log (statystyki dziennych runow)
-- =============================================================================

create table if not exists public.run_log (
    id              uuid primary key default uuid_generate_v4(),
    started_at      timestamptz not null default now(),
    finished_at     timestamptz,
    sources_total   int not null default 0,
    sources_ok      int not null default 0,
    sources_failed  int not null default 0,
    new_calls       int not null default 0,
    enriched_calls  int not null default 0,
    mail_sent       boolean not null default false,
    error           text,
    summary         jsonb
);

create index if not exists idx_run_log_started on public.run_log(started_at desc);

-- =============================================================================
-- Trigger: aktualizacja updated_at
-- =============================================================================

create or replace function public.set_updated_at()
returns trigger as $$
begin
    new.updated_at = now();
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_sources_updated on public.sources;
create trigger trg_sources_updated
    before update on public.sources
    for each row execute function public.set_updated_at();

drop trigger if exists trg_calls_updated on public.calls;
create trigger trg_calls_updated
    before update on public.calls
    for each row execute function public.set_updated_at();

-- Auto-stempel published_at gdy status zmienia sie na 'published'
create or replace function public.set_published_at()
returns trigger as $$
begin
    if new.status = 'published' and (old.status is null or old.status != 'published') then
        new.published_at = now();
    end if;
    return new;
end;
$$ language plpgsql;

drop trigger if exists trg_calls_published on public.calls;
create trigger trg_calls_published
    before update on public.calls
    for each row execute function public.set_published_at();

-- =============================================================================
-- RLS - Row Level Security
-- =============================================================================
-- Dostep przez service_role (z GitHub Actions) jest pelny i pomija RLS.
-- Dla anon role (read-only z frontendu inwestycjepomorze.pl) - tylko `published` calls.
-- =============================================================================

alter table public.sources enable row level security;
alter table public.calls enable row level security;
alter table public.tags enable row level security;
alter table public.call_tags enable row level security;
alter table public.subscribers enable row level security;
alter table public.audit_log enable row level security;
alter table public.run_log enable row level security;

-- Public (anon) widzi tylko opublikowane nabory + ich tagi - dla strony firmy.
drop policy if exists "anon_read_published_calls" on public.calls;
create policy "anon_read_published_calls"
    on public.calls for select
    to anon
    using (status = 'published');

drop policy if exists "anon_read_tags" on public.tags;
create policy "anon_read_tags"
    on public.tags for select
    to anon
    using (true);

drop policy if exists "anon_read_call_tags" on public.call_tags;
create policy "anon_read_call_tags"
    on public.call_tags for select
    to anon
    using (
        exists (
            select 1 from public.calls c
            where c.id = call_tags.call_id and c.status = 'published'
        )
    );

-- Anon moze sie zapisac na newsletter (insert), ale nie czytac listy.
drop policy if exists "anon_insert_subscribers" on public.subscribers;
create policy "anon_insert_subscribers"
    on public.subscribers for insert
    to anon
    with check (true);

-- =============================================================================
-- Widok: published_calls_v - wygodny widok dla frontendu
-- =============================================================================

create or replace view public.published_calls_v as
select
    c.id,
    c.title,
    c.url,
    c.deadline,
    c.deadline_text,
    c.region,
    c.beneficiary,
    c.program,
    c.amount_min,
    c.amount_max,
    c.amount_currency,
    c.summary,
    c.published_at,
    s.name as source_name,
    coalesce(
        (select array_agg(t.slug order by t.slug)
         from public.call_tags ct
         join public.tags t on t.id = ct.tag_id
         where ct.call_id = c.id),
        array[]::text[]
    ) as tags
from public.calls c
left join public.sources s on s.id = c.source_id
where c.status = 'published'
order by c.deadline asc nulls last, c.published_at desc;

grant select on public.published_calls_v to anon;
