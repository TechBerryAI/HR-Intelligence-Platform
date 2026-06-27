"""Write extraction artifacts to disk."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from dataset.extraction.models import ExtractionResult
from dataset.extraction.shared.utils import document_id_from_hash, yaml_dump


def write_document_artifacts(output_root: Path, result: ExtractionResult, artifacts: dict[str, Any]) -> Path:
    doc_id = document_id_from_hash(result.source_hash or "sha256:unknown")
    doc_dir = output_root / "documents" / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)

    (doc_dir / "raw_text.txt").write_text(result.raw_text, encoding="utf-8")
    (doc_dir / "metadata.yaml").write_text(yaml_dump(artifacts["metadata"]), encoding="utf-8")
    (doc_dir / "extraction_report.yaml").write_text(
        yaml_dump(artifacts["extraction_report"]), encoding="utf-8"
    )
    return doc_dir


def write_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml_dump(data), encoding="utf-8")
