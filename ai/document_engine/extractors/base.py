"""Base extractor protocol."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from document_engine.models import ExtractionResult


class BaseExtractor(ABC):
    """Interface for format-specific extractors."""

    format_id: str = "unknown"
    method_name: str = "unknown"

    @abstractmethod
    def extract(self, path: Path, *, relative_path: str, source_hash: str) -> ExtractionResult:
        """Extract text and metadata from a document."""
