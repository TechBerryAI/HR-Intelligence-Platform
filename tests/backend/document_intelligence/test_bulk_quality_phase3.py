"""Phase 3 bulk quality fine-tune — fixtures from 52-resume audit failures."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

from app.ai.document_intelligence.coverage.resume_coverage import (
    has_experience_section_evidence,
    recover_resume_profile_gaps,
)
from app.ai.document_intelligence.deterministic import extract_phone, extract_simple_location
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
from app.ai.document_intelligence.validation import validate_location, validate_phone
from app.ai.parser.deterministic_resume import score_resume_toon
from app.ai.parser.enrichment.resume_text_inference import is_plausible_location_value
from app.ai.parser.layout.heuristic import normalize_section_header


@pytest.fixture(autouse=True)
def _force_skip_llm(monkeypatch):
    """Keep unit tests offline — exercise deterministic + coverage path."""
    monkeypatch.setenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
    monkeypatch.setenv('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')
    # Module caches enable flag at import — force off for this process
    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic.semantic_ai_enabled',
        lambda: False,
    )


def test_internship_training_program_header_maps_to_experience():
    assert normalize_section_header('Internship / Training Programm') == 'Experience'
    assert normalize_section_header('Internship Experience') == 'Experience'
    assert normalize_section_header('Trainings') == 'Experience'


def test_shravya_style_company_city_then_role():
    text = """
SHRAVYA SURESH PATKARE
Email Id: shravyapatkare22@gmail.com
Mob: 8108332848
Thane

SKILLS
HTML, CSS, JS, AWS

Experience
Magic Bus | Thane
AWS Cloud Intern
- Gained hands-on experience with AWS services such as EC2, S3, RDS, and VPC.

EDUCATION
BCA - College of Technology SNDT University 2024
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert len(profile.experience) >= 1
    blob = ' '.join(f'{e.role} {e.company}' for e in profile.experience).lower()
    assert 'intern' in blob or 'magic' in blob
    loc = (form.currentLocation or '').lower()
    assert 'thane' in loc or 'mumbai' in loc
    assert 'html' not in loc
    assert validate_location(form.currentLocation)[0]


def test_sahil_internship_training_section():
    text = """
Sahil Dwarkanath Patangrao
patangraosahil@gmail.com | 9834056263
Mumbai

SKILLS
AWS, Linux, EC2

Internship / Training Programm
AWS Cloud Practitioner Program | AWS re/Start
Dec 2025 – April 2026
• Managed EC2, S3, Auto Scaling Groups, and Load Balancers

EDUCATION
Bachelors of Engineering - Mumbai University [2023]
"""
    assert has_experience_section_evidence(text)
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert len(form.experiences) >= 1 or len(profile.experience) >= 1


def test_dhaval_phone_not_year_soup():
    text = """
31/01/2026 - 30/06/2026
2018
2020
2025
DHAVAL RANE
Mumbai
+91 7304189562 | ranedhaval05@gmail.com

SKILLS
Python, Networking

Experience
ELV Link Technologies Private Limited
Graduate Engineer Trainee
Worked on projects at RailTel Corporation Limited

EDUCATION
B.E. Electronics - Kc College of Engineering
"""
    phone = extract_phone(text)
    assert validate_phone(phone)[0]
    assert '2026' not in phone.replace(' ', '')
    digits = ''.join(c for c in phone if c.isdigit())
    assert '7304189562' in digits
    assert not validate_phone('202620182020202')[0]


def test_om_location_not_summary_fragment():
    text = """
OM GHARTE
+91 93567 91511 | omgharte.official@gmail.com
Pune

Summary
Computer Science Engineering graduate with hands-on experience in RPA-based business process automation.

SKILLS
SQL, RPA, AutomationEdge

Experience
RPA Intern | ValueDX
Jun 2026 – Present
Pune, India
• Automated repetitive business processes using AutomationEdge RPA workflows

EDUCATION
Bachelor of Technology in Computer Science - Parul University
"""
    loc = extract_simple_location(text)
    assert is_plausible_location_value(loc)
    assert 'automation' not in loc.lower()
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert len(profile.experience) >= 1
    assert 'intern' in (profile.experience[0].role or '').lower() or 'valuedx' in (
        profile.experience[0].company or ''
    ).lower()


