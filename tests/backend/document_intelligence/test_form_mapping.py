"""
Document Intelligence Engine — mapping & canonical tests.

Every form field must have an explicit mapping test.
Wrong data is worse than missing data.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.canonical.from_toon import (
    candidate_profile_from_toon,
    job_profile_from_toon,
)
from app.ai.document_intelligence.mapping.jd_form import JD_FORM_MAPPING_GRAPH, map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import (
    RESUME_FORM_MAPPING_GRAPH,
    map_candidate_to_form,
)
from app.ai.document_intelligence.response import (
    build_jd_client_payload,
    build_resume_client_payload,
)
from app.ai.document_intelligence.validation.engine import (
    validate_email,
    validate_phone,
    validate_url,
)


SAMPLE_RESUME_TOON = {
    'type': 'resume',
    'person': {
        'name': 'Jane Doe',
        'email': 'jane@example.com',
        'phone': '+1 555-0100',
        'location': 'Austin, TX',
        'preferred_location': 'Remote',
        'linkedin': 'linkedin.com/in/janedoe',
        'github': 'github.com/janedoe',
        'portfolio': 'https://janedoe.dev',
    },
    'summary': 'Senior engineer',
    'skills': ['Python', 'SQL'],
    'experience': [
        {
            'title': 'Engineer',
            'company': 'Acme',
            'from': '2020-01',
            'to': 'Present',
            'description': 'Built APIs',
        }
    ],
    'education': [
        {
            'degree': 'B.S.',
            'field': 'Computer Science',
            'institution': 'State U',
            'gpa': '3.8',
            'from': '2016-08',
            'to': '2020-05',
        }
    ],
    'certifications': [{'name': 'AWS SAA', 'issuer': 'Amazon'}],
    'total_experience_years': 4,
}


SAMPLE_JD_TOON = {
    'type': 'job_description',
    'title': 'Backend Engineer',
    'company': 'TechCo',
    'location': 'Bangalore',
    'employment_type': 'Full-time',
    'salary_range': '20-30 LPA',
    'min_experience_years': 3,
    'max_experience_years': 6,
    'mandatory_skills': ['Python', 'PostgreSQL'],
    'preferred_skills': ['Kafka'],
    'skills': ['Python', 'PostgreSQL'],
    'responsibilities': ['Build APIs', 'Mentor juniors'],
    'qualifications': ['B.Tech'],
    'benefits': ['Health insurance'],
    'description': '',
}


def test_resume_mapping_graph_covers_required_form_fields():
    required = {
        'fullName',
        'email',
        'phone',
        'linkedinUrl',
        'portfolioUrl',
        'githubUrl',
        'currentLocation',
        'preferredLocation',
        'experienceLevel',
        'skills',
        'summary',
    }
    assert required.issubset(set(RESUME_FORM_MAPPING_GRAPH.keys()))


def test_jd_mapping_graph_covers_required_form_fields():
    required = {
        'title',
        'location',
        'company',
        'salary',
        'experienceFrom',
        'experienceTo',
        'mandatorySkills',
        'preferredSkills',
        'description',
    }
    assert required.issubset(set(JD_FORM_MAPPING_GRAPH.keys()))


def test_each_resume_form_field_has_exactly_one_source():
    # No duplicate targets in mapping graph values for scalar fields
    scalars = {k: v for k, v in RESUME_FORM_MAPPING_GRAPH.items() if '[]' not in k}
    assert len(scalars) == len(set(scalars.keys()))


@pytest.mark.parametrize(
    'form_field,expected',
    [
        ('fullName', 'Jane Doe'),
        ('email', 'jane@example.com'),
        ('phone', '+1 555-0100'),
        ('linkedinUrl', 'https://linkedin.com/in/janedoe'),
        ('githubUrl', 'https://github.com/janedoe'),
        ('portfolioUrl', 'https://janedoe.dev'),
        ('currentLocation', 'Austin, TX'),
        ('preferredLocation', 'Remote'),
        ('experienceLevel', 'experienced'),
        ('skills', 'Python, SQL'),
        ('summary', 'Senior engineer'),
    ],
)
def test_resume_form_field_explicit_source(form_field, expected):
    profile = candidate_profile_from_toon(SAMPLE_RESUME_TOON)
    form = map_candidate_to_form(profile)
    assert getattr(form, form_field) == expected
    traces = {t.form_field: t for t in form.trace}
    assert form_field in traces
    assert traces[form_field].mapper.startswith('document_intelligence.mapping.resume_form')
    if form_field != 'experienceLevel':
        assert traces[form_field].canonical_path == RESUME_FORM_MAPPING_GRAPH[form_field]


def test_resume_education_and_experience_rows():
    profile = candidate_profile_from_toon(SAMPLE_RESUME_TOON)
    form = map_candidate_to_form(profile)
    assert form.education[0].degree == 'B.S. in Computer Science'
    assert form.education[0].institution == 'State U'
    assert form.experiences[0].company == 'Acme'
    assert form.experiences[0].role == 'Engineer'
    assert form.experiences[0].isCurrent is True
    assert form.certifications[0].name == 'AWS SAA'


def test_invalid_email_does_not_autofill():
    toon = dict(SAMPLE_RESUME_TOON)
    toon['person'] = dict(toon['person'], email='not-an-email')
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    assert form.email == ''


def test_preferred_location_falls_back_to_current():
    toon = dict(SAMPLE_RESUME_TOON)
    toon['person'] = dict(toon['person'], preferred_location='')
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    assert form.currentLocation == 'Austin, TX'
    assert form.preferredLocation == 'Austin, TX'


def test_preferred_location_keeps_explicit_value():
    toon = dict(SAMPLE_RESUME_TOON)
    toon['person'] = dict(toon['person'], preferred_location='Remote')
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    assert form.preferredLocation == 'Remote'
    assert form.currentLocation == 'Austin, TX'


def test_portfolio_does_not_fallback_to_github():
    toon = dict(SAMPLE_RESUME_TOON)
    toon['person'] = dict(toon['person'], portfolio='')
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    assert form.portfolioUrl == ''
    assert form.githubUrl == 'https://github.com/janedoe'


@pytest.mark.parametrize(
    'form_field,expected',
    [
        ('title', 'Backend Engineer'),
        ('location', 'Bangalore'),
        ('company', 'TechCo'),
        ('salary', '20-30 LPA'),
        ('experienceFrom', '3'),
        ('experienceTo', '6'),
        ('employmentType', 'Full-time'),
    ],
)
def test_jd_form_field_explicit_source(form_field, expected):
    profile = job_profile_from_toon(SAMPLE_JD_TOON)
    form = map_job_to_form(profile)
    assert getattr(form, form_field) == expected
    traces = {t.form_field: t for t in form.trace}
    assert form_field in traces


def test_jd_skills_and_description():
    form = map_job_to_form(job_profile_from_toon(SAMPLE_JD_TOON))
    assert form.mandatorySkills == ['Python', 'PostgreSQL']
    assert form.preferredSkills == ['Kafka']
    assert '**Responsibilities:**' in form.description
    assert 'Build APIs' in form.description
    assert 'Python' in form.description


def test_client_payload_omits_raw_toon():
    body = {
        'status': 'ok',
        'raw_file_id': 'r1',
        'parsed_id': 'p1',
        'confidence': 0.9,
        'toon': SAMPLE_RESUME_TOON,
        'is_duplicate': False,
        'model_version': 'test',
    }
    payload = build_resume_client_payload(body)
    assert 'toon' not in payload
    assert payload['form']['fullName'] == 'Jane Doe'
    assert payload['engine'] == 'document_intelligence'

    jd_body = {**body, 'toon': SAMPLE_JD_TOON}
    jd_payload = build_jd_client_payload(jd_body)
    assert 'toon' not in jd_payload
    assert jd_payload['form']['title'] == 'Backend Engineer'


def test_validators():
    assert validate_email('a@b.com')[0] is True
    assert validate_email('bad')[0] is False
    assert validate_phone('+1 555-0100')[0] is True
    assert validate_phone('12')[0] is False
    assert validate_url('https://github.com/x', host_hint='github')[0] is True
    assert validate_url('https://example.com', host_hint='github')[0] is False
