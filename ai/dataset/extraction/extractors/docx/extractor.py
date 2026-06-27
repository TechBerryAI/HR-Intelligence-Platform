"""DOCX text extraction."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from dataset.extraction.extractors.base import BaseExtractor
from dataset.extraction.models import ExtractionResult


class DocxExtractor(BaseExtractor):
    format_id = "docx"
    method_name = "python-docx"

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
            document = Document(str(path))
        except (PackageNotFoundError, ValueError, KeyError) as exc:
            result.errors.append(str(exc))
            result.duration_seconds = time.perf_counter() - started
            return result

        sections: dict[str, list[str]] = {
            "paragraphs": [],
            "tables": [],
            "headers": [],
            "footers": [],
        }

        for paragraph in document.paragraphs:
            text = paragraph.text.strip()
            if text:
                sections["paragraphs"].append(text)

        for table in document.tables:
            for row in table.rows:
                row_cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if row_cells:
                    sections["tables"].append(" | ".join(row_cells))

        for section in document.sections:
            header_text = "\n".join(p.text.strip() for p in section.header.paragraphs if p.text.strip())
            footer_text = "\n".join(p.text.strip() for p in section.footer.paragraphs if p.text.strip())
            if header_text:
                sections["headers"].append(header_text)
            if footer_text:
                sections["footers"].append(footer_text)

        ordered_parts: list[str] = []
        for key in ("headers", "paragraphs", "tables", "footers"):
            if sections[key]:
                ordered_parts.append(f"## {key.upper()}\n" + "\n".join(sections[key]))

        result.raw_text = "\n\n".join(ordered_parts)
        result.metadata = self._core_metadata(document)
        result.document_properties = dict(result.metadata)
        result.quality.pages = max(1, len(document.paragraphs) // 40)
        result.success = bool(result.raw_text.strip())

        if not result.success:
            result.errors.append("No extractable text found in DOCX")

        result.duration_seconds = time.perf_counter() - started
        return result

    @staticmethod
    def _core_metadata(document: Document) -> dict[str, Any]:
        props = document.core_properties
        metadata: dict[str, Any] = {"paragraph_count": len(document.paragraphs), "table_count": len(document.tables)}
        for attr in ("author", "title", "subject", "category", "comments", "last_modified_by"):
            value = getattr(props, attr, None)
            if value is not None:
                metadata[attr] = value.isoformat() if hasattr(value, "isoformat") else str(value)
        for attr in ("created", "modified"):
            value = getattr(props, attr, None)
            if value is not None:
                metadata[attr] = value.isoformat()
        return metadata
