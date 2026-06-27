"""Discovery tests."""

from __future__ import annotations

from pathlib import Path

from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.engine.discovery import discover_silver_documents


def test_discover_silver_documents(silver_document: Path, proposal_output: Path) -> None:
    config = GeneratorConfig(
        source_path=silver_document,
        output_path=proposal_output,
    )
    jobs = discover_silver_documents(config)
    assert len(jobs) == 1
    assert jobs[0].document_id == "abc123def4567890"
    assert jobs[0].task_name == "resume_parsing"


def test_discover_requires_documents_root(tmp_path: Path, proposal_output: Path) -> None:
    source = tmp_path / "empty_silver"
    source.mkdir()
    config = GeneratorConfig(source_path=source, output_path=proposal_output)
    try:
        discover_silver_documents(config)
    except FileNotFoundError as exc:
        assert "DOCUMENTS_NOT_FOUND" in str(exc)
    else:
        raise AssertionError("Expected FileNotFoundError")
