"""Fetchery - pobieraja zawartosc strony w roznej formie (HTML/SPA/RSS/PDF)."""

from .base import FetchedPage
from .browser import BrowserFetcher
from .http import HttpFetcher
from .pdf import PdfFetcher
from .rss import RssFetcher

__all__ = [
    "FetchedPage",
    "BrowserFetcher",
    "HttpFetcher",
    "PdfFetcher",
    "RssFetcher",
]
