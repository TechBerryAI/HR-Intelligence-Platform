"""PDF analysis without resume text extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from ..models import OcrSignal, PdfAnalysis

# Minimum stripped characters on a page to consider a text layer present.
TEXT_LAYER_MIN_CHARS = 10
# Fraction of image-heavy pages to classify as likely scanned.
SCANNED_PAGE_RATIO_THRESHOLD = 0.8
# Characters per page below which OCR is recommended.
LOW_TEXT_DENSITY_THRESHOLD = 50


def analyze_pdf(path: Path) -> PdfAnalysis:
    """
    Inspect PDF structure, encryption, page count, and text-layer signals.

    Uses minimal per-page text probes for OCR readiness only — not resume parsing.
    """
    result = PdfAnalysis()
    metadata: dict[str, Any] = {}

    try:
        reader = PdfReader(str(path), strict=False)
    except PdfReadError as exc:
        result.corrupted = True
        result.error = str(exc)
        return result
    except Exception as exc:  # noqa: BLE001 — collect and continue
        result.corrupted = True
        result.error = str(exc)
        return result

    result.encrypted = bool(reader.is_encrypted)
    if result.encrypted:
        try:
            decrypted = reader.decrypt("")
            if decrypted == 0:
                result.metadata_available = bool(reader.metadata)
                return result
        except Exception:  # noqa: BLE001
            return result

    try:
        result.page_count = len(reader.pages)
    except Exception as exc:  # noqa: BLE001
        result.corrupted = True
        result.error = str(exc)
        return result

    if reader.metadata:
        result.metadata_available = True
        for key in ("/Author", "/Title", "/CreationDate", "/Producer"):
            value = reader.metadata.get(key)
            if value is not None:
                metadata[key.lstrip("/").lower()] = str(value)

    text_pages = 0
    image_heavy_pages = 0
    total_chars = 0

    for page in reader.pages:
        page_text = ""
        try:
            page_text = page.extract_text() or ""
        except Exception:  # noqa: BLE001
            page_text = ""

        stripped = page_text.strip()
        char_count = len(stripped)
        total_chars += char_count

        if char_count >= TEXT_LAYER_MIN_CHARS:
            text_pages += 1

        has_images = _page_has_images(page)
        if has_images and char_count < TEXT_LAYER_MIN_CHARS:
            image_heavy_pages += 1

    page_count = result.page_count or 0
    if page_count > 0:
        text_ratio = text_pages / page_count
        image_ratio = image_heavy_pages / page_count
        avg_chars = total_chars / page_count

        result.text_based = text_ratio >= 0.5
        result.likely_scanned = image_ratio >= SCANNED_PAGE_RATIO_THRESHOLD

        if text_ratio == 0 and image_heavy_pages > 0:
            result.ocr_signal = OcrSignal.OCR_REQUIRED
        elif avg_chars < LOW_TEXT_DENSITY_THRESHOLD and image_heavy_pages > 0:
            result.ocr_signal = OcrSignal.OCR_RECOMMENDED
        else:
            result.ocr_signal = OcrSignal.TEXT_LAYER_OK

    result.metadata = metadata
    return result


def _page_has_images(page: Any) -> bool:
    """Detect image XObjects on a PDF page."""
    try:
        resources = page.get("/Resources")
        if not resources:
            return False
        xobjects = resources.get("/XObject")
        if not xobjects:
            return False
        for obj in xobjects.values():
            subtype = obj.get("/Subtype")
            if subtype == "/Image":
                return True
    except Exception:  # noqa: BLE001
        return False
    return False
