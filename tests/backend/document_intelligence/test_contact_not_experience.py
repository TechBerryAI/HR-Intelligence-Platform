"""Contact/reference must never become Experience; Technical Proficiency maps to Skills."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical  # noqa: E402
from app.ai.document_intelligence.validation.engine import (  # noqa: E402
    sanitize_experience_row,
    validate_company,
)
from app.ai.document_intelligence.models.candidate import ExperienceEntry  # noqa: E402
from app.ai.parser.engine.sections import detect_sections  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    extract_skills_from_text,
    is_contact_or_reference_line,
    is_non_job_experience_record,
    looks_like_contact_person_line,
    looks_like_phone_token,
)
from app.ai.parser.layout.heuristic import structure_text_by_headers  # noqa: E402

FIXTURE = ROOT / 'tests' / 'backend' / 'fixtures' / 'resume_gold' / 'vishal_waghmode_pymupdf.txt'


def _parse(text: str):
    return parse_resume_text_to_canonical(text, allow_semantic=False)


def _skill_names(profile) -> list[str]:
    return [str(s.canonical or s.name or '').strip() for s in (profile.skills or [])]


def _skill_blob(profile) -> str:
    return ' '.join(_skill_names(profile)).lower()


def _assert_no_fake_reference_job(profile) -> None:
    for exp in profile.experience:
        company = (exp.company or '').strip()
        role = (exp.role or '').strip()
        assert '9575342145' not in company
        assert '9326579987' not in company
        assert 'ayush' not in role.lower()
        assert 'saxsena' not in role.lower()
        assert 'nipul' not in role.lower()
        assert not looks_like_phone_token(company)
        assert not is_non_job_experience_record(exp)


def test_a_contact_person_after_experience():
    text = """
Jane Doe
jane@example.com

Experience
Software Engineer
Acme Corp
01/2020 - Present
Built APIs.

Contact
Priya Sharma (Manager)
9998887776
"""
    profile, form, _ = _parse(text)
    _assert_no_fake_reference_job(profile)
    companies = [e.company.lower() for e in profile.experience]
    roles = [e.role.lower() for e in profile.experience]
    assert any('acme' in c for c in companies)
    assert any('engineer' in r for r in roles)
    assert not any('priya' in r for r in roles)
    assert not any('9998887776' in c for c in companies)


def test_b_phone_number_after_contact_person():
    text = """
Experience
Analyst
Beta Ltd
03/2021 - 06/2023
Did analysis.

Contact: Rohan Mehta (Lead) - 9123456780
"""
    profile, form, _ = _parse(text)
    _assert_no_fake_reference_job(profile)
    assert not any(looks_like_phone_token(e.company) for e in profile.experience)
    assert any('beta' in (e.company or '').lower() for e in profile.experience)


def test_c_manager_project_head_reference():
    assert looks_like_contact_person_line('Ayush Saxsena (Project Head)')
    assert looks_like_contact_person_line('Contact: Ayush Saxsena (Project Head) - 9575342145')
    assert is_contact_or_reference_line('9575342145')
    assert is_non_job_experience_record(
        {'role': 'Ayush Saxsena (Project Head)', 'company': '9575342145', 'start': '', 'end': ''}
    )
    cleaned = sanitize_experience_row(
        ExperienceEntry(role='Ayush Saxsena (Project Head)', company='9575342145')
    )
    assert not cleaned.role and not cleaned.company
    ok, reason = validate_company('9575342145')
    assert not ok
    assert 'phone' in reason


def test_d_location_immediately_after_contact_reference():
    text = """
Experience
Developer
Gamma Systems
01/2019 - Present
Wrote services.

Contact: Ayush Saxsena (Project Head) - 9575342145
Mumbai
"""
    profile, form, _ = _parse(text)
    _assert_no_fake_reference_job(profile)
    fake = [
        e
        for e in profile.experience
        if (e.company or '').strip() == '9575342145'
        or 'ayush' in (e.role or '').lower()
    ]
    assert fake == []
    assert any('gamma' in (e.company or '').lower() for e in profile.experience)


def test_e_technical_proficiency_section():
    text = """
Name Person
n@example.com

Experience
Engineer
Acme Ltd
01/2020 - Present
Built tools.

TECHNICAL PROFICIENCY:
C#
.NET Core
SQL
HTML5
CSS3
JavaScript
Multi-Threading
Data Structure
Agile
"""
    profile, form, _ = _parse(text)
    blob = _skill_blob(profile)
    for token in ('c#', 'sql', 'html5', 'css3', 'javascript', 'agile'):
        assert token in blob, f'missing {token} in {blob!r}'
    assert '.net' in blob
    assert 'ed in c#' not in blob
    assert 'n@example.com' not in blob


def test_f_normal_skills_section():
    text = """
