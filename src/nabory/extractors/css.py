"""Ekstrakcja przez selektory CSS - selectolax."""

from __future__ import annotations

import logging
from urllib.parse import urljoin

from selectolax.parser import HTMLParser

from ..config import SourceConfig
from ..fetchers.base import FetchedPage
from ..models import CallStub

logger = logging.getLogger(__name__)


class CssExtractor:
    def extract(self, page: FetchedPage, source: SourceConfig) -> list[CallStub]:
        if not page.html:
            return []
        if not source.list_selector:
            logger.warning("Zrodlo %s ma extractor=css ale brak list_selector", source.name)
            return []

        tree = HTMLParser(page.html)
        items: list[CallStub] = []
        seen_urls: set[str] = set()

        list_selectors = [s.strip() for s in source.list_selector.split(",") if s.strip()]
        nodes = []
        for sel in list_selectors:
            nodes = tree.css(sel)
            if nodes:
                break

        if not nodes:
            logger.warning("Zrodlo %s: list_selector zwrocil 0 elementow", source.name)
            return []

        base_url = page.final_url or page.url

        for node in nodes:
            data = {}
            for field_name, selector in (source.fields or {}).items():
                data[field_name] = _extract_field(node, selector, base_url=base_url)

            title = (data.get("title") or "").strip()
            link = (data.get("link") or "").strip()

            if not title or not link:
                continue

            if link in seen_urls:
                continue
            seen_urls.add(link)

            items.append(CallStub(
                title=title,
                url=link,
                deadline_text=_clean(data.get("deadline")),
                program_text=_clean(data.get("program")),
                raw_snippet=node.text(separator=" ", strip=True)[:1500],
                source_name=source.name,
            ))

        logger.info("CSS extractor: %s -> %d ogloszen", source.name, len(items))
        return items


def _extract_field(node, selector: str, base_url: str) -> str | None:
    """Selektor moze byc 'div.title' albo 'a@href' (atrybut)."""
    if "@" in selector:
        css_part, attr = selector.rsplit("@", 1)
        target = node.css_first(css_part) if css_part else node
        if target is None:
            return None
        value = target.attributes.get(attr) or ""
        if attr == "href" and value:
            value = urljoin(base_url, value)
        return value.strip()
    target = node.css_first(selector)
    if target is None:
        return None
    return target.text(separator=" ", strip=True)


def _clean(s: str | None) -> str | None:
    if not s:
        return None
    s = " ".join(s.split())
    return s or None
