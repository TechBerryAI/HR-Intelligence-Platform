"""Proposal Generator integration tests."""

from __future__ import annotations

import json
import logging
from pathlib import Path

from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.engine.orchestrator import ProposalEngine


def test_generate_proposals_end_to_end(silver_document: Path, proposal_output: Path) -> None:
    config = GeneratorConfig(
        source_path=silver_document,
        output_path=proposal_output,
        workers=1,
        runtime_config_path=Path(__file__).resolve().parent / "runtime.test.yaml",
    )
    logger = logging.getLogger("test")
    result = ProposalEngine(config, logger).run()

    assert result.files_processed == 1
    assert result.successful == 1
    assert result.failed == 0

    doc_out = proposal_output / "documents" / "abc123def4567890"
    assert (doc_out / "proposal.json").exists()
    assert (doc_out / "proposal_metadata.yaml").exists()
    assert (doc_out / "proposal_report.yaml").exists()

    proposal = json.loads((doc_out / "proposal.json").read_text(encoding="utf-8"))
    assert proposal["type"] == "resume"
    assert proposal["person"]["name"] == "Jane Doe"

    assert (proposal_output / "proposal_summary.yaml").exists()
    assert (proposal_output / "proposal_statistics.yaml").exists()
    assert (proposal_output / "proposal_errors.yaml").exists()
    assert (proposal_output / "proposal_log.yaml").exists()


def test_resume_skips_completed(silver_document: Path, proposal_output: Path) -> None:
    runtime_cfg = Path(__file__).resolve().parent / "runtime.test.yaml"
    config = GeneratorConfig(
        source_path=silver_document,
        output_path=proposal_output,
        workers=1,
        runtime_config_path=runtime_cfg,
    )
    logger = logging.getLogger("test")
    first = ProposalEngine(config, logger).run()
    assert first.successful == 1

    second = ProposalEngine(
        GeneratorConfig(
            source_path=silver_document,
            output_path=proposal_output,
            workers=1,
            resume=True,
            runtime_config_path=runtime_cfg,
        ),
        logger,
    ).run()
    assert second.skipped == 1
    assert second.successful == 0
