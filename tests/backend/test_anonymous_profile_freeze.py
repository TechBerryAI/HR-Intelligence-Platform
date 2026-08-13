"""Security regression: anonymous apply must not overwrite existing shared profiles."""
from __future__ import annotations

import inspect

from app.domains.candidate.services import profile_service as ps
from app.domains.recruitment.api import jobs as jobs_mod


def test_upsert_returns_created_flag_and_does_not_update_name(monkeypatch):
    updates = []

    def fake_db_get(sql, params=None):
        if 'SELECT cid, name' in sql.replace('\n', ' '):
            return {'cid': 'CID001', 'name': 'Victim Name'}
        return None

    def fake_db_run(sql, params=None):
        updates.append((sql, params))

    monkeypatch.setattr(ps, 'db_get', fake_db_get)
    monkeypatch.setattr(ps, 'db_run', fake_db_run)

    cid, created = ps.upsert_passwordless_candidate(
        'Attacker Name',
        'victim@example.com',
        organization_id='11111111-1111-1111-1111-111111111111',
    )
    assert cid == 'CID001'
    assert created is False
    assert updates == []  # no name overwrite


def test_upsert_creates_new_candidate(monkeypatch):
    state = {'exists': False}

    def fake_db_get(sql, params=None):
        sql_n = ' '.join(sql.split())
        if 'SELECT cid, name' in sql_n:
            return None
        if 'SELECT cid FROM candidates' in sql_n:
            return {'cid': 'CID099'}
        return None

    def fake_db_run(sql, params=None):
        state['exists'] = True
        state['insert'] = params

    monkeypatch.setattr(ps, 'db_get', fake_db_get)
    monkeypatch.setattr(ps, 'db_run', fake_db_run)

    cid, created = ps.upsert_passwordless_candidate(
        'New Person',
        'new@example.com',
        organization_id='11111111-1111-1111-1111-111111111111',
    )
    assert cid == 'CID099'
    assert created is True
    assert state['insert'][0] == 'New Person'


def test_public_apply_freezes_profile_for_existing_candidate():
    src = inspect.getsource(jobs_mod.public_apply_to_job)
    assert 'candidate_created' in src
    assert 'existing_profile' in src
    assert 'if candidate_created or not existing_profile:' in src
    # Must not unconditionally save profile before the freeze gate
    assert 'Freeze shared profile' in src or 'email alone is not ownership' in src.lower() or 'ownership proof' in src


def test_upsert_signature_documents_freeze_invariant():
    assert 'MUST NOT mutate' in (ps.upsert_passwordless_candidate.__doc__ or '')


def test_org_a_lookup_does_not_return_org_b_candidate(monkeypatch):
    """Same email in Org B must not be reused as Org A's candidate."""
    org_a = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'
    org_b = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'
    seen = []

    def fake_db_get(sql, params=None):
        seen.append(params)
        sql_n = ' '.join(sql.split())
        if 'SELECT cid, name' in sql_n:
            if params and params[0] == org_b:
                return {'cid': 'CID-B', 'name': 'Org B Person'}
            return None
        if 'SELECT cid FROM candidates' in sql_n:
            return {'cid': 'CID-A'}
        return None

    monkeypatch.setattr(ps, 'db_get', fake_db_get)
    monkeypatch.setattr(ps, 'db_run', lambda *a, **k: None)

    cid, created = ps.upsert_passwordless_candidate(
        'Org A Person',
        'shared@example.com',
        organization_id=org_a,
    )
    assert created is True
    assert cid == 'CID-A'
    assert seen[0][0] == org_a
    assert org_b not in {p[0] for p in seen if p}
