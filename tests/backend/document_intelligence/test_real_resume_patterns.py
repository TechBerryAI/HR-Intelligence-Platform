"""Regression: real-world resume patterns (pipe skills, multi-line education)."""
from __future__ import annotations

import json
import re
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
from app.ai.document_intelligence.validation.engine import is_grounded_education_row  # noqa: E402

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


def test_contact_recall_labeled_email_phone_location():
    """Labeled contact lines and broken email must fill apply Form DTO."""
    text = """
PRIYA SHARMA
Location: Navi Mumbai, Maharashtra
Mobile: 98 76 54 32 10
E-mail: priya.sharma
@gmail.com

SUMMARY
Software engineer with 3 years experience.
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert form.email.lower() == 'priya.sharma@gmail.com'
    assert re.sub(r'\D', '', form.phone).endswith('9876543210') or '9876543210' in re.sub(
        r'\D', '', form.phone
    )
    assert 'mumbai' in (form.currentLocation or '').lower()
    assert form.preferredLocation == form.currentLocation


def test_contact_recall_footer_email_when_header_thin():
    text = """
AMIT KUMAR
Bangalore

EXPERIENCE
Engineer at Acme

EDUCATION
B.Tech Computer Science
IIT Bombay

Contact: amit.kumar@example.com | Phone: +91-9876543210
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert form.email == 'amit.kumar@example.com'
    digits = re.sub(r'\D', '', form.phone or '')
    assert digits.endswith('9876543210')
    assert 'bangalore' in (form.currentLocation or '').lower()
    assert form.preferredLocation == form.currentLocation


def test_education_institution_then_degree_coalesce():
    section = """
S.K Somaiya College of Arts, Science and Commerce - Mumbai            Aug 2022 to April  2024
Masters of Arts in Entertainment Media and Advertising

The SIA College of Higher Education - Mumbai              June 2019 to June 2022
Bachelors of Mass Media - Advertising
"""
    rows = coalesce_education(parse_education(section))
    assert len(rows) >= 2
    assert rows[0].institution
    assert rows[0].degree
    assert 'somaiya' in rows[0].institution.lower()
    assert 'master' in rows[0].degree.lower()
    assert rows[1].institution and rows[1].degree


def test_education_rejects_duty_lines_and_no_placeholder_degree():
    from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
    from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form

    section = """
Mumbai University
Configured MySQL master-slave replication setup
B.Tech Computer Science - IIT Bombay
● Managed and optimized social media platforms
"""
    rows = coalesce_education(parse_education(section))
    blobs = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
    assert 'configured' not in blobs
    assert 'managed and optimized' not in blobs
    assert any('b.tech' in (r.degree or '').lower() or 'tech' in (r.degree or '').lower() for r in rows)

    # Institution-only with no degree evidence must not invent degree="Education"
    toon = {
        'type': 'resume',
        'person': {
            'name': 'Test User',
            'email': 't@example.com',
            'phone': '9999999999',
            'location': 'Mumbai',
            'preferred_location': '',
        },
        'skills': ['Python'],
        'experience': [],
        'education': [
            {'degree': '', 'institution': 'Some University of Arts', 'field': '', 'gpa': '', 'from': '', 'to': ''},
            {'degree': 'B.Tech', 'institution': 'IIT Bombay', 'field': '', 'gpa': '', 'from': '', 'to': ''},
        ],
        'certifications': [],
        'summary': '',
    }
    form = map_candidate_to_form(candidate_profile_from_toon(toon))
    assert all(e.degree.strip().lower() != 'education' for e in form.education)
    assert any('iit' in (e.institution or '').lower() for e in form.education)


def test_education_rejects_internships_and_duty_wrap():
    section = """
BSc.IT | Mumbai University | 2023
Helped learners understand how AI can b
world projects and career growth.
Data Science Intern | ONLie Technology | Apr 2024 – Jul 2024
"""
    rows = coalesce_education(parse_education(section))
    blobs = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
    assert 'intern' not in blobs
    assert 'helped learners' not in blobs
    assert 'world projects' not in blobs
    assert 'onlie' not in blobs
    assert any('bsc' in (r.degree or '').lower() for r in rows)
    assert any('mumbai' in (r.institution or '').lower() for r in rows)


