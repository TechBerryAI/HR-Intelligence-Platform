"""Education coalesce, skill sanitization, and gated preamble-job recovery.

No candidate names, employers, filenames, coordinates, or resume-specific rules.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    coalesce_education,
    parse_education,
    parse_experience,
    parse_resume_from_sections,
    parse_skills,
)
from app.ai.document_intelligence.validation.engine import validate_skill_item  # noqa: E402
from app.ai.document_intelligence.models.candidate import EducationEntry  # noqa: E402
from app.ai.document_intelligence.sections import detect_sections  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import is_biodata_or_address_line  # noqa: E402


def test_biodata_is_not_an_education_institution():
    assert is_biodata_or_address_line(': Male') is True
    assert is_biodata_or_address_line('Male') is True
    rows = parse_education(
        'Education\n:   Male\nuser@example.com\nFather\'s Name: Alex Parent\n',
        '',
    )
    blob = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
    assert 'male' not in blob
    assert 'example.com' not in blob
    assert 'father' not in blob


def test_split_degree_and_college_coalesce_to_one_row():
    rows = coalesce_education(
        [
            EducationEntry(degree='B.Tech Computer Science', institution=''),
            EducationEntry(degree='', institution='State Institute of Technology'),
        ]
    )
    assert len(rows) == 1
    assert 'b.tech' in (rows[0].degree or '').lower()
    assert 'state institute' in (rows[0].institution or '').lower()


def test_empty_education_header_recovers_degree_from_document():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Education\n\n'
        'Summary\nSeeking an IT role.\n'
        'B.Sc. Information Technology, State University, 2022\n'
        'Skills\nPython, SQL\n'
    )
    rows = parse_education('Education', text)
    assert any((r.degree or '').strip() and (r.institution or '').strip() for r in rows)
    assert any('b.sc' in (r.degree or '').lower() or 'bsc' in (r.degree or '').lower() for r in rows)


def test_internship_under_education_still_becomes_a_job():
    edu = (
        'Software Intern | Northwind Traders | Jun 2020 - Aug 2020\n'
        'Built reporting dashboards.\n'
        'B.E. Computer, Harbor College, 2021\n'
    )
    jobs = parse_experience('', '')
    from app.ai.document_intelligence.parsers.resume import (
        _merge_internships_listed_under_education,
    )

    merged = _merge_internships_listed_under_education(jobs, edu)
    assert any('northwind' in (j.company or '').lower() or 'intern' in (j.role or '').lower() for j in merged)


def test_personal_details_skills_keep_tools_drop_family_and_hobbies():
    text = (
        'Skills\nMS-Office\n'
        'Personal Details\n'
        'Father\'s Name: Alex Parent\n'
        'Hobbies: Swimming\n'
        'Linguistic Proficiency: Marathi\n'
        'Technical Skills: Linux, Ansible, AWS\n'
        'I solemnly say this is true to the best of my knowledge and belief.\n'
    )
    skills = parse_skills('Skills\nMS-Office', text)
    names = ' '.join(s.name.lower() for s in skills)
    assert 'office' in names or 'ms-office' in names
    assert 'linux' in names or 'ansible' in names or 'aws' in names
    assert 'father' not in names
    assert 'swimming' not in names
    assert 'alex parent' not in names
    assert 'knowledge and belief' not in names
    assert validate_skill_item('MS-Office')[0] is True
    assert validate_skill_item('Hive')[0] is True
    assert validate_skill_item('SQL')[0] is True
    assert validate_skill_item("Father's Name: Alex Parent")[0] is False
    assert validate_skill_item('Father’s Name: Alex Parent')[0] is False
    assert validate_skill_item('Hobbies: Swimming')[0] is False
    assert validate_skill_item('knowledge and belief.')[0] is False


def test_unlabeled_preamble_with_org_and_dates_recovers_one_job():
    text = (
        'Casey Morgan\ncasey@example.com\n+919111222333\n'
        'Brightleaf Technologies Pvt Ltd, Pune\nSeptember 2020 - Present\n'
        'Summary\nData engineer with warehouse and pipeline work.\n'
        'Education\nB.E. Computer, State University, 2019\n'
        'Skills\nPython, SQL, Azure\n'
    )
    profile = parse_resume_from_sections(detect_sections(text, 'resume'), text)
    assert len(profile.experience) == 1
    blob = f'{profile.experience[0].company} {profile.experience[0].role}'.lower()
    assert 'brightleaf' in blob or 'technologies' in blob


def test_glued_email_tenure_in_preamble_still_recovers_job():
    text = (
        'Casey Morgan\nDATA ENGINEER\n+919111222333\n'
        'Brightleaf Technologies, Pune\n'
        'casey@example.com                                   -FROM SEPTEMBER 2020 TO STILL DATE-\n'
        'Summary\nData engineer with warehouse work.\n'
        'Education\nB.E. Computer, State University, 2019\n'
        'Skills\nPython, SQL\n'
    )
    profile = parse_resume_from_sections(detect_sections(text, 'resume'), text)
    assert len(profile.experience) == 1
    job = profile.experience[0]
    blob = f'{job.company} {job.role}'.lower()
    assert 'brightleaf' in blob or 'technolog' in blob
    assert (job.start or '').startswith('2020')


def test_duration_only_preamble_does_not_invent_jobs():
    text = (
        'Morgan Lee\nmorgan@example.com\n8217276434\n'
        'Employment background reflects well over 2 years, 7 months in document stores.\n'
        'B.E. Information Science, State University, 2021\n'
        'Python, AWS, Linux\n'
    )
    profile = parse_resume_from_sections(detect_sections(text, 'resume'), text)
    assert profile.experience == []


def test_existing_experience_section_is_not_inflated_from_preamble():
    text = (
        'Riley Chen\nriley@example.com\n'
        'Also worked at Wide World Importers in 2018.\n'
        'Experience\nNorthwind Traders | Analyst | 2021 - 2024\n'
        'Built reporting dashboards.\n'
        'Education\nB.Tech, State University, 2020\n'
        'Skills\nPython, SQL\n'
    )
    profile = parse_resume_from_sections(detect_sections(text, 'resume'), text)
    assert len(profile.experience) == 1
    blob = f'{profile.experience[0].company} {profile.experience[0].role}'.lower()
    assert 'northwind' in blob
    assert 'wide world' not in blob
