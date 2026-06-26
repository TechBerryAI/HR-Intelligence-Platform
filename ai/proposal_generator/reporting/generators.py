"""Generate dataset-level proposal reports."""

from __future__ import annotations

from collections import Counter
from typing import Any

from proposal_generator import __version__
from proposal_generator.engine.config import GeneratorConfig
from proposal_generator.models.proposal import ProposalResult, ProposalRunResult
from proposal_generator.shared.constants import STAGE_ID
from proposal_generator.shared.utils import isoformat_datetime


def build_proposal_summary(run: ProposalRunResult, config: GeneratorConfig) -> dict[str, Any]:
    return {
        "summary": {
            "id": "DATASET-PROPOSAL-SUMMARY",
            "version": "1.0.0",
            "created_at": isoformat_datetime(run.completed_at or run.started_at),
            "run_id": run.run_id,
            "stage_id": STAGE_ID,
            "engine_version": __version__,
        },
        "dataset_ref": {
            "id": config.dataset_id,
            "version": config.dataset_version,
            "doc_type": config.doc_type,
            "medallion_tier": "proposal",
        },
        "source": {
            "path": run.source_path,
            "mutability": "read_only",
        },
        "output": {
            "path": run.output_path,
        },
        "statistics": {
            "files_processed": run.files_processed,
            "successful_proposals": run.successful,
            "failed_proposals": run.failed,
            "skipped": run.skipped,
            "validation_failures": run.validation_failures,
            "runtime_failures": run.runtime_failures,
            "duration_seconds": round(run.duration_seconds, 4),
        },
        "documents": [
            {
                "document_id": result.document_id,
                "relative_path": result.relative_path,
                "artifact_id": result.artifact_id,
                "success": result.success,
                "skipped": result.skipped,
                "task": result.task,
                "provider_id": result.provider_id,
                "latency_ms": result.latency_ms,
                "validation_passed": result.validation_passed,
                "errors": result.errors,
            }
            for result in run.documents
        ],
        "config_snapshot": config.snapshot(),
    }


def build_proposal_statistics(run: ProposalRunResult) -> dict[str, Any]:
    latencies = [r.latency_ms for r in run.documents if r.success and r.latency_ms > 0]
    retries = [r.retries for r in run.documents if r.success]
    providers = Counter(r.provider_id for r in run.documents if r.success and r.provider_id)

    return {
        "statistics": {
            "id": "DATASET-PROPOSAL-STATISTICS",
            "version": "1.0.0",
            "created_at": isoformat_datetime(run.completed_at or run.started_at),
            "run_id": run.run_id,
        },
        "counts": {
            "files_processed": run.files_processed,
            "successful_proposals": run.successful,
            "failed_proposals": run.failed,
            "skipped": run.skipped,
            "validation_failures": run.validation_failures,
            "runtime_failures": run.runtime_failures,
        },
        "runtime": {
            "average_latency_ms": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
            "average_retries": round(sum(retries) / len(retries), 4) if retries else 0.0,
            "provider_distribution": dict(providers),
        },
    }


def build_proposal_errors(run: ProposalRunResult) -> dict[str, Any]:
    return {
        "errors": {
            "id": "DATASET-PROPOSAL-ERRORS",
            "version": "1.0.0",
            "created_at": isoformat_datetime(run.completed_at or run.started_at),
            "run_id": run.run_id,
            "total_failures": run.failed,
            "items": run.errors,
        }
    }


def build_proposal_log(run: ProposalRunResult) -> dict[str, Any]:
    return {
        "log": {
            "id": "DATASET-PROPOSAL-LOG",
            "version": "1.0.0",
            "created_at": isoformat_datetime(run.completed_at or run.started_at),
            "run_id": run.run_id,
            "started_at": isoformat_datetime(run.started_at),
            "completed_at": isoformat_datetime(run.completed_at) if run.completed_at else None,
            "duration_seconds": round(run.duration_seconds, 4),
            "events": [
                {
                    "document_id": result.document_id,
                    "relative_path": result.relative_path,
                    "status": (
                        "skipped"
                        if result.skipped
                        else "success"
                        if result.success
                        else "failed"
                    ),
                    "artifact_id": result.artifact_id,
                    "task": result.task,
                    "errors": result.errors,
                    "warnings": result.warnings,
                }
                for result in run.documents
            ],
        }
    }


def build_document_metadata(
    *,
    job,
    artifact_id: str,
    task_result,
    prompt_version: str,
    schema_version: str,
    runtime_version: str,
    timestamp: str,
) -> dict[str, Any]:
    return {
        "artifact": {
            "artifact_id": artifact_id,
            "artifact_type": "PROPOSAL",
            "stage_id": STAGE_ID,
            "created_at": timestamp,
            "content_path": "proposal.json",
            "dataset_id": job.dataset_id,
            "dataset_version": job.dataset_version,
            "source_document_id": job.document_id,
            "source_hash": job.source_hash,
            "lineage": {
                "silver_path": job.source_dir,
                "source_file": job.source_file,
            },
        },
        "runtime": {
            "version": runtime_version,
            "task": task_result.task,
            "prompt_id": task_result.prompt_id,
            "prompt_version": prompt_version,
            "schema_id": task_result.schema_id,
            "schema_version": schema_version,
            "provider_id": task_result.provider_id,
            "model": task_result.model,
            "latency_ms": round(task_result.latency_ms, 4),
            "attempts": task_result.attempts,
            "retries": task_result.retries,
            "fallbacks_used": task_result.fallbacks_used,
            "validation_passed": task_result.validation_passed,
            "timestamp": timestamp,
        },
    }


def build_document_report(
    *,
    job,
    artifact_id: str,
    task_result,
    warnings: list[str],
    errors: list[str],
    confidence: float | None,
) -> dict[str, Any]:
    output = task_result.output if isinstance(task_result.output, dict) else {}
    return {
        "report": {
            "id": "DOCUMENT-PROPOSAL-REPORT",
            "version": "1.0.0",
            "artifact_id": artifact_id,
            "document_id": job.document_id,
            "source_file": job.source_file,
        },
        "execution": {
            "task": task_result.task,
            "success": True,
            "latency_ms": round(task_result.latency_ms, 4),
            "attempts": task_result.attempts,
            "retries": task_result.retries,
            "fallbacks_used": task_result.fallbacks_used,
            "validation_passed": task_result.validation_passed,
        },
        "validation": {
            "passed": task_result.validation_passed,
            "errors": errors,
        },
        "warnings": warnings,
        "errors": errors,
        "confidence": confidence if confidence is not None else output.get("confidence"),
        "token_usage": task_result.token_usage,
    }
