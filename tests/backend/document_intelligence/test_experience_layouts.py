"""Generalized experience layouts for Apply parse. Synthetic only — no corpus PII."""
from __future__ import annotations

import os
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.parsers.resume import parse_experience  # noqa: E402
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402


def _hit(jobs, *, company=None, role=None):
    assert jobs, 'expected at least one experience row'
    if company:
        found = next((j for j in jobs if company.lower() in (j.company or '').lower()), None)
        if found:
            return found
    if role:
        found = next((j for j in jobs if role.lower() in (j.role or '').lower()), None)
        if found:
            return found
    return jobs[0]


def test_layout_a_role_company_dates_bullets():
    jobs = parse_experience(
        'Experience\n'
        'Senior Software Engineer\n'
        'TechBerry Infotech\n'
        'Jan 2023 - Present\n'
        '• Developed REST APIs\n'
        '• Built ML pipelines\n'
        '• Managed deployments\n'
    )
    hit = _hit(jobs, company='techberry', role='software')
    assert 'engineer' in (hit.role or '').lower()
    assert 'techberry' in (hit.company or '').lower()
    assert (hit.start or '').startswith('2023')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')
    desc = (hit.description or '').lower()
    assert 'developed' in desc or 'pipelines' in desc


def test_layout_b_company_pipe_role_then_dates():
    jobs = parse_experience(
        'Experience\n'
        'TechBerry Infotech | Senior Software Engineer\n'
        'January 2023 – March 2025\n'
        'Responsibilities:\n'
        '• Developed backend services\n'
        '• Maintained APIs\n'
    )
    hit = _hit(jobs, company='techberry', role='software')
    assert 'techberry' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert (hit.end or '').startswith('2025')
    assert 'backend' in (hit.description or '').lower() or 'apis' in (hit.description or '').lower()


def test_layout_c_emdash_year_only_present_prose_duty():
    jobs = parse_experience(
        'Experience\n'
        'Senior Software Engineer — TechBerry Infotech\n'
        '2023 – Present\n'
        'Developed and maintained backend services.\n'
    )
    hit = _hit(jobs, company='techberry', role='software')
    assert 'techberry' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')
    assert 'maintained' in (hit.description or '').lower() or 'backend' in (hit.description or '').lower()


def test_layout_d_allcaps_company_then_role_numeric_month():
    jobs = parse_experience(
        'Experience\n'
        'TECHBERRY INFOTECH\n'
        'Software Engineer\n'
        '01/2023 - Present\n'
        'Job Description:\n'
        '• Built applications\n'
        '• Managed deployment\n'
    )
    hit = _hit(jobs, company='techberry', role='software')
    assert 'techberry' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert 'built' in (hit.description or '').lower() or 'deployment' in (hit.description or '').lower()


def test_layout_e_company_pipe_city_year_to_present():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'TechBerry Infotech | Mumbai\n'
        '2023 to Present\n'
        'Responsible for developing and maintaining backend systems.\n'
    )
    hit = _hit(jobs, company='techberry', role='software')
    assert 'techberry' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')
    assert 'responsible' in (hit.description or '').lower() or 'maintaining' in (hit.description or '').lower()


def test_role_pipe_company_same_line():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer | Northwind Ltd\n'
        'Jan 2021 - Dec 2022\n'
        '- Developed REST APIs\n'
        '- Managed cloud deployments\n'
    )
    hit = _hit(jobs, company='northwind', role='software')
    assert 'northwind' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2021')
    assert (hit.end or '').startswith('2022')
    assert 'developed' in (hit.description or '').lower()


def test_numbered_duties_attach_and_stop_at_next_job():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'Northwind Ltd\n'
        'Jan 2021 - Dec 2022\n'
        '1. Developed REST APIs\n'
        '2. Managed cloud deployments\n'
        'Database Administrator\n'
        'Contoso Pvt Ltd\n'
        'Jan 2023 - Present\n'
        '1. Administered Oracle databases\n'
    )
    assert len(jobs) >= 2
    first = _hit(jobs, company='northwind')
    second = _hit(jobs, company='contoso')
    assert 'northwind' in (first.company or '').lower()
    assert 'developed' in (first.description or '').lower()
    assert 'oracle' not in (first.description or '').lower()
    assert 'contoso' in (second.company or '').lower()
    assert second.is_current or (second.start or '').startswith('2023')


