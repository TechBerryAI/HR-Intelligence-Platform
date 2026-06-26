"""Extractor registry and dispatch."""

from __future__ import annotations

from pathlib import Path

from document_engine.extractors.base import BaseExtractor
from document_engine.extractors.doc.extractor import DocExtractor
from document_engine.extractors.docx.extractor import DocxExtractor
from document_engine.extractors.pdf.extractor import PdfExtractor
from document_engine.extractors.rtf.extractor import RtfExtractor
from document_engine.extractors.txt.extractor import TxtExtractor
from document_engine.models import ExtractionResult


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
