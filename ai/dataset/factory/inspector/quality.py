"""Quality scoring based on quality_model.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .models import DuplicateGroup, FileRecord, FilenameDuplicateGroup, OcrSignal
from .statistics import DatasetStatistics

CATEGORY_WEIGHTS = {
    "integrity": 0.20,
    "extractability": 0.20,
    "ocr_readiness": 0.15,
    "formatting_quality": 0.10,
    "metadata_quality": 0.10,
    "duplication_risk": 0.15,
    "language_consistency": 0.10,
}

GRADE_BANDS = [
    ("A", 90, 100, "production_ready"),
    ("B", 75, 89, "acceptable_with_monitoring"),
    ("C", 60, 74, "requires_remediation"),
    ("D", 40, 59, "extraction_not_recommended"),
    ("F", 0, 39, "reject"),
]


@dataclass
class CategoryScore:
    score: float | None
    weight: float
    signals: dict[str, Any]
    downgrade_triggers_fired: list[str]


@dataclass
class QualityAssessment:
    categories: dict[str, CategoryScore]
    overall_score: float | None
    overall_grade: str | None
    overall_label: str | None
    gates: dict[str, bool | None]
    findings: list[dict[str, Any]]


def _ratio(numerator: int, denominator: int) -> float:
    if denominator == 0:
        return 0.0
    return numerator / denominator


def assess_quality(
    files: list[FileRecord],
    stats: DatasetStatistics,
    duplicate_groups: list[DuplicateGroup],
    filename_duplicates: list[FilenameDuplicateGroup],
) -> QualityAssessment:
    """Compute quality scores and gates from inspection signals."""
    total = stats.files_total or 1
    findings: list[dict[str, Any]] = []

    supported_formats = {"pdf", "docx", "doc", "txt", "rtf", "zip"}
    supported_count = sum(
        1 for f in files if f.format in supported_formats and not f.unsupported_format
    )

    integrity_signals = {
        "zero_byte_files_ratio": round(_ratio(stats.issues["zero_byte"], total), 4),
        "corrupt_files_ratio": round(_ratio(stats.issues["corrupt"], total), 4),
        "read_error_count": stats.issues["read_errors"],
        "unsupported_format_ratio": round(_ratio(stats.issues["unsupported_format"], total), 4),
    }
    integrity_score = max(
        0.0,
        1.0
        - integrity_signals["zero_byte_files_ratio"]
        - integrity_signals["corrupt_files_ratio"]
        - min(1.0, integrity_signals["read_error_count"] / total)
        - integrity_signals["unsupported_format_ratio"] * 0.5,
    )
    integrity_triggers: list[str] = []
    if integrity_signals["corrupt_files_ratio"] > 0.05:
        integrity_triggers.append("corrupt_files_ratio_gt")
    if integrity_signals["read_error_count"] > 0:
        integrity_triggers.append("read_error_count_gt")

    extractability_signals = {
        "password_protected_ratio": round(_ratio(stats.issues["password_protected"], total), 4),
        "supported_format_ratio": round(_ratio(supported_count, total), 4),
        "corrupt_files_ratio": integrity_signals["corrupt_files_ratio"],
        "zip_nested_depth_violations": 0,
    }
    extractability_score = max(
        0.0,
        extractability_signals["supported_format_ratio"]
        * (1.0 - extractability_signals["password_protected_ratio"])
        * (1.0 - extractability_signals["corrupt_files_ratio"]),
    )
    extractability_triggers: list[str] = []
    if extractability_signals["password_protected_ratio"] > 0.10:
        extractability_triggers.append("password_protected_ratio_gt")

    pdf_files = [f for f in files if f.format == "pdf"]
    pdf_total = len(pdf_files) or 1
    ocr_signals = {
        "ocr_required_ratio": round(_ratio(stats.ocr_counts["ocr_required"], pdf_total), 4),
        "ocr_recommended_ratio": round(_ratio(stats.ocr_counts["ocr_recommended"], pdf_total), 4),
        "text_layer_present_ratio": round(_ratio(stats.ocr_counts["text_layer_ok"], pdf_total), 4),
    }
    if pdf_files:
        ocr_readiness_score = max(
            0.0,
            ocr_signals["text_layer_present_ratio"]
            + ocr_signals["ocr_recommended_ratio"] * 0.5
            - ocr_signals["ocr_required_ratio"],
        )
    else:
        ocr_readiness_score = None
        ocr_signals["note"] = "No PDF files present; OCR readiness not applicable."
    ocr_triggers: list[str] = []
    if pdf_files and ocr_signals.get("ocr_required_ratio", 0) > 0.30:
        ocr_triggers.append("ocr_required_ratio_gt")

    txt_files = [f for f in files if f.format == "txt"]
    formatting_signals = {
        "encoding_error_ratio": round(_ratio(sum(1 for f in txt_files if f.encoding_error), len(txt_files) or 1), 4),
        "mixed_line_endings_ratio": round(
            _ratio(sum(1 for f in txt_files if f.mixed_line_endings), len(txt_files) or 1), 4
        ),
        "avg_file_size_bytes": round(stats.average_bytes, 2),
    }
    formatting_score = max(
        0.0,
        1.0
        - formatting_signals["encoding_error_ratio"]
        - formatting_signals["mixed_line_endings_ratio"] * 0.5,
    )

    metadata_present = sum(1 for f in files if f.metadata_available)
    page_count_available = sum(1 for f in files if f.page_count is not None)
    metadata_signals = {
        "metadata_present_ratio": round(_ratio(metadata_present, total), 4),
        "page_count_available_ratio": round(_ratio(page_count_available, total), 4),
        "doc_type_path_consistency": 1.0,
    }
    metadata_score = (
        metadata_signals["metadata_present_ratio"] * 0.5
        + metadata_signals["page_count_available_ratio"] * 0.5
    )

    duplicate_ratio = _ratio(stats.duplicate_files, total)
    largest_group = max((g.count for g in duplicate_groups), default=0)
    duplication_signals = {
        "exact_duplicate_groups_count": stats.duplicate_groups,
        "exact_duplicate_files_ratio": round(duplicate_ratio, 4),
        "largest_duplicate_group_size": largest_group,
        "near_duplicate_ratio": None,
        "duplicate_filename_groups": len(filename_duplicates),
    }
    duplication_score = max(0.0, 1.0 - duplicate_ratio)
    duplication_triggers: list[str] = []
    if duplicate_ratio > 0.15:
        duplication_triggers.append("exact_duplicate_files_ratio_gt")

    language_signals = {
        "reason": "Language detection reserved per architecture.yaml; not implemented in v1.",
        "primary_language_confidence": None,
        "language_entropy": None,
        "unexpected_language_ratio": None,
    }
    language_score: float | None = None

    categories = {
        "integrity": CategoryScore(integrity_score, CATEGORY_WEIGHTS["integrity"], integrity_signals, integrity_triggers),
        "extractability": CategoryScore(
            extractability_score, CATEGORY_WEIGHTS["extractability"], extractability_signals, extractability_triggers
        ),
        "ocr_readiness": CategoryScore(
            ocr_readiness_score, CATEGORY_WEIGHTS["ocr_readiness"], ocr_signals, ocr_triggers
        ),
        "formatting_quality": CategoryScore(
            formatting_score, CATEGORY_WEIGHTS["formatting_quality"], formatting_signals, []
        ),
        "metadata_quality": CategoryScore(
            metadata_score, CATEGORY_WEIGHTS["metadata_quality"], metadata_signals, []
        ),
        "duplication_risk": CategoryScore(
            duplication_score, CATEGORY_WEIGHTS["duplication_risk"], duplication_signals, duplication_triggers
        ),
        "language_consistency": CategoryScore(
            language_score, CATEGORY_WEIGHTS["language_consistency"], language_signals, []
        ),
    }

    scored = [(name, cat) for name, cat in categories.items() if cat.score is not None]
    if scored:
        weight_sum = sum(cat.weight for _, cat in scored)
        overall_score = sum(cat.score * cat.weight for _, cat in scored) / weight_sum * 100.0
    else:
        overall_score = None

    overall_grade: str | None = None
    overall_label: str | None = None
    if overall_score is not None:
        for grade, min_score, max_score, label in GRADE_BANDS:
            if min_score <= overall_score <= max_score:
                overall_grade = grade
                overall_label = label
                break

    integrity_val = categories["integrity"].score or 0.0
    duplication_val = categories["duplication_risk"].score or 0.0

    gates: dict[str, bool | None] = {
        "extraction_ready": None,
        "manual_review_required": None,
        "block_extraction": None,
    }
    if overall_grade is not None:
        gates["extraction_ready"] = overall_grade in {"A", "B", "C"} and integrity_val >= 0.80
        gates["manual_review_required"] = overall_grade in {"C", "D"} or duplication_val < 0.70
        gates["block_extraction"] = overall_grade == "F" or integrity_val < 0.50

    for record in files:
        if record.corrupt:
            findings.append(
                {
                    "code": "CORRUPT_FILE",
                    "severity": "error",
                    "category": "integrity",
                    "path": record.relative_path,
                    "message": record.pdf_analysis.error if record.pdf_analysis and record.pdf_analysis.error else "File failed structural parse probe.",
                }
            )
        if record.password_protected:
            findings.append(
                {
                    "code": "PASSWORD_PROTECTED",
                    "severity": "warning",
                    "category": "extractability",
                    "path": record.relative_path,
                    "message": "File is encrypted or password protected.",
                }
            )
        if record.unsupported_format:
            findings.append(
                {
                    "code": "UNSUPPORTED_FORMAT",
                    "severity": "info",
                    "category": "integrity",
                    "path": record.relative_path,
                    "message": f"Unsupported format detected (extension .{record.extension}).",
                }
            )
        if record.ocr_signal == OcrSignal.OCR_REQUIRED:
            findings.append(
                {
                    "code": "OCR_REQUIRED",
                    "severity": "warning",
                    "category": "ocr_readiness",
                    "path": record.relative_path,
                    "message": "PDF appears scanned with no text layer.",
                }
            )

    for group in duplicate_groups:
        findings.append(
            {
                "code": "EXACT_DUPLICATE_GROUP",
                "severity": "warning",
                "category": "duplication_risk",
                "path": group.paths[0],
                "message": f"Exact duplicate group of {group.count} files sharing hash {group.sha256}.",
            }
        )

    for group in filename_duplicates:
        findings.append(
            {
                "code": "DUPLICATE_FILENAME",
                "severity": "info",
                "category": "duplication_risk",
                "path": group.paths[0],
                "message": f"Filename '{group.filename}' appears {group.count} times.",
            }
        )

    return QualityAssessment(
        categories=categories,
        overall_score=round(overall_score, 2) if overall_score is not None else None,
        overall_grade=overall_grade,
        overall_label=overall_label,
        gates=gates,
        findings=findings,
    )


def quality_to_dict(assessment: QualityAssessment, *, run_id: str, dataset_id: str, dataset_version: str, created_at: str) -> dict[str, Any]:
    """Serialize quality assessment to schema-compatible dictionary."""
    categories_payload = {}
    for name, cat in assessment.categories.items():
        categories_payload[name] = {
            "score": round(cat.score, 4) if cat.score is not None else None,
            "weight": cat.weight,
            "signals": cat.signals,
            "downgrade_triggers_fired": cat.downgrade_triggers_fired,
        }

    return {
        "report": {
            "id": "QUALITY-REPORT",
            "version": "1.0.0",
            "created_at": created_at,
            "run_id": run_id,
            "model_ref": "../quality_model.yaml",
            "computation_status": "computed",
        },
        "dataset_ref": {
            "id": dataset_id,
            "version": dataset_version,
        },
        "categories": categories_payload,
        "overall": {
            "score": assessment.overall_score,
            "grade": assessment.overall_grade,
            "label": assessment.overall_label,
        },
        "gates": assessment.gates,
        "findings": assessment.findings,
    }
