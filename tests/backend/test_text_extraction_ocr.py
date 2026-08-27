"""Unit tests for PDF/image text extraction and OCR fallback (mocked, no Tesseract required)."""

from __future__ import annotations

import io
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
         patch.object(te, "_png_has_ink", return_value=True), \
         patch.object(te, "_ocr_image_bytes", return_value="Scanned resume text " + ("y" * 20)), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    assert "Scanned resume" in text
    assert len(text) >= 30


def _white_png_bytes() -> bytes:
    from PIL import Image

    buf = io.BytesIO()
    Image.new("RGB", (120, 160), (255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _ink_png_bytes() -> bytes:
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, 180, 180), fill=(10, 10, 10))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_has_ink_detects_blank_and_content():
    assert te._png_has_ink(_white_png_bytes()) is False
    assert te._png_has_ink(_ink_png_bytes()) is True


def test_blank_pdf_page_does_not_run_ocr():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = []
    page.find_tables.side_effect = Exception("no tables")

    page2 = MagicMock()
    page2.get_text.return_value = "Digital resume body " + ("x" * 80)
    page2.get_images.return_value = []
    page2.find_tables.side_effect = Exception("no tables")

    doc = MagicMock()
    doc.__len__.return_value = 2
    doc.__getitem__.side_effect = lambda i: page if i == 0 else page2
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", return_value=_white_png_bytes()), \
         patch.object(te, "_ocr_image_bytes") as ocr, \
         patch.object(te, "OCR_ENABLED", True):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    ocr.assert_not_called()
    assert "Digital resume body" in text


def _low_contrast_ink_png_bytes() -> bytes:
    """Gray-on-gray content: old contrast<18 skip, new threshold still sees ink."""
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (200, 200), (205, 205, 205))
    draw = ImageDraw.Draw(img)
    draw.rectangle((20, 20, 180, 180), fill=(193, 193, 193))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_png_has_ink_keeps_low_contrast_content():
    assert te._png_has_ink(_low_contrast_ink_png_bytes()) is True
    assert te._png_has_ink(_white_png_bytes()) is False


def test_image_page_full_dpi_ink_recheck_runs_ocr():
    page = MagicMock()
    page.get_text.return_value = ""
    page.get_images.return_value = [("img",)]
    page.find_tables.side_effect = Exception("no tables")

    doc = MagicMock()
    doc.__len__.return_value = 1
    doc.__getitem__.return_value = page
    doc.close = MagicMock()

    fake_fitz = MagicMock()
    fake_fitz.open.return_value = doc
    fake_fitz.Matrix = MagicMock(return_value="matrix")

    renders = [_white_png_bytes(), _ink_png_bytes()]

    def fake_render(_page, dpi=0):
        return renders.pop(0) if renders else _ink_png_bytes()

    with patch.dict(sys.modules, {"fitz": fake_fitz}), \
         patch.object(te, "_render_page_png", side_effect=fake_render), \
         patch.object(te, "_ocr_image_bytes", return_value="Faint scanned resume " + ("y" * 20)) as ocr, \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "_extract_pdf_page_tables", return_value=""):
        text = te.extract_text_from_pdf_pymupdf(b"%PDF-fake")

    ocr.assert_called()
    assert "Faint scanned" in text


def test_page_needs_ocr_on_garbage_digital_with_images():
    page = MagicMock()
    page.get_images.return_value = [("img",)]
    junk = ":::: **** #### " * 16  # >=200 chars so sparse-image rule does not fire
    assert 200 <= len(junk.strip()) <= 400
    assert te.looks_like_garbage_extract(junk) is True
    assert te._page_needs_ocr(page, junk) is True


def test_should_retry_high_dpi_skips_good_text_and_already_300():
    good = "Jane Doe jane@example.com Experience Python SQL education skills " + ("x" * 20)
    assert te.should_retry_high_dpi_extract("scan.pdf", good, max_dpi_used=180) is False
    assert te.should_retry_high_dpi_extract("scan.pdf", "", extract_failed=True, max_dpi_used=180) is True
    assert te.should_retry_high_dpi_extract("scan.pdf", "", extract_failed=True, max_dpi_used=300) is False
    assert te.should_retry_high_dpi_extract("note.docx", "", extract_failed=True, max_dpi_used=180) is False


def test_ocr_dpi_fast_reads_hardware_start(monkeypatch):
    monkeypatch.delenv("OCR_DPI_FAST", raising=False)
    monkeypatch.setenv("HCIP_OCR_DPI_START", "150")
    assert te._ocr_dpi_fast() == 150
    monkeypatch.setenv("OCR_DPI_FAST", "200")
    assert te._ocr_dpi_fast() == 200


def test_ocr_layout_empty_with_ink_runs_opencv_once():
    from app.ai.parser.layout import detector as det

    ink = _ink_png_bytes()

    with patch.object(det, "preprocess_image_bytes", return_value=ink), \
         patch.object(det, "is_layout_enabled", return_value=True), \
         patch.object(det, "is_jd_layout_enabled", return_value=True), \
         patch.object(det, "_rapidocr_detections", return_value=[]), \
         patch.object(det, "_opencv_then_ocr", return_value="Recovered faint text") as opencv:
        text, source = det.ocr_image_with_layout(ink, ocr_fn=lambda _b: "should-not-run")

    opencv.assert_called_once()
    assert "Recovered" in text
    assert source == "opencv_blocks"


def test_ocr_layout_empty_does_not_call_plain_again():
    with patch.object(te, "OCR_ENABLED", True), \
         patch.object(te, "RESUME_LAYOUT_ENABLED", True), \
         patch.object(te, "ocr_engines_available", return_value=True), \
         patch(
             "app.ai.parser.layout.detector.ocr_image_with_layout",
             return_value=("", "empty"),
         ), \
         patch.object(te, "_ocr_image_bytes_plain") as plain:
        with pytest.raises(ValueError, match="empty"):
            te._ocr_image_bytes(b"png")
        plain.assert_not_called()


def test_extract_text_docx_still_works():
    with pytest.raises(ValueError, match="Unsupported"):
        te.extract_text(b"x", "resume.txt")
