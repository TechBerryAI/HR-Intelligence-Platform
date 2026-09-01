"""Summary/objective extraction: section-aware, contact-safe, PDF/DOCX consistent."""

from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')
os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')

from app.ai.document_intelligence.parsers.resume import parse_resume_from_sections
from app.ai.parser.engine.sections import detect_sections
from app.ai.parser.enrichment.resume_text_inference import (
    extract_phone_from_text,
    extract_summary_details,
    extract_summary_from_text,
    is_valid_summary,
    summary_rejection_reason,
)
from app.ai.parser.engine.text_pipeline import parse_resume_text_via_engine


OBJECTIVE_PROSE = (
    'Motivated IT professional seeking a Service Desk Engineer role to provide '
    'timely technical support and ensure smooth IT operations. Eager to apply '
    'strong troubleshooting skills and customer service experience to enhance '
    'user satisfaction and system reliability.'
)

PHONE = '9699028764'


def _parse_text(text: str):
    sections = detect_sections(text)
    return parse_resume_from_sections(sections, text)


def test_is_valid_summary_rejects_contact_phone_email():
    assert not is_valid_summary(f'Contact {PHONE}')
    assert not is_valid_summary(f'Phone: {PHONE}')
    assert not is_valid_summary('Email: example@gmail.com')
    assert not is_valid_summary('CONTACT')
    assert summary_rejection_reason(f'Contact {PHONE}') in {
        'contains_phone_number',
        'contact_information',
    }
    assert is_valid_summary(OBJECTIVE_PROSE)


def test_graduation_year_marks_are_not_phones():
    """Years + percentages / calendar dates must not trip phone rejection."""
    prose = (
        'Willing to work in a professional company which will provide me with an '
        'elegant platform to use my skills and progress in my career.'
    )
    assert is_valid_summary(prose)
    assert summary_rejection_reason(prose + ' 2019 60.81%') is None
    assert summary_rejection_reason(
        'Seeking assignments in DBA roles. Working from Dt- 15-04-2021 to till date.'
    ) is None
    assert not is_valid_summary(f'Seeking a role. Call {PHONE}')


def test_summary_scrubs_sidebar_contact_bleed():
    text = f"""Name

Summary
A motivated, proactive and keen individual, looking to gain practical and hands
on experience. Always ready to learn new technologies.
IT ENGINEER
Anuj Hegishte
A-103, New Swati CHS Ltd.
www.linkedin.com/in/anuj-hegishte
anuj@example.com

Experience
Middleware Admin
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert 'motivated, proactive' in details['value'].lower()
    assert '@' not in details['value']
    assert 'linkedin' not in details['value'].lower()


def test_empty_summary_heading_uses_intro_prose():
    text = """ANANT VIJAY SHARMA
Dynamic Technical Architect with a proven track record at Publicis Sapient,
specializing in Generative AI, Data and Cloud solutions. Expert in deploying
LLM-based systems and optimizing cloud architectures.
PROFESSIONAL

Summary

Certifications
AWS Certified
Experience
Architect at Sapient
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert 'Technical Architect' in details['value']
    assert 'Generative AI' in details['value']


def test_rejects_experience_crumb_and_skills_dump_as_summary():
    assert summary_rejection_reason('WORK EXPERIENCE:- 2.8 YEARS') in {
        'experience_header',
        'section_heading_only',
        'too_short',
    }
    assert summary_rejection_reason(
        'EXPERTISE Ticketing tools (ServiceNow, Jira), remote support '
        '(TeamViewer, AnyDesk), Basic networking (TCP/IP, DNS, VPN)'
    ) == 'skills_list'
    assert summary_rejection_reason(
        'EVENTSDONETILLNOW DAY EVENT COMPANY 1Day CorporateEvent HyattHotel'
    ) == 'non_summary_content'


def test_location_rejects_section_headers():
    from app.ai.parser.enrichment.resume_text_inference import (
        heal_location_candidate,
        is_plausible_location_value,
    )

    assert not is_plausible_location_value('Professional Profile')
    assert not is_plausible_location_value('Certificate')
    assert not is_plausible_location_value('Personal Profile')
    assert heal_location_candidate('Professional Profile') == ''
    assert heal_location_candidate('Certificate') == ''
    assert is_plausible_location_value('Pune')
    assert is_plausible_location_value('Mumbai')


