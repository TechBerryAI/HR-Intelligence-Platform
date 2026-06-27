"""PDF text extraction."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pdfplumber
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from dataset.extraction.detectors.ocr.detector import OcrDetector
from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.models import ExtractionResult, PageExtraction
from dataset.extraction.shared.constants import MIN_EXTRACTED_CHARS


class PdfExtractor(BaseExtractor):
    format_id = "pdf"
    method_name = "pypdf+pdfplumber"

    def __init__(self, max_pages: int = 0) -> None:
        self.max_pages = max_pages
        self.ocr_detector = OcrDetector()

    def extract(self, path: Path, *, relative_path: str, source_hash: str) -> ExtractionResult:
        started = time.perf_counter()
        result = ExtractionResult(
            source_path=str(path),
            relative_path=relative_path,
            format=self.format_id,
            source_hash=source_hash,
            success=False,
            method=self.method_name,
        )

        try:
            reader = PdfReader(str(path), strict=False)
        except PdfReadError as exc:
            result.errors.append(str(exc))
            result.duration_seconds = time.perf_counter() - started
            return result
        except Exception as exc:  # noqa: BLE001
            result.errors.append(str(exc))
            result.duration_seconds = time.perf_counter() - started
            return result

        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    result.errors.append("PDF is password protected")
                    result.duration_seconds = time.perf_counter() - started
                    return result
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"PDF encryption error: {exc}")
                result.duration_seconds = time.perf_counter() - started
                return result

        pages = reader.pages
        if self.max_pages:
            pages = pages[: self.max_pages]

        metadata = self._pdf_metadata(reader)
        result.metadata = metadata
        result.document_properties = {
            key: metadata.get(key)
            for key in ("author", "title", "creator", "producer", "creation_date", "modification_date")
            if metadata.get(key)
        }

        text_parts: list[str] = []
        page_stats: list[PageExtraction] = []

        for index, page in enumerate(pages, start=1):
            page_text = self._extract_page_text(path, index - 1, page)
            char_count = len(page_text.strip())
            word_count = len(page_text.split())
            empty = char_count == 0
            page_stats.append(
                PageExtraction(
                    page_number=index,
                    char_count=char_count,
                    word_count=word_count,
                    empty=empty,
                )
            )
            if page_text.strip():
                text_parts.append(page_text.strip())

        result.page_stats = page_stats
        result.raw_text = "\n\n".join(text_parts)
        result.quality.pages = len(page_stats)
        result.quality.empty_pages = sum(1 for p in page_stats if p.empty)

        ocr_assessment = self.ocr_detector.assess_pdf(path, extracted_text=result.raw_text)
        result.quality.requires_ocr = ocr_assessment.requires_ocr
        if ocr_assessment.reason:
            result.warnings.append(ocr_assessment.reason)

        if len(result.raw_text.strip()) < MIN_EXTRACTED_CHARS:
            result.errors.append(
                f"Insufficient text extracted ({len(result.raw_text.strip())} chars); PDF may be scanned or corrupt"
            )
        else:
            result.success = True

        result.duration_seconds = time.perf_counter() - started
        return result

    @staticmethod
    def _pdf_metadata(reader: PdfReader) -> dict[str, Any]:
        metadata: dict[str, Any] = {"page_count": len(reader.pages)}
        if not reader.metadata:
            return metadata
        mapping = {
            "/Author": "author",
            "/Title": "title",
            "/Creator": "creator",
            "/Producer": "producer",
            "/CreationDate": "creation_date",
            "/ModDate": "modification_date",
        }
        for pdf_key, field in mapping.items():
            value = reader.metadata.get(pdf_key)
            if value is not None:
                metadata[field] = str(value)
        return metadata

    def _extract_page_text(self, path: Path, page_index: int, page: Any) -> str:
        try:
            text = page.extract_text() or ""
            if text.strip():
                return text
        except Exception:  # noqa: BLE001
            pass

        try:
            with pdfplumber.open(str(path)) as pdf:
                if page_index < len(pdf.pages):
                    plumber_text = pdf.pages[page_index].extract_text() or ""
                    if plumber_text.strip():
                        return plumber_text
        except Exception:  # noqa: BLE001
            pass
        return ""