def test_till_present_is_current():
    jobs = parse_experience(
        'Experience\n'
        'Linux Administrator\n'
        'Northwind Systems Pvt Ltd\n'
        'Apr 2021 till Present\n'
        'Supported production hosts.\n'
    )
    hit = _hit(jobs, company='northwind', role='linux')
    assert (hit.start or '').startswith('2021')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')


def test_multi_job_isolates_dates_and_duties():
    jobs = parse_experience(
        'Experience\n'
        'Northwind Ltd\n'
        'Platform Engineer\n'
        '2019 - 2021\n'
        'Built APIs for billing.\n'
        'Contoso Pvt Ltd\n'
        'Database Administrator\n'
        '2021 - 2023\n'
        'Administered Oracle databases.\n'
        'Adventure Works\n'
        'Software Engineer\n'
        '2023 - Present\n'
        'Developed backend services.\n'
    )
    assert len(jobs) >= 3
    companies = ' '.join((j.company or '') for j in jobs).lower()
    assert 'northwind' in companies
    assert 'contoso' in companies
    nw = _hit(jobs, company='northwind')
    co = _hit(jobs, company='contoso')
    assert (nw.start or '').startswith('2019')
    assert (nw.end or '').startswith('2021')
    assert 'billing' in (nw.description or '').lower()
    assert 'oracle' not in (nw.description or '').lower()
    assert (co.start or '').startswith('2021')


def test_apply_form_keeps_startmonth_schema():
    _profile, form, *_ = parse_resume_text_to_canonical(
        'Pat Lee\npat@example.com\n'
        'Experience\n'
        'Software Engineer\nNorthwind Ltd\nJan 2022 - Present\n'
        '• Developed REST APIs\n'
        'Education\nB.Tech, City College, 2021\n'
    )
    assert form.experiences
    row = form.experiences[0]
    assert hasattr(row, 'startMonth')
    assert hasattr(row, 'endMonth')
    assert hasattr(row, 'isCurrent')
    assert hasattr(row, 'description')
    assert (row.startMonth or '').startswith('2022')
    assert row.isCurrent is True
    assert row.endMonth == ''


def test_current_employer_tenure_bullets():
    jobs = parse_experience(
        'Experience\n'
        '• Current Employer: Northwind Ltd\n'
        '• Tenure: Dec 2021 – Present.\n'
        '• Past Employer: Contoso Infotech\n'
        '• Tenure: Feb 2020 - Dec 2021\n'
        'Supported production hosts.\n'
    )
    companies = ' '.join((j.company or '') for j in jobs).lower()
    assert 'northwind' in companies
    assert 'contoso' in companies
    nw = _hit(jobs, company='northwind')
    assert (nw.start or '').startswith('2021')
    assert nw.is_current or (nw.end or '').lower() in ('', 'present')
    co = _hit(jobs, company='contoso')
    assert (co.start or '').startswith('2020')
    assert (co.end or '').startswith('2021')


def test_client_line_carries_dates_onto_open_job():
    jobs = parse_experience(
        'Experience\n'
        'Northwind Ltd\n'
        'Designation: Sr. Software Engineer\n'
        'Client: - Alight, Canada (From October 2022 to Current)\n'
        'Supported middleware platforms.\n'
    )
    hit = _hit(jobs, company='northwind', role='software')
    assert 'northwind' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2022-10')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')


def test_section_heading_aliases_current_and_background():
    for heading in (
        'Professional Background',
        'Career Experience',
        'Current Experience',
    ):
        jobs = parse_experience(
            f'{heading}\n'
            'Software Engineer\nNorthwind Ltd\nJan 2023 - Present\n'
            'Built APIs.\n'
        )
        hit = _hit(jobs, company='northwind')
        assert (hit.start or '').startswith('2023'), heading