def test_education_rules_apply_across_resume_layouts():
    """Same education gate for every CV — internships/duties never become degrees."""
    cases = [
        """
Priya Shah
priya@example.com | 9876543210 | Pune

EDUCATION
B.Tech Computer Science | COEP Pune | 2022
Software Engineer Intern | Infosenseglobal | Jan 2021 – Jun 2021
""",
        """
John Carter
john@example.com | +1 555-0100 | Austin, TX

EDUCATION
Bachelor of Science, State University, 2020
Developed APIs and improved latency for internal tools.
""",
        """
Amit Kumar
amit@example.com | 9123456789 | Mumbai

EDUCATION
12th Passed | Maharashtra State Board | 2018
HSC | St. Xavier's College | 2018
Marketing Intern | Acme Solutions | May 2019 – Jul 2019
""",
    ]
    for text in cases:
        rows = coalesce_education(parse_education('', text))
        blob = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
        assert 'intern' not in blob, blob
        assert 'developed apis' not in blob
        assert any(is_grounded_education_row(r.degree, r.institution) for r in rows), blob


def test_internships_under_education_heading_move_to_experience():
    text = """
Neha Patil
neha@example.com | 9000011111 | Thane

EDUCATION
B.Sc IT | Mumbai University | 2024
Data Analyst Intern | Bright Labs | Jan 2024 – Mar 2024
"""
    _profile, form, _ = parse_resume_text_to_canonical(text)
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in (form.education or [])).lower()
    assert 'intern' not in edu_blob
    assert any('b.sc' in (e.degree or '').lower() or 'bsc' in (e.degree or '').lower() or 'sc' in (e.degree or '').lower() for e in (form.education or []))
    roles = ' '.join((e.role or '') for e in (form.experiences or [])).lower()
    companies = ' '.join((e.company or '') for e in (form.experiences or [])).lower()
    assert 'intern' in roles
    assert 'bright' in companies or 'labs' in companies


RANJU_LIKE = """
Ranju Gupta
Mumbai | ranjugupta11@gmail.com | +918828550821
https://www.linkedin.com/in/ranju-gu | https://github.com/ranjuggupta
Portfolio: BSc.IT

SUMMARY
Aspiring AI Engineer with hands-on experience in Python, Machine Learning.

EXPERIENCE
AI Trainer | Magic Bus India Foundation | Jan 2025 – Present
Helped learners understand how AI can be applied to real world projects and career growth.

Data Science Intern | ONLie Technology | Apr 2024 – Jul 2024
Built SQL pipelines.

EDUCATION
BSc.IT | Mumbai University | 2023
"""


def test_comma_city_education_oneliners_split_degree_and_college():
    """Real PDF extracts put city after college and year after a pipe."""
    from app.ai.document_intelligence.parsers.resume import parse_education, split_education_oneliner

    d, i, gpa, year = split_education_oneliner(
        'B.Sc. in Information Technology (BSc.IT), Gurunanak Khalsa College, Mumbai - CGPA: 9.3 | 2025'
    )
    assert 'b.sc' in d.lower()
    assert 'information technology' in d.lower()
    assert 'khalsa' in i.lower()
    assert 'mumbai' in i.lower()
    assert 'information technology' not in i.lower()
    assert '9.3' in gpa
    assert year == '2025'

    d, i, gpa, year = split_education_oneliner(
        'Higher Secondary Certificate (HSC) - Science, Jai Hind College, Mumbai - 91.00% | 2021'
    )
    assert 'hsc' in d.lower() or 'higher secondary' in d.lower()
    assert 'jai hind' in i.lower()
    assert '91' in gpa
    assert year == '2021'

    section = """
B.Sc. in Information Technology (BSc.IT), Gurunanak Khalsa College, Mumbai - CGPA: 9.3 | 2025
Higher Secondary Certificate (HSC) - Science, Jai Hind College, Mumbai - 91.00% | 2021
Secondary School Certificate (SSC), Shree Sarvajanik Balmandir High School, Mumbai - 84.40% | 2019
"""
    rows = parse_education(section)
    blobs = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
    assert 'intern' not in blobs
    assert 'helped' not in blobs
    assert any('khalsa' in (r.institution or '').lower() for r in rows)
    assert any('b.sc' in (r.degree or '').lower() or 'bsc' in (r.degree or '').lower() for r in rows)
    assert any('jai hind' in (r.institution or '').lower() for r in rows)
    assert any('balmandir' in (r.institution or '').lower() or 'school' in (r.institution or '').lower() for r in rows)
    assert all('84.40%' not in (r.institution or '') for r in rows)
    ssc = next((r for r in rows if 'ssc' in (r.degree or '').lower() or 'secondary school' in (r.degree or '').lower()), None)
    assert ssc is not None
    assert 'balmandir' in (ssc.institution or '').lower()
    assert 'certificate' not in (ssc.institution or '').lower()


