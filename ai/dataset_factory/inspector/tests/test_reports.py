"""Tests for quality and profile report generation."""

from datetime import datetime, timezone

from dataset_factory.inspector.models import FileRecord, FileTimestamps, InspectionResult
from dataset_factory.inspector.quality import assess_quality, quality_to_dict
from dataset_factory.inspector.reporting.generators import build_profile
from dataset_factory.inspector.statistics import compute_statistics


def _record(path: str, fmt: str = "pdf", corrupt: bool = False) -> FileRecord:
    return FileRecord(
        relative_path=path,
        absolute_path=f"/data/{path}",
        extension=fmt,
        format=fmt,
        size_bytes=1024,
        timestamps=FileTimestamps(),
        sha256=f"sha256:{path.encode().hex().ljust(64, '0')[:64]}",
        metadata_available=True,
        page_count=1,
        corrupt=corrupt,
    )


def test_assess_quality_computes_overall_grade() -> None:
    files = [_record("a.pdf"), _record("b.pdf")]
    stats = compute_statistics(files, [], doc_type="resume")
    assessment = assess_quality(files, stats, [], [])

    assert assessment.overall_score is not None
    assert assessment.overall_grade in {"A", "B", "C", "D", "F"}
    assert assessment.gates["extraction_ready"] is not None


def test_quality_to_dict_marks_computation_status_computed() -> None:
    files = [_record("a.pdf")]
    stats = compute_statistics(files, [], doc_type="resume")
    assessment = assess_quality(files, stats, [], [])

    payload = quality_to_dict(
        assessment,
        run_id="11111111-1111-1111-1111-111111111111",
        dataset_id="DS-RESUMES-RAW",
        dataset_version="1.0.0",
        created_at="2026-06-26T00:00:00Z",
    )

    assert payload["report"]["computation_status"] == "computed"
    assert payload["categories"]["integrity"]["score"] is not None
    assert payload["categories"]["language_consistency"]["score"] is None


def test_build_profile_includes_size_and_formats() -> None:
    started = datetime(2026, 6, 26, tzinfo=timezone.utc)
    files = [_record("a.pdf"), _record("b.docx", fmt="docx")]
    stats = compute_statistics(files, [], doc_type="resume")
    result = InspectionResult(
        run_id="11111111-1111-1111-1111-111111111111",
        started_at=started,
        completed_at=started,
        source_path="/data/resumes",
        output_path="/data/inspection",
        files=files,
    )

    profile = build_profile(
        result,
        stats,
        dataset_id="DS-RESUMES-RAW",
        dataset_version="1.0.0",
        dataset_name="Raw Resume Corpus",
        sampling_method="stratified_by_format_hash_bucket",
        sampling_rate=0.05,
    )

    assert profile["profile"]["id"] == "DATASET-PROFILE"
    assert profile["size"]["total_files"] == 2
    assert "pdf" in profile["formats"]["supported"]
