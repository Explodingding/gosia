# Etap 4 - Integracja sekcji Nabory z `inwestycjepomorze.pl`

## Wnioski z pre-researchu

Strona `inwestycjepomorze.pl` to:

- **Statyczne HTML** hostowane na **Netlify** (nie WordPress, nie Next.js, nie Astro)
- **Tailwind CSS** jako system stylow
- **EmailJS** dla formularzy
- **Font Awesome** dla ikon

WAZNE: w HTML-u sa juz **gotowe puste kontenery** czekajace na podlaczenie:

```html
<section id="fundusze">
  <div id="fundusze-updated"></div>
  <div id="fundusze-count"></div>
  <div id="fundusze-status"></div>
  <div id="fundusze-calls"><div id="fundusze-calls-list"></div></div>
  <div id="fundusze-programs"><div id="fundusze-programs-list"></div></div>
</section>
```

Czyli ktos juz przygotowal miejsce - wystarczy wstrzyknac JavaScript.

## Wybrana strategia

**Client-side JS + Supabase REST** (najprostsza, dziala od reki, zero zmian w build pipelinie strony).

Dwie opcje dostepu do danych:

### Opcja A - bezposredni REST z `published_calls_v`

- Front woła `https://<project>.supabase.co/rest/v1/published_calls_v?...`.
- Anon key publikowany w meta tagu (chroniony przez RLS - `anon` widzi tylko `status=published`).
- **Plus:** zero infrastruktury Supabase Edge Function, prostsze.
- **Minus:** kazdy wpis renderuje request do bazy (Supabase free tier: 500 MB DB, 5 GB transfer/mies - wystarcza z duzym zapasem przy ~200 naborach i ~1000 odwiedzin/mies).

### Opcja B - Edge Function `public-calls` z CDN cache

- Front woła `https://<project>.supabase.co/functions/v1/public-calls?status=open`.
- Function cachuje wynik w edge CDN (5 min `s-maxage`).
- **Plus:** szybciej, mniej query do bazy, latwiej kontrolowac CORS.
- **Minus:** dodatkowy element infrastruktury (chociaz oba sa w tym samym Supabase projekcie).

**Rekomendacja: zaczynamy od opcji A**, jesli ruch wzrosnie -> przelaczymy na B (zmiana 1 linii w widget.js).

Edge Function jest juz przygotowany w [supabase/functions/public-calls/index.ts](../supabase/functions/public-calls/index.ts) - mozna wdrozyc kiedykolwiek.

## Wdrozenie krok-po-kroku

### Krok 1. Pobranie anon key z Supabase

1. Supabase Dashboard -> **Project Settings -> API**.
2. Skopiuj:
   - **Project URL** (np. `https://xxxxxxxxxxxxxxxx.supabase.co`)
   - **anon public** key (ten zaczynajacy sie od `eyJ...`, oznaczony jako `public`).

> UWAGA: anon key jest BEZPIECZNY w HTML. Chroni go RLS (`anon` widzi tylko opublikowane nabory). NIGDY nie wkladaj tu `service_role` key - to byloby krytyczne wycieknnie.

### Krok 2. Dodanie meta tagow do `<head>` strony

W repozytorium strony `inwestycjepomorze.pl` (lub edytor Netlify CMS, jesli go uzywacie), dodaj do `<head>`:

```html
<meta name="supabase-url" content="https://xxxxxxxxxxxxxxxx.supabase.co">
<meta name="supabase-anon-key" content="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...">
```

### Krok 3. Wgranie skryptu widgetu

Skopiuj plik [`integration/website/nabory-widget.js`](../integration/website/nabory-widget.js) do repo strony, np. jako `static/js/nabory-widget.js`.

W `<body>` dodaj na koncu (przed `</body>`):

```html
<script src="/js/nabory-widget.js" defer></script>
```

### Krok 4. (Opcjonalnie) Uzupelnienie szkieletu sekcji

Jesli sekcja `<section id="fundusze">` nie ma jeszcze wewnetrznej struktury HTML zgodnej z widgetem, wklej szkielet z [`integration/website/snippet.html`](../integration/website/snippet.html). Widget sam wypelni elementy.

### Krok 5. Deploy + weryfikacja

1. `git push` -> Netlify automatycznie zbuduje i wdrozy.
2. Wejdz na inwestycjepomorze.pl -> sekcja Fundusze powinna sie wypelnic naborami.
3. Sprawdz konsole przegladarki (F12) - widget loguje bledy do `console.error`.

### Krok 6. (Opcjonalnie) Wdrozenie Edge Function

Jesli chcesz przelaczyc widget na Edge Function (lepsze cache):

```bash
# Lokalnie, w katalogu nabory/
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase functions deploy public-calls --no-verify-jwt
```

W `nabory-widget.js` zmien `fetchPublishedCalls` na:

```javascript
const url = `${CONFIG.url.replace(/\/$/, "")}/functions/v1/public-calls?status=all`;
```

## Filtry, ktore obsluguje widget

- **Status**: Wszystkie / Trwa (deadline >= dzis) / Nadchodzi (brak deadline) / Zakonczone (deadline < dzis)
- **Program**: lista chmurkami, agregowana z tagow naborow (FENG, KPO, FE Pomorze, ...)

## SEO i wydajnosc

- Widget renderuje sie po stronie klienta (CSR). Google rok temu obsluguje JS rendering, ale crawlowanie jest wolniejsze.
- **Jesli SEO bedzie priorytetem** (chcemy, zeby Google indeksowal poszczegolne nabory):
  - Wariant 1 (latwy): Netlify build hook + skrypt build-time, ktory pobiera nabory i generuje statyczne `nabory.json` -> JS pobiera lokalnie zamiast z Supabase. Strona renderuje sie szybciej, ale lista jest "swiezosci buildu".
  - Wariant 2 (lepsze SEO): Netlify Edge Function + per-call URLs (`/nabory/<slug>`) -> kazdy nabor ma wlasna podstrone z metadanymi.
  - To projekt na Etap 4.5 - po obserwacji jak strona radzi sobie SEO-wo z aktualnym widgetem.

## Bezpieczenstwo

- **Anon key + RLS**: anon role widzi TYLKO `calls` ze statusem `published`. RLS jest wlaczony w migracji.
- **CORS** (jesli przelaczysz na Edge Function): zezwalamy tylko na origin `inwestycjepomorze.pl` + localhost dla dev.
- **Rate limit**: Supabase free tier ma limity, ale dla 1000 odwiedzin/mies sa nieosiagalne.

## Rollback

Aby zdjac widget bez wpadu na users:

1. Usun `<script src="/js/nabory-widget.js">` z HTML.
2. Sekcja `#fundusze` pokaze sie pusta lub z fallbackiem (zaleznie od tego, czy uzylismy snippetu).

## Dalsze ulepszenia (nie blokujace)

- **Search box** w sekcji `#fundusze` - prostym filtrem JS po `title`+`summary`.
- **Single-call view** (`/nabory?id=...`) - dedykowana strona z pelnymi szczegolami i przyciskiem "Zglos sie do nas".
- **Sticky CTA**: po wejsciu na nabor -> "Pomozemy Ci aplikowac - umow darmowa konsultacje" -> formularz kontaktowy.
- **Badge "NOWE"** dla naborow opublikowanych w ostatnich 3 dniach.
