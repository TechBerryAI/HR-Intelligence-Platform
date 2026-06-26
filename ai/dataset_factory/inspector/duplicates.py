"""Duplicate detection from content hashes and filenames."""

from __future__ import annotations

from collections import defaultdict

from .models import DuplicateGroup, FileRecord, FilenameDuplicateGroup


def detect_hash_duplicates(files: list[FileRecord]) -> tuple[list[DuplicateGroup], list[dict]]:
    """
    Detect exact duplicates by SHA-256 hash.

    Returns:
        (duplicate_groups, hash_index_entries)
    """
    hash_to_paths: defaultdict[str, list[str]] = defaultdict(list)
    hash_index_entries: list[dict] = []

    for record in files:
        if not record.sha256:
            continue
        hash_to_paths[record.sha256].append(record.relative_path)

    first_seen: dict[str, str] = {}
    duplicate_groups: list[DuplicateGroup] = []

    for record in sorted(files, key=lambda r: r.relative_path):
        if not record.sha256:
            continue

        entry: dict = {
            "path": record.relative_path,
            "sha256": record.sha256,
            "size_bytes": record.size_bytes,
            "format": record.format if record.format != "unknown" else None,
            "duplicate_of": None,
        }

        if record.sha256 in first_seen and first_seen[record.sha256] != record.relative_path:
            entry["duplicate_of"] = first_seen[record.sha256]
        else:
            first_seen.setdefault(record.sha256, record.relative_path)

        hash_index_entries.append(entry)

    for sha256, paths in sorted(hash_to_paths.items()):
        if len(paths) > 1:
            sorted_paths = sorted(paths)
            duplicate_groups.append(
                DuplicateGroup(sha256=sha256, paths=sorted_paths, count=len(sorted_paths))
            )

    return duplicate_groups, hash_index_entries


def detect_filename_duplicates(files: list[FileRecord]) -> list[FilenameDuplicateGroup]:
    """Detect files that share the same basename."""
    name_to_paths: defaultdict[str, list[str]] = defaultdict(list)

    for record in files:
        filename = record.relative_path.rsplit("/", 1)[-1]
        name_to_paths[filename].append(record.relative_path)

    groups: list[FilenameDuplicateGroup] = []
    for filename, paths in sorted(name_to_paths.items()):
        if len(paths) > 1:
            groups.append(
                FilenameDuplicateGroup(
                    filename=filename,
                    paths=sorted(paths),
                    count=len(paths),
                )
            )
    return groups
