"""Regression: real-world resume patterns (pipe skills, multi-line education)."""
from __future__ import annotations

import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.models.candidate import EducationEntry  # noqa: E402
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    coalesce_education,
    parse_education,
)
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402

ROSHAN_LIKE = """
R O S H A N  P A N I C K E R

Dombivili, Maharashtra, India    |   +917977279647
https://www.linkedin.com/in/roshan-panicker-447865213     |   roshuraj99@gmail.com

DIGITAL MARKETING SPECIALIST

I am a Digital marketing Specialist, specialized in making ad campaigns on Google and Meta.

SKILLS AND ABILITIES

Communication Skills │Organizational Skills │Talent Skills │ Team Contributing Skills │ Time
Management Skills │ Google Analytics │ Canva │ Microsoft Word │ Microsoft PowerPoint │
Facebook Ads Manager │ Social Media Strategy Skills  │Social Media Engagement Skills│ Content
making skills │ Research skills

EDUCATION

S.K Somaiya College of Arts, Science and Commerce - Mumbai            Aug 2022 to April  2024
Masters of Arts in Entertainment Media and Advertising

The SIA College of Higher Education - Mumbai              June 2019 to June 2022
Bachelors of Mass Media - Advertising

The South Indian Association, High School and Junior College            June 2018 to April 2019
12th Passed in Arts

Indian School Al Ghubra, Muscat, Sultanate of Oman             April 2016 to May 2017
10th Passed in SSC level
"""

ROSHAN_WITH_PROJECTS = """
R O S H A N  P A N I C K E R

Dombivili, Maharashtra, India    |   +917977279647
https://www.linkedin.com/in/roshan-panicker-447865213     |   roshuraj99@gmail.com

DIGITAL MARKETING SPECIALIST

I am a Digital marketing Specialist, specialized in making ad campaigns on Google and Meta.

SKILLS AND ABILITIES

Communication Skills │ Google Analytics │ Canva │ Facebook Ads Manager

EDUCATION

S.K Somaiya College of Arts, Science and Commerce - Mumbai            Aug 2022 to April  2024
Masters of Arts in Entertainment Media and Advertising

The SIA College of Higher Education - Mumbai              June 2019 to June 2022
Bachelors of Mass Media - Advertising

The South Indian Association, High School and Junior College            June 2018 to April 2019
12th Passed in Arts

Indian School Al Ghubra, Muscat, Sultanate of Oman             April 2016 to May 2017
10th Passed in SSC level

PROJECTS

Coursera Assignment - Digital Marketing Campaign for OOTY KAFFEE
Designed Meta ads and Google Search campaigns for a fictional brand.

College Assignment - Social Media Strategy
Built a content calendar and engagement plan for a campus brand.
"""

ROSHAN_WRAPPED_EDU = """
R O S H A N  P A N I C K E R

Dombivili, Maharashtra, India    |   +917977279647
roshuraj99@gmail.com

SKILLS AND ABILITIES
Google Analytics │ Canva │ Facebook Ads Manager

EDUCATION

S.K Somaiya College of Arts, Science and Commerce - Mumbai
Aug 2022 to April  2024
Masters of Arts in Entertainment Media and Advertising

The SIA College of Higher
Education - Mumbai              June 2019 to June 2022
Bachelors of Mass Media - Advertising

The South Indian Association, High School and Junior College            June 2018 to April 2019
12th Passed in Arts

Indian School Al Ghubra, Muscat, Sultanate of Oman             April 2016 to May 2017
10th Passed in SSC level
"""


def test_pipe_skills_and_abilities_not_header_crumb():
    _p, form, _ = parse_resume_text_to_canonical(ROSHAN_LIKE)
    skills = [s.strip() for s in form.skills.split(',')]
    assert 'AND ABILITIES' not in form.skills.upper()
    assert 'Google Analytics' in form.skills
    assert 'Canva' in form.skills
    assert 'Research skills' in form.skills
    assert len(skills) >= 12


