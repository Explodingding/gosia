"""Wysylka maila przez Resend - HTML + plain text."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

import resend
from jinja2 import Environment, select_autoescape

from ..config import Settings
from ..models import RunSummary

logger = logging.getLogger(__name__)


_HTML_TEMPLATE = """<!doctype html>
<html lang="pl">
<head>
<meta charset="utf-8">
<title>Agent naborow - {{ date_str }}</title>
</head>
<body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 720px; margin: 0 auto; padding: 24px; color: #1a1a1a; background: #fafafa;">

  <div style="background: white; border-radius: 12px; padding: 28px; box-shadow: 0 1px 3px rgba(0,0,0,0.05);">

    <h1 style="font-size: 22px; margin: 0 0 8px; color: #0a4d8c;">Agent naborow {{ date_str }}</h1>
    <p style="margin: 0 0 24px; color: #666; font-size: 14px;">
      InwestycjePomorze.pl - codzienny przeglad nowych naborow funduszowych
    </p>

    <div style="background: #eff6ff; border-left: 4px solid #0a4d8c; padding: 14px 18px; border-radius: 4px; margin-bottom: 24px;">
      <strong style="font-size: 18px; color: #0a4d8c;">{{ summary.new_calls }}</strong>
      <span>{{ 'nowy nabor' if summary.new_calls == 1 else 'nowe nabory' if summary.new_calls < 5 else 'nowych naborow' }}</span>
      &middot;
      <strong>{{ summary.sources_ok }}/{{ summary.sources_total }}</strong> zrodel ok
      {% if summary.sources_failed %}&middot; <span style="color: #b91c1c;">{{ summary.sources_failed }} z bledem</span>{% endif %}
    </div>

    {% if top_calls %}
    <h2 style="font-size: 16px; margin: 28px 0 12px; color: #0a4d8c;">Top {{ top_calls|length }} dopasowanych do profilu</h2>
    {% for call in top_calls %}
      <div style="border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin-bottom: 12px;">
        <div style="display: flex; justify-content: space-between; gap: 12px; margin-bottom: 8px;">
          <a href="{{ call.url }}" style="font-size: 15px; font-weight: 600; color: #0a4d8c; text-decoration: none;">{{ call.title }}</a>
          {% if call.profile_match_score is not none %}
          <span style="background: {{ score_color(call.profile_match_score) }}; color: white; font-size: 12px; padding: 2px 8px; border-radius: 12px; white-space: nowrap; align-self: flex-start;">{{ call.profile_match_score }}/100</span>
          {% endif %}
        </div>
        <div style="font-size: 13px; color: #555; margin-bottom: 6px;">
          {% if call.program %}<strong>{{ call.program }}</strong>{% endif %}
          {% if call.region %}&middot; {{ call.region }}{% endif %}
          {% if call.beneficiary %}&middot; {{ benef_label(call.beneficiary) }}{% endif %}
          {% if call.deadline %}&middot; termin: <strong>{{ call.deadline.isoformat() }}</strong>{% elif call.deadline_text %}&middot; termin: {{ call.deadline_text }}{% endif %}
          {% if call.amount_max %}&middot; do {{ '{:,.0f}'.format(call.amount_max).replace(',', ' ') }} PLN{% endif %}
        </div>
        {% if call.summary %}
        <div style="font-size: 14px; color: #333; line-height: 1.5; margin-bottom: 6px;">{{ call.summary }}</div>
        {% endif %}
        {% if call.profile_match_reason %}
        <div style="font-size: 12px; color: #666; font-style: italic;">Dopasowanie: {{ call.profile_match_reason }}</div>
        {% endif %}
        <div style="margin-top: 8px;">
          <a href="{{ call.url }}" style="font-size: 12px; color: #0a4d8c;">Zobacz oryginal &rarr;</a>
          <span style="font-size: 12px; color: #999;">&middot; {{ call.source_name }}</span>
        </div>
      </div>
    {% endfor %}
    {% endif %}

    {% if other_count > 0 %}
    <p style="font-size: 14px; color: #555; margin: 16px 0;">
      ...oraz <strong>{{ other_count }}</strong> innych naborow w arkuszu (sortowanie po dopasowaniu).
    </p>
    {% endif %}

    {% if sheet_url %}
    <div style="text-align: center; margin: 28px 0 8px;">
      <a href="{{ sheet_url }}" style="display: inline-block; background: #0a4d8c; color: white; padding: 12px 24px; border-radius: 6px; text-decoration: none; font-weight: 600;">Otworz panel w Google Sheets &rarr;</a>
    </div>
    <p style="text-align: center; font-size: 12px; color: #888;">W panelu: kolumna <strong>Decyzja</strong> -> <code>publikuj</code> / <code>odrzuc</code>.</p>
    {% endif %}

    {% if failed %}
    <h3 style="font-size: 14px; margin: 24px 0 8px; color: #b91c1c;">Zrodla z bledem dzis</h3>
    <ul style="font-size: 13px; color: #555; padding-left: 20px;">
    {% for f in failed %}
      <li><strong>{{ f.source_name }}</strong>: {{ f.error }}</li>
    {% endfor %}
    </ul>
    <p style="font-size: 12px; color: #888;">Szczegoly w GitHub Actions logs (artifact ze screenshotami).</p>
    {% endif %}

    <hr style="border: none; border-top: 1px solid #e5e7eb; margin: 28px 0 16px;">
    <p style="font-size: 12px; color: #999; text-align: center;">
      Agent naborow &middot; uruchomiony {{ run_time }} &middot; <a href="{{ repo_url }}" style="color: #999;">repo</a>
    </p>
  </div>
