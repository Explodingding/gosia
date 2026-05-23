"""Fetcher PDF - pobranie i ekstrakcja tekstu."""

from __future__ import annotations

import io
import logging

import httpx
import pdfplumber

from .base import FetchedPage
from .http import DEFAULT_HEADERS

logger = logging.getLogger(__name__)


class PdfFetcher:
    def __init__(self, timeout: float = 30.0) -> None:
        self.timeout = timeout

    def fetch(self, url: str) -> FetchedPage:
        logger.debug("PDF GET %s", url)
        with httpx.Client(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as c:
            r = c.get(url)
            r.raise_for_status()
            buf = io.BytesIO(r.content)
        text_parts: list[str] = []
        with pdfplumber.open(buf) as pdf:
            for page in pdf.pages:
                t = page.extract_text() or ""
                if t:
                    text_parts.append(t)
        text = "\n\n".join(text_parts)
        return FetchedPage(url=url, text=text, final_url=url)
