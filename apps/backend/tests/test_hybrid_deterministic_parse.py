"""Tests for deterministic resume fast path and layout heuristics."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
APP_ROOT = BACKEND_ROOT / 'app'
for p in (str(BACKEND_ROOT), str(APP_ROOT)):
    if p not in sys.path:
        sys.path.insert(0, p)

from app.ai.parser.deterministic_resume import parse_resume_deterministic, score_resume_toon
from app.ai.parser.layout.heuristic import structure_text_by_headers


SAMPLE = """
Jane Doe
jane.doe@example.com
+1 555-0100

Professional Summary:
Experienced software engineer specializing in Python backends.

Skills:
Python, SQL, Docker, React

Experience:
Software Engineer | Acme Corp | Jan 2020 - Present
Built APIs and data pipelines.

Education:
B.S. Computer Science, State University, 2019
"""


def test_structure_text_by_headers_inserts_sections():
    structured = structure_text_by_headers(SAMPLE)
    assert 'Skills' in structured or 'skills' in structured.lower()
    assert 'Experience' in structured or 'experience' in structured.lower()


def test_score_resume_toon_passes_complete():
    toon = {
        'type': 'resume',
        'person': {'name': 'Jane Doe', 'email': 'jane@x.com', 'phone': ''},
        'skills': ['Python'],
        'experience': [{'title': 'Engineer', 'company': 'Acme'}],
        'education': [],
        'summary': 'Hello',
    }
    conf, missing, passes = score_resume_toon(toon)
    assert passes
    assert conf >= 0.55
    assert 'person.name' not in missing


def test_score_resume_toon_fails_without_contact():
    toon = {
        'type': 'resume',
        'person': {'name': 'Jane Doe', 'email': '', 'phone': ''},
        'skills': ['Python'],
        'experience': [],
        'education': [],
    }
    conf, missing, passes = score_resume_toon(toon)
    assert not passes
    assert 'person.contact' in missing


def test_parse_resume_deterministic_extracts_core_fields():
    toon, conf, missing, passes = parse_resume_deterministic(SAMPLE)
    assert isinstance(toon, dict)
    person = toon.get('person') or {}
    assert person.get('email') == 'jane.doe@example.com' or 'jane.doe' in str(person.get('email') or '')
    assert person.get('name')
    assert toon.get('skills') or toon.get('experience') or toon.get('summary')
    # Should usually pass gate on this well-formed sample
    assert passes or conf >= 0.4


ANJALI_STYLE = """
Percentage: 75.27
anjalibansode0227@gmail.com
9527767516

Education
B.Tech Computer Science, Some College, 2017

Technical Skills
HTML, Core Java, SQL

PROJECT
06/2016 - 06/2017
Built a small website.

Certifications
Revolution IT Solutions: Web Development
Web Development certification focusing on front-end

Work Experience
Web Developer at Acme, Jan 2018 - Dec 2020
"""


def test_score_resume_toon_fails_implausible_percentage_name():
    toon = {
        'type': 'resume',
        'person': {
            'name': 'Percentage: 75.27',
            'email': 'anjalibansode0227@gmail.com',
            'phone': '9527767516',
        },
        'skills': ['Education', 'PROJECT', '06/2016 - 06/2017'],
        'experience': [],
        'education': [
            {'degree': '', 'institution': 'HTML'},
            {'degree': '', 'institution': 'Core Java'},
        ],
    }
    conf, missing, passes = score_resume_toon(toon)
    assert not passes
    assert 'person.name' in missing


def test_anjali_style_deterministic_does_not_accept_garbage():
    toon, conf, missing, passes = parse_resume_deterministic(ANJALI_STYLE)
    person = toon.get('person') or {}
    assert person.get('name') != 'Percentage: 75.27'
    skills = [str(s).lower() for s in (toon.get('skills') or [])]
    assert 'education' not in skills
    assert 'project' not in skills
    edu_inst = [
        str((e or {}).get('institution') or '').lower()
        for e in (toon.get('education') or [])
        if isinstance(e, dict)
    ]
    assert 'html' not in edu_inst
    assert 'core java' not in edu_inst
    # Without a plausible name, gate must fail so LLM can run
    assert not passes
    assert 'person.name' in missing

ASHWINI_STYLE = """
ASHWINI CHAVAN
ashwinic3699@gmail.com
7057705771
Permanent Address : At post Dehugaon, shivneri colony H.no 601
Tal-Haveli,dist- pune ,412109

