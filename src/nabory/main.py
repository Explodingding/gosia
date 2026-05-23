"""Orkiestrator agenta - codzienny run.

Sekwencja:
1. Wczytaj sources.yaml + profile.md, zsynchronizuj `sources` z Supabase.
2. Dla kazdego aktywnego zrodla: fetch -> extract (CSS lub LLM, z fallbackiem).
3. Dedup wzgledem Supabase, enrichment LLM dla nowych.
4. Zapis do Supabase (status=draft).
5. Push do Google Sheets (panel akceptacji).
6. Mail do Malgorzaty z top 5 + linkiem do panelu.
7. run_log.
"""

from __future__ import annotations

import logging
import time
from datetime import datetime

from .config import Settings, ensure_dirs, load_profile, load_sources, SourceConfig
from .db import Database
from .enrich import Enricher
from .extractors.css import CssExtractor
from .extractors.llm_extract import LlmExtractor
from .extractors.rss import RssExtractor
from .fetchers.base import FetchedPage
from .fetchers.browser import BrowserFetcher
from .fetchers.http import HttpFetcher
from .fetchers.pdf import PdfFetcher
from .fetchers.rss import RssFetcher
from .logging_setup import setup_logging
from .models import CallRecord, CallStub, RunSummary
from .sinks.mail import send_summary_mail
from .sinks.sheets import push_drafts

logger = logging.getLogger(__name__)


def main() -> int:
    started = datetime.now()
    log = setup_logging()
    log.info("=== Agent naborow start (%s) ===", started.isoformat(timespec="seconds"))
    ensure_dirs()

    try:
        settings = Settings.from_env()
    except SystemExit as e:
        logger.error(str(e))
        return 1

    if settings.dry_run:
        log.warning("DRY_RUN=yes - nie zapiszemy do bazy ani nie wyslemy maila")

    sources = load_sources()
    active_sources = [s for s in sources if s.active]
    profile = load_profile()

    db = Database(settings)
    db.load_tag_cache()
    name_to_id = db.sync_sources(sources)

    summary = RunSummary(started_at=started, sources_total=len(active_sources))

    http_fetcher = HttpFetcher()
    rss_fetcher = RssFetcher()
    pdf_fetcher = PdfFetcher()
    css_extractor = CssExtractor()
    rss_extractor = RssExtractor()

    new_calls: list[CallRecord] = []

    with BrowserFetcher() as browser:
        llm_extractor = LlmExtractor(settings)
        enricher = Enricher(settings, profile, browser=browser)

        all_stubs: list[tuple[SourceConfig, CallStub]] = []

        for source in active_sources:
            t0 = time.monotonic()
            source_id = name_to_id.get(source.name)
            try:
                page = _fetch_source(source, http_fetcher, browser, rss_fetcher, pdf_fetcher)
                stubs = _extract_with_fallback(
                    source, page, css_extractor, rss_extractor, llm_extractor
                )
                if not stubs:
                    raise RuntimeError("Ekstrakcja zwrocila 0 ogloszen (CSS i LLM zawiodly)")
                summary.sources_ok += 1
                if source_id:
                    db.update_source_status(source_id, "ok")
                for s in stubs:
                    all_stubs.append((source, s))
                log.info("Zrodlo %s OK (%d ogloszen, %.1fs)",
                         source.name, len(stubs), time.monotonic() - t0)
            except Exception as e:
                log.warning("Zrodlo %s NOK: %s", source.name, e)
                summary.sources_failed += 1
                summary.failed_sources.append({
                    "source_name": source.name,
                    "url": source.url,
                    "error": str(e)[:300],
                })
                if source_id:
                    db.update_source_status(source_id, "error", error=str(e)[:1000])

        # Dedup wzgledem bazy
        all_hashes = [stub.external_id_hash() for _, stub in all_stubs]
        existing = db.existing_hashes(all_hashes) if not settings.dry_run else set()
        log.info("Wszystkich ogloszen z fetchu: %d, juz w bazie: %d, nowych do enrichmentu: %d",
                 len(all_stubs), len(existing), len(all_stubs) - len(existing))

        enriched_count = 0
        per_run_cap = settings.max_enrich_per_run

        for source, stub in all_stubs:
            h = stub.external_id_hash()
            if h in existing:
                continue
            if enriched_count >= per_run_cap:
                log.warning("Osiagnieto MAX_ENRICH_PER_RUN=%d - reszta poczeka do nastepnego runu", per_run_cap)
                break

            log.info("Enrichment [%d/%d cap]: %s",
                     enriched_count + 1, per_run_cap, stub.title[:80])
            enrichment = enricher.enrich(stub)
            enriched_count += 1

            call = _build_call_record(
                stub=stub,
                enrichment=enrichment,
                source_id=name_to_id.get(source.name),
            )

            if not settings.dry_run:
                inserted_id = db.insert_call(call)
                if inserted_id:
                    new_calls.append(call)
            else:
                new_calls.append(call)

        summary.enriched_calls = enriched_count

    summary.new_calls = len(new_calls)
    summary.all_new_calls = new_calls
    summary.top_calls = sorted(
        new_calls,
        key=lambda c: (c.profile_match_score or 0),
        reverse=True,
    )[:5]

    sheet_url: str | None = None
    if not settings.dry_run and settings.has_sheets:
        try:
            sheet_url = push_drafts(settings, db)
        except Exception:
            log.exception("Push do Sheets nie udal sie")

    summary.mail_sent = send_summary_mail(
        settings,
        summary,
        sheet_url=sheet_url,
        repo_url=_repo_url(),
    )

    summary.finished_at = datetime.now()
    if not settings.dry_run:
        db.insert_run_log(summary)

    duration = (summary.finished_at - summary.started_at).total_seconds()
    log.info(
        "=== Koniec runu: zrodla %d/%d OK, %d nowych naborow, mail=%s, czas=%.1fs ===",
        summary.sources_ok, summary.sources_total,
        summary.new_calls, summary.mail_sent, duration,
    )
    return 0


