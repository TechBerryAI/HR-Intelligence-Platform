"""Input validation tests."""

from __future__ import annotations

from pathlib import Path

from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.engine.discovery import discover_silver_documents
from dataset.proposals.validators.input_validator import InputValidator


def test_skip_failed_extraction(silver_document: Path, proposal_output: Path) -> None:
    report_path = silver_document / "documents" / "abc123def4567890" / "extraction_report.yaml"
    report_path.write_text("quality:\n  extraction_success: false\n", encoding="utf-8")

    config = GeneratorConfig(source_path=silver_document, output_path=proposal_output)
    job = discover_silver_documents(config)[0]
    result = InputValidator().validate(job, config)
    assert result is not None
    assert result.skipped is True


def test_resume_skips_existing(silver_document: Path, proposal_output: Path) -> None:
    config = GeneratorConfig(source_path=silver_document, output_path=proposal_output, resume=True)
    job = discover_silver_documents(config)[0]
    out_dir = Path(job.output_dir)
    out_dir.mkdir(parents=True)
    (out_dir / "proposal.json").write_text("{}", encoding="utf-8")
    (out_dir / "proposal_metadata.yaml").write_text("artifact: {}\n", encoding="utf-8")

    result = InputValidator().validate(job, config)
    assert result is not None
    assert result.skipped is True
