"""Extraction result validation and quality enrichment."""

from __future__ import annotations

from document_engine.cleaners.text_cleaner import clean_extracted_text
from document_engine.models import ExtractionResult
from document_engine.shared.utils import count_words, whitespace_ratio


def finalize_extraction(result: ExtractionResult) -> ExtractionResult:
    """Clean text and populate quality metrics."""
    result.raw_text = clean_extracted_text(result.raw_text)
    result.quality.characters_extracted = len(result.raw_text)
    result.quality.words_extracted = count_words(result.raw_text)
    result.quality.whitespace_ratio = whitespace_ratio(result.raw_text)

    if result.quality.pages <= 0:
        result.quality.pages = max(1, result.quality.empty_pages or 1)

    if result.quality.pages > 0:
        result.quality.average_words_per_page = round(
            result.quality.words_extracted / result.quality.pages, 2
        )

    result.quality.extraction_success = result.success and result.quality.characters_extracted > 0
    return result
