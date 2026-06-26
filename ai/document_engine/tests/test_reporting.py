"""Tests for reporting generators."""

from document_engine.models import ExtractionQuality, ExtractionResult
from document_engine.reporting.generators import build_extraction_report


def test_build_extraction_report_contains_quality_metrics() -> None:
    result = ExtractionResult(
        source_path="/tmp/a.pdf",
        relative_path="a.pdf",
        format="pdf",
        source_hash="sha256:" + "a" * 64,
        success=True,
        quality=ExtractionQuality(
            characters_extracted=100,
            words_extracted=20,
            pages=2,
            average_words_per_page=10.0,
            extraction_success=True,
            requires_ocr=False,
            whitespace_ratio=0.1,
        ),
    )
    report = build_extraction_report(
        result,
        run_id="11111111-1111-1111-1111-111111111111",
        created_at="2026-06-26T00:00:00Z",
    )
    assert report["quality"]["characters_extracted"] == 100
    assert report["quality"]["extraction_success"] is True