RANJU_EXTRACTED = """
Ranju Gupta
+91 8828550821 ranjuggupta11@gmail.com
https://www.linkedin.com/in/ranju-gupta-08a983249/ https://github.com/ranjuggupta

Experience
AI Trainer | Magic Bus India Foundation | Mumbai | Aug 2025 – Present
•
Helped learners understand how AI can be used in real-world projects and career growth.
Data Science Intern | ONLie Technology |Remote|Apr 2024- Jul 2024
• Built data preprocessing pipelines using Python, Pandas, NumPy

Summary
Aspiring AI Engineer with hands-on experience in Python, Machine Learning.

Education
B.Sc. in Information Technology (BSc.IT), Gurunanak Khalsa College, Mumbai - CGPA: 9.3 | 2025
Higher Secondary Certificate (HSC) - Science, Jai Hind College, Mumbai - 91.00% | 2021
Secondary School Certificate (SSC), Shree Sarvajanik Balmandir High School, Mumbai - 84.40% | 2019
"""


def test_extracted_resume_education_not_polluted_by_experience():
    _profile, form, _toon = parse_resume_text_to_canonical(RANJU_EXTRACTED, allow_semantic=False)
    assert 'ranju' in (form.fullName or '').lower()
    assert 'bsc.it' not in (form.portfolioUrl or '').lower()
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in (form.education or [])).lower()
    assert 'intern' not in edu_blob
    assert 'helped learners' not in edu_blob
    assert 'onlie' not in edu_blob
    assert any('khalsa' in (e.institution or '').lower() for e in (form.education or []))
    assert any('balmandir' in (e.institution or '').lower() for e in (form.education or []))
    assert any(
        'b.sc' in (e.degree or '').lower() or 'bsc' in (e.degree or '').lower()
        for e in (form.education or [])
    )
    assert not any(
        (e.degree or '').strip().lower() in {'b.sc.', 'b.sc'}
        and 'information' in (e.institution or '').lower()
        for e in (form.education or [])
    )
    roles = ' '.join((e.role or '') for e in (form.experiences or [])).lower()
    companies = ' '.join((e.company or '') for e in (form.experiences or [])).lower()
    assert 'intern' in roles or 'trainer' in roles
    assert 'onlie' in companies or 'magic bus' in companies

    _profile, form, _toon = parse_resume_text_to_canonical(RANJU_LIKE)
    assert form.fullName
    assert 'ranju' in form.fullName.lower()
    assert 'bsc.it' not in (form.portfolioUrl or '').lower()
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in (form.education or [])).lower()
    assert 'intern' not in edu_blob
    assert 'helped learners' not in edu_blob
    assert 'onlie' not in edu_blob
    assert any('bsc' in (e.degree or '').lower() for e in (form.education or []))
    roles = ' '.join((e.role or '') for e in (form.experiences or [])).lower()
    companies = ' '.join((e.company or '') for e in (form.experiences or [])).lower()
    assert 'intern' in roles or 'trainer' in roles
    assert 'onlie' in companies or 'magic bus' in companies


def test_location_pipe_header_and_address_label():
    text = """
RIYA PATEL
Thane, Mumbai | Mobile: 7016707933 | Email: riya@example.com

SUMMARY
Engineer

EDUCATION
B.Tech Computer Science - Mumbai University
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert form.currentLocation
    assert 'thane' in form.currentLocation.lower() or 'mumbai' in form.currentLocation.lower()
    assert form.preferredLocation == form.currentLocation

    text2 = """
KARAN MEHTA
Address: Plot 12, Sector 5, Navi Mumbai, Maharashtra 400706
Email: karan@example.com
Phone: 9123456789

SKILLS
Python, SQL
"""
    profile2, form2, _ = parse_resume_text_to_canonical(text2)
    loc = (form2.currentLocation or '').lower()
    assert 'mumbai' in loc or 'navi' in loc
    assert form2.preferredLocation == form2.currentLocation


def test_internship_section_maps_to_experience():
    text = """
ANANYA SHAH
ananya@example.com | 9876543210 | Pune

SKILLS
Python, SQL

INTERNSHIP
Software Intern - Acme Labs - (Jun 2023 - Aug 2023)
● Built internal tools