def test_jorka_date_first_experience_block():
    text = """
Jorka Sandeep Kumar
jorkasandeep4117@gmail.com
+91 9392883968
Hyderabad, India

Summary
Results-driven Computer Science graduate with hands-on experience in Cloud DevOps, CI/CD.

SKILLS
Docker, Kubernetes, Jenkins, GitHub Actions

Experience
07/2025 – 10/2025 | Remote
• Designed and managed CI/CD pipelines with GitHub Actions for multiple services.
• Implemented monitoring dashboards and Slack alerts.

EDUCATION
B.Tech CSE - Hyderabad [2025]
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    loc = (form.currentLocation or '').lower()
    assert 'hyderabad' in loc
    assert 'devops' not in loc
    assert 'ci' not in loc.split()
    # Dated block should yield at least a stub or recovered row
    assert len(profile.experience) >= 1 or has_experience_section_evidence(text)


def test_location_rejects_skill_pairs():
    assert not is_plausible_location_value('HTML, JS')
    assert not is_plausible_location_value('Cloud DevOps, CI')
    assert not is_plausible_location_value('based business process automation')
    assert not is_plausible_location_value('TypeScript, Node.js')
    assert is_plausible_location_value('Mumbai')
    assert is_plausible_location_value('Thane, Mumbai')
    assert is_plausible_location_value('Remote')
    assert validate_location('HTML, JS')[0] is False
    assert validate_location('Pune')[0] is True


def test_score_fails_when_experience_section_empty():
    toon = {
        'type': 'resume',
        'person': {
            'name': 'Test User',
            'email': 't@example.com',
            'phone': '9876543210',
        },
        'skills': ['Python', 'SQL'],
        'education': [{'degree': 'B.Tech', 'institution': 'Test University'}],
        'experience': [],
        'summary': 'Fresher looking for roles',
    }
    text = """
Test User
t@example.com | 9876543210 | Pune
SKILLS
Python, SQL
EXPERIENCE
Software Intern - Acme - (Jun 2023 - Aug 2023)
EDUCATION
B.Tech - Test University
"""
    conf, missing, passes = score_resume_toon(toon, source_text=text)
    assert 'experience.section_gap' in missing or 'experience' in missing
    assert passes is False

    fresher = """
