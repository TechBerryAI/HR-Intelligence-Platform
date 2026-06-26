"""Tests for text cleaner."""

from document_engine.cleaners.text_cleaner import clean_extracted_text


def test_clean_extracted_text_normalizes_whitespace() -> None:
    raw = "Hello   world\r\n\r\n\n\nSecond paragraph"
    cleaned = clean_extracted_text(raw)
    assert cleaned == "Hello world\n\nSecond paragraph"
