"""Konfiguracja logowania - kolorowe logi dla GitHub Actions i terminala."""

from __future__ import annotations

import logging
import os
import sys

from rich.console import Console
from rich.logging import RichHandler

_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def setup_logging(level: str | None = None) -> logging.Logger:
    """Ustaw root logger z RichHandler. Idempotentne."""
    level_name = (level or os.environ.get("LOG_LEVEL", "INFO")).upper()
    level_value = _LEVELS.get(level_name, logging.INFO)

    is_actions = bool(os.environ.get("GITHUB_ACTIONS"))
    console = Console(force_terminal=True, file=sys.stderr, soft_wrap=True)

    root = logging.getLogger()
    if getattr(root, "_nabory_configured", False):
        root.setLevel(level_value)
        return logging.getLogger("nabory")

    for h in list(root.handlers):
        root.removeHandler(h)

    handler = RichHandler(
        console=console,
        show_time=True,
        show_path=False,
        markup=False,
        rich_tracebacks=True,
        log_time_format="%H:%M:%S",
        omit_repeated_times=False,
    )
    handler.setLevel(level_value)

    fmt = logging.Formatter("%(message)s")
    handler.setFormatter(fmt)

    root.addHandler(handler)
    root.setLevel(level_value)
    root._nabory_configured = True  # type: ignore[attr-defined]

    if is_actions:
        for noisy in ("httpx", "httpcore", "urllib3", "openai._base_client"):
            logging.getLogger(noisy).setLevel(logging.WARNING)

    return logging.getLogger("nabory")