def test_skill_conjunction_is_not_a_company():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\nNorthwind Ltd\nJan 2023 - Present\n'
        '• Used Frontend technologies like HTML, CSS JavaScript and React\n'
        'JavaScript and React\nJuly 2023 – Present\n'
    )
    companies = ' '.join((j.company or '') for j in jobs).lower()
    assert 'javascript' not in companies
    assert 'northwind' in companies


def test_two_column_date_rail_keeps_dates_with_jobs():
    """Role/company on the left, dates/locations on the right at the same Y."""
    try:
        import fitz
    except ImportError:
        return
    from app.ai.document_intelligence.layout_doc import LayoutLine, _reconstruct_page_regions
    from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text
    from app.ai.parser.text_extraction import extract_text

    doc = fitz.open()
    page = doc.new_page(width=612, height=792)
    page.insert_text((72, 50), 'Pat Lee', fontsize=14)
    page.insert_text((72, 68), 'pat@example.com', fontsize=9)
    left = [
        (90, 'Experience'),
        (110, 'Software Engineer'),
        (124, 'Northwind Ltd'),
        (138, '• Developed REST APIs'),
        (156, 'Database Administrator'),
        (170, 'Contoso Infotech'),
        (184, '• Administered Oracle databases'),
    ]
    right = [
        (110, 'Jan 2023 - Present'),
        (124, 'Mumbai'),
        (156, 'Mar 2021 - Dec 2022'),
        (170, 'Pune'),
    ]
    for y, t in left:
        page.insert_text((48, y), t, fontsize=9)
    for y, t in right:
        page.insert_text((360, y), t, fontsize=9)
    data = doc.tobytes()
    doc.close()

    raw = extract_text(data, 'date-rail.pdf') or ''
    working = prepare_resume_working_text(raw, file_data=data)
    profile, form, *_ = parse_resume_text_to_canonical(working, allow_semantic=False)
    # Prefer the working-text parse used by Apply
    from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
    from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form

    profile, coverage, *_rest = parse_resume_from_working_text(
        working, allow_semantic=False, source_filename='date-rail.pdf'
    )
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    assert form.experiences
    first = form.experiences[0]
    starts = [(e.startMonth or '') for e in form.experiences]
    companies = ' '.join((e.company or '') for e in form.experiences).lower()
    assert 'northwind' in companies
    assert any(s.startswith('2023') for s in starts)
    # Reconstruction helper: rail column must not dump all dates after duties
    lines = _reconstruct_page_regions(
        [
            LayoutLine(text='Experience', bbox=(48, 90, 140, 102), page=1),
            LayoutLine(text='Software Engineer', bbox=(48, 110, 180, 122), page=1),
            LayoutLine(text='Jan 2023 - Present', bbox=(360, 110, 500, 122), page=1),
            LayoutLine(text='Northwind Ltd', bbox=(48, 124, 180, 136), page=1),
            LayoutLine(text='Mumbai', bbox=(360, 124, 420, 136), page=1),
            LayoutLine(text='• Developed REST APIs', bbox=(48, 138, 250, 150), page=1),
            LayoutLine(text='Database Administrator', bbox=(48, 156, 200, 168), page=1),
            LayoutLine(text='Mar 2021 - Dec 2022', bbox=(360, 156, 500, 168), page=1),
            LayoutLine(text='Contoso Infotech', bbox=(48, 170, 200, 182), page=1),
            LayoutLine(text='Pune', bbox=(360, 170, 420, 182), page=1),
        ]
    )
    blob = '\n'.join(lines)
    eng_i = blob.lower().find('software engineer')
    date_i = blob.lower().find('jan 2023')
    duty_i = blob.lower().find('developed rest')
    assert eng_i != -1 and date_i != -1
    assert date_i < duty_i or abs(date_i - eng_i) < 80
    assert first.startMonth or any(s.startswith('202') for s in starts)


