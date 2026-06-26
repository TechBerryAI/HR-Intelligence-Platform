"""Tests for duplicate detection."""

from dataset_factory.inspector.duplicates import detect_filename_duplicates, detect_hash_duplicates
from dataset_factory.inspector.models import FileRecord, FileTimestamps


def _record(path: str, sha256: str | None) -> FileRecord:
    return FileRecord(
        relative_path=path,
        absolute_path=f"/data/{path}",
        extension=path.rsplit(".", 1)[-1],
        format="pdf",
        size_bytes=100,
        timestamps=FileTimestamps(),
        sha256=sha256,
    )


def test_detect_hash_duplicates_groups_exact_matches() -> None:
    files = [
        _record("a.pdf", "sha256:" + "a" * 64),
        _record("b.pdf", "sha256:" + "a" * 64),
        _record("c.pdf", "sha256:" + "b" * 64),
    ]

    groups, entries = detect_hash_duplicates(files)

    assert len(groups) == 1
    assert groups[0].count == 2
    assert len(entries) == 3
    duplicate_entries = [entry for entry in entries if entry["duplicate_of"]]
    assert len(duplicate_entries) == 1
    assert duplicate_entries[0]["duplicate_of"] == "a.pdf"


def test_detect_filename_duplicates() -> None:
    files = [
        _record("dir1/resume.pdf", "sha256:" + "1" * 64),
        _record("dir2/resume.pdf", "sha256:" + "2" * 64),
        _record("unique.pdf", "sha256:" + "3" * 64),
    ]

    groups = detect_filename_duplicates(files)

    assert len(groups) == 1
    assert groups[0].filename == "resume.pdf"
    assert groups[0].count == 2