Test User
t@example.com | 9876543210 | Pune
SKILLS
Python, SQL
EDUCATION
B.Tech - Test University
"""
    conf2, missing2, passes2 = score_resume_toon(toon, source_text=fresher)
    assert 'experience.section_gap' not in missing2
    assert passes2 is True


def test_experience_rejects_edu_table_and_duty_bleed():
    from app.ai.document_intelligence.models.candidate import ExperienceEntry
    from app.ai.document_intelligence.validation.engine import sanitize_experience_row
    from app.ai.document_intelligence.parsers.resume import (
        _is_bullet_or_duty_line,
        parse_experience,
    )
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_job_title

    junk = sanitize_experience_row(
        ExperienceEntry(role='Degree/Certificate: School/College', company='Board/University')
    )
    assert not junk.role and not junk.company
    duty = sanitize_experience_row(
        ExperienceEntry(
            role='Identifying sales trends, customer purchasing patterns',
            company='and inventory movement insights.',
        )
    )
    assert not duty.role
    em = sanitize_experience_row(ExperienceEntry(role='SDE Intern — Edviron', company=''))
    assert 'intern' in em.role.lower()
    assert 'edviron' in em.company.lower()

    # Phase 6: Saloni-style noun-led KPI fragment must never become a title
    saloni = 'Trends, and Revenue KPIs, enabling data driven business decision-making'
    assert not is_plausible_job_title(saloni)
    assert _is_bullet_or_duty_line(saloni)
    saloni_san = sanitize_experience_row(
        ExperienceEntry(role=saloni, company='Codenera')
    )
    assert not (saloni_san.role or '').strip() or 'intern' in (saloni_san.role or '').lower()
    # Company | City stub + next duty line must not promote KPI fragment to role
    from app.ai.document_intelligence.models.candidate import ExperienceEntry as EE  # noqa: F401
    text = (
        "Experience\n"
        "Codenera | Pune\n"
        "Trends, and Revenue KPIs, enabling data\n"
        "Data Analyst Intern\n"
        "Jan 2024 - Present\n"
    )
    # Prefer that no experience role equals the KPI fragment
    entries = parse_experience(text)
    roles = [(e.role or '').strip() for e in entries]
    assert all('Trends' not in r and 'KPI' not in r for r in roles)

def test_location_rejects_pipe_phone_and_section_headers():
    assert not is_plausible_location_value('Magic Bus | Thane')
    assert not is_plausible_location_value('+91 9967705134 ⋄Mumbai')
    assert not is_plausible_location_value('Education')
    assert is_plausible_location_value('Thane')
    assert is_plausible_location_value('Mumbai')


def test_location_peel_edu_job_and_institute():
    """Phase 6: Nasik/edu, Bhubaneswar/job, VIT→Vellore."""
    from app.ai.document_intelligence.coverage.resume_coverage import (
        recover_resume_profile_gaps,
    )
    from app.ai.document_intelligence.models.candidate import (
        CandidateProfile,
        ContactInfo,
        EducationEntry,
        ExperienceEntry,
        PersonalInfo,
        SkillEntry,
    )
    from app.ai.parser.enrichment.resume_text_inference import (
        canonicalize_location_city,
        peel_location_from_structured,
    )

    assert canonicalize_location_city('Nasik') == 'Nashik'
    assert peel_location_from_structured(
        education=[{'institution': 'Savitribai Phule University, Nasik, India'}],
    ) == 'Nashik'
    assert peel_location_from_structured(
        experience=[{'role': 'DBA', 'company': 'LTI', 'location': 'Bhubaneswar'}],
    ) == 'Bhubaneswar'
    assert peel_location_from_structured(
        raw_text='ADAWET RATH\nVellore Institute of Technology\n+91990\n',
    ) == 'Vellore'

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Saloni Khivansara'),
        contact=ContactInfo(email='s@example.com', phone='8080234411', location=''),
        skills=[SkillEntry(canonical='Python')],
        education=[
            EducationEntry(
                degree='BE',
                institution='Savitribai Phule University Nasik, India',
            )
        ],
    )
    text = (
        'Saloni Khivansara\n+91-8080234411\nEducation\n'
        'Savitribai Phule University\nNasik, India\n'
    )
    cleaned, _cov = recover_resume_profile_gaps(profile, text)
    assert cleaned.contact.location == 'Nashik'


def test_sanitize_profile_heals_pipe_location_and_years():
    from app.ai.document_intelligence.models.candidate import (
        CandidateProfile,
        ContactInfo,
        ExperienceEntry,
        PersonalInfo,
        SkillEntry,
    )
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile
    from app.workers.bulk_parser import _flatten_toon

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Om Gharte'),
        contact=ContactInfo(
            email='o@example.com',
            phone='9356791511',
            location='Magic Bus | Thane',
        ),
        skills=[SkillEntry(canonical='RPA')],
        experience=[
            ExperienceEntry(role='RPA Intern', company='ValueDX', start='2026-06', is_current=True),
            ExperienceEntry(role='Pune', company='India', start='2026-06'),
        ],
    )
    cleaned = sanitize_candidate_profile(profile)
    assert cleaned.contact.location == 'Thane'
    assert all(e.role != 'Pune' for e in cleaned.experience)
    assert cleaned.total_experience_years is not None
    assert cleaned.total_experience_years > 0

    # Phase 6: years from description date range when structured from/to empty
    toon = {
        'person': {'name': 'Shravya', 'email': 's@x.com', 'phone': '8108332848'},
        'skills': ['AWS'],
        'experience': [
            {
                'title': 'AWS Cloud Intern',
                'company': 'Magic Bus',
                'description': 'Worked Jan 2024 - Jun 2024 on EC2 and S3.',
            }
        ],
        'total_experience_years': None,
    }
    row = _flatten_toon(toon, 'shravya.pdf')
    assert row['Total Experience Years'] not in ('', None)
    assert float(row['Total Experience Years']) > 0


def test_coverage_clears_polluted_location():
    from app.ai.document_intelligence.models.candidate import (
        CandidateProfile,
        ContactInfo,
        PersonalInfo,
        SkillEntry,
    )

    profile = CandidateProfile(
        personal=PersonalInfo(full_name='Shravya Patkare'),
        contact=ContactInfo(
            email='s@example.com',
            phone='8108332848',
            location='HTML, JS',
            preferred_location='HTML, JS',
        ),
        skills=[SkillEntry(canonical='AWS')],
    )
    text = """
Shravya Patkare
s@example.com | 8108332848
Thane

SKILLS
AWS, HTML, JS

Experience
Magic Bus | Thane
AWS Cloud Intern
• Built cloud projects

EDUCATION
BCA - SNDT University
"""
    updated, report = recover_resume_profile_gaps(profile, text)
    assert is_plausible_location_value(updated.contact.location)
    assert 'html' not in updated.contact.location.lower()
    assert len(updated.experience) >= 1 or any(
        f.key == 'experience' and f.status == 'recovered' for f in report.fields
    )


# --- Phase 4: layout fixtures + years / formats ---


def test_p4_company_city_sets_location_field():
    from app.ai.document_intelligence.parsers.resume import parse_experience

    rows = parse_experience(
        """