def test_personal_profile_heading_extracts_summary():
    text = """ANUJ CHAFLE
Pune
PERSONAL PROFILE
To leverage my skills and experience as a DBA Administrator to contribute
effectively to a dynamic organization that values professionalism.

Experience
Database Administrator
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert 'leverage my skills' in details['value'].lower()


def test_objective_not_rejected_as_skills_list_with_tech_commas():
    prose = (
        'Proficient in designing, developing, and implementing web applications '
        'using .NET technologies (C#, ASP.NET, MVC). Successfully led and '
        'contributed to multiple full-cycle projects.'
    )
    assert is_valid_summary(prose)
    assert summary_rejection_reason(prose) is None


def test_operating_system_distros_does_not_pollute_summary():
    text = """Name
Summary
To obtain a position that will enable me to use my strong skills, educational
background, and ability to work well with people.

OPERATING SYSTEM DISTROS
Linux (CentOS 7), Windows

Skills
Linux
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert 'obtain a position' in details['value'].lower()
    assert 'centos' not in details['value'].lower()


def test_summary_bullet_list_keeps_software_capability_lines():
    """Naukri DBA resumes: Summary is bullets; 'database software' must not bleed-cut."""
    text = """KHALID ANSARI
ORACLE DBA

Experience
Working as an Oracle Database Administrator in (24x7) Production Environment.
Management, Administration, Backup, Performance of Oracle databases.

Summary
• Available to work in 24X7 capability.
• Installing and maintaining Oracle database software 11g, 12c and 19c
• Strong DBA skills and relevant working experience with Oracle Database 11g
• Standalone DB upgrade from 11g to 12c or 19c.

Education
B.Sc
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    value = details['value']
    assert '24X7' in value or 'Oracle Database Administrator' in value
    assert 'database software' in value or 'Production Environment' in value
    assert len(value) > 80


def test_experience_lead_prose_used_when_no_summary_heading():
    text = """Name

Experience
Working as an Oracle Database Administrator in (24x7) Production Environment.
Management, Administration, Backup and Recovery of Oracle databases.

Company: Acme Corp
March 2020 – Present
Position: Oracle DBA
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert 'Oracle Database Administrator' in details['value']
    assert details['source_section'] == 'EXPERIENCE_LEAD'


def test_experience_highlights_when_no_summary_or_lead_prose():
    text = """Personal info
Name : Ashwin R Gedekar
Mob: 7757807216

Education
B.E.

Experience
Company: Comtel infosystem pvt ltd
March 2023 – Present
Position: System-Administrator-Security-L2
Deploying Event log analyser as Central and managed server set-up on Ubuntu Linux
Performing server migration using rsync across datacenter hosts
Configuration of log forwarding from linux system and windows system to SIEM
Vulnerabilities patching of Centos-7, RHEL-7, Ubuntu 18 and 20
Installing Crowdstrike Agent on linux as well windows machine

Projects
Deployed VPC infra
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'passed'
    assert details['source_section'] == 'EXPERIENCE_HIGHLIGHTS'
    assert 'Event log analyser' in details['value'] or 'rsync' in details['value']


def test_career_objective_becomes_summary():
    text = f"""Candidate Name

CAREER OBJECTIVE
{OBJECTIVE_PROSE}

EXPERIENCE
IT Support
EDUCATION
B.Tech
SKILLS
Windows
"""
    details = extract_summary_details(text)
    assert details['source_section'] == 'CAREER OBJECTIVE'
    assert details['validation'] == 'passed'
    assert 'Motivated IT professional' in details['value']
    assert 'Eager to apply' in details['value']

    profile = _parse_text(text)
    assert 'Motivated IT professional' in profile.personal.summary
    assert PHONE not in profile.personal.summary


def test_contact_before_objective_does_not_pollute_summary():
    text = f"""Candidate Name
CONTACT
{PHONE}
candidate@gmail.com

CAREER OBJECTIVE
{OBJECTIVE_PROSE}

EXPERIENCE
Helpdesk
EDUCATION
BSc
SKILLS
ITIL
"""
    profile = _parse_text(text)
    assert profile.contact.phone.replace(' ', '').endswith(PHONE)
    assert 'Motivated IT professional' in profile.personal.summary
    assert PHONE not in profile.personal.summary
    assert 'Contact' not in profile.personal.summary
    assert '@' not in profile.personal.summary


def test_professional_summary_heading():
    prose = 'Experienced software engineer with 5 years of building scalable backend systems and APIs.'
    text = f"""Alex Engineer

PROFESSIONAL SUMMARY
{prose}

EXPERIENCE
Backend Engineer at Acme
"""
    details = extract_summary_details(text)
    assert details['source_section'] == 'PROFESSIONAL SUMMARY'
    assert prose in details['value']
    profile = _parse_text(text)
    assert prose in profile.personal.summary


def test_no_summary_section_returns_empty_not_contact():
    text = f"""Candidate Name
