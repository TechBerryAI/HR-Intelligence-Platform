"""Anti-contamination and field-contract unit tests."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.contracts.registry import (  # noqa: E402
    JD_FIELD_CONTRACTS,
    RESUME_FIELD_CONTRACTS,
    get_contract,
)
from app.ai.document_intelligence.models.candidate import (  # noqa: E402
    CandidateProfile,
    EducationEntry,
    ExperienceEntry,
    PersonalInfo,
    SkillEntry,
)
from app.ai.document_intelligence.validation.engine import (  # noqa: E402
    sanitize_candidate_profile,
    validate_institution,
    validate_person_name,
    validate_skill_item,
)


def test_resume_contracts_cover_core_fields():
    for key in ('fullName', 'email', 'phone', 'skills', 'experiences[].company', 'experiences[].role'):
        assert get_contract(key, kind='resume') is not None
    assert len(RESUME_FIELD_CONTRACTS) >= 15


def test_jd_contracts_cover_core_fields():
    for key in ('title', 'location', 'company', 'mandatorySkills'):
        assert get_contract(key, kind='jd') is not None
    assert len(JD_FIELD_CONTRACTS) >= 8


def test_name_rejects_resume_title():
    ok, reason = validate_person_name('Professional Summary')
    assert not ok
    assert 'title' in reason or 'name' in reason


def test_institution_rejects_month():
    ok, reason = validate_institution('January')
    assert not ok
    assert 'month' in reason or 'date' in reason


def test_skill_rejects_experience_sentence():
    ok, reason = validate_skill_item('Built APIs and services and improved latency significantly')
    assert not ok


def test_sanitize_blanks_contaminated_fields():
    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Curriculum Vitae'),
        education=[EducationEntry(institution='March', degree='B.Tech')],
        experience=[ExperienceEntry(company='Acme', role='Acme')],
        skills=[SkillEntry(name='Developed scalable microservices for production')],
    )
    clean = sanitize_candidate_profile(profile)
    assert clean.personal.full_name == ''
    assert clean.education[0].institution == '' if clean.education else True
    assert not clean.skills