</body>
</html>
"""


_TEXT_TEMPLATE = """Agent naborow - {{ date_str }}

Nowe nabory: {{ summary.new_calls }}
Zrodla OK: {{ summary.sources_ok }}/{{ summary.sources_total }}
{% if summary.sources_failed %}Zrodla z bledem: {{ summary.sources_failed }}{% endif %}

{% for call in top_calls %}
{{ loop.index }}. [{{ call.profile_match_score|default('?', true) }}/100] {{ call.title }}
   Program: {{ call.program or '-' }} | Region: {{ call.region or '-' }} | Termin: {{ call.deadline.isoformat() if call.deadline else (call.deadline_text or '-') }}
   {{ call.summary or '' }}
   Dopasowanie: {{ call.profile_match_reason or '-' }}
   {{ call.url }}

{% endfor %}

{% if other_count > 0 %}...oraz {{ other_count }} innych w arkuszu.{% endif %}

{% if sheet_url %}Panel: {{ sheet_url }}{% endif %}

{% if failed %}Zrodla z bledem:
{% for f in failed %}- {{ f.source_name }}: {{ f.error }}
{% endfor %}{% endif %}
"""


_BENEFICIARY_LABELS = {
    "msp": "MSP",
    "ngo": "NGO",
    "samorzad": "Samorzad",
    "startup": "Start-up",
    "duza_firma": "Duza firma",
    "rolnictwo": "Rolnictwo",
    "osoba_fizyczna": "Osoba fizyczna",
    "inne": "Inne",
}


def _score_color(score: int) -> str:
    if score >= 80:
        return "#16a34a"
    if score >= 60:
        return "#0a4d8c"
    if score >= 40:
        return "#d97706"
    return "#71717a"


def _build_env() -> Environment:
    env = Environment(autoescape=select_autoescape(["html", "xml"]))
    env.globals["score_color"] = _score_color
    env.globals["benef_label"] = lambda b: _BENEFICIARY_LABELS.get(b or "", b or "")
    return env


def should_send_mail(summary: RunSummary, settings: Settings) -> bool:
    """Czy wyslac mail w tym runie?"""
    if settings.dry_run:
        return False
    if summary.new_calls > 0:
        return True
    if summary.failed_sources:
        return True
    return settings.mail_always


def send_summary_mail(
    settings: Settings,
    summary: RunSummary,
    sheet_url: str | None = None,
    repo_url: str = "https://github.com/",
) -> bool:
    """Wyslij mail podsumowujacy run. Zwroc True jesli sie udalo."""
    if not should_send_mail(summary, settings):
        if settings.dry_run:
            logger.info("DRY_RUN=yes - nie wysylam maila (bylby do %s)", settings.mail_to)
        else:
            logger.info("Pomijam mail (0 nowych + MAIL_ALWAYS=no)")
        return False

    resend.api_key = settings.resend_api_key

    env = _build_env()
    html_tpl = env.from_string(_HTML_TEMPLATE)
    text_tpl = env.from_string(_TEXT_TEMPLATE)

    top_calls = summary.top_calls
    other_count = max(0, summary.new_calls - len(top_calls))

    ctx: dict[str, Any] = {
        "summary": summary,
        "top_calls": top_calls,
        "other_count": other_count,
        "failed": summary.failed_sources,
        "sheet_url": sheet_url,
        "date_str": datetime.now().strftime("%Y-%m-%d"),
        "run_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "repo_url": repo_url,
    }

    subject = _build_subject(summary)
    html = html_tpl.render(**ctx)
    text = text_tpl.render(**ctx)

    payload: dict[str, Any] = {
        "from": settings.mail_from,
        "to": [settings.mail_to],
        "subject": subject,
        "html": html,
        "text": text,
    }
    if settings.mail_cc:
        payload["cc"] = [settings.mail_cc]

    try:
        resend.Emails.send(payload)
        logger.info("Mail wyslany do %s (subject: %s)", settings.mail_to, subject)
        return True
    except Exception:
        logger.exception("Blad wysylki maila")
        return False


def _build_subject(summary: RunSummary) -> str:
    n = summary.new_calls
    date_str = datetime.now().strftime("%d.%m")
    if n == 0:
        return f"[Nabory {date_str}] Brak nowosci"
    if n == 1:
        return f"[Nabory {date_str}] 1 nowy nabor"
    return f"[Nabory {date_str}] {n} nowych naborow"


