"""Ekstrakcja z fetchowanego RSS - prosta i bezstratna."""

from __future__ import annotations

import logging

from ..config import SourceConfig
from ..fetchers.base import FetchedPage
from ..models import CallStub

logger = logging.getLogger(__name__)


class RssExtractor:
    def extract(self, page: FetchedPage, source: SourceConfig) -> list[CallStub]:
        items: list[CallStub] = []
        for entry in page.rss_entries:
            title = (entry.get("title") or "").strip()
            link = (entry.get("link") or "").strip()
            if not title or not link:
                continue
            items.append(CallStub(
                title=title,
                url=link,
                deadline_text=None,
                raw_snippet=(entry.get("summary") or "")[:1500] or None,
                source_name=source.name,
            ))
        logger.info("RSS extractor: %s -> %d wpisow", source.name, len(items))
        return items
