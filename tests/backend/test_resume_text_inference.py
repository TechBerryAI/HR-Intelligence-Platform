"""Unit tests for resume text inference helpers."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from resume_text_inference import (
    compute_total_experience_years,
    dedupe_skills,
    extract_certifications_from_text,
    extract_education_from_text,
    extract_experience_from_text,
    extract_name_from_text,
    extract_skills_from_text,
    infer_resume_fields_from_text,
    normalize_date_token,
    split_list_items,
)


def test_split_list_items_bullets():
    text = "- Python\n• Java\n1. Go"
    assert split_list_items(text) == ["Python", "Java", "Go"]


def test_split_list_items_pipe_and_comma():
    assert split_list_items("Python|Java|Go") == ["Python", "Java", "Go"]
    assert split_list_items("Python, Java, Go") == ["Python", "Java", "Go"]


def test_dedupe_skills_case_insensitive():
    assert dedupe_skills(["Python", "python", "SQL"]) == ["Python", "SQL"]


def test_extract_skills_from_markdown_section():
    text = """
**Technical Skills:**
- Python
- TensorFlow
- Docker

Experience
"""
    skills = extract_skills_from_text(text)
    assert "Python" in skills
    assert "TensorFlow" in skills
    assert "Docker" in skills


def test_extract_skills_from_inline_header():
    text = "Skills: Python, SQL, React"
    skills = extract_skills_from_text(text)
    assert "Python" in skills
    assert "SQL" in skills
    assert "React" in skills


def test_infer_resume_fields_from_text_partial():
    text = """
Jane Doe
Skills: Python, SQL
Professional Summary: Experienced engineer.
"""
    inferred = infer_resume_fields_from_text(text)
    assert "Python" in inferred["skills"]
    assert inferred["summary"]


def test_normalize_date_token_formats():
    assert normalize_date_token("Jan 2020") == "2020-01"
    assert normalize_date_token("2020-06") == "2020-06"
    assert normalize_date_token("2020") == "2020"
    assert normalize_date_token("Present") == "Present"
    assert normalize_date_token("03/2021") == "2021-03"


def test_extract_name_skips_section_headers():
    text = """
SUMMARY
Experienced engineer
Jane Doe
jane@example.com
"""
    # Prefer a name-like line; SUMMARY must not win
    name = extract_name_from_text(text)
    assert name.lower() != "summary"
    assert "Jane" in name or "Experienced" in name


def test_extract_education_and_certs_from_sections():
    text = """
Education
B.S. Computer Science, State University, 2018-2022

Certifications
AWS Solutions Architect - Amazon
"""
    edu = extract_education_from_text(text)
    assert edu
    assert any("B.S" in (e.get("degree") or "") or "State" in (e.get("institution") or "") for e in edu)

    certs = extract_certifications_from_text(text)
    assert certs
    first = certs[0]
    name = first["name"] if isinstance(first, dict) else first
    assert "AWS" in name


def test_extract_experience_with_dates():
    text = """
Experience
Software Engineer at Acme, Jan 2020 - Present
Built APIs

Education
"""
    exps = extract_experience_from_text(text)
    assert exps
    assert exps[0]["from"]
    assert exps[0]["to"] == "Present"


def test_compute_total_experience_years():
    years = compute_total_experience_years([
        {"from": "2020-01", "to": "2022-01"},
        {"from": "2022-01", "to": "Present"},
    ])
    assert years is not None
    assert years >= 4.0