Name Person
n@example.com

Skills:
Python, Docker, Kubernetes

Experience
Engineer
Acme Ltd
01/2020 - Present
Built tools.
"""
    profile, form, _ = _parse(text)
    blob = _skill_blob(profile)
    assert 'python' in blob
    assert 'docker' in blob
    assert 'kubernetes' in blob


def test_g_two_column_resume_vishal_extract():
    text = FIXTURE.read_text(encoding='utf-8')
    profile, form, _ = _parse(text)
    _assert_no_fake_reference_job(profile)

    companies = [(e.company or '') for e in profile.experience]
    roles = [(e.role or '') for e in profile.experience]
    assert any('Tata Consultancy Services' in c for c in companies)
    assert any('National Stock Exchange' in c for c in companies)
    assert any('Assistant System Engineer' in r for r in roles)
    assert any('Assistant System Analyst' in r for r in roles)

    tcs = next(e for e in profile.experience if 'Tata Consultancy' in (e.company or ''))
    assert (tcs.start or '').startswith('2022-07') or tcs.start in {'07/2022', '2022-07'}
    assert tcs.is_current or (tcs.end or '').lower() in {'present', ''}

    nseit = next(e for e in profile.experience if 'NSEIT' in (e.company or '') or 'National Stock' in (e.company or ''))
    assert (nseit.start or '').startswith('2024-06') or nseit.start in {'06/2024', '2024-06'}
    assert nseit.is_current or (nseit.end or '').lower() in {'present', ''}
    loc = (nseit.location or nseit.description or '').lower()
    assert 'mumbai' in loc
    nseit_desc = (nseit.description or '').lower()
    assert 'c#' in nseit_desc or '.net' in nseit_desc or 'multithread' in nseit_desc

    tcs_loc = (tcs.location or '').lower()
    assert 'thane' in tcs_loc or 'mumbai' in tcs_loc
    tcs_desc = (tcs.description or '').lower()
    assert 'professional development' in tcs_desc or 'undertaking' in tcs_desc or 'leadership' in tcs_desc

    edu_deg = ' '.join((e.degree or '') for e in profile.education).lower()
    edu_inst = ' '.join((e.institution or '') for e in profile.education).lower()
    assert any('datta meghe' in (e.institution or '').lower() for e in profile.education)
    assert 'bachelor' in edu_deg or 'b.e' in edu_deg
    assert 'information technology' in ' '.join(
        f'{e.degree} {e.field}' for e in profile.education
    ).lower()
    assert not any('aggregate' in (e.institution or '').lower() for e in profile.education)
    be = next(e for e in profile.education if 'datta meghe' in (e.institution or '').lower())
    assert be.gpa
    hsc = next(e for e in profile.education if re.search(r'(?i)\bhsc\b', e.degree or ''))
    assert 'mayer' in (hsc.institution or '').lower() or 'school' in (hsc.institution or '').lower()
    # Do not keep the expanded B.E as a second orphan row
    complete_be = [
        e
        for e in profile.education
        if 'datta meghe' in (e.institution or '').lower()
        or (e.degree or '').lower().startswith('bachelor of engineering')
    ]
    assert len(complete_be) == 1

    blob = _skill_blob(profile)
    for token in ('c#', 'sql', 'html5', 'css3', 'javascript'):
        assert token in blob, f'missing {token} in {_skill_names(profile)!r}'
    assert 'agile' in blob or 'AGILE' in _skill_names(profile)
    assert 'ed in c#' not in blob
    assert 'vishalwaghmode247@gmail.com' not in blob
    assert '8104350466' not in blob
    assert 'linkedin.com' not in blob
    assert 'github.com' not in blob

    labels = [s.label.lower() for s in detect_sections(text, 'resume')]
    exp_idx = labels.index('experience')
    # Contact inside Experience must not become a later top-level section that steals NSEIT
    contact_after_exp = [i for i, lab in enumerate(labels) if lab == 'contact' and i > exp_idx]
    if contact_after_exp:
        # If a Contact section exists after Experience, it must not contain NSEIT
        sections = detect_sections(text, 'resume')
        stolen = sections[contact_after_exp[0]].text
        assert 'National Stock Exchange' not in stolen

    structured = structure_text_by_headers(text)
    # Experience body still contains the second job after in-job Contact
    exp_part = structured.split('Education')[0] if 'Education' in structured else structured
    assert 'National Stock Exchange' in exp_part
    assert 'Assistant System Analyst' in exp_part


def test_h_experience_with_legitimate_contact_information():
    text = """
