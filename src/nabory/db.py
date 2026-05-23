"""Klient Supabase - zapis sources, calls, tagow, audit_log, run_log."""

from __future__ import annotations

import logging
from typing import Any

from supabase import Client, create_client

from .config import Settings, SourceConfig
from .models import CallRecord, RunSummary

logger = logging.getLogger(__name__)


class Database:
    """Cienki wrapper na klient Supabase z metodami uzywanymi przez agenta."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client: Client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        self._tag_cache: dict[str, str] = {}

    # ------------------------------------------------------------------ tags

    def load_tag_cache(self) -> None:
        """Zaladuj tagi z bazy do cache (slug -> id)."""
        try:
            res = self.client.table("tags").select("id,slug").execute()
            self._tag_cache = {row["slug"]: row["id"] for row in (res.data or [])}
            logger.info("Zaladowano %d tagow do cache", len(self._tag_cache))
        except Exception:
            logger.exception("Nie udalo sie zaladowac tagow")
            self._tag_cache = {}

    def ensure_tag(self, slug: str, label: str | None = None) -> str | None:
        """Upewnij sie, ze tag istnieje. Zwroc id."""
        slug = slug.strip().lower()
        if not slug:
            return None
        if slug in self._tag_cache:
            return self._tag_cache[slug]
        try:
            res = (
                self.client.table("tags")
                .upsert({"slug": slug, "label": label or slug.replace("-", " ").title()},
                        on_conflict="slug")
                .execute()
            )
            if res.data:
                tag_id = res.data[0]["id"]
                self._tag_cache[slug] = tag_id
                return tag_id
        except Exception:
            logger.exception("Blad upsert tagu %s", slug)
        return None

    # --------------------------------------------------------------- sources

    def sync_sources(self, sources: list[SourceConfig]) -> dict[str, str]:
        """Synchronizuj sources.yaml -> tabela `sources`. Zwroc mape name -> id."""
        name_to_id: dict[str, str] = {}
        for s in sources:
            payload: dict[str, Any] = {
                "name": s.name,
                "url": s.url,
                "fetcher": s.fetcher,
                "extractor": s.extractor,
                "active": s.active,
                "notes": s.notes,
                "config": {
                    "list_selector": s.list_selector,
                    "wait_for_selector": s.wait_for_selector,
                    "fields": s.fields,
                    **s.extra,
                },
            }
            try:
                res = (
                    self.client.table("sources")
                    .upsert(payload, on_conflict="name")
                    .execute()
                )
                if res.data:
                    name_to_id[s.name] = res.data[0]["id"]
            except Exception:
                logger.exception("Blad upsert zrodla %s", s.name)
        logger.info("Zsynchronizowano %d zrodel z baza", len(name_to_id))
        return name_to_id

    def update_source_status(
        self,
        source_id: str,
        status: str,
        error: str | None = None,
    ) -> None:
        try:
            self.client.table("sources").update({
                "last_run_at": "now()",
                "last_status": status,
                "last_error": error,
            }).eq("id", source_id).execute()
        except Exception:
            logger.exception("Blad update_source_status")

    # ----------------------------------------------------------------- calls

    def existing_hashes(self, hashes: list[str]) -> set[str]:
        """Zwroc te z `hashes`, ktore juz sa w bazie - do deduplikacji."""
        if not hashes:
            return set()
        try:
            existing: set[str] = set()
            for chunk in _chunks(hashes, 200):
                res = (
                    self.client.table("calls")
                    .select("external_id_hash")
                    .in_("external_id_hash", chunk)
                    .execute()
                )
                existing.update(row["external_id_hash"] for row in (res.data or []))
            return existing
        except Exception:
            logger.exception("Blad existing_hashes")
            return set()

    def insert_call(self, call: CallRecord) -> str | None:
        """Wstaw nowy nabor (status=draft). Zwroc ID lub None."""
        payload: dict[str, Any] = {
            "source_id": call.source_id,
            "external_id_hash": call.external_id_hash,
            "title": call.title,
            "url": call.url,
            "deadline": call.deadline.isoformat() if call.deadline else None,
            "deadline_text": call.deadline_text,
            "region": call.region,
            "beneficiary": call.beneficiary,
            "program": call.program,
            "amount_min": call.amount_min,
            "amount_max": call.amount_max,
            "amount_currency": call.amount_currency,
            "summary": call.summary,
            "raw_text": call.raw_text,
            "profile_match_score": call.profile_match_score,
            "profile_match_reason": call.profile_match_reason,
            "status": call.status,
        }
        try:
            res = self.client.table("calls").insert(payload).execute()
            if res.data:
                call_id = res.data[0]["id"]
                self._attach_tags(call_id, call.tags)
                return call_id
        except Exception:
            logger.exception("Blad insert_call (%s)", call.title[:60])
        return None

    def _attach_tags(self, call_id: str, tag_slugs: list[str]) -> None:
        if not tag_slugs:
            return
        rows = []
        for slug in tag_slugs:
            tag_id = self.ensure_tag(slug)
            if tag_id:
                rows.append({"call_id": call_id, "tag_id": tag_id})
        if not rows:
            return
        try:
            self.client.table("call_tags").upsert(rows).execute()
        except Exception:
            logger.exception("Blad attach_tags")

    def fetch_drafts_for_panel(self) -> list[dict]:
        """Wczytaj wszystkie 'draft' calls do panelu Sheets."""
        try:
            res = (
                self.client.table("calls")
                .select("*")
                .eq("status", "draft")
                .order("profile_match_score", desc=True)
                .order("created_at", desc=True)
                .limit(500)
                .execute()
            )
            return res.data or []
        except Exception:
            logger.exception("Blad fetch_drafts_for_panel")
            return []

    def update_call_status(
        self,
        call_id: str,
        status: str,
        actor: str = "panel:sheets",
    ) -> bool:
        try:
            self.client.table("calls").update({"status": status}).eq("id", call_id).execute()
            self.client.table("audit_log").insert({
                "actor": actor,
                "action": f"set_status:{status}",
                "entity": "calls",
                "entity_id": call_id,
            }).execute()
            return True
        except Exception:
            logger.exception("Blad update_call_status")
            return False

    # --------------------------------------------------------------- run_log

    def insert_run_log(self, summary: RunSummary) -> None:
        try:
            self.client.table("run_log").insert({
                "started_at": summary.started_at.isoformat(),
                "finished_at": summary.finished_at.isoformat() if summary.finished_at else None,
                "sources_total": summary.sources_total,
                "sources_ok": summary.sources_ok,
                "sources_failed": summary.sources_failed,
                "new_calls": summary.new_calls,
                "enriched_calls": summary.enriched_calls,
                "mail_sent": summary.mail_sent,
                "error": summary.error,
                "summary": {
                    "failed_sources": summary.failed_sources,
                },
            }).execute()
        except Exception:
            logger.exception("Blad insert_run_log")


def _chunks(items: list, size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]
