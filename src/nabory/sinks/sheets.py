"""Google Sheets - panel akceptacji dla Malgorzaty.

Dwa zadania:
1. PUSH: Supabase -> Sheet ("Nowe nieprzejrzane" + "Wszystkie opublikowane").
2. SYNC-DECISIONS: czyta kolumne `Decyzja` z arkusza, aktualizuje status w Supabase, loguje.

CLI:
    python -m nabory.sinks.sheets push
    python -m nabory.sinks.sheets sync-decisions
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime
from typing import Any

import gspread
from google.oauth2.service_account import Credentials

from ..config import Settings
from ..db import Database
from ..logging_setup import setup_logging
from ..models import CallRecord

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

SHEET_DRAFTS = "Nowe nieprzejrzane"
SHEET_PUBLISHED = "Wszystkie opublikowane"

DRAFT_HEADERS = [
    "ID", "Data dodania", "Decyzja", "Status",
    "Tytul", "Link", "Program", "Region", "Beneficjent",
    "Termin", "Kwota od", "Kwota do",
    "Match", "Streszczenie", "Powod dopasowania",
    "Zrodlo",
]

PUBLISHED_HEADERS = [
    "ID", "Data publikacji", "Tytul", "Link", "Program", "Region",
    "Beneficjent", "Termin", "Kwota od", "Kwota do",
    "Streszczenie", "Zrodlo",
]


def _open_sheet(settings: Settings):
    if not settings.has_sheets:
        raise RuntimeError("Brak GOOGLE_CREDENTIALS_JSON / GOOGLE_SHEET_ID - nie moge otworzyc arkusza")
    creds_data = json.loads(settings.google_credentials_json or "{}")
    creds = Credentials.from_service_account_info(creds_data, scopes=SCOPES)
    gc = gspread.authorize(creds)
    return gc.open_by_key(settings.google_sheet_id)


def _ensure_worksheet(sheet, title: str, headers: list[str]):
    try:
        ws = sheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=title, rows=1000, cols=max(len(headers), 16))
    if ws.row_count < 1:
        ws.resize(rows=1000, cols=max(len(headers), 16))
    existing = ws.row_values(1)
    if existing != headers:
        ws.update(values=[headers], range_name=f"A1:{_col_letter(len(headers))}1")
        ws.format(f"A1:{_col_letter(len(headers))}1", {
            "textFormat": {"bold": True},
            "backgroundColor": {"red": 0.04, "green": 0.30, "blue": 0.55},
            "horizontalAlignment": "CENTER",
        })
        ws.format(f"A1:{_col_letter(len(headers))}1", {
            "textFormat": {"foregroundColor": {"red": 1, "green": 1, "blue": 1}, "bold": True},
        })
    return ws


def _col_letter(n: int) -> str:
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


# ---------------------------------------------------------------------------
# PUSH: Supabase -> Sheet
# ---------------------------------------------------------------------------

def push_drafts(settings: Settings, db: Database, calls: list[CallRecord] | None = None) -> str | None:
    """Zapisz draft-y do arkusza. Zwroc URL arkusza jesli sukces."""
    if not settings.has_sheets:
        logger.warning("Pominieto push do Sheets - brak konfiguracji")
        return None

    if calls is None:
        rows_data = db.fetch_drafts_for_panel()
    else:
        rows_data = [_call_to_row_dict(c) for c in calls]

    sheet = _open_sheet(settings)
    ws = _ensure_worksheet(sheet, SHEET_DRAFTS, DRAFT_HEADERS)

    existing_rows = ws.get_all_values()[1:] if ws.row_count > 1 else []
    existing_by_id: dict[str, dict[str, Any]] = {
        row[0]: {"row_idx": idx + 2, "decision": row[2] if len(row) > 2 else ""}
        for idx, row in enumerate(existing_rows) if row and row[0]
    }

    new_rows: list[list[Any]] = []
    seen_ids: set[str] = set()

    for r in rows_data:
        cid = str(r.get("id") or "")
        if not cid or cid in seen_ids:
            continue
        seen_ids.add(cid)

        row = _build_draft_row(r)
        if cid in existing_by_id:
            row[2] = existing_by_id[cid]["decision"] or ""
            ws.update(
                range_name=f"A{existing_by_id[cid]['row_idx']}:{_col_letter(len(DRAFT_HEADERS))}{existing_by_id[cid]['row_idx']}",
                values=[row],
            )
        else:
            new_rows.append(row)

    if new_rows:
        ws.append_rows(new_rows, value_input_option="USER_ENTERED")

    try:
        ws.set_basic_filter(name=f"A1:{_col_letter(len(DRAFT_HEADERS))}1")
    except Exception:
        pass

    sheet_url = f"https://docs.google.com/spreadsheets/d/{settings.google_sheet_id}/edit"
    logger.info("Sheets push: dopisano %d nowych do '%s' (URL: %s)",
                len(new_rows), SHEET_DRAFTS, sheet_url)
    return sheet_url


def push_published(settings: Settings, db: Database) -> None:
    """Synchronizuj zakladke 'Wszystkie opublikowane'."""
    if not settings.has_sheets:
        return
    sheet = _open_sheet(settings)
    ws = _ensure_worksheet(sheet, SHEET_PUBLISHED, PUBLISHED_HEADERS)
    try:
        res = (
            db.client.table("calls")
            .select("*")
            .eq("status", "published")
            .order("published_at", desc=True)
            .limit(1000)
            .execute()
        )
        rows = res.data or []
    except Exception:
        logger.exception("Nie udalo sie pobrac published z Supabase")
        return

    body: list[list[Any]] = []
    for r in rows:
        body.append([
            r.get("id"),
            r.get("published_at") or "",
            r.get("title") or "",
            r.get("url") or "",
            r.get("program") or "",
            r.get("region") or "",
            r.get("beneficiary") or "",
            r.get("deadline") or "",
            r.get("amount_min") or "",
            r.get("amount_max") or "",
            r.get("summary") or "",
            "",
        ])
    if not body:
        return
    end_col = _col_letter(len(PUBLISHED_HEADERS))
    ws.update(values=body, range_name=f"A2:{end_col}{len(body) + 1}")


def _call_to_row_dict(c: CallRecord) -> dict[str, Any]:
    return {
        "id": None,
        "created_at": c.created_at.isoformat() if c.created_at else "",
        "title": c.title,
        "url": c.url,
        "program": c.program,
        "region": c.region,
        "beneficiary": c.beneficiary,
        "deadline": c.deadline.isoformat() if c.deadline else c.deadline_text,
        "amount_min": c.amount_min,
        "amount_max": c.amount_max,
        "profile_match_score": c.profile_match_score,
        "summary": c.summary,
        "profile_match_reason": c.profile_match_reason,
        "source_name": c.source_name,
        "status": c.status,
    }


def _build_draft_row(r: dict[str, Any]) -> list[Any]:
    return [
        r.get("id") or "",
        _fmt_date(r.get("created_at")),
        "",
        r.get("status") or "draft",
        r.get("title") or "",
        r.get("url") or "",
        r.get("program") or "",
        r.get("region") or "",
        r.get("beneficiary") or "",
        r.get("deadline") or "",
        r.get("amount_min") or "",
        r.get("amount_max") or "",
        r.get("profile_match_score") if r.get("profile_match_score") is not None else "",
        r.get("summary") or "",
        r.get("profile_match_reason") or "",
        r.get("source_name") or "",
    ]


def _fmt_date(value: Any) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M")
    s = str(value)
    return s[:16] if len(s) >= 16 else s


# ---------------------------------------------------------------------------
# SYNC-DECISIONS: Sheet -> Supabase
# ---------------------------------------------------------------------------

DECISION_PUBLISH = {"publikuj", "publish", "tak", "yes", "ok", "x", "v"}
DECISION_REJECT = {"odrzuc", "odrzuc'", "reject", "nie", "no", "x"}


def sync_decisions(settings: Settings, db: Database) -> dict[str, int]:
    """Czytaj kolumne `Decyzja` w arkuszu i aktualizuj statusy w Supabase."""
    if not settings.has_sheets:
        logger.warning("Pominieto sync-decisions - brak konfiguracji Sheets")
        return {"published": 0, "rejected": 0, "errors": 0}

    sheet = _open_sheet(settings)
    try:
        ws = sheet.worksheet(SHEET_DRAFTS)
    except gspread.WorksheetNotFound:
        logger.info("Brak arkusza '%s' - nic do synchronizacji", SHEET_DRAFTS)
        return {"published": 0, "rejected": 0, "errors": 0}

    rows = ws.get_all_values()
    if len(rows) < 2:
        return {"published": 0, "rejected": 0, "errors": 0}

    counters = {"published": 0, "rejected": 0, "errors": 0}

    for idx, row in enumerate(rows[1:], start=2):
        if not row or not row[0]:
            continue
        call_id = row[0]
        decision = (row[2] if len(row) > 2 else "").strip().lower()
        current_status = (row[3] if len(row) > 3 else "").strip().lower()

        new_status: str | None = None
        if decision in DECISION_PUBLISH and current_status != "published":
            new_status = "published"
        elif decision in DECISION_REJECT and current_status != "rejected":
            new_status = "rejected"

        if not new_status:
            continue

        ok = db.update_call_status(call_id, new_status, actor="panel:sheets")
        if ok:
            counters[new_status] += 1
            try:
                ws.update_cell(idx, 4, new_status)
            except Exception:
                pass
        else:
            counters["errors"] += 1

    logger.info("Sync-decisions: opublikowano=%d odrzucono=%d bledy=%d",
                counters["published"], counters["rejected"], counters["errors"])

    push_published(settings, db)
    return counters


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    setup_logging()
    settings = Settings.from_env()
    db = Database(settings)
    db.load_tag_cache()

    cmd = sys.argv[1] if len(sys.argv) > 1 else "push"
    if cmd == "push":
        push_drafts(settings, db)
    elif cmd in ("sync-decisions", "sync"):
        sync_decisions(settings, db)
    elif cmd == "push-published":
        push_published(settings, db)
    else:
        print(f"Nieznana komenda: {cmd}. Dostepne: push, sync-decisions, push-published")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def sync_cli() -> None:
    raise SystemExit(main())
