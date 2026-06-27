"""OCR requirement detection (no OCR performed)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from pypdf import PdfReader

from dataset.extraction.shared.constants import MIN_EXTRACTED_CHARS, TEXT_LAYER_MIN_CHARS


@dataclass
class OcrAssessment:
    requires_ocr: bool
    reason: str | None = None


class OcrDetector:
    """Detect when OCR is required without performing OCR."""

    def assess_pdf(self, path: Path, *, extracted_text: str) -> OcrAssessment:
        stripped = extracted_text.strip()
        if len(stripped) >= MIN_EXTRACTED_CHARS:
            return OcrAssessment(requires_ocr=False)

        image_heavy = self._pdf_image_heavy(path)
        if image_heavy and len(stripped) < TEXT_LAYER_MIN_CHARS:
            return OcrAssessment(
                requires_ocr=True,
                reason="PDF appears scanned; extracted text below minimum threshold",
            )
        if len(stripped) < MIN_EXTRACTED_CHARS:
            return OcrAssessment(
                requires_ocr=True,
                reason=f"Extracted only {len(stripped)} characters; OCR likely required",
            )
        return OcrAssessment(requires_ocr=False)

    @staticmethod
    def _pdf_image_heavy(path: Path) -> bool:
        try:
            reader = PdfReader(str(path), strict=False)
            if not reader.pages:
                return False
            heavy = 0
            for page in reader.pages:
                text = (page.extract_text() or "").strip()
                if len(text) < TEXT_LAYER_MIN_CHARS and OcrDetector._page_has_images(page):
                    heavy += 1
            return heavy / len(reader.pages) >= 0.5
        except Exception:  # noqa: BLE001
            return False

    @staticmethod
    def _page_has_images(page) -> bool:
        try:
            resources = page.get("/Resources")
            if not resources:
                return False
            xobjects = resources.get("/XObject")
            if not xobjects:
                return False
            for obj in xobjects.values():
                if obj.get("/Subtype") == "/Image":
                    return True
        except Exception:  # noqa: BLE001
            return False
        return False
