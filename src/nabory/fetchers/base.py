"""Wspolny kontrakt fetcherow."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class FetchedPage:
    """Wynik pobrania zrodla. Niezaleznie od tego, czy to HTML, RSS czy PDF."""

    url: str
    html: str | None = None
    text: str | None = None
    rss_entries: list[dict[str, Any]] = field(default_factory=list)
    screenshot_path: str | None = None
    final_url: str | None = None

    @property
    def has_content(self) -> bool:
        return bool(self.html or self.text or self.rss_entries)
