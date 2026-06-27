"""Process a single Silver document into proposal artifacts."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

from dataset.proposals.engine import runtime_client
from dataset.proposals.engine.artifact_ids import ArtifactIdAllocator
from dataset.proposals.engine.config import GeneratorConfig
from dataset.proposals.exporters.writer import write_proposal_artifacts
from dataset.proposals.models.proposal import ProposalResult, SilverDocumentJob
from dataset.proposals.reporting.generators import build_document_metadata, build_document_report
from dataset.proposals.shared.utils import isoformat_datetime, utc_now
from dataset.proposals.validators.input_validator import InputValidator
from runtime.exceptions import RetryExhaustedError, RuntimeError, ValidationError

if TYPE_CHECKING:
    pass


class ProposalProcessor:
    """Generate proposal artifacts for one Silver document."""

    def __init__(
        self,
        config: GeneratorConfig,
        allocator: ArtifactIdAllocator,
        logger: logging.Logger,
    ) -> None:
        self.config = config
        self.allocator = allocator
        self.logger = logger
        self.validator = InputValidator()

    def process(self, job: SilverDocumentJob) -> ProposalResult:
        preflight = self.validator.validate(job, self.config)
        if preflight is not None:
            return preflight

        raw_text = (Path(job.source_dir) / "raw_text.txt").read_text(encoding="utf-8")
        try:
            task_result = runtime_client.execute_task(
                job.task_name,
                raw_text,
                runtime_config_path=self.config.runtime_config_path,
            )
        except (RetryExhaustedError, RuntimeError, ValidationError) as exc:
            self.logger.warning("Runtime failure for %s: %s", job.relative_path, exc)
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                task=job.task_name,
                success=False,
                errors=[str(exc)],
            )
        except Exception as exc:  # noqa: BLE001
            self.logger.exception("Unexpected failure for %s", job.relative_path)
            return ProposalResult(
                document_id=job.document_id,
                relative_path=job.relative_path,
                task=job.task_name,
                success=False,
                errors=[str(exc)],
            )

        timestamp = isoformat_datetime(utc_now())
        artifact_id = self.allocator.assign()
        prompt_ver = runtime_client.prompt_version(
            task_result.prompt_id,
            runtime_config_path=self.config.runtime_config_path,
        )
        schema_ver = runtime_client.schema_version(
            task_result.schema_id,
            runtime_config_path=self.config.runtime_config_path,
        )

        warnings: list[str] = []
        errors: list[str] = []
        confidence = None
        if isinstance(task_result.output, dict):
            confidence = task_result.output.get("confidence")
            if task_result.output.get("status") == "mock_success":
                warnings.append("Mock provider response — replace with Ollama for production parsing")

        metadata = build_document_metadata(
            job=job,
            artifact_id=artifact_id,
            task_result=task_result,
            prompt_version=prompt_ver,
            schema_version=schema_ver,
            runtime_version=runtime_client.runtime_version(),
            timestamp=timestamp,
        )
        report = build_document_report(
            job=job,
            artifact_id=artifact_id,
            task_result=task_result,
            warnings=warnings,
            errors=errors,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
        )

        output_dir = write_proposal_artifacts(
            Path(job.output_dir),
            proposal=task_result.output,
            metadata=metadata,
            report=report,
        )

        return ProposalResult(
            document_id=job.document_id,
            relative_path=job.relative_path,
            artifact_id=artifact_id,
            success=True,
            task=task_result.task,
            output_path=str(output_dir),
            latency_ms=task_result.latency_ms,
            attempts=task_result.attempts,
            retries=task_result.retries,
            fallbacks_used=task_result.fallbacks_used,
            validation_passed=task_result.validation_passed,
            provider_id=task_result.provider_id,
            model=task_result.model,
            prompt_id=task_result.prompt_id,
            schema_id=task_result.schema_id,
            warnings=warnings,
            token_usage=task_result.token_usage,
            confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
        )
