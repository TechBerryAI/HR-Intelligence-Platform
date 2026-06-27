"""Document discovery for extraction."""

from __future__ import annotations

from pathlib import Path

from dataset.extraction.engine.config import EngineConfig
from dataset.extraction.models import DocumentJob
from dataset.extraction.shared.inspector_loader import InspectorContext
from dataset.extraction.shared.utils import relative_path


def discover_documents(
    config: EngineConfig,
    inspector: InspectorContext | None,
) -> list[DocumentJob]:
    source = config.source_path
    if not source.exists():
        raise FileNotFoundError(f"SOURCE_NOT_FOUND: {source}")

    jobs: list[DocumentJob] = []
    iterator = source.rglob("*") if config.recursive else source.glob("*")

    for path in sorted(iterator, key=lambda p: p.as_posix()):
        if not path.is_file():
            continue
        rel = relative_path(path, source)

        if config.skip_non_resume_artifacts and path.name.startswith("."):
            continue

        fmt = "unknown"
        if inspector:
            entry = inspector.hash_by_path.get(rel)
            if entry and entry.get("format"):
                fmt = entry["format"]

        source_hash = inspector.hash_for_path(rel) if inspector else None
        jobs.append(
            DocumentJob(
                absolute_path=str(path),
                relative_path=rel,
                format=fmt,
                source_hash=source_hash,
                inspector_ocr_required=rel in inspector.ocr_required_paths if inspector else False,
                is_duplicate=inspector.is_duplicate(rel) if inspector else False,
                duplicate_of=inspector.duplicate_of(rel) if inspector else None,
            )
        )
    return jobs
