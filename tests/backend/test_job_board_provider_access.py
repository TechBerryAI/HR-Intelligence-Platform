"""Job-board providers must not fake a remote publish."""
from __future__ import annotations

from app.domains.integrations.dto import JobSnapshot, ProviderConfig
from app.domains.integrations.mapper.linkedin import linkedin_external_posting_id, to_linkedin_payload
from app.domains.integrations.provider.linkedin import LinkedInProvider
from app.domains.integrations.provider.naukri import NaukriProvider


def _job(**kwargs):
    data = dict(
        job_id='JD-STABLE-1',
        title='Engineer',
        company='Acme',
        company_key='acme',
        location='Bengaluru, India',
        description='Build things.',
        salary=None,
        experience=None,
        keywords=None,
    )
    data.update(kwargs)
    return JobSnapshot(**data)


def _cfg(**kwargs):
    settings = dict(kwargs.pop('settings', None) or {})
    return ProviderConfig(
        id=1,
        company_key='acme',
        company='Acme',
        provider=kwargs.get('provider', 'linkedin'),
        client_id=kwargs.get('client_id', 'id'),
        client_secret=kwargs.get('client_secret', 'secret'),
        access_token=kwargs.get('access_token', ''),
        settings=settings,
    )


def test_linkedin_blocked_without_partner_access():
    r = LinkedInProvider().publish(_job(), _cfg())
    assert r.success is False
    assert 'PROVIDER ACCESS REQUIRED' in (r.error or '')
    assert r.external_job_id is None


def test_naukri_never_fakes_success():
    r = NaukriProvider().publish(_job(), _cfg(provider='naukri'))
    assert r.success is False
    assert 'PROVIDER ACCESS REQUIRED' in (r.error or '')
    assert r.external_job_id is None


def test_linkedin_correlation_id_is_stable_across_retries():
    a = linkedin_external_posting_id('JD-STABLE-1')
    b = linkedin_external_posting_id('JD-STABLE-1')
    assert a == b
    assert a.startswith('hcip:')
    assert len(a) <= 75
    assert a != linkedin_external_posting_id('JD-OTHER')


def test_linkedin_payload_uses_official_operation_and_correlation():
    job = _job()
    cfg = _cfg(settings={'companyApplyUrl': 'https://careers.example/apply'})
    payload = to_linkedin_payload(job, cfg, operation='CREATE')
    assert payload['jobPostingOperationType'] == 'CREATE'
    assert payload['externalJobPostingId'] == linkedin_external_posting_id(job.job_id)
    assert payload['companyApplyUrl'] == 'https://careers.example/apply'
    assert payload['listingType'] == 'BASIC'


def test_linkedin_duplicate_create_is_reconciled(monkeypatch):
    cfg = _cfg(
        access_token='tok',
        settings={'companyApplyUrl': 'https://careers.example/apply'},
    )
    provider = LinkedInProvider()

    def fake_batch(_token, payload):
        return False, {'message': 'Trying to create a job with same partnerIdentifier already exists. Dropping the duplicate job posting creation request.'}, 'duplicate'

    monkeypatch.setattr(provider, '_batch_post', fake_batch)
    r = provider.publish(_job(), cfg)
    assert r.success is True
    assert r.external_job_id == linkedin_external_posting_id('JD-STABLE-1')
    assert r.payload and r.payload.get('reconciled') is True


def test_linkedin_http_success_without_task_succeeded_is_not_published(monkeypatch):
    cfg = _cfg(
        access_token='tok',
        settings={'companyApplyUrl': 'https://careers.example/apply'},
    )
    provider = LinkedInProvider()
    monkeypatch.setattr(
        provider,
        '_batch_post',
        lambda *_a, **_k: (True, {'elements': [{'id': 'urn:li:simpleJobPostingTask:abc'}]}, None),
    )
    monkeypatch.setattr(
        provider,
        '_get_task',
        lambda *_a, **_k: (True, {'results': {'urn:li:simpleJobPostingTask:abc': {'status': 'IN_PROGRESS'}}}, None),
    )
    r = provider.publish(_job(), cfg)
    assert r.success is False
    assert 'IN_PROGRESS' in (r.error or '')


def test_linkedin_task_succeeded_is_published(monkeypatch):
    cfg = _cfg(
        access_token='tok',
        settings={'companyApplyUrl': 'https://careers.example/apply'},
    )
    provider = LinkedInProvider()
    monkeypatch.setattr(
        provider,
        '_batch_post',
        lambda *_a, **_k: (True, {'elements': [{'id': 'urn:li:simpleJobPostingTask:abc'}]}, None),
    )
    monkeypatch.setattr(
        provider,
        '_get_task',
        lambda *_a, **_k: (
            True,
            {'results': {'urn:li:simpleJobPostingTask:abc': {'status': 'SUCCEEDED'}}},
            None,
        ),
    )
    r = provider.publish(_job(), cfg)
    assert r.success is True
    assert r.external_job_id == linkedin_external_posting_id('JD-STABLE-1')
