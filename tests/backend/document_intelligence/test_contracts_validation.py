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
    is_grounded_education_row,
    sanitize_candidate_profile,
    validate_degree,
    validate_institution,
    validate_person_name,
    validate_skill_item,
    validate_url,
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


def test_degree_rejects_job_titles_and_duty_prose():
    assert validate_degree('B.Tech')[0] is True
    assert validate_degree('BSc.IT')[0] is True
    assert validate_degree('Bachelors of Mass Media - Advertising')[0] is True
    assert validate_degree('Data Science Intern')[0] is False
    assert validate_degree('Helped learners understand how AI can b')[0] is False
    assert validate_degree('world projects and career growth.')[0] is False


def test_institution_rejects_companies_and_sentence_fragments():
    assert validate_institution('Mumbai University')[0] is True
    assert validate_institution('State U')[0] is True
    assert validate_institution('ONLie Technology')[0] is False
    assert validate_institution('world projects and career growth.')[0] is False
    assert validate_institution('Magic Bus India Foundation')[0] is False
    assert validate_institution('84.40%')[0] is False
    assert validate_institution('Information Technology (BSc.IT), Gurunanak Khalsa College, Mumbai')[0] is True


def test_grounded_education_row_is_layout_agnostic():
    assert is_grounded_education_row('B.Tech', 'Pune University') is True
    assert is_grounded_education_row('Bachelor of Science', 'State University') is True
    assert is_grounded_education_row('12th Passed', 'Maharashtra State Board') is True
    assert is_grounded_education_row('HSC', "St. Xavier's College") is True
    assert is_grounded_education_row('Software Engineer Intern', 'Infosenseglobal') is False
    assert is_grounded_education_row('Developed APIs', 'internal tools') is False
    assert is_grounded_education_row('Marketing Intern', 'Acme Solutions') is False
    assert is_grounded_education_row('Data Science Intern', 'Bright Labs') is False


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
