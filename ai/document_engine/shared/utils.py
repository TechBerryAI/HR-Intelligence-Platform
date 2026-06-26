"""Utility helpers for Document Processing Engine."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from .constants import HASH_PREFIX


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def relative_path(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def document_id_from_hash(sha256: str) -> str:
    """Derive stable document directory name from content hash."""
    digest = sha256.removeprefix(HASH_PREFIX)
    return digest[:16]


def count_words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def whitespace_ratio(text: str) -> float:
    if not text:
        return 1.0
    whitespace = sum(1 for c in text if c.isspace())
    return round(whitespace / len(text), 4)


def yaml_dump(data: Any) -> str:
    return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True, width=120)


def artifact_id(prefix: str, sha256: str) -> str:
    digest = sha256.removeprefix(HASH_PREFIX)[:8]
    return f"ART-DF-{prefix}-{digest}"


def slugify_filename(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", name).strip("_") or "document"