def test_two_column_reorder_keeps_extract_when_dates_already_adjacent():
    from app.ai.document_intelligence.layout_doc import (
        _count_adjacent_job_dates,
        maybe_reorder_two_column,
    )

    extract = (
        'Pat Lee\npat@example.com\n'
        'Experience\n'
        'Software Engineer\n'
        'Jan 2023 - Present\n'
        'Northwind Ltd\n'
        '• Developed REST APIs\n'
        'Database Administrator\n'
        'Mar 2021 - Dec 2022\n'
        'Contoso Infotech\n'
    )
    assert _count_adjacent_job_dates(extract) >= 2
    assert maybe_reorder_two_column(extract, file_data=None) is None


def test_current_employer_then_role_is_one_job():
    jobs = parse_experience(
        'Experience\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Jan 2023 - Present\n'
        'Senior Software Engineer\n'
        '• Developed REST APIs\n'
    )
    assert len(jobs) == 1
    hit = jobs[0]
    assert 'northwind' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')
    assert 'developed' in (hit.description or '').lower()


def test_role_then_current_employer_is_one_job():
    jobs = parse_experience(
        'Experience\n'
        'Senior Software Engineer\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Jan 2023 - Present\n'
        '• Developed REST APIs\n'
    )
    assert len(jobs) == 1
    hit = jobs[0]
    assert 'northwind' in (hit.company or '').lower()
    assert 'engineer' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2023')
    assert 'developed' in (hit.description or '').lower()


def test_skills_sidebar_survives_date_rail_reconstruct():
    from app.ai.document_intelligence.layout_doc import LayoutLine, _reconstruct_page_regions

    lines = _reconstruct_page_regions(
        [
            LayoutLine(text='Experience', bbox=(48, 90, 140, 102), page=1),
            LayoutLine(text='Software Engineer', bbox=(48, 110, 180, 122), page=1),
            LayoutLine(text='Jan 2023 - Present', bbox=(360, 110, 500, 122), page=1),
            LayoutLine(text='Northwind Ltd', bbox=(48, 124, 180, 136), page=1),
            LayoutLine(text='• Developed REST APIs', bbox=(48, 138, 250, 150), page=1),
            LayoutLine(text='Skills', bbox=(360, 156, 420, 168), page=1),
            LayoutLine(text='Python', bbox=(360, 170, 420, 182), page=1),
            LayoutLine(text='FastAPI', bbox=(360, 184, 420, 196), page=1),
            LayoutLine(text='Docker', bbox=(360, 198, 420, 210), page=1),
            LayoutLine(text='AWS', bbox=(360, 212, 420, 224), page=1),
        ]
    )
    blob = '\n'.join(lines)
    assert 'software engineer' in blob.lower()
    assert 'jan 2023' in blob.lower()
    assert 'skills' in blob.lower()
    assert 'python' in blob.lower()
    assert blob.lower().find('skills') > blob.lower().find('developed rest')

    profile, form, *_ = parse_resume_text_to_canonical(
        'Pat Lee\npat@example.com\n'
        'Experience\n'
        'Software Engineer\nNorthwind Ltd\nJan 2023 - Present\n'
        '• Developed REST APIs\n'
        'Skills\nPython\nFastAPI\nDocker\nAWS\n'
    )
    assert form.experiences
    assert 'northwind' in (form.experiences[0].company or '').lower()
    skills = (form.skills or '').lower()
    assert 'python' in skills
    assert 'fastapi' in skills or 'docker' in skills


def test_employer_metadata_does_not_leak_between_jobs():
    jobs = parse_experience(
        'Experience\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Jan 2023 - Present\n'
        'Senior Software Engineer\n'
        '• Built billing APIs\n'
        'Past Employer: Contoso Infotech\n'
        'Tenure: Jan 2021 - Dec 2022\n'
        'Database Administrator\n'
        '• Administered Oracle databases\n'
    )
    assert len(jobs) >= 2
    nw = _hit(jobs, company='northwind')
    co = _hit(jobs, company='contoso')
    assert 'engineer' in (nw.role or '').lower()
    assert 'billing' in (nw.description or '').lower()
    assert 'oracle' not in (nw.description or '').lower()
    assert 'administrator' in (co.role or '').lower() or 'dba' in (co.role or '').lower()
    assert 'oracle' in (co.description or '').lower()
    assert 'billing' not in (co.description or '').lower()


