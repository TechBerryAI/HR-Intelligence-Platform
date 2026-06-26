"""Report generation for Dataset Inspector artifacts."""

from __future__ import annotations

from typing import Any

from ..models import DirectoryNode, DuplicateGroup, FileRecord, InspectionResult, OcrSignal
from ..quality import QualityAssessment
from ..statistics import DatasetStatistics
from ..utils import aggregate_inventory_hash, isoformat_date, isoformat_datetime, tree_to_dict, utc_now


def build_manifest(
    result: InspectionResult,
    config_snapshot: dict[str, Any],
    *,
    dataset_id: str,
    dataset_version: str,
    dataset_name: str,
    doc_type: str,
    factory_version: str,
    status: str,
) -> dict[str, Any]:
    """Build dataset_manifest.yaml content."""
    created_at = isoformat_datetime(result.started_at)
    completed_at = isoformat_datetime(result.completed_at or utc_now())
    inventory_hash = aggregate_inventory_hash([f.relative_path for f in result.files])

    return {
        "manifest": {
            "id": "DATASET-MANIFEST",
            "version": "1.0.0",
            "artifact_type": "DATASET_MANIFEST",
            "created_at": created_at,
            "factory_version": factory_version,
            "run_id": result.run_id,
        },
        "dataset": {
            "id": dataset_id,
            "version": dataset_version,
            "name": dataset_name,
            "doc_type": doc_type,
            "creation_date": isoformat_date(result.started_at),
        },
        "source": {
            "path": str(result.source_path),
            "mutability": "read_only",
            "hash_of_inventory": inventory_hash,
        },
        "inspection": {
            "stage_id": "STAGE-INSPECTOR",
            "stage_version": "1.0.0",
            "completed_at": completed_at,
            "duration_seconds": round(result.duration_seconds, 3),
        },
        "status": status,
        "medallion": {
            "tier": "bronze",
            "classified_at": completed_at,
        },
        "artifacts": {
            "dataset_profile": "dataset_profile.yaml",
            "quality_report": "quality_report.yaml",
            "statistics": "statistics.yaml",
            "hash_index": "hash_index.json",
            "inspection_log": "inspection_log.yaml",
        },
        "registry": {
            "publish": False,
            "registry_path": None,
        },
    }


def build_profile(
    result: InspectionResult,
    stats: DatasetStatistics,
    *,
    dataset_id: str,
    dataset_version: str,
    dataset_name: str,
    sampling_method: str,
    sampling_rate: float,
) -> dict[str, Any]:
    """Build dataset_profile.yaml content."""
    created_at = isoformat_datetime(result.completed_at or utc_now())
    supported = sorted({f.format for f in result.files if not f.unsupported_format and f.format != "unknown"})
    unsupported = sorted({f.extension for f in result.files if f.unsupported_format})

    file_metadata = []
    ocr_signals = []
    for record in result.files:
        if record.metadata:
            file_metadata.append(
                {
                    "path": record.relative_path,
                    "format": record.format,
                    "metadata": record.metadata,
                }
            )
        if record.ocr_signal is not None:
            ocr_signals.append(
                {
                    "path": record.relative_path,
                    "signal": record.ocr_signal.value,
                }
            )

    tree = tree_to_dict(result.directory_tree) if result.directory_tree else {}

    return {
        "profile": {
            "id": "DATASET-PROFILE",
            "version": "1.0.0",
            "created_at": created_at,
            "run_id": result.run_id,
        },
        "dataset_ref": {
            "id": dataset_id,
            "version": dataset_version,
            "name": dataset_name,
            "creation_date": isoformat_date(result.started_at),
        },
        "formats": {
            "supported": supported,
            "unsupported": unsupported,
            "file_counts": stats.by_format,
        },
        "structure": {
            "directory_structure": {
                "root": str(result.source_path),
                "max_depth": result.max_depth,
                "total_directories": result.total_directories,
                "total_files": stats.files_total,
                "tree": [tree] if tree else [],
            },
            "doc_type_paths": {
                "resumes": str(result.source_path) if "resume" in str(result.source_path).lower() else None,
                "job_descriptions": None,
            },
        },
        "size": {
            "total_files": stats.files_total,
            "total_bytes": stats.total_bytes,
            "average_file_size_bytes": round(stats.average_bytes, 2),
            "largest_file": {
                "path": stats.largest_file[0],
                "size_bytes": stats.largest_file[1],
            },
            "smallest_file": {
                "path": stats.smallest_file[0],
                "size_bytes": stats.smallest_file[1],
            },
        },
        "page_estimates": {
            "total_estimated": stats.pages_total,
            "by_format": stats.pages_by_format,
            "method": "pdf_page_tree_and_docx_paragraph_estimate",
        },
        "strategies": {
            "duplicate_detection": {
                "exact": "hash_equality_via_hash_index",
                "near": "reserved_post_extractor",
            },
            "hash_strategy": {
                "algorithm": "SHA-256",
                "encoding": "hex",
                "prefix": "sha256:",
            },
            "corrupt_file_detection": {"ref": "../architecture.yaml#corrupt_file_detection"},
            "password_protected_strategy": {"ref": "../architecture.yaml#password_protected_detection"},
            "ocr_detection_strategy": {"ref": "../architecture.yaml#ocr_detection"},
            "language_detection_strategy": {"ref": "../architecture.yaml#language_detection"},
            "metadata_extraction_strategy": {"ref": "../architecture.yaml#metadata_extraction"},
            "quality_score_strategy": {"ref": "../quality_model.yaml"},
            "sampling_strategy": {"ref": "../architecture.yaml#sampling_strategy"},
        },
        "sampling": {
            "method": sampling_method,
            "rate": sampling_rate,
            "selected_files": result.selected_sample_files,
        },
        "file_metadata": file_metadata,
        "ocr_signals": ocr_signals,
        "medallion": {
            "tier": "bronze",
            "classification": "Raw corpus — bronze tier until extraction and validation complete.",
        },
    }


