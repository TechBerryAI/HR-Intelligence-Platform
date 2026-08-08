"""Phase 3 bulk quality fine-tune — fixtures from 52-resume audit failures."""
from __future__ import annotations

import os

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
    monkeypatch.setattr(
        'app.ai.document_intelligence.semantic._ENABLED',
        False,
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