# ---------------------------------------------------------------------------

def _fetch_source(
    source: SourceConfig,
    http: HttpFetcher,
    browser: BrowserFetcher,
    rss: RssFetcher,
    pdf: PdfFetcher,
) -> FetchedPage:
    fetcher_type = source.fetcher.lower()
    if fetcher_type == "http":
        return http.fetch(source.url)
    if fetcher_type == "playwright":
        return browser.fetch(
            source.url,
            wait_for_selector=source.wait_for_selector,
            source_name=source.name,
        )
    if fetcher_type == "rss":
        return rss.fetch(source.url)
    if fetcher_type == "pdf":
        return pdf.fetch(source.url)
    raise ValueError(f"Nieznany fetcher: {source.fetcher}")


def _extract_with_fallback(
    source: SourceConfig,
    page: FetchedPage,
    css_extractor: CssExtractor,
    rss_extractor: RssExtractor,
    llm_extractor: LlmExtractor,
) -> list[CallStub]:
    """3-poziomowa strategia: dedykowany ekstraktor -> CSS -> LLM."""
    if source.fetcher == "rss":
        return rss_extractor.extract(page, source)

    extractor_pref = source.extractor.lower()

    if extractor_pref == "css":
        stubs = css_extractor.extract(page, source)
        if stubs:
            return stubs
        logger.info("Fallback CSS->LLM dla %s (CSS zwrocil 0)", source.name)
        return llm_extractor.extract(page, source)

    if extractor_pref == "llm":
        stubs = llm_extractor.extract(page, source)
        if stubs:
            return stubs
        if source.list_selector:
            logger.info("Fallback LLM->CSS dla %s (LLM zwrocil 0)", source.name)
            return css_extractor.extract(page, source)
        return []

    return llm_extractor.extract(page, source)


def _build_call_record(
    stub: CallStub,
    enrichment,
    source_id: str | None,
) -> CallRecord:
    if enrichment is None:
        return CallRecord(
            source_id=source_id,
            source_name=stub.source_name,
            external_id_hash=stub.external_id_hash(),
            title=stub.title,
            url=stub.url,
            deadline_text=stub.deadline_text,
            program=stub.program_text,
            raw_text=stub.raw_snippet,
            summary=None,
            profile_match_score=None,
            profile_match_reason="(enrichment LLM nie powiodl sie)",
            tags=[],
        )
    return CallRecord(
        source_id=source_id,
        source_name=stub.source_name,
        external_id_hash=stub.external_id_hash(),
        title=stub.title,
        url=stub.url,
        deadline=enrichment.deadline,
        deadline_text=stub.deadline_text,
        region=enrichment.region,
        beneficiary=enrichment.beneficiary,
        program=enrichment.program or stub.program_text,
        amount_min=enrichment.amount_min,
        amount_max=enrichment.amount_max,
        summary=enrichment.summary,
        raw_text=stub.raw_snippet,
        profile_match_score=enrichment.profile_match_score,
        profile_match_reason=enrichment.profile_match_reason,
        tags=enrichment.tags,
    )


def _repo_url() -> str:
    import os
    repo = os.environ.get("GITHUB_REPOSITORY")
    if repo:
        return f"https://github.com/{repo}"
    return "https://github.com/"


if __name__ == "__main__":
    raise SystemExit(main())
