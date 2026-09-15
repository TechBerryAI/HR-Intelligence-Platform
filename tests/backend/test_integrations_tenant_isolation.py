"""BUG-004: integrations data must be isolated by organization_id, never by
company name / company_key. Two organizations sharing an identical display
name (which company_key would collide on) must still be fully isolated.

Runs against live PostgreSQL — no DB mocks for the tenant-boundary checks.
"""
from __future__ import annotations

import uuid

import pytest

from live_db_helpers import (
    app_client,
    auth_header,
    login,
    seed_org_with_staff,
    seed_org_with_staff_same_name,
)

SAME_NAME = 'Acme Technologies'


@pytest.fixture(scope='module')
def same_name_tenants(app_client):
    """Two independent orgs that both display as 'Acme Technologies'."""
    a = seed_org_with_staff_same_name(SAME_NAME)
    b = seed_org_with_staff_same_name(SAME_NAME)
    assert a['org_id'] != b['org_id']
    assert a['org_name'] == b['org_name'] == SAME_NAME
    return a, b


def test_same_name_orgs_get_different_company_keys_but_are_distinct_orgs(same_name_tenants):
    from app.domains.recruitment.services.company_scope import normalize_company

    a, b = same_name_tenants
    # This is exactly the collision BUG-004 is about: identical company_key,
    # different organization_id.
    assert normalize_company(a['org_name']) == normalize_company(b['org_name'])
    assert a['org_id'] != b['org_id']


def test_provider_config_isolated_by_org_not_company_key(app_client, same_name_tenants):
    a, b = same_name_tenants
    token_a = login(app_client, a['head_email'])
    token_b = login(app_client, b['head_email'])

    provider = f'ashby{uuid.uuid4().hex[:6]}'
    resp = app_client.post(
        '/api/integrations/provider',
        headers=auth_header(token_a),
        json={
            'provider': provider,
            'custom': True,
            'baseUrl': 'https://api.example-ats.test',
            'clientSecret': 'org-a-secret',
            'enabled': True,
        },
    )
    assert resp.status_code == 201, resp.get_json()

    # Org B (same display name) must not see org A's provider at all.
    listing_b = app_client.get('/api/integrations/providers', headers=auth_header(token_b))
    assert listing_b.status_code == 200
    ids_b = {p['id'] for p in listing_b.get_json()['providers']}
    assert provider not in ids_b

    get_b = app_client.get(f'/api/integrations/provider/{provider}', headers=auth_header(token_b))
    assert get_b.status_code == 404

    # Org A still sees its own provider.
    listing_a = app_client.get('/api/integrations/providers', headers=auth_header(token_a))
    ids_a = {p['id'] for p in listing_a.get_json()['providers']}
    assert provider in ids_a


def test_cannot_delete_or_disconnect_other_orgs_provider_by_slug(app_client, same_name_tenants):
    a, b = same_name_tenants
    token_a = login(app_client, a['head_email'])
    token_b = login(app_client, b['head_email'])

    provider = f'lever{uuid.uuid4().hex[:6]}'
    create = app_client.post(
        '/api/integrations/provider',
        headers=auth_header(token_a),
        json={
            'provider': provider,
            'custom': True,
            'baseUrl': 'https://api.example-ats.test',
            'enabled': True,
        },
    )
    assert create.status_code == 201, create.get_json()

    # Org B (same company name) cannot disconnect or delete org A's provider.
    disconnect = app_client.post(
        f'/api/integrations/provider/{provider}/disconnect', headers=auth_header(token_b)
    )
    assert disconnect.status_code == 404

    delete = app_client.delete(f'/api/integrations/provider/{provider}', headers=auth_header(token_b))
    assert delete.status_code == 404

    # Org A's provider is untouched.
    still_there = app_client.get(f'/api/integrations/provider/{provider}', headers=auth_header(token_a))
    assert still_there.status_code == 200
    assert still_there.get_json()['provider']['enabled'] is True


def test_delete_provider_by_numeric_id_is_org_scoped(app_client, same_name_tenants):
    from app.database.connection.db import db_get

    a, b = same_name_tenants
    token_a = login(app_client, a['head_email'])
    token_b = login(app_client, b['head_email'])

    provider = f'bamboohr{uuid.uuid4().hex[:6]}'
    create = app_client.post(
        '/api/integrations/provider',
        headers=auth_header(token_a),
        json={'provider': provider, 'custom': True, 'baseUrl': 'https://api.example-ats.test'},
    )
    assert create.status_code == 201, create.get_json()
    row = db_get(
        'SELECT id FROM integration_provider WHERE organization_id = ? AND provider = ?',
        (a['org_id'], provider),
    )
    assert row

    # Org B guesses/enumerates the numeric id — must still be denied.
    delete_wrong_org = app_client.delete(
        f"/api/integrations/provider/{row['id']}", headers=auth_header(token_b)
    )
    assert delete_wrong_org.status_code == 404

    still_there = db_get('SELECT id FROM integration_provider WHERE id = ?', (row['id'],))
    assert still_there is not None