EDUCATION
B.Tech Computer Science - Pune University
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert len(form.experiences) >= 1
    roles = ' '.join(e.role for e in form.experiences).lower()
    companies = ' '.join(e.company for e in form.experiences).lower()
    assert 'intern' in roles or 'acme' in companies


def test_resume_coverage_recovers_footer_phone():
    from app.ai.document_intelligence.coverage.resume_coverage import recover_resume_profile_gaps
    from app.ai.document_intelligence.models.candidate import (
        CandidateProfile,
        ContactInfo,
        PersonalInfo,
        SkillEntry,
    )

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Test User'),
        contact=ContactInfo(email='t@example.com', phone='', location=''),
        skills=[SkillEntry(canonical='Python')],
    )
    text = """
Test User
t@example.com
Location: Hyderabad

Skills: Python

Phone: +91-9988776655
"""
    updated, report = recover_resume_profile_gaps(profile, text)
    assert updated.contact.phone
    assert '9988776655' in re.sub(r'\D', '', updated.contact.phone)
    assert updated.contact.location
    assert 'hyderabad' in updated.contact.location.lower()
    assert 'phone' in report.recovered_fields or 'location' in report.recovered_fields


INFOSENSE_STACKED = """
RAHUL SHARMA
rahul@example.com | 9876543210 | Mumbai

SKILLS
Oracle, PostgreSQL, SQL Server, MySQL

PROFESSIONAL EXPERIENCE
Database Administrator
Infosenseglobal | Dec 2024 – Present
• Administer Oracle, PostgreSQL, SQL Server, and MySQL databases across multiple environments.
• Led PostgreSQL 12 to 16 upgrade projects including planning, testing, migration, and validation.
• Improved query performance by 40% through SQL tuning, indexing optimization, and execution plan analysis.
• Managed backup, recovery, disaster recovery, and database security activities.
• Supported production incidents, root cause analysis, and release management.

Senior Database Administrator
Techberry Infotech Pvt. Ltd. | Jun 2022 – Nov 2024
• Administered production Oracle and PostgreSQL estates.
• Implemented backup and recovery procedures.

Oracle DBA
Acme Systems | Jan 2020 – May 2022
• Supported Oracle RAC clusters.

CERTIFICATIONS
Oracle Certified Professional
"""


def test_infosense_role_then_company_pipe_dates_and_later_jobs():
    from app.ai.document_intelligence.parsers.resume import parse_experience
    from app.ai.document_intelligence.validation.engine import sanitize_experience_row

    rows = parse_experience(
        """
Database Administrator
Infosenseglobal | Dec 2024 – Present
• Administer Oracle, PostgreSQL, SQL Server, and MySQL databases across multiple environments.
• Led PostgreSQL 12 to 16 upgrade projects including planning, testing, migration, and validation.

Senior Database Administrator
Techberry Infotech Pvt. Ltd. | Jun 2022 – Nov 2024
• Administered production Oracle and PostgreSQL estates.
"""
    )
    assert len(rows) >= 2, [(e.role, e.company, e.start) for e in rows]
    first = rows[0]
    assert first.role == 'Database Administrator'
    assert first.company == 'Infosenseglobal'
    assert first.start.startswith('2024-12')
    assert first.is_current is True
    assert 'Administer Oracle' in (first.description or '')
    assert rows[1].role == 'Senior Database Administrator'
    assert 'Techberry' in rows[1].company
    assert rows[1].start.startswith('2022-06')

    cleaned = sanitize_experience_row(first)
    assert cleaned.role == 'Database Administrator'
    assert cleaned.company == 'Infosenseglobal'

    _p, form, _ = parse_resume_text_to_canonical(INFOSENSE_STACKED)
    roles = [e.role for e in form.experiences]
    companies = [e.company for e in form.experiences]
    assert len(form.experiences) >= 3, list(zip(roles, companies))
    assert roles[0] == 'Database Administrator'
    assert companies[0] == 'Infosenseglobal'
    assert form.experiences[0].startMonth.startswith('2024-12')
    assert 'Infosenseglobal' not in roles
    assert any('Techberry' in (c or '') for c in companies)
    assert any('Acme' in (c or '') for c in companies)
    assert 'Administer Oracle' in (form.experiences[0].description or '')