Magic Bus | Thane
AWS Cloud Intern
• Built cloud projects
"""
    )
    assert rows
    assert any('magic' in (e.company or '').lower() for e in rows)
    assert any('thane' in (e.location or '').lower() for e in rows)
    assert any('intern' in (e.role or '').lower() for e in rows)


def test_p4_zuhair_em_dash_and_hyphen_intern():
    text = """
ZUHAIR KHAN
zuhair@example.com | 9876543210 | Mumbai

SKILLS
Python

EXPERIENCE
SDE Intern — Edviron
Jun 2024 - Aug 2024
• Wrote APIs

Data Analyst - Acme Labs
Jan 2023 - May 2023

EDUCATION
B.Tech - Mumbai University
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    roles = ' '.join(e.role for e in form.experiences).lower()
    companies = ' '.join(e.company for e in form.experiences).lower()
    assert 'intern' in roles or 'analyst' in roles
    assert 'edviron' in companies or 'acme' in companies
    assert not any(
        (e.role or '').lower().startswith('wrote') for e in form.experiences
    )


def test_p4_jorka_date_first_remote():
    text = """
JORKA SANDEEP
jorka@example.com | 9123456789

SKILLS
DevOps, AWS

EXPERIENCE
07/2025 – 10/2025 | Remote
DevOps Intern
• Engineered CI pipelines

EDUCATION
B.Tech - JNTU
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert len(form.experiences) >= 1
    joined = ' '.join(
        f'{e.role} {e.company}' for e in form.experiences
    ).lower()
    locs = ' '.join((e.location or '') for e in profile.experience).lower()
    assert 'devops' in joined or 'intern' in joined
    assert 'remote' in locs or 'devops' in joined


def test_p4_institution_as_job_rejected():
    from app.ai.document_intelligence.models.candidate import ExperienceEntry
    from app.ai.document_intelligence.validation.engine import sanitize_experience_row

    junk = sanitize_experience_row(
        ExperienceEntry(role='University of Mumbai', company='IIT Bombay')
    )
    assert not junk.role and not junk.company


def test_p4_geo_city_region_rejected_as_role():
    from app.ai.document_intelligence.models.candidate import ExperienceEntry
    from app.ai.document_intelligence.validation.engine import sanitize_experience_row

    geo = sanitize_experience_row(
        ExperienceEntry(role='Pune, Maharashtra', company='Navi Mumbai')
    )
    assert not geo.role
    assert not geo.company or geo.location


def test_p4_prose_years_and_date_years():
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_total_experience_years_from_text,
        merge_experience_years,
    )
    from app.ai.document_intelligence.models.candidate import (
        CandidateProfile,
        ContactInfo,
        ExperienceEntry,
        PersonalInfo,
        SkillEntry,
    )
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile

    assert extract_total_experience_years_from_text(
        'Total Experience: 3 years\nSkills\nPython'
    ) == 3.0
    assert extract_total_experience_years_from_text(
        '5+ years of experience in backend'
    ) == 5.0
    assert merge_experience_years(2.0, 3.0) == 3.0
    assert merge_experience_years(5.0, 1.0) == 5.0  # inconsistent → prefer dates

    text = """
NAME
Total Experience: 4 years
n@example.com | 9876543210 | Pune

SKILLS
Java

EXPERIENCE
Backend Engineer - Foo Corp
Jan 2022 - Dec 2023
• Built APIs

