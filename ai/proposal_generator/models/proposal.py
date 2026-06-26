"""Proposal Generator data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class SilverDocumentJob:
    """Work item discovered from the Silver Dataset."""

    document_id: str
    source_dir: str
    output_dir: str
    relative_path: str
    doc_type: str
    task_name: str
    dataset_id: str
    dataset_version: str
    source_file: str
    source_hash: str
    extraction_success: bool


@dataclass
class ProposalResult:
    """Result of generating a proposal for one document."""

    document_id: str
    relative_path: str
    artifact_id: str | None = None
    success: bool = False
    skipped: bool = False
    skip_reason: str | None = None
    task: str = ""
    output_path: str | None = None
    latency_ms: float = 0.0
    attempts: int = 0
    retries: int = 0
    fallbacks_used: int = 0
    validation_passed: bool = False
    provider_id: str | None = None
    model: str | None = None
    prompt_id: str | None = None
    schema_id: str | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    token_usage: dict[str, int] | None = None
    confidence: float | None = None


@dataclass
class ProposalRunResult:
    """Complete proposal generation run."""

    run_id: str
    started_at: datetime
    completed_at: datetime | None = None
    source_path: str = ""
    output_path: str = ""
    documents: list[ProposalResult] = field(default_factory=list)
    files_processed: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    validation_failures: int = 0
    runtime_failures: int = 0
    duration_seconds: float = 0.0
    errors: list[dict[str, Any]] = field(default_factory=list)
    warnings: list[dict[str, Any]] = field(default_factory=list)
