"""Data models for document extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class PageExtraction:
    """Per-page extraction statistics."""

    page_number: int
    char_count: int
    word_count: int
    empty: bool


@dataclass
class ExtractionQuality:
    """Quality metrics for an extraction run."""

    characters_extracted: int = 0
    words_extracted: int = 0
    pages: int = 0
    average_words_per_page: float = 0.0
    extraction_success: bool = False
    requires_ocr: bool = False
    encoding_issues: bool = False
    empty_pages: int = 0
    whitespace_ratio: float = 0.0


@dataclass
class ExtractionResult:
    """Result of extracting a single document."""

    source_path: str
    relative_path: str
    format: str
    source_hash: str
    success: bool
    raw_text: str = ""
    method: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    document_properties: dict[str, Any] = field(default_factory=dict)
    page_stats: list[PageExtraction] = field(default_factory=list)
    quality: ExtractionQuality = field(default_factory=ExtractionQuality)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    skipped: bool = False
    skip_reason: str | None = None
    duration_seconds: float = 0.0


@dataclass
class DocumentJob:
    """Work item for the extraction engine."""

    absolute_path: str
    relative_path: str
    format: str
    source_hash: str | None = None
    inspector_ocr_required: bool = False
    is_duplicate: bool = False
    duplicate_of: str | None = None


@dataclass
class ExtractionRunResult:
    """Complete extraction run summary."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    source_path: str = ""
    output_path: str = ""
    inspection_path: str | None = None
    documents: list[ExtractionResult] = field(default_factory=list)
    files_processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    ocr_candidates: int = 0
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
