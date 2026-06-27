"""Tests for OCR detector."""

from pathlib import Path

from dataset.extraction.detectors.ocr.detector import OcrDetector


def test_ocr_detector_flags_insufficient_text() -> None:
    detector = OcrDetector()
    assessment = detector.assess_pdf(path=Path("dummy.pdf"), extracted_text="short")
    assert assessment.requires_ocr is True


def test_ocr_detector_accepts_sufficient_text() -> None:
    detector = OcrDetector()
    text = "A" * 100
    assessment = detector.assess_pdf(path=Path("dummy.pdf"), extracted_text=text)
    assert assessment.requires_ocr is False
