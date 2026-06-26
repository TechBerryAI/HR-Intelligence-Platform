"""Aggregate statistics from inspection results."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from .models import DuplicateGroup, FileRecord, OcrSignal
from .utils import median, percentile


@dataclass
class DatasetStatistics:
    """Computed dataset statistics."""

    files_total: int
    by_format: dict[str, int]
    by_extension: dict[str, int]
    by_doc_type: dict[str, int]
    total_bytes: int
    average_bytes: float
    median_bytes: float | None
    min_bytes: int
    max_bytes: int
    percentiles: dict[str, float | None]
    pages_total: int
    pages_average: float
    pages_by_format: dict[str, int]
    duplicate_groups: int
    duplicate_files: int
    unique_files: int
    issues: dict[str, int]
    ocr_counts: dict[str, int]
    largest_file: tuple[str, int]
    smallest_file: tuple[str, int]


def compute_statistics(
    files: list[FileRecord],
    duplicate_groups: list[DuplicateGroup],
    doc_type: str,
) -> DatasetStatistics:
    """Compute aggregate statistics from file records."""
    sizes = [f.size_bytes for f in files]
    total_bytes = sum(sizes)
    files_total = len(files)

    by_format: Counter[str] = Counter()
    by_extension: Counter[str] = Counter()
    pages_by_format: Counter[str] = Counter()
    pages_total = 0

    issues = {
        "corrupt": 0,
        "password_protected": 0,
        "zero_byte": 0,
        "unsupported_format": 0,
        "read_errors": 0,
    }
    ocr_counts = {
        "ocr_required": 0,
        "ocr_recommended": 0,
        "text_layer_ok": 0,
    }

    largest = ("", -1)
    smallest = ("", sizes[0] if sizes else 0)

    for record in files:
        fmt = record.format if record.format != "unknown" else "unknown"
        by_format[fmt] += 1
        ext = record.extension or "none"
        by_extension[ext] += 1

        if record.page_count is not None:
            pages_total += record.page_count
            pages_by_format[record.format] += record.page_count

        if record.corrupt:
            issues["corrupt"] += 1
        if record.password_protected:
            issues["password_protected"] += 1
        if record.zero_byte:
            issues["zero_byte"] += 1
        if record.unsupported_format:
            issues["unsupported_format"] += 1
        if record.read_error or record.hash_error:
            issues["read_errors"] += 1

        if record.ocr_signal == OcrSignal.OCR_REQUIRED:
            ocr_counts["ocr_required"] += 1
        elif record.ocr_signal == OcrSignal.OCR_RECOMMENDED:
            ocr_counts["ocr_recommended"] += 1
        elif record.ocr_signal == OcrSignal.TEXT_LAYER_OK:
            ocr_counts["text_layer_ok"] += 1

        if record.size_bytes > largest[1]:
            largest = (record.relative_path, record.size_bytes)
        if record.size_bytes >= 0 and (smallest[1] < 0 or record.size_bytes < smallest[1]):
            smallest = (record.relative_path, record.size_bytes)

    duplicate_files = sum(group.count - 1 for group in duplicate_groups)
    unique_files = files_total - duplicate_files

    return DatasetStatistics(
        files_total=files_total,
        by_format=dict(sorted(by_format.items())),
        by_extension=dict(sorted(by_extension.items())),
        by_doc_type={doc_type: files_total},
        total_bytes=total_bytes,
        average_bytes=total_bytes / files_total if files_total else 0.0,
        median_bytes=median(sizes),
        min_bytes=min(sizes) if sizes else 0,
        max_bytes=max(sizes) if sizes else 0,
        percentiles={
            "p50": percentile(sizes, 0.5),
            "p90": percentile(sizes, 0.9),
            "p99": percentile(sizes, 0.99),
        },
        pages_total=pages_total,
        pages_average=pages_total / files_total if files_total else 0.0,
        pages_by_format=dict(sorted(pages_by_format.items())),
        duplicate_groups=len(duplicate_groups),
        duplicate_files=duplicate_files,
        unique_files=unique_files,
        issues=issues,
        ocr_counts=ocr_counts,
        largest_file=largest,
        smallest_file=smallest,
    )


def statistics_to_dict(stats: DatasetStatistics, *, run_id: str, dataset_id: str, dataset_version: str, created_at: str) -> dict[str, Any]:
    """Serialize statistics to schema-compatible dictionary."""
    return {
        "statistics": {
            "id": "DATASET-STATISTICS",
            "version": "1.0.0",
            "created_at": created_at,
            "run_id": run_id,
        },
        "dataset_ref": {
            "id": dataset_id,
            "version": dataset_version,
        },
        "files": {
            "total": stats.files_total,
            "by_format": stats.by_format,
            "by_doc_type": stats.by_doc_type,
            "by_extension": stats.by_extension,
        },
        "size": {
            "total_bytes": stats.total_bytes,
            "average_bytes": round(stats.average_bytes, 2),
            "median_bytes": stats.median_bytes,
            "min_bytes": stats.min_bytes,
            "max_bytes": stats.max_bytes,
            "percentiles": stats.percentiles,
        },
        "pages": {
            "total_estimated": stats.pages_total,
            "average_per_file": round(stats.pages_average, 2),
            "by_format": stats.pages_by_format,
        },
        "duplicates": {
            "exact_groups": stats.duplicate_groups,
            "duplicate_files": stats.duplicate_files,
            "unique_files": stats.unique_files,
        },
        "issues": stats.issues,
        "languages": {
            "primary": None,
            "distribution": {},
        },
        "ocr": stats.ocr_counts,
    }
