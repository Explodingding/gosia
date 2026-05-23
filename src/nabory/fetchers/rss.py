"""Fetcher RSS / Atom - feedparser."""

from __future__ import annotations

import logging
from typing import Any

import feedparser
import httpx

from .base import FetchedPage
from .http import DEFAULT_HEADERS

logger = logging.getLogger(__name__)


class RssFetcher:
    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> FetchedPage:
        logger.debug("RSS GET %s", url)
        with httpx.Client(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            content = r.content
        feed = feedparser.parse(content)
        if feed.bozo and not feed.entries:
            raise ValueError(f"Nie udalo sie sparsowac RSS: {feed.bozo_exception}")
        entries: list[dict[str, Any]] = []
        for e in feed.entries:
            entries.append({
                "title": (getattr(e, "title", "") or "").strip(),
                "link": (getattr(e, "link", "") or "").strip(),
                "summary": (getattr(e, "summary", "") or "").strip(),
                "published": getattr(e, "published", None),
            })
        return FetchedPage(url=url, rss_entries=entries, final_url=url)
