"""Artifact ID allocator tests."""

from __future__ import annotations

from pathlib import Path

from proposal_generator.engine.artifact_ids import ArtifactIdAllocator


def test_assign_sequential_ids(tmp_path: Path) -> None:
    allocator = ArtifactIdAllocator(tmp_path)
    first = allocator.assign()
    second = allocator.assign()
    assert first == "ART-00000001"
    assert second == "ART-00000002"


def test_resume_from_existing_metadata(tmp_path: Path) -> None:
    doc_dir = tmp_path / "documents" / "doc1"
    doc_dir.mkdir(parents=True)
    metadata = """
artifact:
  artifact_id: ART-00000007
"""
    (doc_dir / "proposal_metadata.yaml").write_text(metadata, encoding="utf-8")

    allocator = ArtifactIdAllocator(tmp_path)
    assert allocator.assign() == "ART-00000008"
