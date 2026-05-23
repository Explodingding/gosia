"""Modele danych Pydantic - structured output dla LLM i kontrakty wewnetrzne."""

from __future__ import annotations

import hashlib
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

BeneficiaryType = Literal[
    "msp", "ngo", "samorzad", "startup", "duza_firma",
    "rolnictwo", "osoba_fizyczna", "inne"
]


class CallStub(BaseModel):
    """Surowy wpis listy naborow zwrocony przez fetcher/extractor.
    Minimum: tytul + URL. Reszta pol opcjonalna."""

    title: str
    url: str
    deadline_text: str | None = None
    program_text: str | None = None
    raw_snippet: str | None = None
    source_name: str

    model_config = ConfigDict(extra="ignore")

    @field_validator("title", "url")
    @classmethod
    def _strip(cls, v: str) -> str:
        return (v or "").strip()

    def external_id_hash(self) -> str:
        """Stabilne ID do deduplikacji - URL ma najwyzszy priorytet."""
        key = f"{self.url.strip().lower()}|{self.title.strip().lower()}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()


class CallEnrichment(BaseModel):
    """Wynik enrichmentu LLM - structured output."""

    summary: str = Field(
        ...,
        description="Streszczenie naboru w 2-3 zdaniach po polsku, konkretnie i bez lania wody."
    )
    region: str | None = Field(
        None,
        description="Region/wojewodztwo (np. 'Pomorskie', 'Cala Polska'). Null jesli nieznany."
    )
    beneficiary: BeneficiaryType | None = Field(
        None,
        description="Glowny typ beneficjenta. Wybierz najbardziej trafny z dostepnych wartosci."
    )
    program: str | None = Field(
        None,
        description="Nazwa programu (FENG, FE Pomorze, KPO, RPO, PARP, NCBR, BUR...). Null jesli nieznana."
    )
    amount_min: float | None = Field(
        None,
        description="Minimalna kwota dofinansowania w PLN (jesli podana)."
    )
    amount_max: float | None = Field(
        None,
        description="Maksymalna kwota dofinansowania w PLN (jesli podana)."
    )
    deadline: date | None = Field(
        None,
        description="Termin skladania wnioskow (ISO 8601 YYYY-MM-DD). Null jesli nieznany lub niepewny."
    )
    profile_match_score: int = Field(
        ...,
        ge=0, le=100,
        description="Dopasowanie do profilu InwestycjePomorze.pl (0-100). Patrz profil w prompcie."
    )
    profile_match_reason: str = Field(
        ...,
        description="1-2 zdania PO POLSKU - co konkretnie sprawia, ze score jest taki, jaki jest."
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Slugi tagow z listy: feng, fe-pomorze, kpo, kpo-cyfryzacja, kpo-zielona, "
                    "kpo-innowacje, parp, ncbr, rpo, bur, msp, ngo, samorzad, startup, oze, "
                    "br, cyfryzacja, produkcja, turystyka, logistyka, medtech, industry-4-0, "
                    "efektywnosc-energ, goz, eksport, szkolenia, woj-pomorskie, caly-kraj. "
                    "Wybierz tylko te, ktore faktycznie pasuja."
    )

    model_config = ConfigDict(extra="ignore")


class CallRecord(BaseModel):
    """Pelny rekord naboru gotowy do zapisu w bazie."""

    source_id: str | None = None
    source_name: str
    external_id_hash: str
    title: str
    url: str
    deadline: date | None = None
    deadline_text: str | None = None
    region: str | None = None
    beneficiary: BeneficiaryType | None = None
    program: str | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    amount_currency: str = "PLN"
    summary: str | None = None
    raw_text: str | None = None
    profile_match_score: int | None = None
    profile_match_reason: str | None = None
    tags: list[str] = Field(default_factory=list)
    status: Literal["draft", "published", "rejected"] = "draft"
    created_at: datetime | None = None

    model_config = ConfigDict(extra="ignore")


class FetchResult(BaseModel):
    """Wynik fetchu pojedynczego zrodla."""

    source_name: str
    success: bool
    items: list[CallStub] = Field(default_factory=list)
    error: str | None = None
    extractor_used: str | None = None
    duration_seconds: float | None = None
    raw_html: str | None = None
    screenshot_path: str | None = None


class RunSummary(BaseModel):
    """Podsumowanie calego runu - do mailu i logu."""

    started_at: datetime
    finished_at: datetime | None = None
    sources_total: int = 0
    sources_ok: int = 0
    sources_failed: int = 0
    new_calls: int = 0
    enriched_calls: int = 0
    failed_sources: list[dict] = Field(default_factory=list)
    top_calls: list[CallRecord] = Field(default_factory=list)
    all_new_calls: list[CallRecord] = Field(default_factory=list)
    mail_sent: bool = False
    error: str | None = None
