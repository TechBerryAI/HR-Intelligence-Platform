"""Extraction engine orchestrator."""

from __future__ import annotations

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dataset.extraction.engine.config import EngineConfig
from dataset.extraction.engine.discovery import discover_documents
from dataset.extraction.engine.processor import DocumentProcessor
from dataset.extraction.models import ExtractionRunResult
from dataset.extraction.reporting.generators import (
    build_dataset_summary,
    build_document_metadata,
    build_extraction_log,
    build_extraction_report,
)
from dataset.extraction.reporting.writer import write_document_artifacts, write_yaml
from dataset.extraction.shared.inspector_loader import InspectorContext
from dataset.extraction.shared.utils import isoformat_datetime, utc_now


class ExtractionEngine:
    """Orchestrate deterministic document extraction."""

    def __init__(self, config: EngineConfig, logger: logging.Logger) -> None:
        self.config = config
        self.logger = logger
        self.processor = DocumentProcessor(config, logger)

    def run(self) -> ExtractionRunResult:
        started_at = utc_now()
        run = ExtractionRunResult(
            run_id=str(uuid.uuid4()),
            started_at=started_at,
            source_path=str(self.config.source_path),
            output_path=str(self.config.output_path),
        )

        inspector = None
        if self.config.inspection_path and self.config.inspection_path.exists():
            inspector = InspectorContext.load(self.config.inspection_path)
            run.inspection_path = str(self.config.inspection_path)
            if self.config.enforce_extraction_gate and inspector.extraction_ready is False:
                raise RuntimeError("Inspector gate extraction_ready is false")

        jobs = discover_documents(self.config, inspector)
        self.logger.info("Discovered %d documents for extraction", len(jobs))

        t0 = time.perf_counter()
        results = self._process_concurrent(jobs)
        run.documents = results
        run.files_processed = len(results)
        run.successful = sum(1 for r in results if r.quality.extraction_success)
        run.failed = sum(
            1 for r in results if not r.skipped and not r.quality.extraction_success
        )
        run.skipped = sum(1 for r in results if r.skipped)
        run.ocr_candidates = sum(1 for r in results if r.quality.requires_ocr)

        for result in results:
            if result.errors and not result.skipped:
                run.errors.append(
                    {
                        "path": result.relative_path,
                        "errors": result.errors,
                    }
                )
            for warning in result.warnings:
                run.warnings.append({"path": result.relative_path, "message": warning})

        run.completed_at = utc_now()
        run.duration_seconds = time.perf_counter() - t0

        self._write_outputs(run)
        self.logger.info(
            "Extraction complete — processed=%d success=%d failed=%d skipped=%d ocr=%d elapsed=%.2fs",
            run.files_processed,
            run.successful,
            run.failed,
            run.skipped,
            run.ocr_candidates,
            run.duration_seconds,
        )
        return run

    def _process_concurrent(self, jobs):
        results = []
        with ThreadPoolExecutor(max_workers=self.config.workers) as executor:
            futures = {executor.submit(self.processor.process, job): job for job in jobs}
            for future in as_completed(futures):
                job = futures[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001
                    from dataset.extraction.models import ExtractionResult

                    result = ExtractionResult(
                        source_path=job.absolute_path,
                        relative_path=job.relative_path,
                        format=job.format,
                        source_hash=job.source_hash or "",
                        success=False,
                        errors=[str(exc)],
                    )
                    self.logger.exception("Failed processing %s", job.relative_path)

                results.append(result)
        return sorted(results, key=lambda r: r.relative_path)

    def _write_outputs(self, run: ExtractionRunResult) -> None:
        output = self.config.output_path
        output.mkdir(parents=True, exist_ok=True)
        created_at = isoformat_datetime(run.completed_at or utc_now())

        for result in run.documents:
            if result.skipped and result.skip_reason == "Already extracted (--resume)":
                continue
            metadata = build_document_metadata(
                result,
                run_id=run.run_id,
                dataset_id=self.config.dataset_id,
                dataset_version=self.config.dataset_version,
                doc_type=self.config.doc_type,
                created_at=created_at,
            )
            report = build_extraction_report(result, run_id=run.run_id, created_at=created_at)
            write_document_artifacts(
                output,
                result,
                {"metadata": metadata, "extraction_report": report},
            )

        summary = build_dataset_summary(
            run,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
            doc_type=self.config.doc_type,
            config_snapshot=self.config.snapshot(),
        )
        log = build_extraction_log(
            run,
            dataset_id=self.config.dataset_id,
            dataset_version=self.config.dataset_version,
        )
        write_yaml(output / "extraction_summary.yaml", summary)
        write_yaml(output / "extraction_log.yaml", log)