def test_company_only_metadata_attaches_not_bogus_row():
    jobs = parse_experience(
        'Experience\n'
        'Senior Software Engineer\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Mar 2022 - Present\n'
        'Supported production hosts.\n'
        'Organization:\n'
        'Adventure Works\n'
    )
    companies = [(j.company or '').lower() for j in jobs]
    roles = [(j.role or '').lower() for j in jobs]
    assert any('northwind' in c for c in companies)
    assert any('engineer' in r for r in roles)
    lone = [j for j in jobs if 'adventure' in (j.company or '').lower() and not (j.role or '').strip()]
    assert not lone


def test_intern_first_remains_row_zero():
    jobs = parse_experience(
        'Experience\n'
        'Intern\n'
        'Northwind Ltd\n'
        'Jun 2022 - Aug 2022\n'
        'Assisted with API tests.\n'
        'Software Engineer\n'
        'Contoso Infotech\n'
        'Jan 2023 - Present\n'
        'Developed backend services.\n'
    )
    assert jobs
    first = jobs[0]
    assert 'intern' in (first.role or '').lower()
    assert 'northwind' in (first.company or '').lower()
    assert (first.start or '').startswith('2022')


def test_organization_section_recovers_employment_evidence():
    from app.ai.document_intelligence.parsers.resume import parse_resume_from_sections
    from app.ai.parser.engine.types import SectionSpan

    profile = parse_resume_from_sections(
        [
            SectionSpan(label='Preamble', start=0, end=20, text='Pat Lee\npat@example.com\n'),
            SectionSpan(label='Experience', start=20, end=40, text='EMPLOYMENT DETAILS\n'),
            SectionSpan(
                label='Unclassified',
                start=40,
                end=200,
                text=(
                    'Other Skills\n'
                    'Organization: KG Information System PVT LTD (KGISL)\n'
                    'Team Lead\n'
                    'Jan 2021 - Present\n'
                    '• Led a team of 6 developers\n'
                ),
            ),
        ],
        'Pat Lee\npat@example.com\nEMPLOYMENT DETAILS\n'
        'Organization: KG Information System PVT LTD (KGISL)\n'
        'Team Lead\nJan 2021 - Present\n'
        '• Led a team of 6 developers\n',
    )
    assert profile.experience
    blob = ' '.join(
        f'{e.company or ""} {e.role or ""}' for e in profile.experience
    ).lower()
    assert 'kgisl' in blob or 'kg information' in blob
    assert 'lead' in blob or 'team' in blob


def test_employer_not_replaced_by_client():
    jobs = parse_experience(
        'Experience\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Dec 2021 – Present\n'
        'Database Administrator\n'
        'Contoso Infotech Pvt Ltd (Client – Northwind Ltd)\n'
        '• Configured high availability clusters\n'
    )
    assert jobs
    hit = jobs[0]
    assert 'contoso' in (hit.company or '').lower()
    assert 'northwind' not in (hit.company or '').lower()
    assert 'administrator' in (hit.role or '').lower() or 'dba' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2021')


def test_client_then_employer_then_role():
    jobs = parse_experience(
        'Experience\n'
        'Client: Northwind Ltd\n'
        'Employer: Contoso Infotech Pvt Ltd\n'
        'Role: Database Administrator\n'
        'Tenure: Jan 2022 - Present\n'
        '• Administered PostgreSQL clusters\n'
    )
    hit = _hit(jobs, company='contoso', role='administrator')
    assert 'contoso' in (hit.company or '').lower()
    assert 'northwind' not in (hit.company or '').lower()
    assert 'administrator' in (hit.role or '').lower()


