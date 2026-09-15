"""Regression: authenticated parse endpoints enforce the same upload
validation as the public ones.

Before this fix, ``/api/parse/resume`` and ``/api/parse/resume/stream``
skipped both the magic-byte content sniff and the MAX_FILE_SIZE cap, and
``/api/parse/jd``/``/api/parse/jd/stream`` skipped the content sniff — an
authenticated staff account could upload a renamed executable (any bytes
with a ``.pdf``/``.docx`` extension) or an oversized file that only the
public endpoints rejected. Runs against live PostgreSQL (real login) since
the auth middleware re-reads the user row from ``hr_signup``.
"""
from __future__ import annotations

from io import BytesIO

from live_db_helpers import app_client, auth_header, login, seed_org_with_staff  # noqa: F401

from app.domains.recruitment.api import parsing as parsing_mod


def test_authenticated_resume_upload_rejects_content_mismatch(app_client):
    a = seed_org_with_staff()
    token = login(app_client, a['head_email'])

    # Not actually a PDF, despite the extension and declared content type.
    fake = b'MZ\x90\x00\x03\x00\x00\x00this-is-not-a-pdf-at-all'
    res = app_client.post(
        '/api/parse/resume',
        headers=auth_header(token),
        data={'file': (BytesIO(fake), 'resume.pdf')},
        content_type='multipart/form-data',
    )
    assert res.status_code == 400
    assert 'content' in (res.get_json() or {}).get('error', '').lower()


def test_authenticated_resume_upload_rejects_oversized_file(app_client, monkeypatch):
    a = seed_org_with_staff()
    token = login(app_client, a['head_email'])
    monkeypatch.setattr(parsing_mod, 'MAX_FILE_SIZE', 1024)

    oversized = b'%PDF-1.4' + (b'x' * 2048)
    res = app_client.post(
        '/api/parse/resume',
        headers=auth_header(token),
        data={'file': (BytesIO(oversized), 'resume.pdf')},
        content_type='multipart/form-data',
    )
    assert res.status_code == 413


def test_authenticated_jd_upload_rejects_content_mismatch(app_client):
    a = seed_org_with_staff()
    token = login(app_client, a['head_email'])

    fake = b'\x7fELF-not-a-real-docx-or-pdf-either'
    res = app_client.post(
        '/api/parse/jd',
        headers=auth_header(token),
        data={'file': (BytesIO(fake), 'jd.docx')},
        content_type='multipart/form-data',
    )
    assert res.status_code == 400
    assert 'content' in (res.get_json() or {}).get('error', '').lower()


def test_authenticated_jd_upload_rejects_oversized_file(app_client, monkeypatch):
    a = seed_org_with_staff()
    token = login(app_client, a['head_email'])
    monkeypatch.setattr(parsing_mod, 'MAX_FILE_SIZE', 1024)

    oversized = b'%PDF-1.4' + (b'x' * 2048)
    res = app_client.post(
        '/api/parse/jd',
        headers=auth_header(token),
        data={'file': (BytesIO(oversized), 'jd.pdf')},
        content_type='multipart/form-data',
    )
    assert res.status_code == 413