def test_repository_layer_scopes_by_organization_id(same_name_tenants):
    """Direct repository calls — the actual persistence boundary — must key
    on organization_id even when company_key is identical across orgs."""
    from app.domains.integrations import repository as repo

    a, b = same_name_tenants
    provider = f'greenhouse{uuid.uuid4().hex[:6]}'

    repo.upsert_provider(
        a['org_id'], a['org_name'], provider,
        company_key='acme technologies', enabled=True, status='connected',
        client_secret='org-a-only-secret',
    )
    repo.upsert_provider(
        b['org_id'], b['org_name'], provider,
        company_key='acme technologies', enabled=False, status='disconnected',
    )

    row_a = repo.get_provider_row(a['org_id'], provider)
    row_b = repo.get_provider_row(b['org_id'], provider)
    assert row_a and row_b
    assert row_a['id'] != row_b['id']
    assert row_a['enabled'] is True
    assert row_b['enabled'] is False
    assert row_a['client_secret'] != row_b.get('client_secret')

    # Listing for org A must never include org B's row, despite identical company_key.
    ids_a = {r['id'] for r in repo.list_providers(a['org_id'])}
    ids_b = {r['id'] for r in repo.list_providers(b['org_id'])}
    assert row_a['id'] in ids_a
    assert row_a['id'] not in ids_b
    assert row_b['id'] in ids_b
    assert row_b['id'] not in ids_a


def test_external_jobs_and_sync_logs_scoped_by_org(same_name_tenants):
    from app.domains.integrations import repository as repo

    a, b = same_name_tenants
    job_id = f'JD{uuid.uuid4().hex[:10].upper()}'

    repo.upsert_external_job(a['org_id'], job_id, 'linkedin', company_key='acme technologies')
    repo.insert_sync_log(a['org_id'], 'linkedin', 'publish', 'success', company_key='acme technologies', job_id=job_id)

    # Org B must see none of it, even though the two orgs' company_key is identical.
    assert repo.list_external_jobs(b['org_id'], job_id=job_id) == []
    assert repo.count_external_by_status(b['org_id']) == []
    logs_b = [log for log in repo.list_sync_logs(b['org_id'], limit=200) if log.get('job_id') == job_id]
    assert logs_b == []

    assert repo.list_external_jobs(a['org_id'], job_id=job_id) != []
    logs_a = [log for log in repo.list_sync_logs(a['org_id'], limit=200) if log.get('job_id') == job_id]
    assert logs_a != []


def test_oauth_tokens_scoped_by_hrid_survive_identical_company_key(same_name_tenants):
    """Two recruiters in different (same-named) orgs must each get their own
    OAuth row. Under the old UNIQUE(company_key, provider) constraint this
    would have raised an IntegrityError on the second insert."""
    from datetime import datetime, timedelta, timezone

    from app.domains.integrations.repository import oauth_tokens as oauth_repo

    a, b = same_name_tenants
    provider = f'google_calendar_test_{uuid.uuid4().hex[:6]}'
    expires = datetime.now(timezone.utc) + timedelta(hours=1)

    oauth_repo.upsert_oauth_tokens(
        provider=provider, hrid=a['recruiter_hrid'], organization_id=a['org_id'],
        company_key='acme technologies', access_token='token-a', refresh_token='refresh-a',
        expires_at=expires,
    )
    oauth_repo.upsert_oauth_tokens(
        provider=provider, hrid=b['recruiter_hrid'], organization_id=b['org_id'],
        company_key='acme technologies', access_token='token-b', refresh_token='refresh-b',
        expires_at=expires,
    )

    row_a = oauth_repo.get_oauth_row(provider, a['recruiter_hrid'])
    row_b = oauth_repo.get_oauth_row(provider, b['recruiter_hrid'])
    assert row_a and row_b
    assert row_a['id'] != row_b['id']
    assert str(row_a['organization_id']) == a['org_id']
    assert str(row_b['organization_id']) == b['org_id']


def test_distinct_name_orgs_still_isolated_baseline(app_client):
    """Control case: ordinary distinct-name orgs (existing coverage extended
    to the integrations surface specifically)."""
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    token_b = login(app_client, b['head_email'])

    from app.domains.integrations import repository as repo

    provider = f'workday{uuid.uuid4().hex[:6]}'
    repo.upsert_provider(a['org_id'], a['org_name'], provider, enabled=True)

    listing_b = app_client.get('/api/integrations/providers', headers=auth_header(token_b))
    ids_b = {p['id'] for p in listing_b.get_json()['providers']}
    assert provider not in ids_b
