"""LLM enrichment pojedynczego naboru: streszczenie, tagi, dopasowanie do profilu."""

from __future__ import annotations

import json
import logging
from datetime import date
from typing import Any

from openai import OpenAI
from pydantic import ValidationError

from .config import Settings
from .fetchers.browser import BrowserFetcher
from .fetchers.http import HttpFetcher
from .models import CallStub, CallEnrichment

logger = logging.getLogger(__name__)

MAX_DETAIL_CHARS = 12000


_SYSTEM_PROMPT = """Jestes asystentem analityka funduszy unijnych dla firmy doradczej InwestycjePomorze.pl.
Twoja rola: dla danego naboru wygeneruj zwiezle streszczenie po polsku, wyciagnij kluczowe pola
(region, beneficjent, program, kwota, deadline) i ocen, jak bardzo nabor pasuje do profilu firmy.

Zasady:
- Streszczenie: 2-3 zdania, KONKRETNIE. Bez "ten ciekawy nabor", bez lania wody.
- Region: nazwa wojewodztwa/regionu albo "Cala Polska". Null jesli niejasne.
- Beneficjent: jedna z wartosci enum (msp/ngo/samorzad/startup/duza_firma/rolnictwo/osoba_fizyczna/inne).
- Kwoty: tylko liczby, w PLN, jesli sa jasno podane. Nie zgaduj.
- Deadline: ISO YYYY-MM-DD jesli pewny. Null jesli niepewny.
- profile_match_score: 0-100 wedlug profilu w prompcie. profile_match_reason: 1-2 zdania PL.
- Tagi: TYLKO ze zdefiniowanej listy. Wybierz te, ktore faktycznie pasuja.

Pamietaj, ze treci jakie analizujesz pochodza z surowego tekstu strony - moga byc niedokladne.
Lepiej zwrocic null niz halucynowac."""


_USER_PROMPT = """## Profil firmy InwestycjePomorze.pl

{profile}

## Nabor do analizy

Tytul: {title}
URL: {url}
Zrodlo: {source_name}
Termin (z listy): {deadline_text}
Program (z listy): {program_text}

### Tresc strony szczegolow (uciete do {max_chars} znakow):

{detail_text}

---

Wykonaj analize zgodnie z systemowym promptem i zwroc strukturyzowany JSON."""


class Enricher:
    """LLM enrichment z opcjonalnym pobraniem strony szczegolow."""

    def __init__(
        self,
        settings: Settings,
        profile: str,
        browser: BrowserFetcher | None = None,
    ) -> None:
        self.settings = settings
        self.profile = profile
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model
        self.http = HttpFetcher(timeout=15.0)
        self.browser = browser

    def enrich(self, stub: CallStub) -> CallEnrichment | None:
        detail_text = self._fetch_detail(stub.url)
        if not detail_text and stub.raw_snippet:
            detail_text = stub.raw_snippet

        prompt = _USER_PROMPT.format(
            profile=self.profile or "(brak profilu)",
            title=stub.title,
            url=stub.url,
            source_name=stub.source_name,
            deadline_text=stub.deadline_text or "(brak)",
            program_text=stub.program_text or "(brak)",
            max_chars=MAX_DETAIL_CHARS,
            detail_text=(detail_text or "(brak tresci szczegolowej)")[:MAX_DETAIL_CHARS],
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "call_enrichment",
                        "strict": True,
                        "schema": _enrichment_schema(),
                    },
                },
                temperature=0.0,
                max_tokens=1500,
            )
        except Exception:
            logger.exception("LLM enrichment: blad OpenAI dla %s", stub.title[:60])
            return None

        content = resp.choices[0].message.content or "{}"
        try:
            data: dict[str, Any] = json.loads(content)
            return _to_enrichment(data)
        except (json.JSONDecodeError, ValidationError):
            logger.exception("LLM enrichment: nieparsowalne wyjscie dla %s", stub.title[:60])
            return None

    def _fetch_detail(self, url: str) -> str | None:
        """Sciagnij strone szczegolow naboru. Najpierw HTTP, w razie 403/SPA - Playwright."""
        try:
            page = self.http.fetch(url)
            text = _html_to_text(page.html or "")
            if text and len(text) > 300:
                return text
        except Exception as e:
            logger.debug("HTTP fetch detail nie udal sie (%s): %s - probuje Playwright", url, e)
        if self.browser is not None:
            try:
                page = self.browser.fetch(url, extra_wait_ms=1500, source_name="detail")
                return _html_to_text(page.html or "")
            except Exception:
                logger.debug("Playwright fetch detail nie udal sie dla %s", url)
        return None


def _html_to_text(html: str) -> str:
    if not html:
        return ""
    try:
        from selectolax.parser import HTMLParser
        tree = HTMLParser(html)
        for tag in ("script", "style", "noscript", "iframe", "header", "footer", "nav"):
            for n in tree.css(tag):
                n.decompose()
        body = tree.body or tree.root
        return body.text(separator="\n", strip=True) if body else ""
    except Exception:
        return html


def _to_enrichment(data: dict[str, Any]) -> CallEnrichment:
    raw_deadline = data.get("deadline")
    parsed_date: date | None = None
    if isinstance(raw_deadline, str) and raw_deadline.strip():
        try:
            parsed_date = date.fromisoformat(raw_deadline.strip())
        except ValueError:
            parsed_date = None
    data["deadline"] = parsed_date

    benef = data.get("beneficiary")
    if benef in ("", "null", None):
        data["beneficiary"] = None

    tags = data.get("tags") or []
    data["tags"] = [t.strip().lower() for t in tags if isinstance(t, str) and t.strip()]

    return CallEnrichment.model_validate(data)


def _enrichment_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "summary", "region", "beneficiary", "program",
            "amount_min", "amount_max", "deadline",
            "profile_match_score", "profile_match_reason", "tags",
        ],
        "properties": {
            "summary": {"type": "string"},
            "region": {"type": ["string", "null"]},
            "beneficiary": {
                "type": ["string", "null"],
                "enum": [
                    "msp", "ngo", "samorzad", "startup",
                    "duza_firma", "rolnictwo", "osoba_fizyczna", "inne", None,
                ],
            },
            "program": {"type": ["string", "null"]},
            "amount_min": {"type": ["number", "null"]},
            "amount_max": {"type": ["number", "null"]},
            "deadline": {
                "type": ["string", "null"],
                "description": "ISO 8601 date YYYY-MM-DD lub null",
            },
            "profile_match_score": {"type": "integer", "minimum": 0, "maximum": 100},
            "profile_match_reason": {"type": "string"},
            "tags": {
                "type": "array",
                "items": {"type": "string"},
            },
        },
    }
