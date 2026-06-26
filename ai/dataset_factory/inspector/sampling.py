"""Deterministic sampling for human spot-checks."""

from __future__ import annotations

import hashlib

from .models import FileRecord


def select_sample_files(
    files: list[FileRecord],
    *,
    rate: float,
    min_samples: int,
    max_samples: int,
) -> tuple[list[str], str]:
    """
    Select a deterministic stratified sample by format using hash buckets.

    Returns:
        (selected_relative_paths, method_name)
    """
    if not files:
        return [], "stratified_by_format_hash_bucket"

    target = int(len(files) * rate)
    target = max(min_samples, target)
    target = min(max_samples, target, len(files))

    by_format: dict[str, list[FileRecord]] = {}
    for record in files:
        by_format.setdefault(record.format, []).append(record)

    selected: list[str] = []
    formats = sorted(by_format.keys())
    per_format = max(1, target // max(len(formats), 1))

    for fmt in formats:
        candidates = sorted(by_format[fmt], key=lambda r: r.relative_path)
        scored = sorted(
            candidates,
            key=lambda r: int(hashlib.sha256(r.relative_path.encode()).hexdigest(), 16),
        )
        selected.extend(record.relative_path for record in scored[:per_format])

    selected = sorted(set(selected))[:target]
    return selected, "stratified_by_format_hash_bucket"
