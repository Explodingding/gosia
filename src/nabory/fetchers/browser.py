"""Fetcher Playwright - dla SPA i stron z anty-bot ochrona (np. funduszeunijne.gov.pl)."""

from __future__ import annotations

import logging
import re
from datetime import datetime
from pathlib import Path

from playwright.sync_api import (
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    sync_playwright,
)
from tenacity import retry, stop_after_attempt, wait_exponential

from ..config import SCREENSHOTS_DIR
from .base import FetchedPage

logger = logging.getLogger(__name__)

REAL_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)


class BrowserFetcher:
    """Renderowanie stron w Chromium (headless). Wspoldzieli jeden browser na wiele zrodel."""

    def __init__(
        self,
        timeout_ms: int = 30000,
        headless: bool = True,
        save_screenshot_on_error: bool = True,
    ) -> None:
        self.timeout_ms = timeout_ms
        self.headless = headless
        self.save_screenshot_on_error = save_screenshot_on_error
        self._pw: Playwright | None = None
        self._browser = None
        self._context = None

    def __enter__(self) -> BrowserFetcher:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(
            headless=self.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        self._context = self._browser.new_context(
            user_agent=REAL_UA,
            locale="pl-PL",
            timezone_id="Europe/Warsaw",
            viewport={"width": 1366, "height": 900},
            extra_http_headers={
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            },
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._context:
                self._context.close()
            if self._browser:
                self._browser.close()
            if self._pw:
                self._pw.stop()
        except Exception:
            logger.exception("Blad przy zamykaniu browsera")

    @retry(stop=stop_after_attempt(2), wait=wait_exponential(multiplier=1, min=2, max=8), reraise=True)
    def fetch(
        self,
        url: str,
        wait_for_selector: str | None = None,
        wait_until: str = "networkidle",
        extra_wait_ms: int = 1500,
        source_name: str = "source",
    ) -> FetchedPage:
        if self._context is None:
            raise RuntimeError("BrowserFetcher trzeba uzyc jako context manager (with ...)")
        page: Page = self._context.new_page()
        screenshot_path: str | None = None
        try:
            logger.debug("Playwright goto %s", url)
            page.set_default_timeout(self.timeout_ms)
            page.goto(url, wait_until=wait_until)
            if wait_for_selector:
                # Selektory z sources.yaml moga byc lista z przecinkami - probujemy kazdy.
                selectors = [s.strip() for s in wait_for_selector.split(",") if s.strip()]
                matched = False
                for sel in selectors:
                    try:
                        page.wait_for_selector(sel, timeout=self.timeout_ms // max(len(selectors), 1))
                        matched = True
                        break
                    except PlaywrightTimeoutError:
                        continue
                if not matched:
                    logger.warning("Zaden z wait_for_selector nie zmatchowal sie na %s", url)
            page.wait_for_timeout(extra_wait_ms)
            html = page.content()
            final_url = page.url
            return FetchedPage(url=url, html=html, final_url=final_url)
        except Exception as e:
            if self.save_screenshot_on_error:
                screenshot_path = _save_error_screenshot(page, source_name)
            logger.warning("Playwright error na %s: %s (screenshot: %s)", url, e, screenshot_path)
            raise
        finally:
            try:
                page.close()
            except Exception:
                pass


def _save_error_screenshot(page: Page, source_name: str) -> str | None:
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r"[^a-z0-9]+", "-", source_name.lower()).strip("-")
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = Path(SCREENSHOTS_DIR) / f"{slug}-{ts}.png"
        page.screenshot(path=str(path), full_page=True)
        return str(path)
    except Exception:
        logger.exception("Nie udalo sie zapisac screenshotu")
        return None
