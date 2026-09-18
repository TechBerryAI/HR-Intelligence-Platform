"""Generalized parser/sanitizer rules — no candidate-specific strings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.models.candidate import (  # noqa: E402
    EducationEntry,
    ExperienceEntry,
    SkillEntry,
)
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_education,
    parse_experience,
    parse_personal,
    parse_skills,
    parse_summary,
)
from app.ai.document_intelligence.validation.engine import (  # noqa: E402
    sanitize_education_row,
    sanitize_experience_row,
    sanitize_skills,
    validate_person_name,
    validate_skill_item,
)
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    extract_name_from_text,
    is_plausible_person_name,
)


# --- Name -----------------------------------------------------------------


def test_overview_rejected_as_full_name():
    assert is_plausible_person_name('Overview') is False
    assert validate_person_name('Overview')[0] is False
    text = (
        'Overview\n'
        'jordan.hale@example.com\n'
        '+919876543210\n'
        'Experience\nSoftware Engineer | Northwind Ltd | 2020 - 2022\n'
    )
    assert extract_name_from_text(text) != 'Overview'
    pers = parse_personal(text, text)
    assert pers.full_name != 'Overview'


def test_name_near_contact_preferred_over_section_title():
    text = (
        'Overview\n'
        'Jordan Hale\n'
        'jordan.hale@example.com\n'
        '+919876543210\n'
        'Summary\nSeeking a software role.\n'
    )
    name = extract_name_from_text(text)
    assert name == 'Jordan Hale'
    pers = parse_personal(text, text)
    assert pers.full_name == 'Jordan Hale'


def test_explicitly_labeled_name_still_works():
    text = 'Name: Jordan Hale\njordan.hale@example.com\n'
    assert extract_name_from_text(text) == 'Jordan Hale'
    pers = parse_personal(text, text)
    assert pers.full_name == 'Jordan Hale'


def test_empty_name_when_only_document_titles_exist():
    text = (
        'Resume\nOverview\nProfessional Summary\n'
        'Experience\nEducation\nSkills\n'
    )
    assert extract_name_from_text(text) == ''
    pers = parse_personal(text, text)
    assert pers.full_name == ''


# --- Experience -----------------------------------------------------------


def test_project_heading_is_not_company():
    jobs = parse_experience(
        'Project #1\n'
        'Client: Northwind Bank Ltd\n'
        'Duration: Feb 2020 - Mar 2021\n'
        'Environment: Java, Spring\n'
        'Implemented UPI settlement for retail payments.\n',
        '',
    )
    companies = [(j.company or '').lower() for j in jobs]
    roles = [(j.role or '').lower() for j in jobs]
    blob = ' '.join(companies + roles)
    assert 'project' not in blob
    assert 'client' not in blob
    assert 'duration' not in blob
    assert 'environment' not in blob


def test_client_duration_environment_not_role_or_company():
    row = sanitize_experience_row(
        ExperienceEntry(company='Duration : Feb', role='Client:', start='2020-02', end='2021-03')
    )
    assert 'duration' not in (row.company or '').lower()
    assert 'client' not in (row.role or '').lower()
    env = sanitize_experience_row(
        ExperienceEntry(company='Environment: Java, Spring', role='Analyst', start='2020-01')
    )
    assert 'environment' not in (env.company or '').lower()
    assert env.role == 'Analyst'
    assert env.start


def test_org_looking_role_plus_project_label_company_is_conservative():
    row = sanitize_experience_row(
        ExperienceEntry(
            company='Project #2',
            role='Northwind Bank Ltd',
            start='2020-02',
            end='2021-03',
        )
    )
    assert 'project' not in (row.company or '').lower()
    assert row.company == ''
    assert 'bank' not in (row.role or '').lower()


def test_duty_sentence_is_not_role():
    jobs = parse_experience(
        'Northwind Ltd | Software Engineer | Jan 2020 - Dec 2021\n'
        'Implement UPI settlement across merchant rails\n'
        'based payment routing for partner banks\n',
        '',
    )
    assert jobs
    assert not any('implement upi' in (j.role or '').lower() for j in jobs)
    assert not any('based payment' in (j.company or '').lower() for j in jobs)
    duty = sanitize_experience_row(
        ExperienceEntry(company='Northwind Ltd', role='Implement UPI', start='2020-01')
    )
    assert 'implement' not in (duty.role or '').lower()
    assert duty.company == 'Northwind Ltd'


def test_lowercase_fragment_is_not_company():
    row = sanitize_experience_row(
        ExperienceEntry(company='based payment routing for partners', role='Analyst', start='2020-01')
    )
    assert row.company == ''
    assert row.role == 'Analyst'


def test_role_and_dates_survive_without_company():
    jobs = parse_experience(
        'Software Engineer | Jan 2020 - Dec 2021\n'
        '• Built reporting dashboards\n',
        '',
    )
    assert any(
        'engineer' in (j.role or '').lower() and j.start and not (j.company or '').strip()
        for j in jobs
    ) or any('engineer' in (j.role or '').lower() and j.start for j in jobs)
    row = sanitize_experience_row(
        ExperienceEntry(company='', role='Software Engineer', start='2020-01', end='2021-12')
    )
    assert row.role == 'Software Engineer'
    assert row.start
    assert row.company == ''


def test_project_only_block_not_converted_to_experience():
    jobs = parse_experience(
        'Project #1\n'
        'Inventory portal for campus students\n'
        'Project #2\n'
        'Billing workflow using Python\n',
        '',
    )
    assert jobs == [] or not any(
        'project' in f'{(j.company or "")} {(j.role or "")}'.lower() for j in jobs
    )


def test_description_continuation_beginning_with_and():
    jobs = parse_experience(
        'Northwind Ltd | Software Engineer | Jan 2020 - Dec 2021\n'
        '• Developed payment systems\n'
        'and settlement workflows for partner banks.\n',
        '',
    )
    assert jobs
    desc = (jobs[0].description or '').lower()
    assert 'settlement' in desc or 'and settlement' in desc
    assert not any((j.company or '').lower().startswith('and ') for j in jobs)
    assert not any((j.role or '').lower().startswith('and ') for j in jobs)


# --- Education ------------------------------------------------------------


def test_numbered_duty_is_not_tenth_or_twelfth():
    rows = parse_education(
        '10. Monitoring production databases for uptime\n'
        '12. OS patching across virtual machines\n',
        '',
    )
    blob = ' '.join(f'{r.degree} {r.institution}' for r in rows).lower()
    assert '10.' not in blob
    assert '12.' not in blob
    assert not any(
        (r.degree or '').lower() in {'10th', '12th', '10', '12'} for r in rows
    )


def test_explicit_tenth_and_twelfth_are_recognized():
    rows = parse_education(
        '10th, State Board, 2010\n'
        '12th in Science, May 2012\n'
        'SSC, City School, 2008\n'
        'HSC, City School, 2010\n',
        '',
    )
    blob = ' '.join((r.degree or '') for r in rows).lower()
    assert '10th' in blob or 'ssc' in blob
    assert '12th' in blob or 'hsc' in blob


def test_bachelor_month_year_moves_to_end():
    rows = parse_education('Bachelor of Science, May 2016\n', '')
    assert rows
    row = rows[0]
    assert 'bachelor' in (row.degree or '').lower()
    assert '2016' in (row.end or '')
    assert 'may' not in (row.degree or '').lower()


def test_trailing_city_after_date_removed_from_degree():
    rows = parse_education('12th in Science, May 2012 Mumbai\n', '')
    assert rows
    row = next(r for r in rows if '12th' in (r.degree or '').lower())
    assert '2012' in (row.end or '')
    assert 'mumbai' not in (row.degree or '').lower()
    assert '12th' in (row.degree or '').lower()


def test_degree_from_institution_is_split():
    rows = parse_education(
        'Bachelor of Engineering from State University\n',
        '',
    )
    assert rows
    row = rows[0]
    assert 'bachelor' in (row.degree or '').lower()
    assert 'from' not in (row.degree or '').lower()
    assert 'university' in (row.institution or '').lower()
    assert 'university' not in (row.degree or '').lower()


def test_generic_university_city_state_orphan_removed():
    rows = parse_education('University, City, State\n', '')
    assert not any(
        (r.institution or '').lower().startswith('university,')
        or (r.institution or '').lower() in {'university', 'institute'}
        for r in rows
    )
    cleaned = sanitize_education_row(
        EducationEntry(degree='', institution='University, City, State')
    )
    assert not cleaned.institution
    assert not cleaned.degree
    kept = sanitize_education_row(
        EducationEntry(degree='B.Tech', institution='State University')
    )
    assert 'university' in (kept.institution or '').lower()


def test_new_twelfth_row_not_glued_to_previous_institution():
    rows = parse_education(
        'Bachelor of Commerce from Harbor College\n'
        '12th in Science, May 2012\n',
        '',
    )
    assert len(rows) >= 2
    bachelor = next(r for r in rows if 'bachelor' in (r.degree or '').lower())
    twelfth = next(r for r in rows if '12th' in (r.degree or '').lower())
    assert '12th' not in (bachelor.institution or '').lower()
    assert 'harbor' not in (twelfth.institution or '').lower()


def test_leading_colon_ssc_normalized():
    rows = parse_education(': SSC\nCity School\n', '')
    blob = ' '.join(f'{r.degree} {r.institution}' for r in rows)
    assert 'SSC' in blob or 'ssc' in blob.lower()
    assert not any((r.degree or '').startswith(':') for r in rows)


# --- Skills ---------------------------------------------------------------


def test_address_nationality_page_and_edu_table_rejected_as_skills():
    skills = parse_skills(
        'Vashi, Navi, Maharashtra\n'
        ': Indian\n'
        '1 of 2\n'
        '2 of 2\n'
        'Degree: University, Year of passing, B.COM: 2018\n'
        'Build strong social media campaigns across regions\n'
        'Python, SQL, Excel\n',
        '',
    )
    names = [s.name.lower() for s in skills]
    joined = ' '.join(names)
    assert 'maharashtra' not in joined
    assert 'indian' not in names
    assert '1 of 2' not in names
    assert '2 of 2' not in names
    assert not any('year of passing' in n for n in names)
    assert not any(n.startswith('build strong') for n in names)
    assert any('python' in n or 'sql' in n or 'excel' in n for n in names)


def test_labeled_skills_remain_intact():
    skills = parse_skills('Skills: Python, SQL, Docker\n', '')
    names = {s.name.lower() for s in skills}
    assert {'python', 'sql', 'docker'} <= names or {'python', 'sql'} <= names
    ok, _ = validate_skill_item('Python')
    assert ok
    cleaned = sanitize_skills(
        [
            SkillEntry(name='Python'),
            SkillEntry(name='Vashi, Navi, Maharashtra'),
            SkillEntry(name='Indian'),
        ]
    )
    kept = {s.name.lower() for s in cleaned}
    assert 'python' in kept
    assert 'indian' not in kept


def test_duty_sentence_rejected_as_skill():
    ok, _ = validate_skill_item('Build strong social media presence for brands')
    assert ok is False


# --- Summary --------------------------------------------------------------


def test_professional_objective_heading_alone_is_empty():
    assert parse_summary('PROFESSIONAL OBJECTIVE:', '') == ''
    assert parse_summary('Career Objective', '') == ''
    assert parse_summary('Professional Summary', '') == ''


def test_heading_plus_body_keeps_body_only():
    body = parse_summary(
        'PROFESSIONAL OBJECTIVE:\n'
        'Seeking a challenging software engineering role in a product team.\n',
        '',
    )
    assert 'seeking' in body.lower()
    assert 'professional objective' not in body.lower()


def test_existing_summary_parsing_remains_intact():
    text = (
        'Summary\n'
        'Experienced software engineer with 5 years building APIs.\n'
    )
    out = parse_summary(text, text)
    assert 'software engineer' in out.lower()
    assert out.lower().strip() != 'summary'