def build_hash_index(
    result: InspectionResult,
    duplicate_groups: list[DuplicateGroup],
    hash_entries: list[dict[str, Any]],
    *,
    dataset_id: str,
    dataset_version: str,
) -> dict[str, Any]:
    """Build hash_index.json content."""
    created_at = isoformat_datetime(result.completed_at or utc_now())
    return {
        "index": {
            "id": "HASH-INDEX",
            "version": "1.0.0",
            "algorithm": "SHA-256",
            "encoding": "hex",
            "prefix": "sha256:",
            "created_at": created_at,
            "run_id": result.run_id,
        },
        "dataset_ref": {
            "id": dataset_id,
            "version": dataset_version,
        },
        "entries": hash_entries,
        "duplicate_groups": [
            {
                "sha256": group.sha256,
                "paths": group.paths,
                "count": group.count,
            }
            for group in duplicate_groups
        ],
    }


def build_inspection_log(
    result: InspectionResult,
    config_snapshot: dict[str, Any],
    *,
    dataset_id: str,
    dataset_version: str,
    factory_version: str,
    artifacts_written: list[str],
) -> dict[str, Any]:
    """Build inspection_log.yaml content."""
    completed_at = result.completed_at or utc_now()
    run_status = "success"
    if result.errors > 0 and len(result.files) > 0:
        run_status = "partial"
    elif result.errors > 0 and not result.files:
        run_status = "failed"

    return {
        "log": {
            "id": "INSPECTION-LOG",
            "version": "1.0.0",
        },
        "run": {
            "run_id": result.run_id,
            "stage_id": "STAGE-INSPECTOR",
            "stage_version": "1.0.0",
            "factory_version": factory_version,
            "dataset_id": dataset_id,
            "dataset_version": dataset_version,
            "source_path": str(result.source_path),
            "output_path": str(result.output_path),
            "started_at": isoformat_datetime(result.started_at),
            "completed_at": isoformat_datetime(completed_at),
            "status": run_status,
            "source_mutated": False,
        },
        "config_snapshot": config_snapshot,
        "phases": [
            {
                "phase_id": phase.phase_id,
                "started_at": isoformat_datetime(phase.started_at) if phase.started_at else None,
                "completed_at": isoformat_datetime(phase.completed_at) if phase.completed_at else None,
                "status": phase.status.value,
            }
            for phase in result.phases
        ],
        "events": [
            {
                "timestamp": isoformat_datetime(event.timestamp),
                "level": event.level,
                "phase_id": event.phase_id,
                "code": event.code,
                "path": event.path,
                "message": event.message,
                "details": event.details,
            }
            for event in result.events
        ],
        "summary": {
            "files_scanned": len(result.files),
            "files_hashed": sum(1 for f in result.files if f.sha256),
            "files_skipped": result.files_skipped,
            "errors": result.errors,
            "warnings": result.warnings,
            "artifacts_written": artifacts_written,
        },
    }
