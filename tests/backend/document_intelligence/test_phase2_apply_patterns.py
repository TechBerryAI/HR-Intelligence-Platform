"""Synthetic Apply-layout patterns for Phase 2 parser fixes. No real resumes."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.coverage.resume_coverage import (  # noqa: E402
    _has_location_evidence,
    _has_phone_evidence,
    recover_resume_profile_gaps,
)
from app.ai.document_intelligence.deterministic import extract_phone  # noqa: E402
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form  # noqa: E402
from app.ai.document_intelligence.models.candidate import (  # noqa: E402
    CandidateProfile,
    ContactInfo,
    ExperienceEntry,
    PersonalInfo,
)
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_certifications,
    parse_experience,
)
from app.ai.document_intelligence.validation.engine import sanitize_experience_row  # noqa: E402


def test_date_first_then_role_and_company():
    jobs = parse_experience(
        'Experience\n'
        'Apr 2021 till date\n'
        'Linux Administrator\n'
        'Northwind Systems Pvt Ltd\n'
        'Supported production hosts.\n'
    )
    assert jobs
    hit = next(
        (j for j in jobs if 'northwind' in (j.company or '').lower() or 'linux' in (j.role or '').lower()),
        jobs[0],
    )
    assert (hit.start or '').startswith('2021')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')


def test_date_after_duties_attaches_to_open_job():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'Acme Technologies Pvt Ltd\n'
        'Built APIs and coordinated releases with several teams.\n'
        'Jan 2020 - Present\n'
    )
    assert jobs
    hit = next(
        (j for j in jobs if 'acme' in (j.company or '').lower() or 'engineer' in (j.role or '').lower()),
        jobs[0],
    )
    assert (hit.start or '').startswith('2020')


def test_date_on_next_line_attaches_to_job():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'Acme Technologies Pvt Ltd\n'
        'Jan 2020 - Present\n'
        'Built APIs.\n'
    )
    assert jobs
    assert any(j.start.startswith('2020') for j in jobs)
    assert any('acme' in (j.company or '').lower() or 'engineer' in (j.role or '').lower() for j in jobs)


def test_till_date_range_fills_current_job():
    jobs = parse_experience(
        'Experience\n'
        'Database Administrator | Northwind Ltd\n'
        'July 2022 to till date\n'
    )
    assert jobs
    assert any(j.is_current or (j.start or '').startswith('2022') for j in jobs)


def test_role_at_company_line():
    jobs = parse_experience(
        'Experience\n'
        'Oracle DBA at Contoso Solutions Pvt Ltd (2021 - 2024)\n'
    )
    assert jobs
    blob = ' '.join(f'{j.role} {j.company}' for j in jobs).lower()
    assert 'dba' in blob or 'oracle' in blob
    assert 'contoso' in blob


def test_company_only_dated_row_survives_sanitize_and_form():
    row = sanitize_experience_row(
        ExperienceEntry(company='Infosenseglobal', role='', start='2024-12', end='', is_current=True)
    )
    assert row.company and row.start
    form = map_candidate_to_form(
        CandidateProfile(
            personal=PersonalInfo(full_name='Pat Lee'),
            contact=ContactInfo(email='pat@example.com'),
            experience=[row],
        )
    )
    assert form.experiences
    assert form.experiences[0].company == 'Infosenseglobal'


def test_unanchored_rows_replaced_by_reparse():
    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Pat Lee'),
        contact=ContactInfo(email='pat@example.com'),
        experience=[ExperienceEntry(company='', role='and visualization', start='', end='')],
    )
    text = (
        'Pat Lee\npat@example.com\n'
        'Experience\n'
        'Software Engineer at Northwind Ltd\n'
        'Jan 2021 - Present\n'
        'Education\nB.E. Example University\n'
    )
    recovered, cov = recover_resume_profile_gaps(profile, text)
    assert any((e.company or e.role) and e.start for e in recovered.experience)
    statuses = {f.field: f.status for f in cov.fields}
    assert statuses.get('experience') in {'filled', 'recovered'}


def test_phone_heals_labeled_spaced_mobile():
    text = 'Jordan Hale\nMobile No: 98765 43210\nMumbai\n'
    phone = extract_phone(text)
    digits = ''.join(c for c in phone if c.isdigit())
    assert digits.endswith('9876543210')
    assert _has_phone_evidence(text)
    assert not _has_phone_evidence('Mobile:\nSkills\nPython')


def test_location_evidence_is_header_not_job_city():
    header = 'Jordan Hale\nEmail: jordan@example.com\nLocation: Pune\nExperience\n'
    assert _has_location_evidence(header)
    job_only = (
        'Jordan Hale\nEmail: jordan@example.com\n'
        'Experience\nEngineer at Acme\nWorked in Bengaluru office\n'
    )
    assert not _has_location_evidence(job_only)


def test_certifications_same_line_list():
    certs = parse_certifications('Certifications: AWS, ITIL, PMP')
    names = {c.name.upper() for c in certs}
    assert {'AWS', 'ITIL', 'PMP'} <= names


def test_certifications_section_items_without_cue():
    certs = parse_certifications(
        'Certifications\n'
        'Oracle Database 19c\n'
        'Red Hat Linux Admin\n'
    )
    blob = ' '.join(c.name for c in certs).lower()
    assert 'oracle' in blob or 'linux' in blob


def test_certifications_heading_only_does_not_invent():
    assert parse_certifications('Certifications') == []


def test_orphan_date_line_fills_end_when_start_exists():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'Acme Technologies Pvt Ltd\n'
        'Jan 2020\n'
        'Built APIs and maintained services.\n'
        'Dec 2023\n'
    )
    assert jobs
    hit = next((j for j in jobs if 'acme' in (j.company or '').lower()), jobs[0])
    assert (hit.start or '').startswith('2020')
    assert (hit.end or '').startswith('2023') or hit.is_current


def test_duty_bullets_attach_to_current_job_not_echo():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer | Acme Technologies Pvt Ltd\n'
        'Jan 2020 - Present\n'
        '• Developed REST APIs for billing\n'
        '• Supported production releases\n'
    )
    assert jobs
    hit = next((j for j in jobs if 'acme' in (j.company or '').lower()), jobs[0])
    desc = (hit.description or '').lower()
    assert 'developed' in desc or 'supported' in desc
    assert 'acme technologies pvt ltd' not in desc or 'developed' in desc


def test_merge_does_not_mark_same_title_at_other_company_current():
    from app.ai.document_intelligence.experience_quality import merge_experience_field_level

    existing = [
        ExperienceEntry(
            company='Hawkium',
            role='Digital Marketing Executive',
            start='2024-09',
            is_current=True,
        ),
        ExperienceEntry(
            company='Tridhya Tech Public Limited',
            role='Digital Marketing Executive',
            start='2023-12',
            end='2024-09',
        ),
    ]
    incoming = list(existing)
    merged = merge_experience_field_level(existing, incoming)
    assert merged[1].is_current is False
    assert (merged[1].end or '').startswith('2024-09')


def test_merge_fills_end_and_description():
    from app.ai.document_intelligence.experience_quality import merge_experience_field_level

    existing = [
        ExperienceEntry(company='Acme Ltd', role='Engineer', start='2020-01', end='', description=''),
    ]
    incoming = [
        ExperienceEntry(
            company='Acme Ltd',
            role='Engineer',
            start='2020-01',
            end='2023-12',
            description='Built APIs.',
        ),
    ]
    merged = merge_experience_field_level(existing, incoming)
    assert merged[0].end.startswith('2023')
    assert 'built' in (merged[0].description or '').lower()


def test_cert_heading_recovers_from_full_text():
    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Pat Lee'),
        contact=ContactInfo(email='pat@example.com'),
    )
    text = (
        'Pat Lee\npat@example.com\n'
        'Experience\nSoftware Engineer at Northwind Ltd\nJan 2021 - Present\n'
        'Certifications\nAWS Certified Solutions Architect\nITIL Foundation\n'
    )
    recovered, _cov = recover_resume_profile_gaps(profile, text)
    blob = ' '.join(c.name for c in recovered.certificates).lower()
    assert 'aws' in blob or 'itil' in blob


def test_format_jd_description_from_responsibilities_when_summary_thin():
    from app.ai.document_intelligence.mapping.jd_form import format_jd_description
    from app.ai.document_intelligence.models.job import (
        JobBasicInfo,
        JobProfile,
        JobRequirements,
        JobResponsibilities,
        JobSkills,
    )

    profile = JobProfile(
        basic=JobBasicInfo(title='QA Engineer', description='QA role'),
        responsibilities=JobResponsibilities(items=[
            'Design and maintain automated test scripts',
            'Report defects and track resolution',
        ]),
        skills=JobSkills(mandatory=['Python', 'Selenium']),
        requirements=JobRequirements(qualifications=['B.E. Computer Science']),
    )
    body = format_jd_description(profile)
    assert body
    low = body.lower()
    assert 'test' in low or 'python' in low or 'selenium' in low
