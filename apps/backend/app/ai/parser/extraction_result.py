"""Per-document / per-page text extraction results.

Metadata stays on the request object so concurrent bulk workers cannot
overwrite each other's DPI, extractor, or OCR retry state.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class TextQuality(str, Enum):
    GOOD = 'good'
    WEAK = 'weak'
    GARBAGE = 'garbage'
    EMPTY = 'empty'


QUALITY_RANK = {
    TextQuality.GOOD: 3,
    TextQuality.WEAK: 2,
    TextQuality.GARBAGE: 1,
    TextQuality.EMPTY: 0,
}


# Extraction status values (plain strings for easy logging / tests)
STATUS_OK = 'ok'
STATUS_OCR_RECOVERED = 'ocr_recovered'
STATUS_OCR_WEAK = 'ocr_weak'
STATUS_OCR_UNAVAILABLE = 'ocr_unavailable'
STATUS_OCR_FAILED = 'ocr_failed'
STATUS_FAILED = 'failed'


@dataclass
class PageExtractionResult:
    page_number: int
    source: str = ''
    text: str = ''
    used_ocr: bool = False
    ocr_engine: str = ''
    ocr_confidence: float | None = None
    dpi: int = 0
    quality: TextQuality = TextQuality.EMPTY
    fallback: str = ''
    warnings: list[str] = field(default_factory=list)


@dataclass
class ExtractionResult:
    text: str = ''
    source: str = ''
    used_ocr: bool = False
    ocr_engine: str = ''
    ocr_pages: list[int] = field(default_factory=list)
    initial_dpi: int = 0
    final_dpi: int = 0
    quality: TextQuality = TextQuality.EMPTY
    status: str = STATUS_OK
    warnings: list[str] = field(default_factory=list)
    page_results: list[PageExtractionResult] = field(default_factory=list)
    page_count: int = 0
    retry_count: int = 0

    def with_text(self, text: str, *, quality: TextQuality | None = None) -> ExtractionResult:
        """Return a copy with replaced document text (layout / normalize)."""
        self.text = text or ''
        if quality is not None:
            self.quality = quality
        return self
