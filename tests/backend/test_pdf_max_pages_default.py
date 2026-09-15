"""Regression: PDF page-count is bounded by default (resource-exhaustion guard).

Before this fix, an unset PDF_MAX_PAGES defaulted to 0, which every call
site treats as "no limit" — a single upload could force OCR across an
attacker-chosen number of pages. An operator can still opt back into
unlimited by setting PDF_MAX_PAGES=0 explicitly.
"""
from __future__ import annotations

import importlib


def test_pdf_max_pages_defaults_to_a_bounded_value(monkeypatch):
    monkeypatch.delenv('PDF_MAX_PAGES', raising=False)
    from app.ai.parser import text_extraction

    reloaded = importlib.reload(text_extraction)
    try:
        assert reloaded.PDF_MAX_PAGES > 0
    finally:
        importlib.reload(text_extraction)


def test_pdf_max_pages_explicit_zero_still_means_unlimited(monkeypatch):
    monkeypatch.setenv('PDF_MAX_PAGES', '0')
    from app.ai.parser import text_extraction

    reloaded = importlib.reload(text_extraction)
    try:
        assert reloaded.PDF_MAX_PAGES == 0
    finally:
        monkeypatch.delenv('PDF_MAX_PAGES', raising=False)
        importlib.reload(text_extraction)
