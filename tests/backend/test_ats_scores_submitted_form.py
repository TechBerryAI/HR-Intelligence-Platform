"""The ATS must score what the candidate submitted, not only what the parser guessed.

`parsed_resumes.toon` is written once at parse time and never revised, so
corrections made on the Apply screen used to be invisible to matching — while
skills carry 60% of the ATS weight.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ['ATS_API_URL'] = ''
os.environ['ATS_API_KEY'] = ''
os.environ['ATS_NARRATIVE_LLM'] = '0'
os.environ['DOCUMENT_INTELLIGENCE_SEMANTIC_AI'] = 'false'

from app.ai.document_intelligence.mapping.resume_form import apply_form_to_resume_toon
from app.domains.recruitment.services.ats_service import _internal_match

PARSED = {
    'type': 'resume',
    'person': {'name': 'Alex Dev', 'email': 'alex@example.com', 'phone': '555', 'location': 'Pune'},
    'skills': ['Excel'],
    'experience': [{'title': 'Intern', 'company': 'Tiny Co', 'from': '2019', 'to': '2020'}],
    'education': [{'degree': 'B.S. Computer Science', 'institution': 'State U'}],
}

JD = {
    'type': 'job_description',
    'title': 'Senior Python Developer',
    'location': 'Remote',
    'mandatory_skills': ['Python', 'Django', 'PostgreSQL'],
    'preferred_skills': ['AWS'],
    'qualifications': ['Bachelor degree in Computer Science'],
    'min_experience_years': 5,
}


def test_corrected_skills_reach_the_ats():
    """The parser found 'Excel'; the candidate corrected it on the form."""
    form = {'_skills': ['Python', 'Django', 'PostgreSQL']}

    before = _internal_match(PARSED, JD)
    after = _internal_match(apply_form_to_resume_toon(PARSED, form), JD)

    assert before['mandatory_skills_match_pct'] == 0.0
    assert after['mandatory_skills_match_pct'] == 100.0
    assert after['overall_match_score'] > before['overall_match_score']


def test_skills_accepted_as_a_comma_string():
    out = apply_form_to_resume_toon(PARSED, {'skills': 'Python, Django ,PostgreSQL'})
    assert out['skills'] == ['Python', 'Django', 'PostgreSQL']


def test_deleting_a_hallucinated_row_is_honoured():
    """An empty list that the form actually sent is a correction, not a gap."""
    out = apply_form_to_resume_toon(PARSED, {'experiences': []})
    assert out['experience'] == []


def test_absent_keys_leave_the_parse_alone():
    out = apply_form_to_resume_toon(PARSED, {'fullName': 'Alex Dev'})
    assert out['skills'] == ['Excel']
    assert out['experience'] == PARSED['experience']
    assert out['education'] == PARSED['education']


def test_blank_required_scalar_does_not_wipe_the_parsed_value():
    """A blank scalar means the field was never rendered, not cleared."""
    out = apply_form_to_resume_toon(PARSED, {'email': '', 'phone': ''})
    assert out['person']['email'] == 'alex@example.com'
    assert out['person']['phone'] == '555'


def test_form_rows_map_onto_the_toon_shape_the_ats_reads():
    form = {
        'experiences': [
            {'role': 'Engineer', 'company': 'Acme', 'startMonth': '2020-01',
             'endMonth': '', 'isCurrent': True, 'description': 'Built APIs'},
        ],
        'education': [
            {'degree': 'B.Tech', 'institution': 'IIT', 'cgpa': '8.5',
             'startMonth': '2015-06', 'endMonth': '2019-05'},
        ],
        'certifications': [
            {'name': 'AWS SAA', 'issuer': 'Amazon', 'validTill': '2027-01',
             'validationUrl': 'https://aws.example/verify', 'status': 'active'},
        ],
    }
    out = apply_form_to_resume_toon(PARSED, form)

    assert out['experience'] == [
        {'title': 'Engineer', 'company': 'Acme', 'from': '2020-01',
         'to': 'Present', 'description': 'Built APIs'},
    ]
    assert out['education'] == [
        {'degree': 'B.Tech', 'institution': 'IIT', 'gpa': '8.5',
         'from': '2015-06', 'to': '2019-05'},
    ]
    assert out['certifications'][0]['name'] == 'AWS SAA'
    assert out['certifications'][0]['url'] == 'https://aws.example/verify'


def test_blank_rows_from_the_ui_are_dropped():
    form = {'education': [{'degree': '', 'institution': ''}, {'degree': 'B.Tech', 'institution': 'IIT'}]}
    out = apply_form_to_resume_toon(PARSED, form)
    assert len(out['education']) == 1


def test_the_stored_parse_is_not_mutated():
    snapshot = {'skills': list(PARSED['skills']), 'person': dict(PARSED['person'])}
    apply_form_to_resume_toon(PARSED, {'_skills': ['Rust'], 'fullName': 'Someone Else'})
    assert PARSED['skills'] == snapshot['skills']
    assert PARSED['person'] == snapshot['person']


def test_empty_or_missing_form_is_a_no_op():
    assert apply_form_to_resume_toon(PARSED, {}) == PARSED
    assert apply_form_to_resume_toon(PARSED, None) == PARSED


def test_corrected_location_moves_the_location_score():
    jd = dict(JD, location='Mumbai')
    before = _internal_match(PARSED, jd)
    after = _internal_match(apply_form_to_resume_toon(PARSED, {'currentLocation': 'Mumbai'}), jd)
    assert after['overall_match_score'] > before['overall_match_score']
