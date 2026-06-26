"""DOCX analysis without resume text extraction."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from zipfile import BadZipFile

from docx import Document
from docx.opc.exceptions import PackageNotFoundError

from ..models import DocxAnalysis


def analyze_docx(path: Path) -> DocxAnalysis:
    """Inspect DOCX readability and core metadata."""
    result = DocxAnalysis()
    metadata: dict[str, Any] = {}

    try:
        document = Document(str(path))
    except (PackageNotFoundError, BadZipFile, KeyError, ValueError) as exc:
        result.corrupted = True
        result.error = str(exc)
        return result
    except Exception as exc:  # noqa: BLE001
        result.corrupted = True
        result.error = str(exc)
        return result

    result.readable = True
    try:
        result.paragraph_count_estimate = len(document.paragraphs)
    except Exception:  # noqa: BLE001
        result.paragraph_count_estimate = None

    props = document.core_properties
    for attr in ("author", "title", "subject", "created", "modified", "last_modified_by"):
        value = getattr(props, attr, None)
        if value is not None:
            metadata[attr] = value.isoformat() if hasattr(value, "isoformat") else str(value)

    if metadata:
        result.metadata_available = True
    result.metadata = metadata
    return result
