"""Generalized structural field-boundary tests — no candidate-specific strings."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.experience_quality import (  # noqa: E402
    experience_is_incomplete,
)
from app.ai.document_intelligence.models.candidate import ExperienceEntry  # noqa: E402
from app.ai.document_intelligence.parsers.resume import (  # noqa: E402
    parse_education,
    parse_experience,
    parse_skills,
)
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    document_identity_names,
    is_labeled_contact_metadata,
    peel_inline_contact,
)


HEADER = (
    'Jordan Hale\n'
    'Phone: +919876543210\n'
    'E-mail: jordan.hale@example.com\n'
    'Place: Harbor City\n'
)


def _parse(text: str):
    return parse_resume_text_to_canonical(text, allow_semantic=False)


def _skill_names(profile) -> list[str]:
    return [str(s.canonical or s.name or '').strip() for s in (profile.skills or [])]


def test_labeled_contact_metadata_detection():
    assert is_labeled_contact_metadata('Place: Harbor City')
    assert is_labeled_contact_metadata('E-mail: jordan.hale@example.com')
    assert is_labeled_contact_metadata('Phone: +919876543210')
    assert is_labeled_contact_metadata('Location: Harbor City')
    assert not is_labeled_contact_metadata('Linux, AIX, Windows')
    assert not is_labeled_contact_metadata('Middleware Administrator')


def test_peel_inline_contact_keeps_role_remainder():
    assert peel_inline_contact(
        'Middleware Administrator E-mail: jordan.hale@example.com'
    ) == 'Middleware Administrator'
    assert peel_inline_contact('Developer Phone: +919876543210') == 'Developer'
    assert peel_inline_contact('Software Engineer') == 'Software Engineer'
    # Date ranges must not be mistaken for trailing phone numbers
    assert peel_inline_contact('Woodgrove Bank | Teller | 2021 - 2023') == (
        'Woodgrove Bank | Teller | 2021 - 2023'
    )


def test_header_contact_does_not_contaminate_company_role_skills_education():
    text = (
        f'{HEADER}\n'
        'Summary\nSeeking a middleware administration role.\n\n'
        'Skills:\nPython, SQL, Linux\n\n'
        'Experience\n'
        'Northwind Ltd\n'
        'Software Engineer\n'
        'Jan 2022 - Present\n'
        'Built internal services.\n\n'
        'Education\n'
        'B.E. in Computer Engineering\n'
        'Harbor University\n'
        'May 2016\n'
    )
    profile, form, _ = _parse(text)
    companies = [(e.company or '').lower() for e in profile.experience]
    roles = [(e.role or '').lower() for e in profile.experience]
    skills_blob = ' '.join(_skill_names(profile)).lower()
    degrees = ' '.join((e.degree or '') for e in profile.education).lower()
    institutions = ' '.join((e.institution or '') for e in profile.education).lower()

    assert profile.personal.full_name == 'Jordan Hale'
    assert not any('jordan hale' in c for c in companies)
    assert not any('@' in r or 'e-mail' in r or 'phone' in r for r in roles)
    assert 'place' not in skills_blob
    assert 'harbor city' not in skills_blob
    assert 'jordan hale' not in skills_blob
    assert 'place' not in degrees
    assert 'jordan hale' not in institutions
    assert any('northwind' in c for c in companies)
    assert any('engineer' in r for r in roles)


def test_stacked_company_role_dates_form_one_job():
    jobs = parse_experience(
        'Northwind Ltd\n'
        'Middleware Administrator\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n',
        '',
    )
    assert jobs
    job = jobs[0]
    assert 'northwind' in (job.company or '').lower()
    assert 'administrator' in (job.role or '').lower()
    assert (job.start or '').startswith('2022')
    assert 'production' in (job.description or '').lower()


def test_contact_appended_to_role_same_line_and_next_line():
    same = parse_experience(
        'Northwind Ltd\n'
        'Middleware Administrator E-mail: jordan.hale@example.com\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n',
        HEADER,
    )
    assert same
    assert 'administrator' in (same[0].role or '').lower()
    assert 'e-mail' not in (same[0].role or '').lower()
    assert '@' not in (same[0].role or '')

    nxt = parse_experience(
        'Northwind Ltd\n'
        'Middleware Administrator\n'
        'E-mail: jordan.hale@example.com\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n',
        HEADER,
    )
    assert nxt
    assert 'administrator' in (nxt[0].role or '').lower()
    assert 'e-mail' not in (nxt[0].role or '').lower()


def test_header_person_name_is_not_experience_company():
    text = (
        f'{HEADER}\n'
        'Experience\n'
        'Jordan Hale\n'
        'Middleware Administrator\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n'
    )
    profile, _, _ = _parse(text)
    companies = [(e.company or '').strip().lower() for e in profile.experience]
    assert 'jordan hale' not in companies
    assert profile.personal.full_name == 'Jordan Hale'
    assert any('administrator' in (e.role or '').lower() for e in profile.experience)
    names = document_identity_names(text)
    assert 'jordan hale' in names


def test_role_plus_dates_kept_when_company_unknown():
    jobs = parse_experience(
        'Middleware Administrator\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n',
        '',
    )
    assert jobs
    job = jobs[0]
    assert not (job.company or '').strip()
    assert 'administrator' in (job.role or '').lower()
    assert (job.start or '').startswith('2022')
    assert not experience_is_incomplete(jobs, 'Experience\nMiddleware Administrator\nJan 2022 - Present\n')


def test_duration_label_attaches_dates_to_employment_block():
    jobs = parse_experience(
        'Northwind Ltd\n'
        'Middleware Administrator\n'
        'Duration: Jan 2022 - Present\n'
        'Supported production middleware.\n',
        '',
    )
    assert jobs
    job = jobs[0]
    assert 'northwind' in (job.company or '').lower()
    assert (job.start or '').startswith('2022')
    assert 'duration' not in (job.company or '').lower()
    assert 'duration:' not in (job.description or '').lower()


def test_project_block_is_not_experience_and_does_not_append_to_prior_job():
    jobs = parse_experience(
        'Northwind Ltd\n'
        'Middleware Administrator\n'
        'Jan 2022 - Present\n'
        'Supported production middleware.\n'
        'Project #1\n'
        'Client: Contoso Bank\n'
        'Duration: Jan 2018 - Dec 2018\n'
        'Environment: Java, Spring\n'
        'Implemented settlement processing.\n',
        '',
    )
    assert jobs
    assert len(jobs) == 1
    job = jobs[0]
    blob = f'{job.company} {job.role} {job.description}'.lower()
    assert 'northwind' in (job.company or '').lower()
    assert 'project' not in blob
    assert 'client' not in blob
    assert 'environment' not in blob
    assert 'contoso' not in blob


def test_skills_keep_tech_tokens_and_drop_contact_lines():
    skills = parse_skills(
        'Skills:\n'
        'Place: Harbor City\n'
        'Jordan Hale\n'
        'Linux, AIX, Windows, Oracle, WebLogic\n',
        HEADER,
    )
    names = [s.name.lower() for s in skills]
    blob = ' '.join(names)
    assert 'linux' in blob
    assert 'oracle' in blob
    assert 'place' not in blob
    assert 'harbor city' not in blob
    assert 'jordan hale' not in blob


def test_education_adjacent_degree_institution_date():
    rows = parse_education(
        'B.E. in Computer Engineering\n'
        'Harbor University\n'
        'May 2016\n',
        '',
    )
    assert rows
    row = rows[0]
    assert 'b.e' in (row.degree or '').lower() or 'computer' in (row.degree or '').lower()
    assert 'university' not in (row.degree or '').lower()
    assert 'university' in (row.institution or '').lower()
    assert '2016' in (row.end or '')


def test_education_from_and_colon_split_degree_institution():
    from_rows = parse_education(
        'B.E. in Computer Engineering from Harbor University, May 2016\n',
        '',
    )
    assert from_rows
    fr = from_rows[0]
    assert 'from' not in (fr.degree or '').lower()
    assert 'university' in (fr.institution or '').lower()
    assert 'university' not in (fr.degree or '').lower()
    assert '2016' in (fr.end or '')

    colon_rows = parse_education(
        'B.E. in Computer Engineering: Harbor University\n',
        '',
    )
    assert colon_rows
    cr = colon_rows[0]
    assert 'university' not in (cr.degree or '').lower()
    assert 'university' in (cr.institution or '').lower()


def test_education_pipe_row_splits_fields():
    rows = parse_education(
        'B.E. in Computer Engineering | Harbor University | 2016\n',
        '',
    )
    assert rows
    row = rows[0]
    assert 'computer' in (row.degree or '').lower()
    assert 'university' in (row.institution or '').lower()
    assert 'university' not in (row.degree or '').lower()


def test_wrapped_description_stays_description():
    jobs = parse_experience(
        'Northwind Ltd\n'
        'Software Engineer\n'
        'Jan 2022 - Present\n'
        'Implemented payment gateway integration and\n'
        'coordinated with clients for deployment.\n'
        'and troubleshooting production issues\n',
        '',
    )
    assert jobs
    desc = (jobs[0].description or '').lower()
    assert 'payment gateway' in desc
    assert 'troubleshooting' in desc
    assert not any(
        'troubleshooting' in (j.company or '').lower()
        or 'coordinated' in (j.role or '').lower()
        for j in jobs
    )


def test_section_isolation_contact_and_projects_do_not_leak():
    text = (
        f'{HEADER}\n'
        'Skills:\nPython, SQL, Linux, Oracle\n\n'
        'Experience\n'
        'Northwind Ltd\n'
        'Software Engineer\n'
        'Jan 2022 - Present\n'
        'Built internal services.\n\n'
        'Projects\n'
        'Project #1\n'
        'Client: Contoso Bank\n'
        'Duration: Jan 2018 - Dec 2018\n'
        'Environment: Java, Spring\n'
    )
    profile, _, _ = _parse(text)
    skills_blob = ' '.join(_skill_names(profile)).lower()
    companies = [(e.company or '').lower() for e in profile.experience]
    roles = [(e.role or '').lower() for e in profile.experience]
    desc_blob = ' '.join((e.description or '').lower() for e in profile.experience)

    assert 'python' in skills_blob
    assert 'place' not in skills_blob
    assert 'jordan hale' not in skills_blob
    assert not any('jordan hale' in c for c in companies)
    assert not any('contoso' in c for c in companies)
    assert 'client:' not in desc_blob
    assert 'environment' not in desc_blob
    assert any('engineer' in r for r in roles)


def test_yyyy_mm_dates_survive_toon_roundtrip():
    from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
    from app.ai.document_intelligence.models.candidate import CandidateProfile, ExperienceEntry
    from app.ai.document_intelligence.serialize.toon import candidate_to_toon

    profile = CandidateProfile(
        experience=[
            ExperienceEntry(
                company='Northwind Ltd',
                role='Software Engineer',
                start='2022-01',
                end='2023-05',
            )
        ]
    )
    roundtrip = candidate_profile_from_toon(candidate_to_toon(profile))
    assert roundtrip.experience[0].start == '2022-01'
    assert roundtrip.experience[0].end == '2023-05'


def test_role_plus_dates_row_is_not_incomplete_quality_flag():
    rows = [
        ExperienceEntry(
            role='Middleware Administrator',
            company='',
            start='2022-01',
            is_current=True,
            description='Supported production middleware.',
        )
    ]
    assert not experience_is_incomplete(rows, '')


def test_full_pipeline_structural_contamination_regression():
    text = (
        f'{HEADER}\n'
        'Professional Summary\n'
        'Seeking a middleware administration role with production ownership.\n\n'
        'Skills:\n'
        'Place: Harbor City\n'
        'Jordan Hale\n'
        'Linux, AIX, Windows, Oracle, WebLogic\n\n'
        'Experience\n'
        'Northwind Ltd\n'
        'Middleware Administrator E-mail: jordan.hale@example.com\n'
        'Jan 2022 - Present\n'
        'Implemented payment gateway integration and\n'
        'coordinated with clients for deployment.\n'
        'Developer Phone: +919876543210\n'
        'Feb 2019 - May 2021\n'
        'Built internal tools.\n'
        'Project #1\n'
        'Client: Contoso Bank\n'
        'Duration: Jan 2018 - Dec 2018\n'
        'Environment: Java, Spring\n'
        'Implemented settlement processing.\n\n'
        'Education\n'
        'B.E. in Computer Engineering: Harbor University\n'
        'May 2016\n'
    )
    profile, form, _ = _parse(text)
    skills_blob = ' '.join(_skill_names(profile)).lower()
    companies = [(e.company or '').lower() for e in profile.experience]
    roles = [(e.role or '').lower() for e in profile.experience]
    desc_blob = ' '.join((e.description or '').lower() for e in profile.experience)

    assert profile.personal.full_name == 'Jordan Hale'
    assert not any('jordan hale' in c for c in companies)
    assert any('northwind' in c for c in companies)
    assert any('administrator' in r for r in roles)
    assert not any('e-mail' in r or '@' in r or 'phone' in r for r in roles)
    assert any((e.start or '').startswith('2022') for e in profile.experience)
    assert 'linux' in skills_blob and 'oracle' in skills_blob
    assert 'place' not in skills_blob
    assert 'jordan hale' not in skills_blob
    assert 'client:' not in desc_blob
    assert 'contoso' not in desc_blob
    assert 'environment' not in desc_blob
    assert profile.education
    edu = profile.education[0]
    assert 'university' not in (edu.degree or '').lower()
    assert 'university' in (edu.institution or '').lower()
    form_roles = [(e.role or '').lower() for e in (form.experiences or [])]
    assert not any('e-mail' in r or '@' in r for r in form_roles)
