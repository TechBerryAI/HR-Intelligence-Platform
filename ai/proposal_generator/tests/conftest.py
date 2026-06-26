"""Shared test fixtures."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

import runtime.core.runtime as runtime_module


@pytest.fixture(autouse=True)
def reset_runtime_singleton() -> None:
    runtime_module._default_runtime = None
    yield
    runtime_module._default_runtime = None


@pytest.fixture
def silver_document(tmp_path: Path) -> Path:
    """Create a minimal Silver document directory."""
    root = tmp_path / "silver" / "resumes"
    doc_dir = root / "documents" / "abc123def4567890"
    doc_dir.mkdir(parents=True)
    (doc_dir / "raw_text.txt").write_text("Jane Doe\nSenior Python Engineer\n", encoding="utf-8")
    metadata = {
        "artifact": {
            "artifact_id": "ART-DF-EXTR-abc123de",
            "dataset_id": "DS-RESUMES-RAW",
            "dataset_version": "1.0.0",
            "sha256": "sha256:abc123def4567890",
        },
        "document": {
            "source_file": "jane_doe.pdf",
            "doc_type": "resume",
            "source_hash": "sha256:abc123def4567890",
        },
        "extraction": {"success": True},
    }
    report = {
        "quality": {"extraction_success": True, "characters_extracted": 35},
        "warnings": [],
        "errors": [],
    }
    (doc_dir / "metadata.yaml").write_text(yaml.dump(metadata), encoding="utf-8")
    (doc_dir / "extraction_report.yaml").write_text(yaml.dump(report), encoding="utf-8")
    return root


@pytest.fixture
def proposal_output(tmp_path: Path) -> Path:
    path = tmp_path / "proposals" / "resumes"
    path.mkdir(parents=True)
    return path
