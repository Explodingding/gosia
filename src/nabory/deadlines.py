"""Pomocnicze funkcje do oceny terminu naboru."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any


def parse_deadline(value: Any) -> date | None:
    """Parsuj deadline z bazy (ISO date/datetime string) lub obiektu date."""
    if value is None or value == "":
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def is_expired(deadline: date | None, *, today: date | None = None) -> bool:
    """True gdy znany termin minal (wczesniejszy niz dzisiaj)."""
    if deadline is None:
        return False
    ref = today or date.today()
    return deadline < ref


def is_row_expired(row: dict[str, Any], *, today: date | None = None) -> bool:
    return is_expired(parse_deadline(row.get("deadline")), today=today)


def split_rows_by_deadline(
    rows: list[dict[str, Any]],
    *,
    today: date | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Podziel rekordy na aktywne (termin dzisiaj lub przyszlosc / brak daty) i po terminie."""
    active: list[dict[str, Any]] = []
    expired: list[dict[str, Any]] = []
    for row in rows:
        if is_row_expired(row, today=today):
            expired.append(row)
        else:
            active.append(row)
    return active, expired
