"""Runtime integration tests for Proposal Generator."""

from __future__ import annotations

from pathlib import Path

import logging

from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.engine.discovery import discover_silver_documents
from dataset.proposals.engine.processor import ProposalProcessor
from dataset.proposals.engine.artifact_ids import ArtifactIdAllocator
from dataset.proposals.engine import runtime_client

TEST_RUNTIME_CONFIG = Path(__file__).resolve().parent / "runtime.test.yaml"


def test_processor_uses_runtime_only(silver_document, proposal_output) -> None:
    config = GeneratorConfig(
        source_path=silver_document,
        output_path=proposal_output,
        runtime_config_path=TEST_RUNTIME_CONFIG,
    )
    job = discover_silver_documents(config)[0]
    logger = logging.getLogger("test")
    processor = ProposalProcessor(config, ArtifactIdAllocator(proposal_output), logger)
    result = processor.process(job)

    assert result.success is True
    assert result.artifact_id == "ART-00000001"
    assert result.provider_id == "mock"
    assert result.prompt_id == "resume_parser_v1"
    assert result.schema_id == "resume_milestone_v1"
    assert result.validation_passed is True


def test_runtime_client_returns_task_result(silver_document) -> None:
    text = (silver_document / "documents" / "abc123def4567890" / "raw_text.txt").read_text()
    result = runtime_client.execute_task(
        "resume_parsing", text, runtime_config_path=TEST_RUNTIME_CONFIG
    )
    assert result.task == "resume_parsing"
    assert result.output["type"] == "resume"
