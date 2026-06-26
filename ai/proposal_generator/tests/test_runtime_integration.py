"""Runtime integration tests for Proposal Generator."""

from __future__ import annotations

import logging

from proposal_generator.engine.config import GeneratorConfig
from proposal_generator.engine.discovery import discover_silver_documents
from proposal_generator.engine.processor import ProposalProcessor
from proposal_generator.engine.artifact_ids import ArtifactIdAllocator
from proposal_generator.engine import runtime_client


def test_processor_uses_runtime_only(silver_document, proposal_output) -> None:
    config = GeneratorConfig(
        source_path=silver_document,
        output_path=proposal_output,
    )
    job = discover_silver_documents(config)[0]
    logger = logging.getLogger("test")
    processor = ProposalProcessor(config, ArtifactIdAllocator(proposal_output), logger)
    result = processor.process(job)

    assert result.success is True
    assert result.artifact_id == "ART-00000001"
    assert result.provider_id == "mock"
    assert result.prompt_id == "resume_parser_v1"
    assert result.schema_id == "resume_v1"
    assert result.validation_passed is True


def test_runtime_client_returns_task_result(silver_document) -> None:
    text = (silver_document / "documents" / "abc123def4567890" / "raw_text.txt").read_text()
    result = runtime_client.execute_task("resume_parsing", text)
    assert result.task == "resume_parsing"
    assert result.output["status"] == "mock_success"
