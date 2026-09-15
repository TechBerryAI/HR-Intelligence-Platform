"""Regression: extract_zip_to_job must not decompress an oversized ZIP entry.

Before this fix there was no per-entry, total, or entry-count cap — a small
ZIP whose central directory declares a huge uncompressed size (or one with
many entries) would be fully decompressed into memory with zf.read() before
any size check ran.
"""
from __future__ import annotations

import io
import uuid
import zipfile

from live_db_helpers import app_client, seed_org_with_staff  # noqa: F401

from app.workers import bulk_parser


def _no_owner(_job_id):
    return None


def _zip_with_entry(name: str, data: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(name, data)
    return buf.getvalue()


def test_oversized_entry_is_rejected_before_decompression(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', tmp_path / 'bulk_uploads')
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner', _no_owner
    )
    monkeypatch.setattr(bulk_parser, '_ZIP_MAX_ENTRY_BYTES', 1024)

    # Highly compressible payload whose *declared* uncompressed size exceeds
    # the per-entry cap, but whose compressed size is tiny.
    huge_but_compressible = b'A' * (10 * 1024)
    zip_bytes = _zip_with_entry('resume.pdf', b'%PDF-1.4' + huge_but_compressible)

    ok, result = bulk_parser.extract_zip_to_job(
        str(uuid.uuid4()), zip_bytes, started_by='attacker-hrid'
    )
    # The single oversized entry is skipped, leaving nothing valid to stage.
    assert ok is False
    assert 'No valid resume files' in result.get('error', '')


def test_too_many_entries_is_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', tmp_path / 'bulk_uploads')
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner', _no_owner
    )
    monkeypatch.setattr(bulk_parser, '_ZIP_MAX_ENTRIES', 3)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for i in range(5):
            zf.writestr(f'resume_{i}.pdf', b'%PDF-1.4 fake content')

    ok, result = bulk_parser.extract_zip_to_job(
        str(uuid.uuid4()), buf.getvalue(), started_by='attacker-hrid'
    )
    assert ok is False
    assert 'too many files' in result.get('error', '').lower()


def test_total_decompressed_size_cap_is_enforced(tmp_path, monkeypatch):
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', tmp_path / 'bulk_uploads')
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner', _no_owner
    )
    monkeypatch.setattr(bulk_parser, '_ZIP_MAX_ENTRY_BYTES', 10 * 1024)
    monkeypatch.setattr(bulk_parser, '_ZIP_MAX_TOTAL_BYTES', 15 * 1024)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('resume_1.pdf', b'%PDF-1.4' + b'A' * (9 * 1024))
        zf.writestr('resume_2.pdf', b'%PDF-1.4' + b'B' * (9 * 1024))

    ok, result = bulk_parser.extract_zip_to_job(
        str(uuid.uuid4()), buf.getvalue(), started_by='attacker-hrid'
    )
    assert ok is False
    assert 'too large when decompressed' in result.get('error', '').lower()


def test_normal_small_zip_still_works(tmp_path, monkeypatch, app_client):
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', tmp_path / 'bulk_uploads')

    org = seed_org_with_staff()
    zip_bytes = _zip_with_entry('resume.pdf', b'%PDF-1.4 a perfectly normal small resume')
    job_id, _ = bulk_parser.create_local_job(started_by=org['recruiter_hrid'])
    try:
        ok, result = bulk_parser.extract_zip_to_job(job_id, zip_bytes, started_by=org['recruiter_hrid'])
        assert ok is True, result
        assert result.get('added_files') == 1
    finally:
        with bulk_parser._local_jobs_lock:
            bulk_parser._local_jobs.pop(job_id, None)
