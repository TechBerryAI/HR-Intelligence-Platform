"""Proposal generation orchestrator."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from proposal_generator.engine.artifact_ids import ArtifactIdAllocator
from proposal_generator.engine.config import GeneratorConfig
from proposal_generator.engine.discovery import discover_silver_documents
from proposal_generator.engine.processor import ProposalProcessor
from proposal_generator.engine import runtime_client
from proposal_generator.models.proposal import ProposalResult, ProposalRunResult
from proposal_generator.reporting.generators import (
    build_proposal_errors,
    build_proposal_log,
    build_proposal_statistics,
    build_proposal_summary,
)
from proposal_generator.reporting.writer import write_dataset_reports
from proposal_generator.shared.utils import utc_now


class ProposalEngine:
    """Orchestrate Silver → Proposal artifact generation."""

    def __init__(self, config: GeneratorConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.allocator = ArtifactIdAllocator(config.output_path)
        self.processor = ProposalProcessor(config, self.allocator, logger)

    def run(self) -> ProposalRunResult:
        started_at = utc_now()
        run = ProposalRunResult(
            run_id=str(uuid.uuid4()),
            started_at=started_at,
            source_path=str(self.config.source_path),
            output_path=str(self.config.output_path),
        )

        jobs = discover_silver_documents(self.config)
        self.logger.info("Discovered %d Silver documents for proposal generation", len(jobs))

        t0 = time.perf_counter()
        results = self._process_concurrent(jobs)
        run.documents = results
        run.files_processed = len(results)
        run.successful = sum(1 for result in results if result.success)
        run.failed = sum(1 for result in results if not result.skipped and not result.success)
        run.skipped = sum(1 for result in results if result.skipped)
        run.validation_failures = sum(
            1 for result in results if result.success and not result.validation_passed
        )
        run.runtime_failures = sum(
            1
            for result in results
            if not result.skipped and not result.success and result.errors
        )

        for result in results:
            if result.errors and not result.skipped:
                run.errors.append(
                    {
                        "document_id": result.document_id,
                        "relative_path": result.relative_path,
                        "errors": result.errors,
                    }
                )
            for warning in result.warnings:
                run.warnings.append(
                    {
                        "document_id": result.document_id,
                        "relative_path": result.relative_path,
                        "message": warning,
                    }
                )

        run.completed_at = utc_now()
        run.duration_seconds = time.perf_counter() - t0

        self._write_outputs(run)
        metrics = runtime_client.runtime_metrics_summary(
            runtime_config_path=self.config.runtime_config_path
        )
        self.logger.info(
            "Proposal generation complete — processed=%d success=%d failed=%d skipped=%d "
            "validation_failures=%d runtime_failures=%d elapsed=%.2fs runtime_tasks=%s",
            run.files_processed,
            run.successful,
            run.failed,
            run.skipped,
            run.validation_failures,
            run.runtime_failures,
            run.duration_seconds,
            metrics.get("total_tasks", 0),
        )
        return run

    def _process_concurrent(self, jobs) -> list[ProposalResult]:
        results: list[ProposalResult] = []
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {executor.submit(self.processor.process, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    self.logger.exception("Failed processing %s", job.relative_path)
                    result = ProposalResult(
                        document_id=job.document_id,
                        relative_path=job.relative_path,
                        task=job.task_name,
                        success=False,
                        errors=[str(exc)],
                    )
                results.append(result)
        return sorted(results, key=lambda item: item.relative_path)

    def _write_outputs(self, run: ProposalRunResult) -> None:
        statistics = build_proposal_statistics(run)
        runtime_metrics = runtime_client.runtime_metrics_summary(
            runtime_config_path=self.config.runtime_config_path
        )
        statistics["runtime"]["metrics_summary"] = runtime_metrics

        reports = {
            "summary": build_proposal_summary(run, self.config),
            "statistics": statistics,
            "errors": build_proposal_errors(run),
            "log": build_proposal_log(run),
        }
        write_dataset_reports(self.config.output_path, reports)
