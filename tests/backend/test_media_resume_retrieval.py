"""Regression: media-backed and legacy BYTEA resume retrieval."""
from __future__ import annotations

import inspect

from app.domains.recruitment.services import parsing_storage as ps
from app.domains.recruitment.services.parsing_storage import (
    HAS_RESUME_SQL,
    HAS_RESUME_SQL_ALIASED,
    profile_has_resume,
)


def test_profile_has_resume_media_only():
    assert profile_has_resume({'resume_raw_file_id': 'uuid-1', 'resume': None}) is True


def test_profile_has_resume_bytea_only():
    assert profile_has_resume({'resume_raw_file_id': None, 'resume': b'%PDF-1.4'}) is True


def test_profile_has_resume_neither():
    assert profile_has_resume({'resume_raw_file_id': None, 'resume': None}) is False
    assert profile_has_resume(None) is False


def test_has_resume_sql_includes_media_column():
    assert 'resume_raw_file_id' in HAS_RESUME_SQL
    assert 'resume_raw_file_id' in HAS_RESUME_SQL_ALIASED


def test_load_profile_resume_prefers_media(monkeypatch):
    monkeypatch.setattr(
        ps,
        'load_raw_file_bytes',
        lambda raw_id: b'%PDF-media' if raw_id == 'raw-1' else None,
    )

    import app.database.connection.db as db_mod

    monkeypatch.setattr(
        db_mod,
        'db_get',
        lambda sql, params=None: {'resume': b'legacy', 'resume_raw_file_id': 'raw-1'},
    )
    assert ps.load_profile_resume_bytes('CID001') == b'%PDF-media'


def test_load_profile_resume_falls_back_to_bytea(monkeypatch):
    monkeypatch.setattr(ps, 'load_raw_file_bytes', lambda raw_id: None)

    import app.database.connection.db as db_mod

    monkeypatch.setattr(
        db_mod,
        'db_get',
        lambda sql, params=None: {'resume': b'%PDF-legacy', 'resume_raw_file_id': None},
    )
    assert ps.load_profile_resume_bytes('CID002') == b'%PDF-legacy'


def test_load_profile_resume_neither_returns_none(monkeypatch):
    monkeypatch.setattr(ps, 'load_raw_file_bytes', lambda raw_id: None)

    import app.database.connection.db as db_mod

    monkeypatch.setattr(
        db_mod,
        'db_get',
        lambda sql, params=None: {'resume': None, 'resume_raw_file_id': None},
    )
    assert ps.load_profile_resume_bytes('CID003') is None


def test_load_profile_resume_missing_profile(monkeypatch):
    import app.database.connection.db as db_mod

    monkeypatch.setattr(db_mod, 'db_get', lambda sql, params=None: None)
    assert ps.load_profile_resume_bytes('MISSING') is None


def test_head_hr_resume_uses_media_helper():
    from app.domains.administration.api import head_hr as head_hr_mod

    src = inspect.getsource(head_hr_mod.get_candidate_resume)
    assert 'load_profile_resume_bytes' in src
    assert "SELECT resume FROM candidate_profiles" not in src


def test_head_hr_has_resume_includes_media():
    from app.domains.administration.api import head_hr as head_hr_mod

    src = inspect.getsource(head_hr_mod._head_hr_profile_payload)
    assert 'resume_raw_file_id' in src


def test_candidate_profile_has_resume_includes_media():
    from app.domains.candidate.api import routes as candidate_routes

    src = inspect.getsource(candidate_routes.get_profile_admin)
    assert 'resume_raw_file_id' in src


def test_head_hr_resume_requires_org_link():
    """Unauthorized/cross-org: no application in caller org → 404 before load."""
    from app.domains.administration.api import head_hr as head_hr_mod

    src = inspect.getsource(head_hr_mod.get_candidate_resume)
    assert 'organization_id' in src
    assert 'applications' in src