def test_employer_then_role_then_client():
    jobs = parse_experience(
        'Experience\n'
        'Techberry Infotech | Navi Mumbai, Maharashtra\n'
        'Position: Technical Consultant\n'
        'Client: Northwind Finance\n'
        'Duration: June 2024 – Present\n'
        '• Implemented CI/CD pipelines\n'
    )
    hit = _hit(jobs, company='techberry', role='consultant')
    assert 'techberry' in (hit.company or '').lower()
    assert 'northwind' not in (hit.company or '').lower()
    assert 'consultant' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2024')


def test_payroll_company_not_client_company():
    jobs = parse_experience(
        'Experience\n'
        'Database Administrator\n'
        'Payroll Company: Nayagara Technologies\n'
        'Duration: 2021 - 2025\n'
        'Client Company: Calsoft Pvt. Ltd.\n'
        '• Installed and configured MongoDB\n'
    )
    hit = _hit(jobs, role='administrator')
    assert 'nayagara' in (hit.company or '').lower()
    assert 'calsoft' not in (hit.company or '').lower()
    assert (hit.start or '').startswith('2021')


def test_same_row_abbreviated_year_date():
    jobs = parse_experience(
        'Experience\n'
        "Associate Sales Manager, SpectrumTek, Bellevue, WA Dec'21– Present\n"
        '• Research and pre-qualify prospects\n'
    )
    hit = jobs[0]
    assert 'spectrum' in (hit.company or '').lower() or 'sales' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2021')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')


def test_right_side_date_rail_still_pairs():
    from app.ai.document_intelligence.layout_doc import LayoutLine, _reconstruct_page_regions

    lines = _reconstruct_page_regions(
        [
            LayoutLine(text='Experience', bbox=(48, 90, 140, 102), page=1),
            LayoutLine(text='Software Engineer', bbox=(48, 110, 180, 122), page=1),
            LayoutLine(text='Jan 2023 - Present', bbox=(360, 110, 500, 122), page=1),
            LayoutLine(text='Northwind Ltd', bbox=(48, 124, 180, 136), page=1),
            LayoutLine(text='• Developed REST APIs', bbox=(48, 138, 250, 150), page=1),
        ]
    )
    blob = '\n'.join(lines)
    jobs = parse_experience(blob)
    hit = _hit(jobs, company='northwind', role='engineer')
    assert (hit.start or '').startswith('2023')


def test_stacked_abbreviated_date_then_company_then_role():
    jobs = parse_experience(
        'Experience\n'
        "Aug'20 – Till date\n"
        'Aparajitha Corporate Service Pvt Ltd - Mumbai, Maharashtra\n'
        'Role: Compliance Executive\n'
        '• Handling professional tax remittance\n'
    )
    hit = _hit(jobs, role='compliance')
    assert 'aparajitha' in (hit.company or '').lower()
    assert 'compliance' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2020')
    assert hit.is_current or (hit.end or '').lower() in ('', 'present')


def test_docx_table_like_labeled_company_duration_role():
    jobs = parse_experience(
        'Professional Experience And Accomplishments\n'
        'Name of the Company\t: CLOVER INFOTECH\n'
        'Period/ Duration\t: 24 DEC 2024 to till date\n'
        'Designation\t: POSTGRE SQL DBA\n'
        'Knowledge about PostgreSQL installation\n'
    )
    hit = _hit(jobs, company='clover', role='dba')
    assert 'clover' in (hit.company or '').lower()
    assert 'dba' in (hit.role or '').lower() or 'postgres' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2024')


def test_prose_with_org_as_role_and_abbreviated_dates():
    jobs = parse_experience(
        'Previous Experience\n'
        "Jun'18-Sep'21 with Kotak Mahindra Bank Limited, Mumbai as Sr. Manager\n"
        '• Implemented network security controls\n'
    )
    hit = _hit(jobs, company='kotak', role='manager')
    assert 'kotak' in (hit.company or '').lower()
    assert 'manager' in (hit.role or '').lower()
    assert (hit.start or '').startswith('2018')
    assert (hit.end or '').startswith('2021')