EDUCATION
B.Tech - Pune University
"""
    profile, form, _ = parse_resume_text_to_canonical(text)
    assert profile.total_experience_years is not None
    assert float(profile.total_experience_years) >= 1.5
    assert form.experienceLevel  # derived from years

    cleaned = sanitize_candidate_profile(
        CandidateProfile(
            personal=PersonalInfo(full_name='A'),
            contact=ContactInfo(email='a@a.com', phone='9876543210', location='Pune'),
            skills=[SkillEntry(canonical='Java')],
            experience=[
                ExperienceEntry(
                    role='Backend Engineer',
                    company='Foo Corp',
                    start='2022-01',
                    end='2023-12',
                )
            ],
            total_experience_years=None,
        ),
        source_text='Total Experience: 4 yrs\n',
    )
    assert cleaned.total_experience_years is not None
    assert cleaned.total_experience_years >= 1.5


def test_location_parse_contract_is_city_canonical():
    """E2E parse contract: plausible US city+state heals to the known city token."""
    from app.ai.parser.enrichment.resume_text_inference import heal_location_candidate

    assert heal_location_candidate('Austin, TX') == 'Austin'
    assert heal_location_candidate('San Francisco, CA') == 'San Francisco'
    assert heal_location_candidate('Seattle, WA') == 'Seattle'


def test_gold_generator_resume_location_is_city_canonical():
    """Generator writes city-only resume expected; source and JD keep city+state."""
    eval_dir = Path(__file__).resolve().parents[3] / 'ai' / 'eval'
    if str(eval_dir) not in sys.path:
        sys.path.insert(0, str(eval_dir))
    from generate_gold_lake import _jd_case, _resume_case

    expected = {
        5: ('Austin, TX', 'Austin'),
        6: ('San Francisco, CA', 'San Francisco'),
        7: ('Seattle, WA', 'Seattle'),
        15: ('Austin, TX', 'Austin'),
        16: ('San Francisco, CA', 'San Francisco'),
        17: ('Seattle, WA', 'Seattle'),
    }
    for i, (raw, canon) in expected.items():
        text, toon, form = _resume_case(i)
        assert raw in text
        assert form['currentLocation'] == canon
        assert toon['person']['location'] == canon

    text, toon, form = _jd_case(5)
    assert 'Austin, TX' in text
    assert form['location'] == 'Austin, TX'
    assert toon['location'] == 'Austin, TX'


def test_p4_location_heal_phone_bleed_and_ambernath():
    from app.ai.parser.enrichment.resume_text_inference import heal_location_candidate

    assert heal_location_candidate('Magic Bus | Thane') == 'Thane'
    assert 'mumbai' in heal_location_candidate('+91 9967705134 ⋄Mumbai').lower()
    loc = extract_simple_location(
        'RIYA\nLocation: Ambernath\nriya@example.com\n\nSKILLS\nHTML\n'
    )
    assert loc and 'ambernath' in loc.lower()
    assert not is_plausible_location_value('Skills')
    assert not is_plausible_location_value('Education')


def test_p4_bulk_allowed_ext_rejects_doc():
    from app.workers import bulk_parser as bp

    assert 'doc' not in bp.ALLOWED_EXT
    assert 'pdf' in bp.ALLOWED_EXT and 'docx' in bp.ALLOWED_EXT
    assert 'png' not in bp.ALLOWED_EXT
    assert 'jpg' not in bp.ALLOWED_EXT
    assert 'jpeg' not in bp.ALLOWED_EXT
    assert 'webp' in bp.ALLOWED_EXT and 'tiff' in bp.ALLOWED_EXT
    # Staging gate mirrors ALLOWED_EXT (legacy .doc and PNG/JPG never queued)
    assert all(
        ext in bp.ALLOWED_EXT
        for ext in ('pdf', 'docx', 'webp', 'tif', 'tiff')
    )


def test_p4_single_parse_rejects_png():
    from app.domains.recruitment.api.parsing import ALLOWED_EXTENSIONS, allowed_file

    assert 'png' not in ALLOWED_EXTENSIONS
    assert 'jpg' not in ALLOWED_EXTENSIONS
    assert 'jpeg' not in ALLOWED_EXTENSIONS
    assert not allowed_file('Janhavi_Rane_Digital_marketing_intern_resume.png')
    assert not allowed_file('resume.jpg')
    assert not allowed_file('resume.jpeg')
    assert allowed_file('resume.pdf')
    assert allowed_file('resume.docx')


def test_p6_bulk_gate_refuses_bad_titles_and_ocr_mush():
    from app.workers.bulk_parser import (
        _experience_titles_implausible,
        _ocr_experience_slice_mushy,
    )

    assert _experience_titles_implausible(
        {
            'experience': [
                {'title': 'Trends, and Revenue KPIs enabling data', 'company': 'X'},
            ]
        }
    )
    assert not _experience_titles_implausible(
        {'experience': [{'title': 'Data Analyst Intern', 'company': 'Codenera'}]}
    )
    mush = (
        "Experience\n"
        "ITLINUXBASEDCLOUDAPPLICATIONSJNTERNA GLOBALINFOCOMMNETWORKSLLP\n"
        "REGRESSIONTESTINGSMOKEAPPLICATIONSJNTERNAABCDEFGHIJKLMNOP\n"
        "MOREGLUEDTOKENSWITHOUTSPACESXXXXXXXXXXXXXXXXXXXX\n"
        "Education\n"
    )
    assert _ocr_experience_slice_mushy(mush)
    clean = (
        "Experience\n"
        "Data Analyst Intern at Codenera (2024-01-Present)\n"
        "Built dashboards and cleaned datasets for revenue KPIs.\n"
        "Education\n"
    )
    assert not _ocr_experience_slice_mushy(clean)

