"""Regression tests for High/Medium bug-audit fixes (authz, parse claim, OTP)."""
from __future__ import annotations

import sys
from pathlib import Path

import jwt
import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.auth import JWT_SECRET
from app.domains.candidate.services.parse_claim import issue_parse_claim, verify_parse_claim
from app.domains.candidate.services import profile_service as ps
from app.domains.identity.authorization.rbac import can_modify_job, can_act_on_application
from app.ai.document_intelligence.pipeline import resume_deterministic_is_strong


ORG = '11111111-1111-1111-1111-111111111111'


def test_parse_claim_roundtrip():
    claim = issue_parse_claim('parsed-abc')
    assert verify_parse_claim(claim, 'parsed-abc') is True
    assert verify_parse_claim(claim, 'parsed-other') is False
    assert verify_parse_claim('garbage', 'parsed-abc') is False
    assert verify_parse_claim(None, 'parsed-abc') is False


def test_parse_claim_rejects_wrong_type():
    token = jwt.encode(
        {'type': 'access', 'parsed_id': 'parsed-abc'},
        JWT_SECRET,
        algorithm='HS256',
    )
    assert verify_parse_claim(token, 'parsed-abc') is False


def test_recruiter_can_modify_own_job_only(monkeypatch):
    monkeypatch.setattr(
        'app.domains.identity.services.organizations.get_organization_id_for_user',
        lambda _u: ORG,
    )
    owner = {'user_id': 'HRID001', 'role': 'RECRUITER', 'organization_id': ORG}
    peer = {'user_id': 'HRID002', 'role': 'RECRUITER', 'organization_id': ORG}
    head = {'user_id': 'HRID003', 'role': 'HEAD_HR', 'organization_id': ORG}

    assert can_modify_job(owner, posted_by='HRID001', organization_id=ORG) is True
    assert can_modify_job(peer, posted_by='HRID001', organization_id=ORG) is False
    assert can_modify_job(head, posted_by='HRID001', organization_id=ORG) is True
    assert can_act_on_application(peer, job_posted_by='HRID001', organization_id=ORG) is False
    assert can_act_on_application(owner, job_posted_by='HRID001', organization_id=ORG) is True


def test_link_parsed_resume_rejects_foreign_without_claim(monkeypatch):
    calls = []

    def fake_db_get(sql, params=None):
        calls.append(('get', sql, params))
        sql_n = ' '.join(sql.split())
        if 'FROM parsed_resumes WHERE id' in sql_n:
            return {
                'id': 'pid-1',
                'toon': 't',
                'confidence': 0.9,
                'raw_file_id': 'rf-1',
                'candidate_id': 'CID-OTHER',
            }
        return None

    monkeypatch.setattr(ps, 'db_get', fake_db_get)
    monkeypatch.setattr(ps, 'db_run', lambda *a, **k: None)

    assert ps.link_parsed_resume('pid-1', 'CID-SELF', claim_verified=False) is None
    assert ps.link_parsed_resume('pid-1', 'CID-SELF', claim_verified=True)['id'] == 'pid-1'


def test_link_parsed_resume_unowned_requires_claim_or_uploader(monkeypatch):
    def fake_db_get(sql, params=None):
        sql_n = ' '.join(sql.split())
        if 'FROM parsed_resumes WHERE id' in sql_n:
            return {
                'id': 'pid-2',
                'toon': 't',
                'confidence': 0.9,
                'raw_file_id': 'rf-2',
                'candidate_id': None,
            }
        if 'FROM raw_files' in sql_n:
            return None
        return None

    monkeypatch.setattr(ps, 'db_get', fake_db_get)
    monkeypatch.setattr(ps, 'db_run', lambda *a, **k: None)

    assert ps.link_parsed_resume('pid-2', 'CID-NEW', 'PUB-X', claim_verified=False) is None
    bound = ps.link_parsed_resume('pid-2', 'CID-NEW', 'PUB-X', claim_verified=True)
    assert bound is not None


def test_deterministic_strong_fails_closed_on_exception(monkeypatch):
    class FakeProfile:
        personal = type('P', (), {'full_name': 'Ada'})()
        contact = type('C', (), {'email': 'a@b.c', 'phone': '999'})()
        skills = ['Python']
        experience = [{'title': 'Eng'}]
        education = [{'degree': 'BS'}]

    def boom(*_a, **_k):
        raise RuntimeError('boom')

    monkeypatch.setattr(
        'app.ai.document_intelligence.experience_quality.experience_is_incomplete',
        boom,
    )
    assert resume_deterministic_is_strong(FakeProfile(), 'text') is False


def test_email_otp_fail_closed_without_mail(monkeypatch):
    from app.domains.identity.otp import otp_utils

    class FakeApp:
        config = {'MAIL_USERNAME': None, 'MAIL_PASSWORD': None, 'MAIL_SUPPRESS_SEND': False}
        class logger:
            @staticmethod
            def info(*_a, **_k):
                pass

            @staticmethod
            def error(*_a, **_k):
                pass

    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_DEV_OTP', 'false')
    monkeypatch.setattr(otp_utils, 'current_app', FakeApp())
    assert otp_utils.send_email_otp('user@example.com', '123456') is False


def test_sms_otp_fail_closed_without_provider(monkeypatch):
    from app.domains.identity.otp import otp_utils

    class FakeApp:
        config = {}
        class logger:
            @staticmethod
            def info(*_a, **_k):
                pass

            @staticmethod
            def error(*_a, **_k):
                pass

    monkeypatch.setenv('FLASK_DEBUG', 'false')
    monkeypatch.setenv('ALLOW_DEV_OTP', 'false')
    monkeypatch.delenv('FAST2SMS_API_KEY', raising=False)
    monkeypatch.delenv('SMS_API_KEY', raising=False)
    monkeypatch.setattr(otp_utils, 'current_app', FakeApp())
    assert otp_utils.send_sms_otp('9876543210', '123456') is False
