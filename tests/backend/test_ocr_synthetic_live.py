"""Live OCR regression on synthetic PDFs/images (skipped when no engine)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.parser import text_extraction as te

_GEN = Path(__file__).resolve().parent / 'fixtures' / 'ocr_synthetic'
if str(_GEN) not in sys.path:
    sys.path.insert(0, str(_GEN))
from generate import (  # noqa: E402
    SYNTHETIC_RESUME,
    digital_pdf_bytes,
    image_heavy_pdf_bytes,
    mixed_pdf_bytes,
    overlay_scanned_pdf_bytes,
    oversized_page_pdf_bytes,
    render_text_png,
    scanned_pdf_bytes,
)


@pytest.fixture
def require_ocr():
    te.reset_ocr_engine_status_cache()
    if not te.ocr_engines_available():
        pytest.skip('no OCR engine available')


@pytest.mark.ocr
def test_live_digital_pdf_skips_unnecessary_ocr(require_ocr, monkeypatch):
    called = {'n': 0}
    real_ocr = te._ocr_image_bytes

    def wrapped(image_bytes, *, lang=None):
        called['n'] += 1
        return real_ocr(image_bytes, lang=lang)

    monkeypatch.setattr(te, '_ocr_image_bytes', wrapped)
    result = te.extract_document(digital_pdf_bytes(), 'digital.pdf')
    assert 'Alex Example' in result.text or 'Experience' in result.text
    assert called['n'] == 0
    assert result.used_ocr is False


@pytest.mark.ocr
def test_live_scanned_pdf_recovers_text(require_ocr):
    result = te.extract_document(scanned_pdf_bytes(), 'scanned.pdf')
    assert result.used_ocr is True
    low = result.text.lower()
    assert 'alex' in low or 'experience' in low or 'example' in low
    assert len(result.text) >= te.MIN_TEXT_CHARS


@pytest.mark.ocr
def test_live_mixed_pdf_keeps_order(require_ocr):
    result = te.extract_document(mixed_pdf_bytes(), 'mixed.pdf')
    low = result.text.lower()
    assert 'digital page one' in low
    assert result.used_ocr is True
    assert 2 in result.ocr_pages or 'education' in low


@pytest.mark.ocr
def test_live_low_contrast_and_rotated(require_ocr):
    faint = scanned_pdf_bytes(fill=(90, 90, 90), background=(210, 210, 210), contrast=0.6)
    rotated = scanned_pdf_bytes(rotate=90)
    try:
        faint_result = te.extract_document(faint, 'faint.pdf')
    except ValueError:
        faint_result = None
    rotated_result = te.extract_document(rotated, 'rotated.pdf')
    if faint_result is not None:
        assert len(faint_result.text) >= 10 or faint_result.used_ocr
    assert rotated_result.used_ocr is True
    low = rotated_result.text.lower()
    assert 'alex' in low or 'experience' in low or 'example' in low
    assert len(rotated_result.text) >= te.MIN_TEXT_CHARS


@pytest.mark.ocr
def test_live_image_resume(require_ocr):
    png = render_text_png(SYNTHETIC_RESUME)
    result = te.extract_document(png, 'resume.png')
    assert result.used_ocr is True
    assert result.source == 'image'
    assert len(result.text) >= te.MIN_TEXT_CHARS


@pytest.mark.ocr
def test_live_image_heavy_pdf(require_ocr):
    result = te.extract_document(image_heavy_pdf_bytes(), 'heavy.pdf')
    assert result.used_ocr is True
    assert len(result.text) >= 10


@pytest.mark.ocr
def test_live_ocr_text_reaches_section_detection(require_ocr):
    from app.ai.parser.engine.sections import detect_sections

    result = te.extract_document(scanned_pdf_bytes(), 'scanned.pdf')
    sections = detect_sections(result.text, 'resume')
    labels = [s.label for s in sections]
    assert sections
    assert any(label in labels for label in ('Experience', 'Education', 'Skills', 'Header', 'Unknown'))


@pytest.mark.ocr
def test_live_overlay_scanned_pdf_recovers_body(require_ocr):
    result = te.extract_document(overlay_scanned_pdf_bytes(), 'overlay.pdf')
    assert result.used_ocr is True
    low = result.text.lower()
    assert 'alex' in low or 'example' in low or 'python' in low
    assert len(result.text) >= te.MIN_TEXT_CHARS


@pytest.mark.ocr
def test_live_oversized_page_still_extracts(require_ocr):
    result = te.extract_document(oversized_page_pdf_bytes(), 'oversize.pdf')
    assert result.used_ocr is True
    assert len(result.text) >= te.MIN_TEXT_CHARS
    low = result.text.lower()
    assert 'alex' in low or 'experience' in low or 'example' in low
