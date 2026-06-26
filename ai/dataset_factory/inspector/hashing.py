"""Streaming SHA-256 hashing for dataset files."""

from __future__ import annotations

import hashlib
from pathlib import Path

HASH_PREFIX = "sha256:"
CHUNK_SIZE = 1024 * 1024


def hash_file(path: Path, max_bytes: int | None = None) -> tuple[str, str | None]:
    """
    Compute SHA-256 hash of file contents using streaming reads.

    Args:
        path: File to hash.
        max_bytes: Optional upper bound on bytes to read.

    Returns:
        Tuple of (prefixed_hash, error_message).
    """
    digest = hashlib.sha256()
    bytes_read = 0

    try:
        with path.open("rb") as handle:
            while True:
                chunk = handle.read(CHUNK_SIZE)
                if not chunk:
                    break
                if max_bytes is not None:
                    remaining = max_bytes - bytes_read
                    if remaining <= 0:
                        break
                    if len(chunk) > remaining:
                        chunk = chunk[:remaining]
                digest.update(chunk)
                bytes_read += len(chunk)
    except OSError as exc:
        return "", str(exc)

    return f"{HASH_PREFIX}{digest.hexdigest()}", None


def normalize_hash(value: str) -> str:
    """Ensure hash value includes sha256: prefix."""
    if value.startswith(HASH_PREFIX):
        return value
    return f"{HASH_PREFIX}{value}"
