"""Extractor registry and dispatch."""

from __future__ import annotations

from pathlib import Path

from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.extractors.doc.extractor import DocExtractor
from dataset.extraction.extractors.docx.extractor import DocxExtractor
from dataset.extraction.extractors.pdf.extractor import PdfExtractor
from dataset.extraction.extractors.rtf.extractor import RtfExtractor
from dataset.extraction.extractors.txt.extractor import TxtExtractor
from dataset.extraction.models import ExtractionResult


class ExtractorRegistry:
    """Dispatch extraction by detected format."""

    def __init__(self, pdf_max_pages: int = 0) -> None:
        self._extractors: dict[str, BaseExtractor] = {
            "pdf": PdfExtractor(max_pages=pdf_max_pages),
            "docx": DocxExtractor(),
            "doc": DocExtractor(),
            "txt": TxtExtractor(),
            "rtf": RtfExtractor(),
        }

    def extract(
        self,
        path: Path,
        *,
        format_id: str,
        relative_path: str,
        source_hash: str,
    ) -> ExtractionResult:
        extractor = self._extractors.get(format_id)
        if extractor is None:
            return ExtractionResult(
                source_path=str(path),
                relative_path=relative_path,
                format=format_id,
                source_hash=source_hash,
                success=False,
                errors=[f"Unsupported format for extraction: {format_id}"],
            )
        return extractor.extract(path, relative_path=relative_path, source_hash=source_hash)
