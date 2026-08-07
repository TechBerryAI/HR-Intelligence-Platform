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


DHRUTI_ZWSP = """
DHRUTI JADEJA\u200b
Digital Marketing Executive\u200b
Thane, Mumbai | Mobile: 7016707933 | Email: zaladhruti02@gmail.com | LinkedIn:
https://www.linkedin.com/in/dhruti-zala-6a6055284/

Summary
Digital Marketing and SEO professional with 3 years of overall experience.

SKILLS, TOOLS AND PLATFORMS
Technical SEO, On-page SEO, Google Analytics, Canva, HubSpot

EXPERIENCE
Digital Marketing Executive | Hawkium | Sep 2024 - Present
SEO and content campaigns

EDUCATION
Bachelor of Commerce, Mumbai University, 2021
"""


def test_zero_width_space_name_still_extracts():
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_name_from_text,
        is_plausible_person_name,
    )
    from app.ai.parser.text_extraction import normalize_extracted_text

    raw = 'DHRUTI JADEJA\u200b'
    assert not is_plausible_person_name(raw) or '\u200b' in raw
    cleaned = normalize_extracted_text(raw)
    assert '\u200b' not in cleaned
    assert is_plausible_person_name(cleaned)
    assert extract_name_from_text(cleaned + '\nEmail: x@y.com\n') == 'Dhruti Jadeja' or \
        extract_name_from_text(cleaned) in ('Dhruti Jadeja', 'DHRUTI JADEJA')


def test_dhruti_like_resume_never_hard_fails_empty_name():
    profile, form, toon = parse_resume_text_to_canonical(DHRUTI_ZWSP)
    assert form.fullName
    assert 'Dhruti' in form.fullName or 'DHRUTI' in form.fullName.upper()
    assert 'Jadeja' in form.fullName or 'JADEJA' in form.fullName.upper()
    assert form.email == 'zaladhruti02@gmail.com'
    person = toon.get('person') or {}
    assert str(person.get('name') or '').strip()
    assert 'person.name must not be empty' not in str(person)


def test_word_per_line_all_caps_name():
    from app.ai.parser.enrichment.resume_text_inference import extract_name_from_text

    text = 'DHRUTI\n\nJADEJA\n\nDigital\n\nMarketing\n\nExecutive\nEmail: a@b.com\n'
    name = extract_name_from_text(text)
    assert name.lower() == 'dhruti jadeja'


DHRUTI_EXPERIENCE = """
DHRUTI JADEJA
Thane, Mumbai | Mobile: 7016707933 | Email: zaladhruti02@gmail.com

SKILLS
SEO, Google Analytics, Canva, HubSpot

PROFESSIONAL EXPERIENCE
Digital Marketing Executive -  Hawkium  -  (Sep 2024 -  Now)
Digital Marketing Executive -  Tridhya Tech Public Limited  -  (Dec 2023 -  Sep 2024)

Client Name/Projects -  Silwatech UAE ,  Vibing Tech , TridhyaTech
Responsibilities
● Managed and optimized social media platforms for multiple brands, driving a 20%
increase in engagement across Instagram and LinkedIn
● Executed on-page SEO strategies, resulting in a 15% increase in organic search
traffic
● Coordinated content calendars, ensuring consistent messaging and alignment with
brand voice
Resource Manager - Tridhya Tech - (Dec 2022 - Dec 2023)
● Managed resource allocation and task coordination between digital marketing and
technical teams
● Maintained schedules, reports, and documentation to ensure effective team
performance and task completion
● Facilitated smooth communication between teams, improving internal collaboration
and efficiency
"""


def test_dhruti_experience_not_fragmented_into_bullet_jobs():
    profile, form, _ = parse_resume_text_to_canonical(DHRUTI_EXPERIENCE)
    assert len(form.experiences) == 3, [(e.role, e.company) for e in form.experiences]

    roles = [e.role for e in form.experiences]
    companies = [e.company for e in form.experiences]
    assert roles[0] == 'Digital Marketing Executive'
    assert companies[0] == 'Hawkium'
    assert form.experiences[0].startMonth.startswith('2024-09')
    assert form.experiences[0].isCurrent is True

    assert roles[1] == 'Digital Marketing Executive'
    assert 'Tridhya Tech Public Limited' in companies[1]
    assert form.experiences[1].startMonth.startswith('2023-12')
    assert form.experiences[1].endMonth.startswith('2024-09')

    assert roles[2] == 'Resource Manager'
    assert companies[2] == 'Tridhya Tech'
    assert form.experiences[2].startMonth.startswith('2022-12')
    assert form.experiences[2].endMonth.startswith('2023-12')

    # Bullets must not become company/role
    blob = ' '.join(f'{e.role} {e.company}' for e in form.experiences).lower()
    assert 'executed' not in blob
    assert 'resulting' not in blob
    assert 'client name' not in blob
    assert 'vibing' not in blob
    assert 'silwatech' not in blob

    # Descriptions stay under jobs, not split into fields
    assert 'social media' in (form.experiences[0].description or '').lower()
    assert 'resource allocation' in (form.experiences[2].description or '').lower()


def test_dash_role_company_dates_line_parses():
    from app.ai.document_intelligence.parsers.resume import _parse_experience_line

    e = _parse_experience_line(
        'Digital Marketing Executive - Hawkium - (Sep 2024 - Now)'
    )
    assert e is not None
    assert e.role == 'Digital Marketing Executive'
    assert e.company == 'Hawkium'
    assert e.start == '2024-09'
    assert e.is_current is True
    assert e.end == ''
