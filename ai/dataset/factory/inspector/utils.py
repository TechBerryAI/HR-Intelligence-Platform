"""Shared utilities for Dataset Inspector."""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> datetime:
    """Return current UTC datetime."""
    return datetime.now(timezone.utc)


def isoformat_datetime(value: datetime) -> str:
    """Format datetime as ISO-8601 with Z suffix."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def isoformat_date(value: datetime) -> str:
    """Format datetime as ISO date."""
    return value.date().isoformat()


def relative_path(path: Path, root: Path) -> str:
    """Return POSIX-style path relative to root."""
    return path.relative_to(root).as_posix()


def safe_stat_timestamps(path: Path) -> tuple[datetime | None, datetime | None]:
    """Read creation and modification timestamps when available."""
    try:
        stat = path.stat()
    except OSError:
        return None, None

    modified_at = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
    created_at: datetime | None
    try:
        created_at = datetime.fromtimestamp(stat.st_birthtime, tz=timezone.utc)
    except AttributeError:
        created_at = datetime.fromtimestamp(stat.st_ctime, tz=timezone.utc)
    return created_at, modified_at


def percentile(values: list[int], pct: float) -> float | None:
    """Compute percentile from sorted integer values."""
    if not values:
        return None
    if len(values) == 1:
        return float(values[0])

    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = int(rank)
    upper = min(lower + 1, len(ordered) - 1)
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight


def median(values: list[int]) -> float | None:
    """Compute median from integer values."""
    return percentile(values, 0.5)


def aggregate_inventory_hash(paths: list[str]) -> str:
    """Compute deterministic aggregate hash over sorted relative paths."""
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.encode("utf-8"))
        digest.update(b"\n")
    return f"sha256:{digest.hexdigest()}"


def tree_to_dict(node: Any) -> dict[str, Any]:
    """Serialize a DirectoryNode to a nested dictionary."""
    payload: dict[str, Any] = {
        "name": node.name,
        "path": node.path,
        "type": node.type,
        "depth": node.depth,
    }
    if node.type == "directory":
        payload["file_count"] = node.file_count
        payload["children"] = [tree_to_dict(child) for child in node.children]
    return payload


def yaml_dump(data: Any) -> str:
    """Dump data to YAML with stable formatting."""
    import yaml

    return yaml.dump(
        data,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=120,
    )
