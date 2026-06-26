"""Tests for statistics generation."""

from dataset_factory.inspector.models import DuplicateGroup, FileRecord, FileTimestamps
from dataset_factory.inspector.statistics import compute_statistics, statistics_to_dict


def _record(path: str, size: int, fmt: str = "pdf") -> FileRecord:
    return FileRecord(
        relative_path=path,
        absolute_path=f"/data/{path}",
        extension=fmt,
        format=fmt,
        size_bytes=size,
        timestamps=FileTimestamps(),
        sha256=f"sha256:{'a' * 64}",
        page_count=2,
    )


def test_compute_statistics_aggregates_sizes_and_counts() -> None:
    files = [
        _record("a.pdf", 100),
        _record("b.pdf", 300),
        _record("c.docx", 200, fmt="docx"),
    ]
    duplicate_groups = [
        DuplicateGroup(sha256="sha256:" + "a" * 64, paths=["a.pdf", "x.pdf"], count=2),
    ]

    stats = compute_statistics(files, duplicate_groups, doc_type="resume")

    assert stats.files_total == 3
    assert stats.total_bytes == 600
    assert stats.by_format["pdf"] == 2
    assert stats.by_format["docx"] == 1
    assert stats.pages_total == 6
    assert stats.duplicate_groups == 1


def test_statistics_to_dict_matches_schema_shape() -> None:
    files = [_record("a.pdf", 100)]
    stats = compute_statistics(files, [], doc_type="resume")

    payload = statistics_to_dict(
        stats,
        run_id="11111111-1111-1111-1111-111111111111",
        dataset_id="DS-RESUMES-RAW",
        dataset_version="1.0.0",
        created_at="2026-06-26T00:00:00Z",
    )

    assert payload["statistics"]["id"] == "DATASET-STATISTICS"
    assert payload["files"]["total"] == 1
    assert "size" in payload
    assert "duplicates" in payload
