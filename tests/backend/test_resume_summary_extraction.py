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
    assert details['reason'] in {'contains_phone_number', 'contact_information'}
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
