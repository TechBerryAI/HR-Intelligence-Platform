"""Data models for dataset inspection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class InspectionPhase(str, Enum):
    """Execution phases from architecture.yaml."""

    DISCOVER = "discover"
    CLASSIFY = "classify"
    MEASURE = "measure"
    HASH = "hash"
    DETECT_ISSUES = "detect_issues"
    SAMPLE = "sample"
    SCORE = "score"
    EMIT = "emit"


class PhaseStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    SKIPPED = "skipped"
    FAILED = "failed"


class OcrSignal(str, Enum):
    OCR_REQUIRED = "ocr_required"
    OCR_RECOMMENDED = "ocr_recommended"
    TEXT_LAYER_OK = "text_layer_ok"


@dataclass
class FileTimestamps:
    """File creation and modification timestamps when available."""

    created_at: datetime | None = None
    modified_at: datetime | None = None


@dataclass
class PdfAnalysis:
    """PDF-specific inspection results."""

    page_count: int | None = None
    encrypted: bool = False
    corrupted: bool = False
    likely_scanned: bool = False
    text_based: bool | None = None
    metadata_available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    ocr_signal: OcrSignal | None = None
    error: str | None = None


@dataclass
class DocxAnalysis:
    """DOCX-specific inspection results."""

    readable: bool = False
    corrupted: bool = False
    metadata_available: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    paragraph_count_estimate: int | None = None
    error: str | None = None


@dataclass
class FileRecord:
    """Inspection record for a single file."""

    relative_path: str
    absolute_path: str
    extension: str
    format: str
    size_bytes: int
    timestamps: FileTimestamps
    sha256: str | None = None
    hash_error: str | None = None
    read_error: str | None = None
    zero_byte: bool = False
    unsupported_format: bool = False
    corrupt: bool = False
    password_protected: bool = False
    page_count: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    metadata_available: bool = False
    ocr_signal: OcrSignal | None = None
    pdf_analysis: PdfAnalysis | None = None
    docx_analysis: DocxAnalysis | None = None
    encoding_error: bool = False
    mixed_line_endings: bool = False


@dataclass
class DirectoryNode:
    """Node in the directory tree summary."""

    name: str
    path: str
    type: str  # "directory" | "file"
    depth: int
    file_count: int = 0
    children: list[DirectoryNode] = field(default_factory=list)


@dataclass
class DuplicateGroup:
    """Group of files sharing identical content hash."""

    sha256: str
    paths: list[str]
    count: int


@dataclass
class FilenameDuplicateGroup:
    """Group of files sharing the same basename."""

    filename: str
    paths: list[str]
    count: int


@dataclass
class LogEvent:
    """Structured log event for inspection_log.yaml."""

    timestamp: datetime
    level: str
    message: str
    phase_id: str | None = None
    code: str | None = None
    path: str | None = None
    details: dict[str, Any] | None = None


@dataclass
class PhaseRecord:
    """Timeline record for an execution phase."""

    phase_id: str
    started_at: datetime | None = None
    completed_at: datetime | None = None
    status: PhaseStatus = PhaseStatus.PENDING


@dataclass
class InspectionResult:
    """Complete inspection run result."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    source_path: str = ""
    output_path: str = ""
    files: list[FileRecord] = field(default_factory=list)
    directory_tree: DirectoryNode | None = None
    max_depth: int = 0
    total_directories: int = 0
    duplicate_groups: list[DuplicateGroup] = field(default_factory=list)
    filename_duplicate_groups: list[FilenameDuplicateGroup] = field(default_factory=list)
    hash_entries: list[dict[str, Any]] = field(default_factory=list)
    selected_sample_files: list[str] = field(default_factory=list)
    phases: list[PhaseRecord] = field(default_factory=list)
    events: list[LogEvent] = field(default_factory=list)
    errors: int = 0
    warnings: int = 0
    files_skipped: int = 0
    duration_seconds: float = 0.0
    status: str = "running"
    dry_run: bool = False
    artifacts_written: list[str] = field(default_factory=list)
    stats: Any = None
    quality: Any = None
