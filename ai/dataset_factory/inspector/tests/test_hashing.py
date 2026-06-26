"""Tests for SHA-256 hashing."""

from pathlib import Path

from dataset_factory.inspector.hashing import HASH_PREFIX, hash_file, normalize_hash


def test_hash_file_produces_prefixed_sha256(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"hello dataset inspector")

    digest, error = hash_file(sample)

    assert error is None
    assert digest.startswith(HASH_PREFIX)
    assert len(digest) == len(HASH_PREFIX) + 64


def test_hash_file_is_deterministic(tmp_path: Path) -> None:
    sample = tmp_path / "sample.bin"
    sample.write_bytes(b"deterministic content")

    first, _ = hash_file(sample)
    second, _ = hash_file(sample)

    assert first == second


def test_normalize_hash_adds_prefix() -> None:
    raw = "a" * 64
    assert normalize_hash(raw) == f"{HASH_PREFIX}{raw}"
