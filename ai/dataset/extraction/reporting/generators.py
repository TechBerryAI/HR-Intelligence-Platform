"""Per-document and dataset reporting."""

from __future__ import annotations

from typing import Any

from dataset.extraction.models import ExtractionResult, ExtractionRunResult
from dataset.extraction.shared.constants import ENGINE_VERSION, FACTORY_VERSION, STAGE_ID, STAGE_VERSION
from dataset.extraction.shared.utils import artifact_id, isoformat_datetime, slugify_filename


def build_document_metadata(
    result: ExtractionResult,
    *,
    run_id: str,
    dataset_id: str,
    dataset_version: str,
    doc_type: str,
    created_at: str,
) -> dict[str, Any]:
    return {
        "artifact": {
            "artifact_id": artifact_id("EXTR", result.source_hash or "sha256:unknown"),
            "artifact_type": "EXTRACTED_RECORD",
            "stage_id": STAGE_ID,
            "created_at": created_at,
            "content_path": "raw_text.txt",
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "sha256": result.source_hash,
            "lineage": {
                "factory_version": FACTORY_VERSION,
                "run_id": run_id,
                "upstream_stage": "STAGE-INSPECTOR",
            },
        },
        "document": {
            "source_file": result.relative_path,
            "source_filename": slugify_filename(result.relative_path.rsplit("/", 1)[-1]),
            "source_path": result.source_path,
            "doc_type": doc_type,
            "format": result.format,
            "source_hash": result.source_hash,
        },
        "extraction": {
            "engine_version": ENGINE_VERSION,
            "stage_version": STAGE_VERSION,
            "method": result.method,
            "success": result.quality.extraction_success,
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
            "duration_seconds": round(result.duration_seconds, 4),
        },
        "metadata": result.metadata,
        "document_properties": result.document_properties,
    }


def build_extraction_report(result: ExtractionResult, *, run_id: str, created_at: str) -> dict[str, Any]:
    return {
        "report": {
            "id": "DOCUMENT-EXTRACTION-REPORT",
            "version": "1.0.0",
            "created_at": created_at,
            "run_id": run_id,
        },
        "document": {
            "source_file": result.relative_path,
            "format": result.format,
            "source_hash": result.source_hash,
        },
        "quality": {
            "characters_extracted": result.quality.characters_extracted,
            "words_extracted": result.quality.words_extracted,
            "pages": result.quality.pages,
            "average_words_per_page": result.quality.average_words_per_page,
            "extraction_success": result.quality.extraction_success,
            "requires_ocr": result.quality.requires_ocr,
            "encoding_issues": result.quality.encoding_issues,
            "empty_pages": result.quality.empty_pages,
            "whitespace_ratio": result.quality.whitespace_ratio,
        },
        "page_statistics": [
            {
                "page_number": page.page_number,
                "char_count": page.char_count,
                "word_count": page.word_count,
                "empty": page.empty,
            }
            for page in result.page_stats
        ],
        "warnings": result.warnings,
        "errors": result.errors,
        "processing": {
            "method": result.method,
            "duration_seconds": round(result.duration_seconds, 4),
            "skipped": result.skipped,
            "skip_reason": result.skip_reason,
        },
    }


def build_dataset_summary(
    run: ExtractionRunResult,
    *,
    dataset_id: str,
    dataset_version: str,
    doc_type: str,
    config_snapshot: dict[str, Any],
) -> dict[str, Any]:
    created_at = isoformat_datetime(run.completed_at or run.started_at)
    by_format: dict[str, int] = {}
    for doc in run.documents:
        by_format[doc.format] = by_format.get(doc.format, 0) + 1

    return {
        "summary": {
            "id": "DATASET-EXTRACTION-SUMMARY",
            "version": "1.0.0",
            "created_at": created_at,
            "run_id": run.run_id,
            "stage_id": STAGE_ID,
            "engine_version": ENGINE_VERSION,
        },
        "dataset_ref": {
            "id": dataset_id,
            "version": dataset_version,
            "doc_type": doc_type,
            "medallion_tier": "silver",
        },
        "source": {
            "path": run.source_path,
            "inspection_path": run.inspection_path,
            "mutability": "read_only",
        },
        "statistics": {
            "files_processed": run.files_processed,
            "successful_extractions": run.successful,
            "failed_extractions": run.failed,
            "skipped": run.skipped,
            "ocr_candidates": run.ocr_candidates,
            "by_format": dict(sorted(by_format.items())),
            "duration_seconds": round(run.duration_seconds, 3),
            "average_seconds_per_file": round(
                run.duration_seconds / run.files_processed, 3
            )
            if run.files_processed
            else 0.0,
        },
        "documents": [
            {
                "source_file": doc.relative_path,
                "source_hash": doc.source_hash,
                "format": doc.format,
                "success": doc.quality.extraction_success,
                "requires_ocr": doc.quality.requires_ocr,
                "characters_extracted": doc.quality.characters_extracted,
                "words_extracted": doc.quality.words_extracted,
                "skipped": doc.skipped,
                "errors": doc.errors,
            }
            for doc in run.documents
        ],
        "errors": run.errors,
        "warnings": run.warnings,
        "config_snapshot": config_snapshot,
    }


def build_extraction_log(run: ExtractionRunResult, *, dataset_id: str, dataset_version: str) -> dict[str, Any]:
    return {
        "log": {
            "id": "EXTRACTION-LOG",
            "version": "1.0.0",
        },
        "run": {
            "run_id": run.run_id,
            "stage_id": STAGE_ID,
            "stage_version": STAGE_VERSION,
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "source_path": run.source_path,
            "output_path": run.output_path,
            "started_at": isoformat_datetime(run.started_at),
            "completed_at": isoformat_datetime(run.completed_at or run.started_at),
            "duration_seconds": round(run.duration_seconds, 3),
            "source_mutated": False,
        },
        "summary": {
            "files_processed": run.files_processed,
            "successful": run.successful,
            "failed": run.failed,
            "skipped": run.skipped,
            "ocr_candidates": run.ocr_candidates,
        },
    }
