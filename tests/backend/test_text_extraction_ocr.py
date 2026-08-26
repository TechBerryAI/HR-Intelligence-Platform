"""Unit tests for PDF/image text extraction and OCR fallback (mocked, no Tesseract required)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser import text_extraction as te


def test_extract_text_from_image_uses_ocr():
    with patch.object(te, "_ocr_image_bytes", return_value="A" * 40) as ocr:
        result = te.extract_text_from_image(b"fake-image-bytes", "resume.png")
    assert len(result) >= 30
    ocr.assert_called_once()


def test_extract_text_from_image_rejects_short_ocr():
    with patch.object(te, "_ocr_image_bytes", return_value="hi"):
        with pytest.raises(ValueError, match="only .* characters"):
            te.extract_text_from_image(b"x", "blank.png")


def test_ocr_image_bytes_missing_engines_message():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "get_ocr_engine_status", return_value=(False, "no engines")):
        with pytest.raises(ValueError, match="OCR engines unavailable"):
            te._ocr_image_bytes(b"x")


def test_ocr_engines_disabled_status():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "OCR_ENABLED", False):
        te.reset_ocr_engine_status_cache()
        ok, detail = te.get_ocr_engine_status()
        assert ok is False
        assert "OCR_ENABLED" in detail


def test_pdf_skips_per_page_ocr_when_engines_missing():
    """Scanned pages must not burn time rendering/OCR when no engine is installed."""
    te.reset_ocr_engine_status_cache()
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]

    doc = MagicMock()
    doc.__len__.return_value = 3
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=False), \
         patch.object(te, "ocr_unavailable_reason", return_value="no engines"), \
         patch.object(te, "_render_page_png") as render, \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        with pytest.raises(ValueError, match="Insufficient text"):
            te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    render.assert_not_called()
    ocr.assert_not_called()


def test_force_pdf_ocr_fails_fast_without_engines():
    te.reset_ocr_engine_status_cache()
    with patch.object(te, "ocr_engines_available", return_value=False), \
         patch.object(te, "ocr_unavailable_reason", return_value="no engines"):
        with pytest.raises(ValueError, match="Cannot force PDF OCR"):
            te._force_pdf_ocr(b"%PDF-fake")


def test_bulk_needs_ocr_retry_false_without_engines():
    from app.workers import bulk_parser as bp

    with patch(
        "app.ai.parser.text_extraction.ocr_engines_available",
        return_value=False,
    ):
        assert bp._bulk_needs_ocr_retry(
            "pdf", "", "OCR failed", looks_like_garbage=lambda s: True
        ) is False


def test_extract_text_routes_image_extension():
    with patch.object(te, "extract_text_from_image", return_value="X" * 40) as img:
        out = te.extract_text(b"img", "scan.JPEG")
    assert out.startswith("X")
    img.assert_called_once()


def test_extract_text_from_pdf_pymupdf_ocr_when_page_image_based():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]

    doc = MagicMock()
    doc.__len__.return_value = 1
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=b"png"), \
         patch.object(te, "_ocr_image_bytes", return_value="Scanned resume text " + ("y" * 20)), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    assert "Scanned resume" in text
    assert len(text) >= 30


def test_extract_text_docx_still_works():
    with pytest.raises(ValueError, match="Unsupported"):
        te.extract_text(b"x", "resume.txt")
