"""Konfiguracja: ladowanie .env, sources.yaml, profile.md, walidacja sekretow."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
SOURCES_PATH = REPO_ROOT / "sources.yaml"
PROFILE_PATH = REPO_ROOT / "profile.md"
ARTIFACTS_DIR = REPO_ROOT / "artifacts"
SCREENSHOTS_DIR = REPO_ROOT / "screenshots"


@dataclass(slots=True)
class SourceConfig:
    """Pojedyncze zrodlo z sources.yaml."""

    name: str
    url: str
    fetcher: str
    extractor: str = "css"
    list_selector: str | None = None
    wait_for_selector: str | None = None
    fields: dict[str, str] = field(default_factory=dict)
    active: bool = True
    notes: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> SourceConfig:
        known = {"name", "url", "fetcher", "extractor", "list_selector",
                 "wait_for_selector", "fields", "active", "notes"}
        extra = {k: v for k, v in raw.items() if k not in known}
        return cls(
            name=raw["name"],
            url=raw["url"],
            fetcher=raw.get("fetcher", "http"),
            extractor=raw.get("extractor", "css"),
            list_selector=raw.get("list_selector"),
            wait_for_selector=raw.get("wait_for_selector"),
            fields=raw.get("fields", {}) or {},
            active=bool(raw.get("active", True)),
            notes=raw.get("notes"),
            extra=extra,
        )


@dataclass(slots=True)
class Settings:
    """Agregat wszystkich sekretow i ustawien runtime'owych."""

    supabase_url: str
    supabase_service_role_key: str
    openai_api_key: str
    openai_model: str
    resend_api_key: str
    mail_from: str
    mail_to: str
    mail_cc: str | None
    google_credentials_json: str | None
    google_sheet_id: str | None
    dry_run: bool
    mail_always: bool
    max_enrich_per_run: int
    log_level: str
    tz: str

    @classmethod
    def from_env(cls) -> Settings:
        load_dotenv(REPO_ROOT / ".env", override=False)

        def req(key: str) -> str:
            value = os.environ.get(key, "").strip()
            if not value:
                raise SystemExit(
                    f"Brak wymaganego sekretu: {key}. "
                    "Wpisz go w GitHub Actions Secrets albo w lokalnym .env (patrz SETUP.md)."
                )
            return value

        def opt(key: str, default: str = "") -> str:
            return os.environ.get(key, default).strip()

        def flag(key: str, default: bool = False) -> bool:
            raw = os.environ.get(key, "").strip().lower()
            if not raw:
                return default
            return raw in ("1", "yes", "true", "y", "tak", "on")

        return cls(
            supabase_url=req("SUPABASE_URL"),
            supabase_service_role_key=req("SUPABASE_SERVICE_ROLE_KEY"),
            openai_api_key=req("OPENAI_API_KEY"),
            openai_model=opt("OPENAI_MODEL", "gpt-4o-mini"),
            resend_api_key=req("RESEND_API_KEY"),
            mail_from=req("MAIL_FROM"),
            mail_to=req("MAIL_TO"),
            mail_cc=opt("MAIL_CC") or None,
            google_credentials_json=opt("GOOGLE_CREDENTIALS_JSON") or None,
            google_sheet_id=opt("GOOGLE_SHEET_ID") or None,
            dry_run=flag("DRY_RUN"),
            mail_always=flag("MAIL_ALWAYS"),
            max_enrich_per_run=int(opt("MAX_ENRICH_PER_RUN", "80") or "80"),
            log_level=opt("LOG_LEVEL", "INFO"),
            tz=opt("TZ", "Europe/Warsaw"),
        )

    @property
    def has_sheets(self) -> bool:
        return bool(self.google_credentials_json and self.google_sheet_id)


def load_sources() -> list[SourceConfig]:
    if not SOURCES_PATH.exists():
        raise FileNotFoundError(f"Nie znaleziono {SOURCES_PATH}")
    raw = yaml.safe_load(SOURCES_PATH.read_text(encoding="utf-8"))
    items = raw.get("sources") if isinstance(raw, dict) else raw
    if not isinstance(items, list):
        raise ValueError(f"sources.yaml: oczekiwana lista 'sources', dostalismy {type(items)}")
    sources = [SourceConfig.from_dict(s) for s in items]
    logger.info("Wczytano %d zrodel z sources.yaml (%d aktywnych)",
                len(sources), sum(1 for s in sources if s.active))
    return sources


def load_profile() -> str:
    if not PROFILE_PATH.exists():
        logger.warning("Brak profile.md - LLM bedzie pracowal bez kontekstu profilu")
        return ""
    return PROFILE_PATH.read_text(encoding="utf-8")


def ensure_dirs() -> None:
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
