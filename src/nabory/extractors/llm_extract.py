"""Awaryjna ekstrakcja LLM - dostaje czysty tekst strony, zwraca liste naborow.

Uzywana, gdy:
1. Zrodlo ma extractor=llm w sources.yaml.
2. CssExtractor zwrocil 0 elementow (auto-fallback).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urljoin

from openai import OpenAI
from pydantic import BaseModel, Field
from selectolax.parser import HTMLParser

from ..config import Settings, SourceConfig
from ..fetchers.base import FetchedPage
from ..models import CallStub

logger = logging.getLogger(__name__)

MAX_TEXT_CHARS = 25000


class _LlmStub(BaseModel):
    title: str = Field(..., description="Pelny tytul naboru/ogloszenia")
    url: str = Field(..., description="Pelny absolutny URL do szczegolow naboru")
    deadline_text: str | None = Field(None, description="Termin skladania - tekst z oryginalu")
    program_text: str | None = Field(None, description="Nazwa programu jesli widoczna")


class _LlmList(BaseModel):
    items: list[_LlmStub] = Field(default_factory=list)


_PROMPT = """Jestes systemem ekstrakcji listy naborow z polskich portali dotacyjnych.

Z ponizszego tekstu strony wyciagnij WSZYSTKIE ogloszenia o naborach/konkursach/dotacjach,
ktore widzisz na liscie. Dla kazdego zwroc tytul i pelny URL do szczegolow.

WAZNE:
- Zwracaj TYLKO realne ogloszenia o naborach. Pomijaj elementy nawigacji, stopki, banery.
- Jesli URL jest wzgledny (zaczyna sie od "/"), podaj go tak jak widzisz - ja zlacze go z domena.
- Jesli widzisz ten sam nabor wielokrotnie - zwroc go tylko raz.
- Jesli nie widzisz zadnych naborow (strona pusta, blad, captcha) - zwroc pusta liste.
- Maksymalnie 50 elementow.

Zrodlo: {source_name}
URL bazowy: {base_url}

TEKST STRONY (uciety do {max_chars} znakow):
---
{text}
---
"""


class LlmExtractor:
    """LLM-extraction listy naborow z czystego tekstu strony."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = OpenAI(api_key=settings.openai_api_key)
        self.model = settings.openai_model

    def extract(self, page: FetchedPage, source: SourceConfig) -> list[CallStub]:
        text = self._page_to_text(page)
        if not text:
            logger.warning("LLM extractor: brak tekstu dla %s", source.name)
            return []

        prompt = _PROMPT.format(
            source_name=source.name,
            base_url=page.final_url or page.url,
            max_chars=MAX_TEXT_CHARS,
            text=text[:MAX_TEXT_CHARS],
        )

        try:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "Wyciagasz strukturyzowane dane. Zwracasz wylacznie poprawny JSON pasujacy do schematu."},
                    {"role": "user", "content": prompt},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "call_list",
                        "strict": True,
                        "schema": _strict_schema(),
                    },
                },
                temperature=0.0,
                max_tokens=4000,
            )
        except Exception:
            logger.exception("LLM extractor: blad OpenAI dla %s", source.name)
            return []

        content = resp.choices[0].message.content or "{}"
        try:
            data: dict[str, Any] = json.loads(content)
            parsed = _LlmList.model_validate(data)
        except Exception:
            logger.exception("LLM extractor: nie udalo sie sparsowac wyjscia dla %s", source.name)
            return []

        base_url = page.final_url or page.url
        stubs: list[CallStub] = []
        seen_urls: set[str] = set()
        for item in parsed.items:
            title = item.title.strip()
            url = item.url.strip()
            if not title or not url:
                continue
            if not url.startswith("http"):
                url = urljoin(base_url, url)
            if url in seen_urls:
                continue
            seen_urls.add(url)
            stubs.append(CallStub(
                title=title,
                url=url,
                deadline_text=item.deadline_text,
                program_text=item.program_text,
                raw_snippet=None,
                source_name=source.name,
            ))

        logger.info("LLM extractor: %s -> %d ogloszen", source.name, len(stubs))
        return stubs

    @staticmethod
    def _page_to_text(page: FetchedPage) -> str:
        if page.text:
            return page.text
        if page.html:
            tree = HTMLParser(page.html)
            for tag in ("script", "style", "noscript", "iframe", "header", "footer", "nav"):
                for n in tree.css(tag):
                    n.decompose()
            body = tree.body or tree.root
            if body is None:
                return ""
            return body.text(separator="\n", strip=True)
        if page.rss_entries:
            return "\n".join(
                f"{e.get('title','')}\n{e.get('link','')}\n{e.get('summary','')}"
                for e in page.rss_entries
            )
        return ""


def _strict_schema() -> dict[str, Any]:
    """Strict JSON schema dla OpenAI structured outputs."""
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["items"],
        "properties": {
            "items": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["title", "url", "deadline_text", "program_text"],
                    "properties": {
                        "title": {"type": "string"},
                        "url": {"type": "string"},
                        "deadline_text": {"type": ["string", "null"]},
                        "program_text": {"type": ["string", "null"]},
                    },
                },
            },
        },
    }