def test_education_not_split_on_institution_commas():
    _p, form, _ = parse_resume_text_to_canonical(ROSHAN_LIKE)
    assert len(form.education) == 4
    first = form.education[0]
    assert 'Somaiya' in first.institution
    assert 'Science and Commerce' in first.institution
    assert first.degree.startswith('Masters')
    assert first.startMonth.startswith('2022')
    assert first.endMonth.startswith('2024')
    # Must not put half institution in degree
    assert 'Somaiya' not in first.degree
    assert form.education[1].degree.startswith('Bachelors')
    assert 'SIA' in form.education[1].institution


def test_spaced_letter_name():
    _p, form, _ = parse_resume_text_to_canonical(ROSHAN_LIKE)
    assert form.fullName == 'Roshan Panicker'


def test_projects_never_become_experience():
    profile, form, _ = parse_resume_text_to_canonical(ROSHAN_WITH_PROJECTS)
    assert form.experiences == [] or all(
        not (e.role or e.company)
        for e in form.experiences
    )
    roles = ' '.join(
        f'{e.role} {e.company}'
        for e in (form.experiences or [])
    ).lower()
    assert 'coursera' not in roles
    assert 'assignment' not in roles
    assert 'ooty' not in roles
    assert 'college assignment' not in roles
    # Projects still parsed on canonical profile
    assert any(
        'Coursera' in (p.name or '') or 'Assignment' in (p.name or '')
        for p in profile.projects
    ) or len(profile.projects) >= 1
    assert len(form.education) == 4


def test_wrapped_education_still_four_complete_rows():
    _p, form, _ = parse_resume_text_to_canonical(ROSHAN_WRAPPED_EDU)
    assert len(form.education) == 4
    for edu in form.education:
        assert edu.degree.strip(), f'missing degree: {edu}'
        assert edu.institution.strip(), f'missing institution: {edu}'
    first = form.education[0]
    assert 'Somaiya' in first.institution
    assert first.degree.startswith('Masters')
    assert first.startMonth.startswith('2022-08') or first.startMonth.startswith('2022')
    assert '2024-04' in first.endMonth or first.endMonth.startswith('2024')
    tenth = form.education[3]
    assert '2016-04' in tenth.startMonth or tenth.startMonth.startswith('2016')
    assert '2017-05' in tenth.endMonth or tenth.endMonth.startswith('2017')
    # SIA wrap joined
    assert 'SIA' in form.education[1].institution
    assert 'Higher' in form.education[1].institution or 'Education' in form.education[1].institution


def test_coalesce_education_orphan_pairs():
    rows = [
        EducationEntry(
            institution='The SIA College of Higher Education - Mumbai',
            start='2019-06',
            end='2022-06',
        ),
        EducationEntry(degree='Bachelors of Mass Media - Advertising'),
        EducationEntry(degree='Masters of Arts in Entertainment Media'),
        EducationEntry(institution='S.K Somaiya College'),
    ]
    merged = coalesce_education(rows)
    assert len(merged) == 2
    assert merged[0].institution and merged[0].degree
    assert 'SIA' in merged[0].institution
    assert merged[0].degree.startswith('Bachelors')
    assert merged[0].start == '2019-06'
    assert merged[1].degree.startswith('Masters')
    assert 'Somaiya' in merged[1].institution


def test_parse_education_wrapped_section_direct():
    section = """
The SIA College of Higher
Education - Mumbai              June 2019 to June 2022
Bachelors of Mass Media - Advertising
"""
    rows = parse_education(section)
    assert len(rows) == 1
    assert 'SIA' in rows[0].institution
    assert rows[0].degree.startswith('Bachelors')
    assert rows[0].start.startswith('2019')
    assert rows[0].end.startswith('2022')


def test_sse_payload_uuid_json_serializable():
    payload = {
        'raw_file_id': uuid.uuid4(),
        'parsed_id': uuid.uuid4(),
        'status': 'ok',
    }
    # Mirrors parsing.py stream serialization
    dumped = json.dumps(payload, default=str)
    loaded = json.loads(dumped)
    assert isinstance(loaded['raw_file_id'], str)
    assert isinstance(loaded['parsed_id'], str)