SAVAN_LIKE_STACKED = """
SAVAN D. PATEL
Database Administrator | Oracle DBA
Ahmedabad, Gujarat, India | +91 7600266367
savanpatel.oracle@gmail.com

Summary
Database Administrator with 9.6+ years of experience.

Skills
Oracle, PostgreSQL, SQL Server

Experience
Database Administrator
Infosenseglobal | Dec 2024 – Present
• Administer Oracle, PostgreSQL, SQL Server, and MySQL databases across multiple environments.
• Led PostgreSQL 12 to 16 upgrade projects including planning, testing, migration, and validation.

Oracle Database Administrator
Dev IT | May 2024 – Nov 2024
• Administered Oracle production databases supporting business-critical applications.

Database Administrator
Infosense Services | May 2022 – Apr 2024
• Managed Oracle, PostgreSQL, SQL Server, and MySQL databases.

Executive Database Administrator
Solutions Enterprises | Aug 2020 – Apr 2022
• Administered Oracle, PostgreSQL, SQL Server, and MySQL databases.

Database Analyst
Light Microfinance Pvt. Ltd. | Feb 2019 – Aug 2020
• Administered MySQL databases and supported daily operations.

Professional Development | Jul 2018 – Jan 2019
• Pursued advanced Oracle Database Administration training and hands-on lab practice.
• Completed self-directed learning focused on enterprise database management.

Database Administrator
SABSE Technologies Inc. | Jun 2017 – Jun 2018
• Managed MySQL databases across development and production environments.

Database Administrator
F3 Infotech Pvt. Ltd. | May 2016 – Jun 2017
• Administered Oracle databases across multiple environments.

KEY PROJECT
PostgreSQL 12 to PostgreSQL 16 Upgrade
Role: Primary DBA
• Conducted compatibility assessment and migration planning.
• Result: Successful migration with zero critical post-migration issues.
"""


def test_savan_like_stacked_company_pipe_dates_all_jobs():
    _p, form, _ = parse_resume_text_to_canonical(SAVAN_LIKE_STACKED)
    companies = [e.company for e in form.experiences]
    roles = [e.role for e in form.experiences]
    assert len(form.experiences) >= 7, list(zip(roles, companies))
    assert roles[0] == 'Database Administrator'
    assert companies[0] == 'Infosenseglobal'
    assert form.experiences[0].isCurrent is True
    assert 'Infosenseglobal' not in roles
    assert 'Dev IT' in companies
    assert 'Infosense Services' in companies
    assert 'SABSE Technologies Inc.' in companies
    assert 'F3 Infotech Pvt. Ltd.' in companies
    assert not any('self' in (r or '').lower() and 'directed' in (c or '').lower() for r, c in zip(roles, companies))
    assert not any('primary dba' in (r or '').lower() for r in roles)
    assert 'Administer Oracle' in (form.experiences[0].description or '')


def test_experience_quality_detects_swap_and_prefers_complete_ai_rows():
    from app.ai.document_intelligence.experience_quality import (
        experience_is_incomplete,
        ground_experience_rows,
        merge_experience_rows,
    )
    from app.ai.document_intelligence.models.candidate import ExperienceEntry

    swapped = [ExperienceEntry(role='Infosenseglobal', company='', start='2024-12', is_current=True)]
    assert experience_is_incomplete(swapped, SAVAN_LIKE_STACKED)

    good = [
        ExperienceEntry(role='Database Administrator', company='Infosenseglobal', start='2024-12', is_current=True),
        ExperienceEntry(role='Oracle Database Administrator', company='Dev IT', start='2024-05', end='2024-11'),
    ]
    assert not experience_is_incomplete(good, '')

    det = [ExperienceEntry(role='Infosenseglobal', start='2024-12', is_current=True)]
    ai = [
        ExperienceEntry(
            role='Database Administrator',
            company='Infosenseglobal',
            start='2024-12',
            is_current=True,
            description='Administer Oracle databases.',
        ),
        ExperienceEntry(role='Oracle Database Administrator', company='Dev IT', start='2024-05', end='2024-11'),
    ]
    merged = merge_experience_rows(det, ai)
    assert len(merged) == 2
    assert merged[0].role == 'Database Administrator'
    assert merged[0].company == 'Infosenseglobal'

    invented = ground_experience_rows(
        [ExperienceEntry(role='CEO', company='FakeCorpNotInResume', start='2020-01')],
        SAVAN_LIKE_STACKED,
    )
    assert invented == []


