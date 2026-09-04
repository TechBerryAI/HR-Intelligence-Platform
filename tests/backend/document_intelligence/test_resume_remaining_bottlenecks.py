"""Generalized regressions for remaining resume bottlenecks.

No candidate-specific, employer-specific, filename-specific, or coordinate rules.
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
    parse_personal,
    parse_skills,
)
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.document_intelligence.validation.engine import validate_skill_item  # noqa: E402
from app.ai.parser.engine.confidence import provenance_outranks  # noqa: E402
from app.ai.parser.engine.sections import detect_sections  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    extract_name_from_text,
    has_credible_employment_evidence,
    is_non_job_experience_record,
    is_plausible_person_name,
    join_spaced_letter_name,
    looks_like_skill_or_duration_company,
    name_from_resume_filename,
)
from app.ai.parser.layout.heuristic import normalize_section_header  # noqa: E402
from app.ai.document_intelligence.models.candidate import EducationEntry  # noqa: E402


def test_short_skills_section_does_not_drop_document_skills():
    text = (
        'Jordan Hale\njordan@example.com\n9876543210\n\n'
        'Skills\nMS-Office\n\n'
        'Achievements\nCompleted a Python and SQL workshop.\n'
        'Personal Details\nTechnical Skills: Linux, Ansible, AWS\n'
    )
    skills = parse_skills('Skills\nMS-Office', text)
    names = ' '.join(s.name.lower() for s in skills)
    assert 'office' in names or 'ms-office' in names
    assert 'linux' in names or 'ansible' in names or 'aws' in names
    jobs = parse_experience('', text)
    companies = ' '.join((j.company or '').lower() for j in jobs)
    assert 'linux' not in companies
    assert 'ansible' not in companies


def test_short_education_section_recovers_from_document():
    text = (
        'Alex Rivera\nalex@example.com\n\n'
        'Education\n\n'
        'Summary\nSeeking an IT role.\n\n'
        'B.Sc. Information Technology, State University, 2022\n'
    )
    rows = parse_education('Education', text)
    assert any((r.degree or '').strip() and (r.institution or '').strip() for r in rows)
    assert any('b.sc' in (r.degree or '').lower() or 'bsc' in (r.degree or '').lower() for r in rows)


def test_wrapped_education_degree_stays_one_record():
    rows = parse_education(
        'Education\nPh.D. (Pursuing\nI.T.)\nState Institute of Technology\n',
        '',
    )
    assert rows
    blob = ' '.join(f'{r.degree} {r.institution}' for r in rows)
    assert 'Ph.D' in blob or 'Ph.D.' in blob or 'phd' in blob.lower()
    assert not any((r.institution or '').strip() in {'I.T.)', 'I.T.'} for r in rows)
    one_liner = parse_education('Education\n: Ph.D. (Pursuing-I.T.)\nCoastal University\n', '')
    assert one_liner
    deg = ' '.join((r.degree or '') for r in one_liner)
    assert 'Pursuing' in deg
    assert not any((r.institution or '').strip() in {'I.T.)', 'I.T.'} for r in one_liner)


def test_multiline_education_institution_coalesces():
    rows = coalesce_education(
        [
            EducationEntry(degree='B.Sc.', field='', institution=''),
            EducationEntry(degree='', field='', institution='The New College of Arts'),
        ]
    )
    assert len(rows) == 1
    assert 'B.Sc' in (rows[0].degree or '')
    assert 'New College' in (rows[0].institution or '')


def test_skills_without_skills_heading_recover_into_skills_not_jobs():
    text = (
        'Casey Ng\ncasey@example.com\n\n'
        'Summary\nTECHNICALSKILL: Red Hat, Linux, Ansible, AWS\n\n'
        'Education\nB.Com, City College, 2021\n'
    )
    assert normalize_section_header('TECHNICALSKILL') == 'Skills'
    skills = parse_skills('', text)
    names = ' '.join(s.name.lower() for s in skills)
    assert 'linux' in names or 'ansible' in names or 'aws' in names
    profile, _form, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    companies = ' '.join((e.company or '').lower() for e in profile.experience)
    assert 'linux' not in companies
    assert 'ansible' not in companies


def test_language_line_is_not_a_job():
    jobs = parse_experience('English\nHindi\nMarathi\n', '')
    companies = [(j.company or '').lower() for j in jobs]
    assert 'english' not in companies
    assert 'hindi' not in companies
    assert looks_like_skill_or_duration_company('English') is True


def test_duration_only_line_is_not_a_job():
    jobs = parse_experience('5 Years 6 Months\nDuration:\n', '')
    companies = [(j.company or '').lower() for j in jobs]
    assert not any('year' in c and 'month' in c for c in companies)
    assert 'duration' not in companies
    assert looks_like_skill_or_duration_company('5 Years 6 Months') is True


def test_duty_fragment_is_not_a_job_or_skill():
    jobs = parse_experience(
        'Recruitments: Onboarding\nSuccessfully configured backup strategy\n',
        '',
    )
    blob = ' '.join(f'{j.company} {j.role}' for j in jobs).lower()
    assert 'recruitments' not in blob
    assert 'successfully configured' not in blob
    assert validate_skill_item('ensuring cluster availability')[0] is False
    assert validate_skill_item('managing dat')[0] is False
    assert validate_skill_item('Python')[0] is True


def test_academic_label_fragments_are_not_jobs():
    jobs = parse_experience(
        'Experience\n4.7 Years\nPaper published in\nJournals /\n: 3\n'
        'FDP / Conferences\nPh. D Students\n: NA\nMembership of\nProfessional\n',
        '',
    )
    companies = ' '.join((j.company or '').lower() for j in jobs)
    assert 'paper published' not in companies
    assert 'journals' not in companies
    assert ': 3' not in companies
    assert 'ph. d students' not in companies


def test_career_break_and_section_headers_are_not_jobs():
    jobs = parse_experience(
        '|\n'
        'AREAS OF STRENGTH\n'
        'HOBBIES\n'
        'PERSONAL SUMMARY\n'
        'WORK SUMMARY\n'
        'PERSONALINFORMATION:\n'
        'SQL DBA\n',
        '',
    )
    companies = ' '.join((j.company or '').lower() for j in jobs)
    assert 'hobbies' not in companies
    assert 'strength' not in companies
    assert 'personal' not in companies
    assert 'work summary' not in companies
    assert not any(is_non_job_experience_record(j) is False and not has_credible_employment_evidence(j) for j in jobs)


def test_two_column_address_first_layout_does_not_use_locality_as_name():
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

    assert is_plausible_person_name('Maruthi Nagar') is False
    address_first = (
        '8217276434\n'
        'x96@example.com\n'
        '#244, 1st Main Road, 2nd Cross\n'
        'Maruthi Nagar\n'
        'Bapuji Nagar, Bangalore\n'
        'Contact\n'
        'Summary\n'
    )
    assert extract_name_from_text(address_first) != 'Maruthi Nagar'
    assert is_plausible_person_name('Fundamentals') is False
    assert is_plausible_person_name('Tamil') is False
    assert looks_like_skill_or_duration_company('Bapuji Nagar, Bangalore') is True
    assert looks_like_skill_or_duration_company('In MEGAC') is True
    plumber = 'P A D M I N I P\nASSOCIATE DATABASE ENGINEER\n8217276434\n'
    assert join_spaced_letter_name('P A D M I N I P')
    assert extract_name_from_text(plumber)
    from app.ai.parser import pdfplumber_extractor as pe

    assert pe.fallback_reason(address_first + 'Experience\n2 years of administration.\n', None) == (
        'address_first_missing_name'
    )
    assert pe.pdfplumber_result_is_preferable(
        address_first + 'Experience\n2 years of administration.\n',
        plumber + 'Summary\nEmployment background reflects administration.\nEducation\nBachelor of Engineering\n',
    ) is True


def test_spaced_letter_name_normalizes_before_identity_compare():
    assert join_spaced_letter_name('R O S H A N  P A N I C K E R') == 'Roshan Panicker'
    joined = join_spaced_letter_name('P A D M I N I P')
    assert joined
    assert ' ' in joined or len(joined) >= 6
    assert extract_name_from_text('P A D M I N I P\nAssociate Engineer\n')


def test_filename_cannot_override_document_identity():
    body = (
        'Priya Sharma\n'
        'priya.sharma@example.com\n'
        '9876543210\n'
        'Mumbai\n'
        'Summary\nSoftware engineer with 3 years of experience.\n'
    )
    pers = parse_personal(body, body, source_filename='Anushka Gohil MYSQL DBA.pdf')
    assert 'Priya' in pers.full_name
    assert 'Anushka' not in pers.full_name
    # Tech tokens are stripped; leftover given name is last-resort only
    assert 'Mysql' not in name_from_resume_filename('Jordan K MYSQL DBA.pdf')
    assert name_from_resume_filename('Riley Chen Mongo dba Expertia AI.pdf')
    assert 'Mongo' not in name_from_resume_filename('Riley Chen Mongo dba Expertia AI.pdf')


def test_fresher_resume_does_not_invent_employment():
    text = (
        'Dana Parthe\ndparthe45@example.com\n8408897040\nMumbai\n\n'
        'Career Objective\nTo work in a challenging IT position.\n\n'
        'Skills\nWebLogic Server, Linux, SSH\n\n'
        'Education\nB.Sc IT, Mumbai University, 2022\n\n'
        'Work experience = fresher\n'
        'Completed weblogic class from Hyderabad team.\n'
    )
    profile, _form, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    assert profile.experience == []
    assert profile.field_meta.get('_field_provenance', {}).get('personal.full_name') in {
        'deterministic',
        '',
    }


def test_internship_is_experience_not_invented_from_project():
    text = (
        'Riley Chen\nriley@example.com\n\n'
        'Internship\n'
        'Intern — Contoso Labs | May 2024 - Jul 2024\n'
        '• Researched customer analytics\n\n'
        'Projects\n'
        'Campus Portal\nBuilt a student attendance system in MySQL.\n'
    )
    profile, _form, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    assert any('contoso' in (e.company or '').lower() for e in profile.experience)
    assert not any('campus' in (e.company or '').lower() for e in profile.experience)
    assert not any('mysql' == (e.company or '').lower() for e in profile.experience)


def test_project_description_is_not_a_job():
    jobs = parse_experience(
        'Arduino projects\nBuilt a line-follower robot.\n'
        'Inventory App\nDeveloped REST APIs using .NET\n',
        '',
    )
    companies = ' '.join((j.company or '').lower() for j in jobs)
    assert 'arduino' not in companies
    assert 'inventory app' not in companies


def test_bullet_heavy_experience_keeps_logical_items():
    section = (
        'Northwind Ltd | Software Engineer | Jan 2022 - Present\n'
        '• Developed REST APIs using .NET\n'
        '• Improved application performance by 40%\n'
        '• Worked with SQL Server\n'
    )
    jobs = parse_experience(section, '')
    assert len(jobs) == 1
    lines = [ln for ln in (jobs[0].description or '').splitlines() if ln.strip()]
    assert len(lines) >= 3
    assert '40%' in (jobs[0].description or '')


def test_uncertain_section_source_is_marked_not_discarded():
    text = 'Name Line\nSkills\nContact\nEducation\nSummary\nTechnical Skills: Python, SQL, Linux\n'
    spans = detect_sections(text, 'resume')
    skills = [s for s in spans if s.label == 'Skills']
    assert skills
    assert any(s.source == 'uncertain' for s in skills)
    parsed = parse_skills(skills[0].text, text)
    names = ' '.join(s.name.lower() for s in parsed)
    assert 'python' in names or 'sql' in names or 'linux' in names


def test_lower_confidence_provenance_cannot_outrank_deterministic():
    assert provenance_outranks('filename', 'deterministic') is False
    assert provenance_outranks('llm', 'deterministic') is False
    assert provenance_outranks('repair', 'deterministic') is False
    assert provenance_outranks('document_wide_recovery', 'filename') is True


def test_city_address_phone_email_rejected_as_skills():
    assert validate_skill_item('Navi Mumbai')[0] is False
    assert validate_skill_item('Pune')[0] is False
    assert validate_skill_item('user@example.com')[0] is False
    assert validate_skill_item('+919876543210')[0] is False
    assert validate_skill_item('PROJECT-1: Campus Portal')[0] is False
    assert validate_skill_item('Organization : Contoso')[0] is False
    assert validate_skill_item('Linux')[0] is True