Experience
Account Manager
Helios Pvt Ltd
02/2018 - 11/2022
Managed enterprise accounts. Reporting contact: Suresh Nair (Director) available on request.
Phone of client desk noted in CRM as 9876501234.
"""
    profile, form, _ = _parse(text)
    assert any('helios' in (e.company or '').lower() for e in profile.experience)
    assert any('manager' in (e.role or '').lower() for e in profile.experience)
    job = next(e for e in profile.experience if 'helios' in (e.company or '').lower())
    assert (job.start or '').startswith('2018') or '2018' in (job.start or '')


def test_i_experience_with_legitimate_phone_in_description():
    text = """
Experience
Support Engineer
Omega Technologies
05/2019 - Present
On-call rotation. Escalation number 022-12345678 is listed in the runbook.
"""
    profile, form, _ = _parse(text)
    assert any('omega' in (e.company or '').lower() for e in profile.experience)
    job = next(e for e in profile.experience if 'omega' in (e.company or '').lower())
    assert 'engineer' in (job.role or '').lower()
    assert not looks_like_phone_token(job.company)


def test_j_resume_without_skills_section():
    text = """
Alex Kumar
alex.kumar@example.com
9876543210
linkedin.com/in/alexkumar

Career Objective
Skilled in c# and teamwork. Passionate engineer seeking a backend role.

Experience
Developer
Nimbus Labs
01/2021 - Present
Shipped APIs.
"""
    profile, form, _ = _parse(text)
    blob = _skill_blob(profile)
    assert 'ed in c#' not in blob
    assert 'alex.kumar@example.com' not in blob
    assert '9876543210' not in blob
    assert 'linkedin.com' not in blob
    # Do not treat the objective sentence as a skills list
    assert not any(s.lower().startswith('skilled in') for s in _skill_names(profile))


def test_skills_fallback_ignores_summary_when_proficiency_exists():
    text = FIXTURE.read_text(encoding='utf-8')
    skills = extract_skills_from_text(text)
    joined = ' '.join(skills).lower()
    assert 'ed in c#' not in joined
    assert 'vishalwaghmode247@gmail.com' not in joined
    assert any('c#' in s.lower() or s.lower() == 'c #' for s in skills) or 'c#' in joined
    assert any('sql' in s.lower() for s in skills)


def test_top_level_contact_details_still_a_section():
    text = """
Jane Doe
Contact Details
jane@example.com
+91 9876543210

Experience
Engineer
Acme Ltd
01/2020 - Present
Built APIs.
"""
    labels = [s.label.lower() for s in detect_sections(text, 'resume')]
    assert 'experience' in labels
    assert any('contact' in lab for lab in labels)


def _vishal_pdf_path() -> Path | None:
    named = [
        Path(r'C:\Users\DELL\Downloads\resume testing') / '#1_Vishal_Waghmode_Resume.pdf',
        Path(r'C:\Users\DELL\Downloads\resume testing') / '1_Vishal_Waghmode_Resume.pdf',
        Path(r'C:\Users\DELL\Downloads') / '#1_Vishal_Waghmode_Resume.pdf',
    ]
    media = Path(r'C:\Users\DELL\Documents\GitHub\hcip-data\media\uploads')
    extra: list[Path] = []
    if media.is_dir():
        extra.extend(media.glob('*Vishal*'))
        extra.extend(media.glob('*1_Vishal*'))
    for p in named + extra:
        if p.is_file():
            return p
    return None


def test_real_vishal_pdf_roundtrip():
    pdf_path = _vishal_pdf_path()
    if pdf_path is None:
        pytest.skip('Vishal Waghmode resume PDF not found on disk')
    from app.ai.parser.text_extraction import extract_text_from_pdf

    raw = extract_text_from_pdf(pdf_path.read_bytes())
    assert 'Assistant System Engineer' in raw
    assert 'Ayush Saxsena' in raw or 'Ayush' in raw
    profile, form, _ = _parse(raw)
    _assert_no_fake_reference_job(profile)
    companies = ' '.join(e.company or '' for e in profile.experience)
    roles = ' '.join(e.role or '' for e in profile.experience)
    assert 'Tata Consultancy' in companies
    assert 'NSEIT' in companies or 'National Stock' in companies
    assert 'Assistant System Engineer' in roles
    assert 'Assistant System Analyst' in roles
    blob = _skill_blob(profile)
    assert 'c#' in blob or 'c #' in blob
    assert 'sql' in blob
    assert 'ed in c#' not in blob