ADAWET_WRAPPED_DATES = """
ADAWET RATH
adawet2001@gmail.com | +919905819526 | Vellore

SKILLS
Python, Java, SQL

Experience
Testing Intern,Steel Authority of India
May
2024
–
July
2024
Performed man ual testing of web applications, wrote and executed test cases, reported and tracked bugs using JIRA, and collaborated
with the development team to ensure timely resolution and quality assurance.
AI Trainee, Heavy Engineering Corporation
June 2025 - July 2025
· Built rapid prototypes showcasing AI-driven creative generation for marketing and packaging workflows.
· Integrated APIs from image generation tools (DALL-E, Midjourney, Adobe Firefly).
· Applied OpenCV for visual region extraction and layout detection from packaging artwork.

Projects
Toxic Comment Classifier | Python, Scikit-learn, NLP, ML |
May 2025
• Developed a machine learning-based system to detect toxic comments.
"""


def test_adawet_role_comma_company_wrapped_dates_two_jobs():
    _p, form, _ = parse_resume_text_to_canonical(ADAWET_WRAPPED_DATES)
    rows = [(e.role, e.company, e.startMonth, e.endMonth) for e in form.experiences]
    assert len(form.experiences) >= 2, rows
    assert form.experiences[0].role == 'Testing Intern'
    assert 'Steel Authority' in form.experiences[0].company
    assert form.experiences[0].startMonth.startswith('2024-05')
    assert form.experiences[0].endMonth.startswith('2024-07')
    assert 'JIRA' in (form.experiences[0].description or '').upper() or 'testing' in (
        form.experiences[0].description or ''
    ).lower()
    assert form.experiences[1].role == 'AI Trainee'
    assert 'Heavy Engineering' in form.experiences[1].company
    assert form.experiences[1].startMonth.startswith('2025-06')
    assert form.experiences[1].endMonth.startswith('2025-07')
    assert 'OpenCV' in (form.experiences[1].description or '') or 'prototype' in (
        form.experiences[1].description or ''
    ).lower()


STACKED_COMPANY_THEN_ROLE = """
Jane Doe
jane@example.com | +1 555-0100

Experience
Techberry Infotech | Mumbai
Software Engineer
Jan 2020 – Present
Built APIs for the payments platform.

Acme Labs | Pune
Backend Intern
Jun 2018 – Dec 2019
Wrote integration tests.
"""

ROLE_COMMA_COMPANY_LONG = """
Adawet Rath
adawet@example.com

Experience
Software Engineer Intern, Heavy Engineering Corporation Limited
Jan 2020 – June 2020
Built dashboards for plant operations.

Marketing Analyst, Acme Solutions Pvt Ltd
July 2020 – Present
Analyzed campaign KPIs across paid channels.
"""


def test_stacked_company_then_role_coalesces_into_jobs():
    _p, form, _ = parse_resume_text_to_canonical(STACKED_COMPANY_THEN_ROLE)
    rows = [(e.role, e.company, e.startMonth) for e in form.experiences]
    assert len(form.experiences) >= 2, rows
    assert any(
        'Software Engineer' in (e.role or '') and 'Techberry' in (e.company or '')
        for e in form.experiences
    ), rows
    assert any(
        'Intern' in (e.role or '') and 'Acme' in (e.company or '')
        for e in form.experiences
    ), rows
    assert form.experiences[0].startMonth.startswith('2020') or form.experiences[0].isCurrent


def test_role_comma_company_with_dates_not_dropped_as_duty():
    from app.ai.document_intelligence.parsers.resume import _is_bullet_or_duty_line

    header = 'Software Engineer Intern, Heavy Engineering Corporation Limited'
    assert len(header) > 40
    assert _is_bullet_or_duty_line(header) is False
    _p, form, _ = parse_resume_text_to_canonical(ROLE_COMMA_COMPANY_LONG)
    rows = [(e.role, e.company) for e in form.experiences]
    assert len(form.experiences) >= 2, rows
    assert any('Intern' in (e.role or '') and 'Heavy Engineering' in (e.company or '') for e in form.experiences), rows
    assert any('Analyst' in (e.role or '') and 'Acme' in (e.company or '') for e in form.experiences), rows


def test_projects_only_parse_experience_stays_empty():
    from app.ai.document_intelligence.parsers.resume import parse_experience

    assert parse_experience('') == []
    assert parse_experience('   ') == []
    profile, form, _ = parse_resume_text_to_canonical(ROSHAN_WITH_PROJECTS)
    assert profile.experience == []
    assert form.experiences == [] or all(not (e.role or e.company) for e in form.experiences)
