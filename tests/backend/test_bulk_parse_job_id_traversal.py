"""Regression: bulk-parse job_id must never escape the intended staging root.

``POST /api/admin/bulk-parse/upload`` accepts a client-supplied ``job_id``
form field with no route-converter restriction (unlike the ``<job_id>`` URL
path segments used elsewhere), so a malicious value such as
``../../../../tmp/evil`` reached ``_staging_dir()``/``_ensure_job()``
unsanitized and — because any authenticated caller is truthy ``started_by`` —
bypassed the "unknown job" guard, creating directories and writing uploaded
bytes outside ``MEDIA_ROOT/bulk_uploads``. Fixed by requiring job_id to be a
uuid4 string (the only shape this module itself ever generates) before it is
used as a filesystem path component.
"""
from __future__ import annotations

from pathlib import Path

from app.workers import bulk_parser

MALICIOUS_JOB_IDS = [
    '../../../../tmp/evil',
    '..\\..\\..\\windows\\evil',
    '..',
    '../escaped',
]


def _no_owner(_job_id):
    return None


def test_ensure_job_rejects_path_traversal_job_id(tmp_path, monkeypatch):
    upload_root = tmp_path / 'bulk_uploads'
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', upload_root)
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner',
        _no_owner,
    )

    for job_id in MALICIOUS_JOB_IDS:
        result = bulk_parser._ensure_job(job_id, started_by='attacker-hrid')
        assert result is None, f'job_id {job_id!r} must be rejected, not turned into a job'

    # The real security boundary: no directory was created anywhere outside
    # (or even inside) the intended upload root as a side effect of the calls
    # above. tmp_path is the whole sandbox for this test, so nothing beyond
    # upload_root existing at all is proof nothing escaped.
    assert not upload_root.exists()
    assert list(tmp_path.iterdir()) == []


def test_stage_files_rejects_path_traversal_job_id(tmp_path, monkeypatch):
    upload_root = tmp_path / 'bulk_uploads'
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', upload_root)
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner',
        _no_owner,
    )

    ok, result = bulk_parser.stage_files(
        '../../../../tmp/evil',
        [('resume.pdf', b'%PDF-1.4 fake malicious content')],
        started_by='attacker-hrid',
    )

    assert ok is False
    assert result.get('error') == 'Job not found'
    # No file was written anywhere on disk — neither inside the sandbox's
    # escaped target nor inside the intended upload root.
    assert not upload_root.exists()
    assert list(tmp_path.rglob('*.pdf')) == []


def test_ensure_job_still_accepts_a_real_uuid_job_id(tmp_path, monkeypatch):
    """Sanity: the fix must not break the legitimate flow."""
    upload_root = tmp_path / 'bulk_uploads'
    monkeypatch.setattr(bulk_parser, '_BULK_UPLOAD_DIR', upload_root)
    monkeypatch.setattr(
        'app.domains.administration.repositories.bulk_session_db.get_session_owner',
        _no_owner,
    )

    job_id, _payload = bulk_parser.create_local_job(started_by='recruiter-hrid')
    try:
        assert bulk_parser._is_valid_job_id(job_id)
        job = bulk_parser._ensure_job(job_id, started_by='recruiter-hrid')
        assert job is not None
        assert (upload_root / job_id).is_dir()
    finally:
        with bulk_parser._local_jobs_lock:
            bulk_parser._local_jobs.pop(job_id, None)