CONTACT
{PHONE}
a@b.com
EXPERIENCE
Developer at Co
EDUCATION
BTech CS
SKILLS
Python, SQL
"""
    profile = _parse_text(text)
    assert profile.contact.phone.replace(' ', '').endswith(PHONE)
    assert not (profile.personal.summary or '').strip()
    assert extract_summary_from_text(text) == ''


def test_phone_nearby_never_becomes_summary():
    text = f"""Name Here
LinkedIn Profile
Contact {PHONE}
email@example.com

CAREER OBJECTIVE
{OBJECTIVE_PROSE}

EXPERIENCE
Support Analyst
"""
    # Regression: bare "Profile" substring must not capture Contact+phone
    assert extract_summary_from_text(text) != f'Contact {PHONE}'
    profile = _parse_text(text)
    assert PHONE not in (profile.personal.summary or '')
    assert 'Motivated IT professional' in profile.personal.summary
    assert extract_phone_from_text(text).replace(' ', '').endswith(PHONE)


def test_summary_section_with_only_contact_rejected():
    text = f"""Name
Summary
Contact {PHONE}
EXPERIENCE
Dev
EDUCATION
BSc
"""
    details = extract_summary_details(text)
    assert details['validation'] == 'failed'
    assert details['reason'] in {
        'contains_phone_number',
        'contact_information',
        'section_heading_only',
        'empty',
        'too_short',
    }
    assert details['value'] == ''
    profile = _parse_text(text)
    assert not (profile.personal.summary or '').strip()
    assert profile.contact.phone.replace(' ', '').endswith(PHONE)


def test_heading_case_and_colon_variants():
    for heading in ('Career Objective', 'CAREER OBJECTIVE:', 'career objective'):
        text = f"""Name\n\n{heading}\n{OBJECTIVE_PROSE}\n\nSKILLS\nPython\n"""
        assert 'Motivated IT professional' in extract_summary_from_text(text)


def test_engine_path_preserves_phone_and_summary():
    text = f"""Anjali Bhore
Contact
{PHONE}
anjali@example.com

CAREER OBJECTIVE
{OBJECTIVE_PROSE}

EXPERIENCE
Service Desk
EDUCATION
B.Tech
SKILLS
Windows
"""
    toon, *_ = parse_resume_text_via_engine(text, allow_llm=False, source_filename='anjali.pdf')
    assert (toon.get('summary') or '').find('Motivated IT professional') >= 0
    phone = ((toon.get('person') or {}).get('phone') or '')
    assert PHONE in phone.replace(' ', '').replace('-', '')


def _make_docx_bytes(paragraphs: list[str]) -> bytes:
    from docx import Document

    doc = Document()
    for p in paragraphs:
        doc.add_paragraph(p)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def _make_pdf_bytes(lines: list[str]) -> bytes:
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    y = 72
    for line in lines:
        page.insert_text((72, y), line, fontsize=11)
        y += 16
        if y > 750:
            page = doc.new_page()
            y = 72
    data = doc.tobytes()
    doc.close()
    return data


def test_docx_roundtrip_summary_extraction():
    from app.ai.parser.text_extraction import extract_text_from_docx

    paragraphs = [
        'Anjali Bhore',
        'Contact',
        PHONE,
        'anjali@example.com',
        'CAREER OBJECTIVE',
        OBJECTIVE_PROSE,
        'EXPERIENCE',
        'Service Desk Engineer',
        'EDUCATION',
        'B.Tech Information Technology',
        'SKILLS',
        'Windows, Networking',
    ]
    raw = extract_text_from_docx(_make_docx_bytes(paragraphs))
    assert 'CAREER OBJECTIVE' in raw.upper() or 'Career Objective' in raw
    profile = _parse_text(raw)
    assert 'Motivated IT professional' in profile.personal.summary
    assert PHONE not in profile.personal.summary
    assert profile.contact.phone.replace(' ', '').endswith(PHONE)


def test_pdf_roundtrip_summary_extraction():
    from app.ai.parser.text_extraction import extract_text_from_pdf

    lines = [
        'Anjali Bhore',
        f'Contact {PHONE}',
        'anjali@example.com',
        'CAREER OBJECTIVE',
        'Motivated IT professional seeking a Service Desk Engineer role to provide',
        'timely technical support and ensure smooth IT operations.',
        'EXPERIENCE',
        'Service Desk',
        'EDUCATION',
        'B.Tech',
        'SKILLS',
        'Windows',
    ]
    raw = extract_text_from_pdf(_make_pdf_bytes(lines))
    assert raw.strip()
    profile = _parse_text(raw)
    assert 'Motivated IT professional' in profile.personal.summary
    assert PHONE not in profile.personal.summary
    assert extract_phone_from_text(raw).replace(' ', '').endswith(PHONE)
