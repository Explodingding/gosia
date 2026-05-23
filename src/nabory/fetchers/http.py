"""Fetcher HTTP - statyczny HTML, retry, prawdziwy User-Agent."""

from __future__ import annotations

import logging

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from .base import FetchedPage

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
}


class HttpFetcher:
    """Pobieranie statycznego HTML przez httpx."""

    def __init__(self, timeout: float = 20.0) -> None:
        self.timeout = timeout

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        retry=retry_if_exception_type((httpx.HTTPError, httpx.TransportError)),
        reraise=True,
    )
    def fetch(self, url: str) -> FetchedPage:
        logger.debug("HTTP GET %s", url)
        with httpx.Client(
            headers=DEFAULT_HEADERS,
            timeout=self.timeout,
            follow_redirects=True,
            http2=False,
        ) as client:
            r = client.get(url)
            r.raise_for_status()
            return FetchedPage(
                url=url,
                html=r.text,
                final_url=str(r.url),
            )
