"""End-to-end tests for the REAL Apply parse path.

These call ``prepare_resume_working_text`` + ``parse_resume_from_working_text``
— the same tail ``_run_resume`` / public parse uses after extraction.
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

from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form  # noqa: E402
from app.ai.document_intelligence.pipeline import (  # noqa: E402
    parse_resume_from_working_text,
    parse_resume_text_to_canonical,
)
from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text  # noqa: E402
from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile  # noqa: E402
from app.ai.parser.enrichment.resume_text_inference import (  # noqa: E402
    document_identity_names,
    peel_inline_contact,
)


def _apply_parse(text: str):
    working = prepare_resume_working_text(text)
    profile, coverage, _sections, used_llm, _toon = parse_resume_from_working_text(
        working,
        allow_semantic=False,
        source_filename='apply-e2e.txt',
    )
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    return profile, form, coverage, used_llm, working


def test_apply_and_canonical_share_prepare_path():
    text = (
        'Alex Rivera\nPhone: +919876543210\nEmail: alex@example.com\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\nBuilt APIs.\n'
        'Skills\nPython, SQL\n'
        'Education\nB.E. in Computer Engineering\nExample University\nMay 2016\n'
    )
    working = prepare_resume_working_text(text)
    via_apply, *_ = parse_resume_from_working_text(working, allow_semantic=False)
    via_canonical, _, _ = parse_resume_text_to_canonical(text, allow_semantic=False)
    assert via_apply.personal.full_name == via_canonical.personal.full_name
    assert [(e.company, e.role, e.start) for e in via_apply.experience] == [
        (e.company, e.role, e.start) for e in via_canonical.experience
    ]


def test_case1_wrapped_employment_bullet():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        '\u27a2 Currently working with Example Technologies, Mumbai as Technical Associate '
        'from March 2020 to\ntill date\n'
        'Education\nB.E. in Computer Engineering\nExample University\n'
    )
    assert form.experiences
    job = form.experiences[0]
    assert 'example technologies' in (job.company or '').lower()
    assert 'technical associate' in (job.role or '').lower()
    assert (job.startMonth or '').startswith('2020-03')
    assert job.isCurrent or (job.endMonth or '').lower() in ('', 'present')


def test_case1_employment_sentence():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Experience\n'
        'Currently working with Example Technologies, Mumbai as Technical Associate '
        'from March 2020 to till date\n'
        'Education\nB.E. in Computer Engineering\nExample University\n'
    )
    _profile, form, coverage, used_llm, _w = _apply_parse(text)
    assert used_llm is False
    assert form.experiences
    job = form.experiences[0]
    assert 'example technologies' in (job.company or '').lower()
    assert 'mumbai as technical' not in (job.company or '').lower()
    assert 'technical associate' in (job.role or '').lower()
    assert 'currently working' not in (job.role or '').lower()
    assert (job.startMonth or '').startswith('2020-03')
    assert job.isCurrent or (job.endMonth or '').lower() in ('', 'present')
    assert 'experience' not in (coverage.missing_with_evidence or [])


def test_case2_role_plus_contact():
    text = (
        'Jordan Hale\nEmail: person@example.com\nPhone: +919876543210\n'
        'Experience\n'
        'Middleware Administrator E-mail: person@example.com\n'
        'July 2022 - Present\n'
        'Managed middleware environments.\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    role = form.experiences[0].role or ''
    assert 'administrator' in role.lower()
    assert 'e-mail' not in role.lower()
    assert '@' not in role
    assert (form.experiences[0].startMonth or '').startswith('2022-07')


def test_case2_glued_contact_label():
    assert peel_inline_contact('Middleware AdministratorE-mail: person@example.com') == (
        'Middleware Administrator'
    )
    assert peel_inline_contact('Jordan HalePlace: Harbor City') == 'Jordan Hale'
    assert peel_inline_contact('Workplace: remote office') == 'Workplace: remote office'


def test_case3_header_identity_not_company_or_skill():
    text = (
        'Jordan Hale\n'
        'Phone: +919876543210\n'
        'Email: jordan.hale@example.com\n'
        'Place: Harbor City\n'
        'Experience\n'
        'Northwind Ltd\n'
        'Software Engineer\n'
        'Jan 2022 - Present\n'
        'Built services.\n'
        'Skills\nPython, SQL, Linux\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    assert profile.personal.full_name == 'Jordan Hale'
    companies = [(e.company or '').lower() for e in profile.experience]
    assert not any('jordan hale' in c for c in companies)
    skills = (form.skills or '').lower()
    assert 'place' not in skills
    assert 'jordan hale' not in skills
    assert 'python' in skills


def test_case4_skills_exclude_header_and_signature():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Skills\n'
        'Python, SQL, Linux, Oracle\n'
        'Place: Harbor City\n'
        'Jordan Hale\n'
        'Signature\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert skills == ['python', 'sql', 'linux', 'oracle']


def test_case5_education_two_line():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\n'
        'B.E. in Computer Engineering\n'
        'Example University\n'
        'May 2016\n'
        'Skills\nPython\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.education
    edu = form.education[0]
    assert 'computer engineering' in (edu.degree or '').lower()
    assert 'example university' in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2016-05')


def test_case6_education_same_line():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\n'
        'Bachelor of Engineering Example University May 2016\n'
        'Skills\nPython\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.education
    edu = form.education[0]
    assert 'bachelor of engineering' in (edu.degree or '').lower()
    assert 'university' not in (edu.degree or '').lower()
    assert 'example university' in (edu.institution or '').lower()
    assert 'engineering' not in (edu.institution or '').lower()


def test_case7_education_stops_at_technical_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\n'
        'Bachelor of Engineering\n'
        'Example University\n'
        '2018\n'
        'Technical Experience\n'
        'Example Technologies\n'
        'Middleware Administrator\n'
        '2020 - Present\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    edu_blob = ' '.join(
        f'{e.degree} {e.institution}' for e in profile.education
    ).lower()
    assert 'technical experience' not in edu_blob
    assert 'middleware' not in edu_blob
    assert form.experiences
    assert 'example technologies' in (form.experiences[0].company or '').lower()
    assert 'administrator' in (form.experiences[0].role or '').lower()


def test_case8_project_is_not_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Projects\n'
        'Project #1\n'
        'Client: Example Client\n'
        'Duration: Jan 2020 - Mar 2020\n'
        'Environment: Linux, Oracle\n'
        'Education\nB.E.\nExample University\n'
    )
    profile, _form, _c, _llm, _w = _apply_parse(text)
    assert not profile.experience


def test_case9_role_plus_dates_survives_without_company():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Experience\n'
        'Middleware Administrator\n'
        'July 2022 - Present\n'
        'Managed middleware environments.\n'
        'Skills\nLinux, Oracle\n'
    )
    profile, form, coverage, used_llm, _w = _apply_parse(text)
    assert used_llm is False
    assert form.experiences
    job = form.experiences[0]
    assert 'administrator' in (job.role or '').lower()
    assert not (job.company or '').strip()
    assert (job.startMonth or '').startswith('2022-07')
    assert job.isCurrent or (job.endMonth or '').lower() in ('', 'present')
    assert 'experience' not in (coverage.missing_with_evidence or [])
    assert any((e.role or '') and e.start for e in profile.experience)


def test_identity_invariant_name_not_company():
    text = (
        'Jordan Hale\nPhone: +919876543210\nEmail: jordan.hale@example.com\n'
        'Experience\nJordan Hale\nMiddleware Administrator\nJan 2022 - Present\n'
    )
    profile, form, _c, _llm, working = _apply_parse(text)
    names = document_identity_names(working)
    assert 'jordan hale' in names
    assert profile.personal.full_name == 'Jordan Hale'
    assert not any((e.company or '').strip().lower() == 'jordan hale' for e in profile.experience)
    assert not any((e.company or '').strip().lower() == 'jordan hale' for e in form.experiences)


def test_invariants_contact_identity_and_sections():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Place: Harbor City\n'
        'Education\nB.E. in Computer Engineering\nExample University\n2018\n'
        'Technical Experience\nExample Technologies\nEngineer\n2020 - Present\n'
        'Projects\nClient: Example Client\nDuration: Jan 2020 - Mar 2020\n'
        'Skills\nPython, SQL\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    role_blob = ' '.join((e.role or '') for e in profile.experience).lower()
    company_blob = ' '.join((e.company or '') for e in profile.experience).lower()
    skill_blob = (form.skills or '').lower()
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in profile.education).lower()
    assert '@' not in role_blob and 'e-mail' not in role_blob
    assert 'jordan hale' not in company_blob
    assert 'example client' not in company_blob
    assert 'technical experience' not in edu_blob
    assert 'python' in skill_blob
    assert 'jordan.hale@example.com' not in skill_blob
    assert '+919876543210' not in skill_blob
    assert 'harbor city' not in skill_blob
    assert 'jordan hale' not in skill_blob


def test_final_sanitize_is_last_writer():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    working = prepare_resume_working_text(text)
    profile, _coverage, _s, _llm, _t = parse_resume_from_working_text(
        working, allow_semantic=False
    )
    again = sanitize_candidate_profile(profile, source_text=working)
    assert [(e.company, e.role, e.start) for e in again.experience] == [
        (e.company, e.role, e.start) for e in profile.experience
    ]
    assert again.personal.full_name == profile.personal.full_name


def test_layout_two_column_contact_and_experience():
    text = (
        'Jordan Hale\nPhone: +919876543210\nEmail: jordan.hale@example.com\n'
        'Skills\nPython, SQL\n'
        'Experience\nNorthwind Ltd\nSoftware Engineer\nJan 2022 - Present\n'
        'Education\nB.E. in Computer Engineering\nExample University\n2016\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    assert profile.personal.full_name == 'Jordan Hale'
    assert form.experiences
    assert 'northwind' in (form.experiences[0].company or '').lower()
    assert 'engineer' in (form.experiences[0].role or '').lower()
    assert 'python' in (form.skills or '').lower()
    assert 'jordan hale' not in (form.skills or '').lower()


def test_layout_two_column_skills_and_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\nPython, SQL, Linux\n'
        'Experience\nExample Technologies\nTechnical Associate\nMarch 2020 - Present\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    skills = (form.skills or '').lower()
    assert 'python' in skills and 'linux' in skills
    assert form.experiences
    assert 'example technologies' in (form.experiences[0].company or '').lower()
    assert 'technical associate' in (form.experiences[0].role or '').lower()


def test_layout_glued_section_heading():
    from app.ai.parser.layout.heuristic import split_glued_heading_line

    heading, rest = split_glued_heading_line('SkillsPython, SQL, Linux')
    assert heading == 'Skills'
    assert 'python' in rest.lower()
    heading, rest = split_glued_heading_line('EducationBachelor of Engineering')
    assert heading == 'Education'
    assert 'bachelor' in rest.lower()
    assert split_glued_heading_line('Developer') == (None, 'Developer')
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'SkillsPython, SQL, Linux\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert 'python' in (form.skills or '').lower()
    assert 'developer' not in (form.skills or '').lower()


def test_layout_glued_contact_label():
    assert peel_inline_contact('Middleware AdministratorE-mail: person@example.com') == (
        'Middleware Administrator'
    )
    text = (
        'Jordan Hale\nEmail: person@example.com\n'
        'Experience\nMiddleware AdministratorE-mail: person@example.com\n'
        'July 2022 - Present\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    role = form.experiences[0].role or ''
    assert 'administrator' in role.lower()
    assert '@' not in role and 'e-mail' not in role.lower()


def test_layout_employment_wrapped_three_lines():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Currently working with Example Technologies,\n'
        'Harbor City as Technical Associate\n'
        'from March 2020 to till date\n'
        'Education\nB.E. in Computer Engineering\nExample University\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    job = form.experiences[0]
    assert 'example technologies' in (job.company or '').lower()
    assert 'technical associate' in (job.role or '').lower()
    assert (job.startMonth or '').startswith('2020-03')
    assert job.isCurrent or (job.endMonth or '').lower() in ('', 'present')


def test_layout_employment_bullet_is_job():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        '• Working as Middleware Administrator for Example Technologies '
        'from July 2022 to Present\n'
        '• Installed patches on Linux servers\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    job = form.experiences[0]
    assert 'administrator' in (job.role or '').lower()
    assert 'example technologies' in (job.company or '').lower()
    assert (job.startMonth or '').startswith('2022-07')
    desc = ' '.join((e.description or '') for e in profile.experience).lower()
    assert 'installed patches' in desc
    assert not any('installed patches' in (e.role or '').lower() for e in profile.experience)


def test_layout_duty_bullet_is_not_job():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Northwind Ltd | Engineer | Jan 2022 - Present\n'
        '• Installed patches on Linux servers\n'
        '• Developed REST APIs\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    assert len(form.experiences) == 1
    assert 'northwind' in (form.experiences[0].company or '').lower()
    desc = (profile.experience[0].description or '').lower()
    assert 'installed patches' in desc


def test_layout_education_wrapped_institution():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\n'
        'B.E. in Computer Engineering\n'
        'Example\n'
        'University\n'
        'May 2016\n'
        'Skills\nPython\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.education
    edu = form.education[0]
    assert 'computer engineering' in (edu.degree or '').lower()
    assert 'example university' in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2016-05')


def test_layout_education_same_line_no_separator():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nBachelor of Engineering Example University May 2016\n'
        'Skills\nPython\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    edu = form.education[0]
    assert 'bachelor of engineering' in (edu.degree or '').lower()
    assert 'university' not in (edu.degree or '').lower()
    assert 'example university' in (edu.institution or '').lower()


def test_layout_education_stops_at_glued_technical_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nBachelor of Engineering\nExample University\n2018\n'
        'Technical ExperienceExample Technologies\n'
        'Middleware Administrator\n2020 - Present\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in profile.education).lower()
    assert 'technical experience' not in edu_blob
    assert 'middleware' not in edu_blob
    assert form.experiences
    assert 'example technologies' in (form.experiences[0].company or '').lower()


def test_layout_skills_then_declaration():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\nPython, SQL, Linux, Oracle\n'
        'Declaration\nI hereby declare the information is true.\n'
        'Place: Harbor City\nJordan Hale\nSignature\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills and 'oracle' in skills
    assert 'harbor city' not in (form.skills or '').lower()
    assert 'jordan hale' not in (form.skills or '').lower()
    assert 'declare' not in (form.skills or '').lower()


def test_layout_invariants_name_heading_and_dto():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Skills\nPython\n'
    )
    profile, form, _c, _llm, working = _apply_parse(text)
    from app.ai.parser.layout.heuristic import normalize_section_header

    assert normalize_section_header(profile.personal.full_name or '') is None
    assert profile.personal.full_name == form.fullName
    assert not any((e.company or '').lower() == 'jordan hale' for e in profile.experience)
    assert '@' not in (form.experiences[0].role or '')
    assert '+91' not in (form.experiences[0].role or '')
    again = sanitize_candidate_profile(profile, source_text=working)
    assert again.personal.full_name == profile.personal.full_name
    assert [(e.company, e.role, e.start) for e in again.experience] == [
        (e.company, e.role, e.start) for e in profile.experience
    ]


def test_public_apply_form_dto_fields():
    """Final payload keys are what Apply receives from build_resume_client_payload."""
    from app.ai.document_intelligence.response import build_resume_client_payload

    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Place: Harbor City\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\nBuilt APIs.\n'
        'Skills\nPython, SQL\n'
        'Education\nB.E. in Computer Engineering\nExample University\nMay 2016\n'
        'Summary\nEngineer focused on reliable services.\n'
    )
    profile, form, coverage, _llm, _w = _apply_parse(text)
    payload = build_resume_client_payload({
        'status': 'ok',
        'form': form.to_autofill_dict(),
        'canonical': profile.model_dump(),
    })
    final = payload['form']
    assert final['fullName'] == form.fullName == profile.personal.full_name
    assert final['email'] == form.email
    assert final['phone'] == form.phone
    assert final['currentLocation'] == form.currentLocation
    assert final['experiences']
    assert final['education']
    assert 'python' in (final.get('skills') or '').lower()
    assert (final.get('summary') or form.summary)
    from app.domains.recruitment.api import parsing as parsing_api
    assert 'run_resume_parse_pipeline' in parsing_api.parse_resume_public.__code__.co_names


def test_layout_two_column_header_sidebar_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Summary\nReliable engineer.\n'
        'Skills\nPython\nSQL\n'
        'Languages\nEnglish\n'
        'Company Name: Northwind Ltd\n'
        'Role: Engineer\n'
        'Duration: Jan 2022 - Present\n'
        'Experience\n'
        'Declaration\nI hereby declare the information is true.\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    assert 'northwind' in (form.experiences[0].company or '').lower()
    assert 'engineer' in (form.experiences[0].role or '').lower()
    assert (form.experiences[0].startMonth or '').startswith('2022-01')


def test_layout_two_column_skills_and_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Python, SQL\n'
        'Languages\n'
        'English, Hindi\n'
        'Experience\n'
        'Northwind Ltd | Engineer | Jan 2022 - Present\n'
        '• Built APIs\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    assert 'northwind' in (form.experiences[0].company or '').lower()
    skills = (form.skills or '').lower()
    assert 'python' in skills
    assert 'built apis' not in skills


def test_layout_full_width_header_two_column_body():
    text = (
        'JORDAN HALE\nMiddleware Administrator\n'
        'Email: jordan.hale@example.com\nPhone: +919876543210\n'
        'Technical Skills\nLinux, Python\n'
        'Experience\n'
        'Example Technologies\nMiddleware Administrator\nJuly 2022\nPresent\n'
        '• Managed middleware servers\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.fullName
    assert form.experiences
    assert 'example technologies' in (form.experiences[0].company or '').lower()
    assert 'middleware' in (form.experiences[0].role or '').lower()


def test_layout_glued_heading_and_contact():
    from app.ai.parser.layout.heuristic import split_glued_heading_line

    heading, rest = split_glued_heading_line('ExperienceDeveloper')
    assert heading == 'Experience'
    assert 'developer' in rest.lower()
    heading, intact = split_glued_heading_line('Developer')
    assert heading is None
    assert intact == 'Developer'
    peeled = peel_inline_contact('AdministratorE-mail: a@b.com')
    assert 'administrator' in peeled.lower()
    assert '@' not in peeled
    peeled_m = peel_inline_contact('AdministratorMobile9876543210')
    assert 'administrator' in peeled_m.lower()
    assert '9876543210' not in peeled_m


def test_layout_experience_table():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        "Organization's Name | Designation | From | To | Location\n"
        'Example Technologies | Middleware Administrator | 20-JAN-2021 | Till Date | Harbor City\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    job = form.experiences[0]
    assert 'example technologies' in (job.company or '').lower()
    assert 'middleware' in (job.role or '').lower()
    assert job.isCurrent or (job.startMonth or '').startswith('2021')


def test_layout_education_table():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\n'
        'Degree | University/Board | Year of Pass out | Percentage\n'
        'B.E. in Computer Engineering | Example University | 2016 | 72.00\n'
        'Experience\nNorthwind Ltd | Engineer | Jan 2022 - Present\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.education
    assert 'computer engineering' in (form.education[0].degree or '').lower()
    assert 'example university' in (form.education[0].institution or '').lower()
    assert form.experiences


def test_layout_sparse_docx_paragraph_structure():
    text = (
        'Jordan Hale\n'
        '+91-9876543210\n'
        'jordan.hale@example.com\n'
        'Summary\nEngineer with platform experience.\n'
        'Experience\n'
        'Client : Example Technologies  (Currently Working)\n'
    )
    extra = (
        "Organization's Name | Designation | From | To\n"
        'Example Technologies | Middleware Administrator | 20-JAN-2021 | Till Date\n'
        'Degree | University/Board | Year of Pass out | Percentage\n'
        'B.E. in Computer Engineering | Example University | 2020 | 57.54\n'
        'Name: : | Mr. Jordan Hale\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text + extra)
    assert form.fullName
    assert form.experiences
    assert form.education
    assert 'example technologies' in (form.experiences[0].company or '').lower()


def test_layout_sparse_docx_table_structure():
    from app.ai.parser.text_extraction import _serialize_table_row

    header = _serialize_table_row(
        ["Organization's Name", 'Designation', 'From', 'To'],
        force_pipes=True,
    )
    row = _serialize_table_row(
        ['Example Technologies', 'Middleware Administrator', '20-JAN-2021', 'Till Date'],
        force_pipes=True,
    )
    assert '|' in header and '|' in row
    assert not row.lower().startswith('example technologies:')
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        f'{header}\n{row}\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert form.experiences
    assert 'middleware' in (form.experiences[0].role or '').lower()


def test_layout_education_must_not_consume_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.E. in Computer Engineering\nExample University\n2018\n'
        'Technical Experience\nExample Technologies\nEngineer\n2020 - Present\n'
        'Skills\nPython\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    edu_blob = ' '.join(f'{e.degree} {e.institution}' for e in profile.education).lower()
    assert 'example technologies' not in edu_blob
    assert form.experiences


def test_layout_experience_must_not_consume_skills():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\nNorthwind Ltd | Engineer | Jan 2022 - Present\n'
        'Skills\nPython, SQL, Linux\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills
    assert not any('northwind' in s for s in skills)


def test_layout_project_must_not_become_experience():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Projects\nInventory Portal\nBuilt a dashboard for stock alerts.\n'
        'Skills\nPython\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    assert not form.experiences


def test_layout_skills_reject_label_crumbs():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills:\n'
        ':\n'
        '•\n'
        'Skill:\n'
        'Technical Skills:\n'
        'Python, SQL, Linux\n'
    )
    _profile, form, _c, _llm, _w = _apply_parse(text)
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills and 'sql' in skills
    assert not any(s in {':', '-', 'skills', 'skill', 'technical skills'} for s in skills)


def test_layout_header_name_not_company_or_skill():
    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\nPhone: +919876543210\n'
        'Place: Harbor City\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Skills\nPython\n'
    )
    profile, form, _c, _llm, _w = _apply_parse(text)
    assert not any('jordan hale' in (e.company or '').lower() for e in profile.experience)
    assert 'jordan hale' not in (form.skills or '').lower()
    assert '@' not in (form.experiences[0].role or '')
    assert 'harbor city' not in (form.skills or '').lower()


def test_education_year_phrase_in_the_year():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nExample University in the year 2018\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert (edu.institution or '').strip() == 'Example University'
    assert 'year' not in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2018')


def test_education_year_of_passing_phrase():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nState Institute year of passing 2016\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert 'state institute' in (edu.institution or '').lower()
    assert 'passing' not in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2016')


def test_education_trailing_year_and_of_preserved():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.Sc.\nUniversity of Example\n2016\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert (edu.institution or '').strip() == 'University of Example'
    assert (edu.endMonth or '').startswith('2016')


def test_education_degree_only_survives():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.COM\n2018\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert 'b.com' in (edu.degree or '').lower().replace(' ', '')
    assert (edu.endMonth or '').startswith('2018')


def test_education_institution_only_survives():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nExample University\n2018\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert 'example university' in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2018')


def test_education_glued_from_keeps_source_institution():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nS.S.C.FROM IDEAL HIGH SCHOOL IN MARCH 2010.\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    deg = ''.join(ch for ch in (edu.degree or '').lower() if ch.isalpha())
    assert deg.startswith('ssc')
    assert 'ideal high school' in (edu.institution or '').lower()
    assert (edu.endMonth or '').startswith('2010')


def test_education_partial_from_not_invented():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.COM FROM YASHWANRAO\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    assert 'b.com' in (edu.degree or '').lower().replace(' ', '')
    inst = (edu.institution or '').strip()
    assert inst == '' or inst.upper() == 'YASHWANRAO'
    assert 'chavan' not in inst.lower()
    assert 'open university' not in inst.lower()


def test_education_wrapped_institution():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.E.\nVisvesvaraya Technological\nUniversity Belagavi in the year 2018.\n'
        'Skills\nPython\n'
    )
    assert form.education
    edu = form.education[0]
    inst = (edu.institution or '').lower()
    assert 'university' in inst
    assert 'year' not in inst
    assert (edu.endMonth or '').startswith('2018')


def test_skills_comma_pipe_multiline_and_labels():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Languages: Python, Java\n'
        'Databases: Oracle, MySQL\n'
        'Linux | AIX | Windows\n'
        'Docker\n'
        'Jenkins\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    for token in ('python', 'java', 'oracle', 'mysql', 'linux', 'aix', 'windows', 'docker', 'jenkins'):
        assert token in skills
    assert 'languages' not in skills
    assert 'databases' not in skills


def test_skills_prose_after_token_list_is_rejected():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Python, SQL, Linux, Oracle\n'
        'Project Description: Developed and implemented a payment system for retail clients.\n'
        'Responsible for managing production databases and reporting to stakeholders.\n'
        'Successfully completed the client migration with zero downtime.\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills and 'sql' in skills and 'linux' in skills
    blob = ' '.join(skills)
    assert 'developed' not in blob
    assert 'responsible' not in blob
    assert 'successfully' not in blob
    assert 'payment system' not in blob


def test_skills_mixed_line_splits_then_rejects_prose():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Python, SQL, Developed enterprise payment platform for retail clients in 2022\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills and 'sql' in skills
    assert not any('developed' in s or 'payment' in s for s in skills)


def test_skills_stop_at_project_and_achievement_headings():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\nPython\nSQL\nLinux\n'
        'Project Experience\nInventory Portal\nBuilt a dashboard for stock alerts.\n'
        'Achievements\nReduced batch runtime by 40 percent.\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills
    assert not any('dashboard' in s or 'batch' in s or 'inventory' in s for s in skills)
    assert not form.experiences


def test_skills_two_column_does_not_eat_experience():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\nPython\nSQL\nLinux\nOracle\nJava\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Developed and implemented a payment system for retail clients.\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'python' in skills and 'java' in skills
    assert not any('developed' in s or 'payment' in s for s in skills)
    assert form.experiences
    assert 'northwind' in (form.experiences[0].company or '').lower()


def test_property_education_date_not_left_in_institution():
    from app.ai.document_intelligence.deterministic import peel_education_date_phrase

    cases = (
        ('Example University in the year 2018', 'Example University', '2018'),
        ('State Institute year of passing 2016', 'State Institute', '2016'),
        ('SWAMI VIVEKANAND & JR. COLLEGE IN MARCH 2012.', 'SWAMI VIVEKANAND & JR. COLLEGE', '2012'),
        ('University Belagavi in the year 2018.', 'University Belagavi', '2018'),
    )
    for source, expected_core, expected_year in cases:
        core, year = peel_education_date_phrase(source)
        assert core == expected_core, source
        assert year.startswith(expected_year), source
        assert 'year' not in core.lower()
        assert 'passing' not in core.lower()
        assert 'march' not in core.lower()
    of_core, of_year = peel_education_date_phrase('University of Example')
    assert of_core == 'University of Example'
    assert of_year == ''


def test_property_skills_reject_prose_and_category_labels():
    from app.ai.document_intelligence.validation.engine import validate_skill_item
    from app.ai.parser.enrichment.resume_text_inference import (
        clip_skills_section_at_prose,
        filter_skill_items,
        skill_item_looks_like_prose,
    )

    assert skill_item_looks_like_prose(
        'Developed and implemented a payment system for retail clients.'
    )
    assert skill_item_looks_like_prose(
        'Responsible for managing production databases and reporting.'
    )
    assert not skill_item_looks_like_prose('Python')
    assert validate_skill_item('Languages')[0] is False
    assert validate_skill_item('Databases')[0] is False
    kept = filter_skill_items(['Languages: Python, Java', 'Databases:'])
    assert 'python' in [k.lower() for k in kept]
    assert not any(k.lower() in {'languages', 'databases'} for k in kept)
    skills_body, prose = clip_skills_section_at_prose(
        'Skills\nPython\nSQL\nLinux\n'
        'Project Description: Developed a payment system for clients.\n'
        'Responsible for managing production databases.\n'
    )
    assert 'Python' in skills_body and 'SQL' in skills_body
    assert 'Project Description' in prose
    assert 'Developed' in prose


def test_property_final_sanitize_is_last_writer():
    profile, _form, _c, _llm, working = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\nEngineer\nJan 2022 - Present\n'
        'Skills\nPython, Developed and implemented a payment system for clients.\n'
        'Education\nExample University in the year 2018\n'
    )
    again = sanitize_candidate_profile(profile, source_text=working)
    assert [(e.degree, e.institution, e.end) for e in again.education] == [
        (e.degree, e.institution, e.end) for e in profile.education
    ]
    assert [s.name for s in again.skills] == [s.name for s in profile.skills]
    assert not any('developed' in (s.name or '').lower() for s in again.skills)


def test_glued_skill_tokens_split_only_with_morphology_evidence():
    from app.ai.parser.enrichment.resume_text_inference import (
        filter_skill_items,
        maybe_split_glued_skill_tokens,
    )

    assert maybe_split_glued_skill_tokens('TOAD Putty Winscp') == ['TOAD', 'Putty', 'Winscp']
    assert maybe_split_glued_skill_tokens('Putty winscp Kibana') == ['Putty', 'winscp', 'Kibana']
    assert maybe_split_glued_skill_tokens('Oracle SQL') == ['Oracle SQL']
    assert maybe_split_glued_skill_tokens('Golden Gate') == ['Golden Gate']
    assert maybe_split_glued_skill_tokens('PL/SQL') == ['PL/SQL']
    assert maybe_split_glued_skill_tokens('Oracle 19C/12c/11g') == ['Oracle 19C/12c/11g']
    assert maybe_split_glued_skill_tokens('Visual Studio Code') == ['Visual Studio Code']
    assert maybe_split_glued_skill_tokens('MS server studio') == ['MS server studio']
    assert maybe_split_glued_skill_tokens('TOAD Putty Winscp Skills') == ['TOAD', 'Putty', 'Winscp']
    kept = filter_skill_items(
        ['TOAD Putty Winscp', 'Oracle SQL', 'PL/SQL', 'Oracle 19C/12c/11g', 'Golden Gate']
    )
    low = [k.lower() for k in kept]
    assert 'toad' in low and 'putty' in low and 'winscp' in low
    assert 'oracle sql' in low
    assert 'pl/sql' in low
    assert 'oracle 19c/12c/11g' in low
    assert 'golden gate' in low
    mixed = [k.lower() for k in filter_skill_items(['Python, SQL | Linux\nDocker, Kubernetes'])]
    for token in ('python', 'sql', 'linux', 'docker', 'kubernetes'):
        assert token in mixed


def test_glued_and_separated_skills_in_apply_form():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'TOAD Putty Winscp\n'
        'Oracle SQL\n'
        'PL/SQL\n'
        'Oracle 19C/12c/11g\n'
        'Golden Gate\n'
        'Python, SQL | Linux\n'
        'Docker\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    for token in ('toad', 'putty', 'winscp', 'oracle sql', 'pl/sql', 'oracle 19c/12c/11g',
                  'golden gate', 'python', 'sql', 'linux', 'docker'):
        assert token in skills


def test_skills_prose_cannot_reenter_after_peel_or_sanitize():
    from app.ai.document_intelligence.models.candidate import SkillEntry
    from app.ai.document_intelligence.coverage.resume_coverage import recover_resume_profile_gaps

    text = (
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Linux, Oracle SQL, PL/SQL\n'
        'Project Description: I am responsible for maintaining database performance.\n'
        'Achievement: Secured a training on Oracle Database Architecture.\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    profile, form, _c, _llm, working = _apply_parse(text)
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    assert 'linux' in skills and 'oracle sql' in skills and 'pl/sql' in skills
    blob = ' '.join(skills)
    assert 'responsible' not in blob
    assert 'secured' not in blob
    assert 'project description' not in blob
    polluted = profile.model_copy(
        update={
            'skills': list(profile.skills) + [
                SkillEntry(
                    name='Project Description: I am responsible for maintaining database performance.',
                    canonical='Project Description: I am responsible for maintaining database performance.',
                ),
                SkillEntry(
                    name='Secured a training on Oracle Database Architecture.',
                    canonical='Secured a training on Oracle Database Architecture.',
                ),
            ]
        }
    )
    recovered, _cov = recover_resume_profile_gaps(polluted, working)
    cleaned = sanitize_candidate_profile(recovered, source_text=working)
    names = [s.name.lower() for s in cleaned.skills]
    assert not any('responsible' in n or 'secured' in n or 'project description' in n for n in names)
    form2 = map_candidate_to_form(cleaned)
    form_blob = (form2.skills or '').lower()
    assert 'linux' in form_blob
    assert 'responsible' not in form_blob
    assert 'secured a training' not in form_blob


def test_assess_does_not_mutate_canonical():
    from app.ai.document_intelligence.coverage.resume_coverage import assess_resume_coverage

    profile, _form, _c, _llm, working = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Skills\nPython, SQL\n'
        'Education\nB.E.\nExample University\n2018\n'
    )
    before = profile.model_dump()
    assess_resume_coverage(profile, working)
    assert profile.model_dump() == before


def test_education_does_not_invent_partial_from():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Education\nB.COM FROM YASHWANRAO\n'
        'Skills\nPython\n'
    )
    edu = form.education[0]
    inst = (edu.institution or '').lower()
    assert 'chavan' not in inst
    assert 'open university' not in inst
    assert 'year' not in (edu.institution or '').lower()


def test_company_city_role_and_bullet_dates():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Northwind Services, Pune\n'
        'IT Analyst\n'
        '• 2022 - Present\n'
        'Coordinated recovery drills.\n'
        'Contoso Labs, Pune\n'
        'Software Engineer\n'
        '• 2016 - 2022\n'
        'Built services.\n'
        'Education\nB.E.\nExample University\n2018\n'
    )
    assert len(form.experiences) >= 2
    companies = [(e.company or '').lower() for e in form.experiences]
    roles = [(e.role or '').lower() for e in form.experiences]
    assert any('northwind' in c for c in companies)
    assert any('contoso' in c for c in companies)
    assert any('analyst' in r for r in roles)
    assert any('engineer' in r for r in roles)
    assert any((e.startMonth or '').startswith('2022') for e in form.experiences)

    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Organisation : Northwind Ltd\n'
        'Designation : Platform Engineer\n'
        'Duration : Jan 2021 to Present\n'
        'Built services.\n'
    )
    assert form.experiences
    job = form.experiences[0]
    assert 'northwind' in (job.company or '').lower()
    assert 'platform engineer' in (job.role or '').lower()
    assert (job.startMonth or '').startswith('2021-01')
    assert job.isCurrent or (job.endMonth or '').lower() in ('', 'present')


def test_education_row_cannot_become_experience():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Northwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Education\n'
        'Bachelor of Computer Applications (BCA)\n'
        'Example State College\n'
        '2010–2013\n'
        'Skills\nPython\n'
    )
    companies = [(e.company or '').lower() for e in form.experiences]
    roles = [(e.role or '').lower() for e in form.experiences]
    blob = ' '.join(companies + roles)
    assert 'bachelor' not in blob
    assert 'bca' not in blob
    assert any('northwind' in c for c in companies)
    assert form.education
    assert 'bachelor' in (form.education[0].degree or '').lower() or 'bca' in (
        form.education[0].degree or ''
    ).lower()


def test_job_title_and_dates_produce_experience():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Summary\nA short professional overview.\n'
        'Company name : Contoso Services LLP\n'
        'Database Administrator in Harbor City since 2022, supporting production clusters.\n'
        'Education\nB.E.\nExample University\n2018\n'
    )
    assert form.experiences
    job = form.experiences[0]
    assert 'contoso' in (job.company or '').lower()
    assert 'administrator' in (job.role or '').lower() or (job.startMonth or '').startswith('2022')


def test_section_heading_cannot_become_company():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Organisation : Northwind Ltd\n'
        'Designation : System Administrator\n'
        'Duration : Nov 2019 to till date\n'
        'AWARDS AND ACHIEVEMENTS\n'
        'Named employee of the month.\n'
        'PROFILE INFO\n'
        'Place: Harbor City\n'
    )
    companies = [(e.company or '').lower() for e in form.experiences]
    assert companies
    assert not any('award' in c or 'achievement' in c for c in companies)
    assert not any('profile' in c and 'info' in c for c in companies)
    assert any('northwind' in c for c in companies)


def test_project_heading_cannot_become_name():
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_name_from_text,
        join_spaced_letter_name,
    )

    assert join_spaced_letter_name('P R O J E C T S') == ''
    text = (
        'A L E X A N D E R\n'
        'H A L E\n'
        'D I S A S T E R R E C O V E R Y E N G I N E E R\n'
        'E X P E R I E N C E ( 5 + Y E A R S )\n'
        'Platform Engineer | Northwind Ltd |\n'
        'Email: alexander.hale@example.com\n'
        'P R O J E C T S\n'
        'Resiliency tooling\n'
    )
    working = prepare_resume_working_text(text)
    profile, form, _c, _llm, _w = _apply_parse(text)
    name = (form.fullName or profile.personal.full_name or extract_name_from_text(working) or '')
    assert 'project' not in name.lower()
    assert 'hale' in name.lower()


def test_explicit_skills_section_without_valid_items_may_be_empty():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Skills\n'
        'Database:\n'
        'Programming Languages:\n'
        'Operating System:\n'
        'Education\nB.E.\nExample University\n2018\n'
    )
    skills = [s.strip() for s in (form.skills or '').split(',') if s.strip()]
    assert skills == []


def test_skills_cannot_contain_employment_dates():
    from app.ai.document_intelligence.validation.engine import validate_skill_item

    ok, reason = validate_skill_item("(Nov '23 - Present)")
    assert ok is False
    assert 'date' in reason
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Python, SQL\n'
        "(Nov '23 - Present)\n"
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    blob = (form.skills or '').lower()
    assert 'python' in blob
    assert 'nov' not in blob
    assert 'present' not in blob


def test_skills_cannot_contain_employer_names_without_skill_evidence():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Experience\n'
        'Northwind Ltd\nEngineer\nJan 2022 - Present\n'
        'Skills\n'
        'Python, SQL\n'
        'Northwind Ltd\n'
        'Contoso Services Pvt Ltd\n'
    )
    blob = (form.skills or '').lower()
    assert 'python' in blob
    assert 'northwind' not in blob
    assert 'contoso' not in blob
    assert 'pvt' not in blob


def test_skills_cannot_contain_duty_prose():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Python, SQL\n'
        'Responsible for maintaining database performance during failovers.\n'
        'Working on automation tooling for recovery drills.\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    blob = (form.skills or '').lower()
    assert 'python' in blob
    assert 'responsible' not in blob
    assert 'working on' not in blob
    assert 'failovers' not in blob


def test_valid_multiword_skills_remain_valid():
    _profile, form, _c, _llm, _w = _apply_parse(
        'Jordan Hale\nEmail: jordan.hale@example.com\n'
        'Skills\n'
        'Oracle SQL, PL/SQL, Visual Studio Code, Golden Gate, MS server studio\n'
        'Experience\nNorthwind Ltd\nEngineer\nJan 2022 - Present\n'
    )
    skills = [s.strip().lower() for s in (form.skills or '').split(',') if s.strip()]
    for token in ('oracle sql', 'pl/sql', 'visual studio code', 'golden gate', 'ms server studio'):
        assert token in skills


def test_deterministic_role_not_overwritten_by_semantic_enrichment():
    from app.ai.document_intelligence.experience_quality import merge_experience_rows
    from app.ai.document_intelligence.models.candidate import ExperienceEntry

    det = [
        ExperienceEntry(
            company='Northwind Ltd',
            role='Platform Engineer',
            start='2022-01',
            end='',
            is_current=True,
        )
    ]
    ai = [
        ExperienceEntry(
            company='Northwind Ltd',
            role='Consultant',
            start='2022-01',
            end='',
            is_current=True,
        )
    ]
    merged = merge_experience_rows(det, ai)
    assert merged
    assert merged[0].role == 'Platform Engineer'
    assert 'northwind' in (merged[0].company or '').lower()

