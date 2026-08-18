"""Organization isolation for job publish authorization."""
from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.domains.integrations.api.routes import _job_belongs_to_company
from app.domains.identity.authorization.rbac import can_access_job


ORG_A = '11111111-1111-1111-1111-111111111111'
ORG_B = '22222222-2222-2222-2222-222222222222'


def _user(org_id: str, user_id: str = 'hr-b'):
    return {
        'user_id': user_id,
        'organization_id': org_id,
        'role': 'HEAD_HR',
        'company': 'Acme',
    }


def test_a_same_organization_allows(monkeypatch):
    job = {
        'jdid': 'job-a',
        'organization_id': ORG_A,
        'company': 'Acme',
        'posted_by': 'hr-a',
    }
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.db_get',
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(
        'app.domains.identity.services.organizations.get_organization_id_for_user',
        lambda _u: ORG_A,
    )
    assert _job_belongs_to_company('job-a', 'acme', _user(ORG_A, 'hr-a')) is True
    assert can_access_job(_user(ORG_A, 'hr-a'), posted_by='hr-a', organization_id=ORG_A) is True


def test_b_different_org_same_company_name_denies(monkeypatch):
    job = {
        'jdid': 'job-a',
        'organization_id': ORG_A,
        'company': 'Acme',
        'posted_by': 'hr-a',
    }
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.db_get',
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(
        'app.domains.identity.services.organizations.get_organization_id_for_user',
        lambda _u: ORG_B,
    )
    user_b = _user(ORG_B)
    assert _job_belongs_to_company('job-a', 'acme', user_b) is False
    assert can_access_job(user_b, posted_by='hr-a', organization_id=ORG_A) is False


def test_c_different_org_different_company_denies(monkeypatch):
    job = {
        'jdid': 'job-a',
        'organization_id': ORG_A,
        'company': 'Acme',
        'posted_by': 'hr-a',
    }
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.db_get',
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(
        'app.domains.identity.services.organizations.get_organization_id_for_user',
        lambda _u: ORG_B,
    )
    user_b = {**_user(ORG_B), 'company': 'Other Co'}
    assert _job_belongs_to_company('job-a', 'other co', user_b) is False
    assert can_access_job(user_b, posted_by='hr-a', organization_id=ORG_A) is False


def test_d_legacy_unscoped_company_fallback_allows(monkeypatch):
    """Jobs with NULL organization_id and no owner org use company-name fallback."""
    job = {
        'jdid': 'job-legacy',
        'organization_id': None,
        'company': 'Acme',
        'posted_by': None,
    }
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.db_get',
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(
        'app.domains.integrations.api.routes._resolve_job_organization_id',
        lambda **_k: None,
    )
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.resolve_company_for_user',
        lambda _u: ('acme', 'Acme'),
    )
    assert _job_belongs_to_company('job-legacy', 'acme', _user(ORG_B)) is True


def test_d_legacy_unscoped_owner_org_denies_other_tenant(monkeypatch):
    """NULL job.organization_id still denies when posted_by belongs to another org."""
    job = {
        'jdid': 'job-legacy',
        'organization_id': None,
        'company': 'Acme',
        'posted_by': 'hr-a',
    }
    monkeypatch.setattr(
        'app.domains.integrations.api.routes.db_get',
        lambda *_a, **_k: job,
    )
    monkeypatch.setattr(
        'app.domains.integrations.api.routes._resolve_job_organization_id',
        lambda **_k: ORG_A,
    )
    monkeypatch.setattr(
        'app.domains.identity.services.organizations.get_organization_id_for_user',
        lambda _u: ORG_B,
    )
    assert _job_belongs_to_company('job-legacy', 'acme', _user(ORG_B)) is False