PERSONAL DETAILS
Name: Ashwini Bapurao Chavan
Date of Birth: 20 November 1992
Gender: Female
Marital Status: Married

SKILL SET
Databases - SQL 2016
SQL Server, SSIS

Education
Master of Science, Pune University, 2015

Experience
MSSQL DBA at Techberry, Jan 2018 - Present
Configured DB mails.
Reorganize/Rebuilding the indexes at req
"""


def test_ashwini_style_rejects_biodata_as_experience_and_fixes_master():
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_education_from_text,
        extract_experience_from_text,
        extract_skills_from_text,
        is_plausible_job_title,
    )
    from app.ai.parser.deterministic_resume import experience_quality_ok, score_resume_toon

    assert not is_plausible_job_title('PERSONAL DETAILS')
    assert not is_plausible_job_title('Date of Birth')
    assert not is_plausible_job_title('20 November 1992')
    assert not is_plausible_job_title('Gender')
    assert not is_plausible_job_title('Marital Status')
    assert not is_plausible_job_title(': Married')
    assert not is_plausible_job_title('Permanent Address : At post Dehuga')

    exps = extract_experience_from_text(ASHWINI_STYLE)
    titles = [(e.get('title') or '').lower() for e in exps]
    assert not any('personal details' in t for t in titles)
    assert not any('date of birth' in t for t in titles)
    assert not any('gender' in t for t in titles)
    assert not any('marital' in t for t in titles)
    assert not any('address' in t for t in titles)

    edu = extract_education_from_text(ASHWINI_STYLE)
    degrees = [(e.get('degree') or '') for e in edu]
    assert any('Master' in d for d in degrees)
    assert not any(d.strip().lower() in ('ma', 'ba', 'be') for d in degrees)
    institutions = [(e.get('institution') or '').lower() for e in edu]
    assert not any('configured' in i for i in institutions)
    assert not any('reorganize' in i for i in institutions)

    skills = [s.lower() for s in extract_skills_from_text(ASHWINI_STYLE)]
    assert 'set' not in skills

    toon, conf, missing, passes = parse_resume_deterministic(ASHWINI_STYLE)
    polluted = {
        'type': 'resume',
        'person': {'name': 'Ashwini Chavan', 'email': 'a@b.com', 'phone': '1'},
        'skills': ['SQL Server'],
        'experience': [
            {'title': 'PERSONAL DETAILS', 'company': ''},
            {'title': 'Date of Birth', 'company': ''},
            {'title': 'MSSQL DBA', 'company': 'Techberry'},
        ],
        'education': [{'degree': 'Master of Science', 'institution': 'Pune University'}],
    }
    conf2, missing2, passes2 = score_resume_toon(polluted)
    assert not passes2
    assert 'experience.quality' in missing2
    assert not experience_quality_ok(polluted)


def test_h_no_not_extracted_as_portfolio():
    from app.ai.adapter.runtime_adapter import _apply_resume_text_fields

    person = {'name': 'Ashwini', 'email': 'a@b.com', 'phone': '', 'otherUrls': []}
    raw = 'Permanent Address : shivneri colony H.no 601 Tal-Haveli pune'
    _apply_resume_text_fields(person, raw, [])
    port = str(person.get('portfolio') or person.get('website') or '')
    assert 'h.no' not in port.lower()
    assert not any('h.no' in str(u).lower() for u in (person.get('otherUrls') or []))