def test_education_dates_do_not_become_employment_period():
    _profile, form, *_ = parse_resume_text_to_canonical(
        'Pat Lee\npat@example.com\n'
        'Experience\n'
        'Software Engineer\n'
        'ABC Ltd\n'
        '• Developed REST APIs\n'
        'Education\n'
        'B.Tech\n'
        '2019 - 2022\n'
    )
    assert form.experiences
    job = form.experiences[0]
    assert 'abc' in (job.company or '').lower()
    assert (job.startMonth or '') != '2019'
    assert (job.endMonth or '') != '2022'


def test_multiple_jobs_keep_distinct_dates():
    jobs = parse_experience(
        'Experience\n'
        'Software Engineer\n'
        'Northwind Ltd\n'
        'Jan 2019 - Dec 2021\n'
        '• Built APIs\n'
        'Database Administrator\n'
        'Contoso Pvt Ltd\n'
        'Jan 2022 - Present\n'
        '• Administered Oracle\n'
    )
    assert len(jobs) >= 2
    nw = _hit(jobs, company='northwind')
    co = _hit(jobs, company='contoso')
    assert (nw.start or '').startswith('2019')
    assert (nw.end or '').startswith('2021')
    assert (co.start or '').startswith('2022')
    assert 'oracle' not in (nw.description or '').lower()


def test_skills_empty_heading_recovers_labeled_and_token_run():
    _profile, form, *_ = parse_resume_text_to_canonical(
        'Pat Lee\npat@example.com\n'
        'Skills\n'
        'S\n'
        'Experience\n'
        'Software Engineer\n'
        'Northwind Ltd\n'
        'Jan 2023 - Present\n'
        '• Developed REST APIs\n'
        'VMware Server\n'
        'Oracle WebLogic Server\n'
        'IBM WAS\n'
        'Basic Sql\n'
        'Patch Management\n'
        'Databases: MySQL, PostgreSQL\n'
    )
    skills = (form.skills or '').lower()
    assert 'mysql' in skills or 'vmware' in skills or 'weblogic' in skills


def test_skills_docx_two_column_leftover_tokens():
    from app.ai.document_intelligence.parsers.resume import parse_skills

    skills = parse_skills(
        'Skills\nS\n',
        'Skills\nS\n'
        'Experience\nSoftware Engineer\nNorthwind Ltd\nJan 2023 - Present\n'
        'VMware Server\nOutlook\nPatching Windows\nOracle WebLogic Server\nBasic Sql\n',
    )
    names = ' '.join(s.name.lower() for s in skills)
    assert 'vmware' in names or 'weblogic' in names or 'outlook' in names


def test_skills_labeled_section_not_duties():
    from app.ai.document_intelligence.parsers.resume import parse_skills

    skills = parse_skills(
        'Skills\nPython\nSQL\nDocker\n',
        'Experience\nSoftware Engineer\nNorthwind Ltd\n'
        '• Developed REST APIs and managed deployments\n'
        'Skills\nPython\nSQL\nDocker\n',
    )
    names = ' '.join(s.name.lower() for s in skills)
    assert 'python' in names
    assert 'developed' not in names


def test_languages_list_is_not_a_job():
    jobs = parse_experience(
        'Experience\n'
        'Name of the Company: CLOVER INFOTECH\n'
        'Period/ Duration: 24 DEC 2024 to till date\n'
        'Designation: POSTGRE SQL DBA\n'
        'Known Language : Odia, Hindi, English\n'
        'Hindi, English\n'
    )
    assert jobs
    companies = ' '.join((j.company or '').lower() for j in jobs)
    roles = ' '.join((j.role or '').lower() for j in jobs)
    assert 'clover' in companies
    assert 'hindi' not in companies
    assert 'odia' not in roles
    assert 'language' not in roles


def test_role_only_header_merges_into_following_employer():
    jobs = parse_experience(
        'Experience\n'
        'Training and Content Development Manager\n'
        'July 2023 - Present\n'
        'Loan Network Technology Pvt Ltd.\n'
        '• Identify training needs and deliver classroom programs\n'
        'Assistant Manager\n'
        'Bharat Financial Inclusion\n'
        'Sept 2021 - June 2023\n'
        '• Facilitated virtual training programs\n'
    )
    first = jobs[0]
    assert 'loan network' in (first.company or '').lower()
    assert 'manager' in (first.role or '').lower()
    assert (first.start or '').startswith('2023')


def test_client_org_complete_job_outranks_labeled_employer_stub():
    jobs = parse_experience(
        'Experience\n'
        'Current Employer: Northwind Ltd\n'
        'Tenure: Dec 2021 – Present\n'
        'Past Employer: Contoso Infotech\n'
        'Tenure: Feb 2021 - Dec 2021\n'
        'DBA\n'
        'Contoso Infotech Pvt Ltd (Client – Northwind Ltd)\n'
        'Feb 2021 – Present\n'
        '• Configured PgPool to achieve high availability\n'
    )
    first = jobs[0]
    assert 'contoso' in (first.company or '').lower()
    assert 'northwind' not in (first.company or '').lower()
    assert 'dba' in (first.role or '').lower() or 'administrator' in (first.role or '').lower()
    assert first.start


def test_experience_colon_org_heading_attaches_title_tenure():
    profile, form, *_ = parse_resume_text_to_canonical(
        'SUMMERRY\n'
        'EXPERIENCE  : Northwind Consultancy Services                                      2023 -  Present\n'
        'RESUME\n'
        'Name: Pat Lee  |   Email: pat@example.com\n'
        'Mob.No; +91-9529952829  |   LinkedIn:  www.linkedin.com/in/pat-lee\n'
        'Middleware & DevOps Engineer with 1.7+ years of hands-on experience in configuring servers.\n'
        'Middleware & DevOps Engineer : 1.7+ Year\n'
        '• Installed and configured Oracle WebLogic and Apache Tomcat\n'
        'Skills\n'
        'WebLogic, Jenkins, Docker\n'
        'Education\n'
        'B.E in Mechanical Engineering                                                                 2019 - 2023\n',
        allow_semantic=False,
    )
    assert profile.experience
    first = profile.experience[0]
    assert 'northwind' in (first.company or '').lower()
    assert 'mob' not in (first.company or '').lower()
    assert 'engineer' in (first.role or '').lower()
    assert (first.start or '').startswith('2023')
    edu_blob = ' '.join(
        f'{e.institution or ""} {e.start or ""} {e.end or ""}' for e in (profile.education or [])
    )
    assert '2019' not in (first.start or '')
    assert '2019' in edu_blob or not profile.education


def test_banner_title_attaches_to_roleless_employer():
    profile, form, *_ = parse_resume_text_to_canonical(
        'Pat Lee\n'
        'Database Administrator | Relational, Cloud & NoSQL Databases\n'
        'Email: pat@example.com\n'
        'PROFESSIONAL SUMMARY\n'
        'Results-driven Database Administrator with 3.5+ years of enterprise experience.\n'
        'Skills\n'
        'MySQL, MongoDB\n'
        'Experience\n'
        'Northwind Infotech Pvt Ltd\n'
        'Mumbai   (June 2022 – Present)\n'
        '• Installed and configured MySQL in production\n'
        'Education\n'
        'B.Sc Computer Science  2018 - 2021  CGPA 8.0\n',
        allow_semantic=False,
    )
    assert profile.experience
    first = profile.experience[0]
    assert 'northwind' in (first.company or '').lower()
    assert 'mumbai' not in (first.role or '').lower()
    assert 'administrator' in (first.role or '').lower()
    assert (first.start or '').startswith('2022')


def test_complete_job_outranks_company_only_metadata_row():
    jobs = parse_experience(
        'Experience\n'
        'Northwind Ltd\n'
        'Dec 2021 – Present\n'
        '• Roles and Responsibilities: Configured high availability clusters\n'
        'Database Administrator\n'
        'Contoso Infotech Pvt Ltd\n'
        'Feb 2021 – Present\n'
        '• Configured PgPool to achieve high availability\n'
    )
    first = jobs[0]
    assert 'contoso' in (first.company or '').lower()
    assert 'administrator' in (first.role or '').lower() or 'dba' in (first.role or '').lower()
