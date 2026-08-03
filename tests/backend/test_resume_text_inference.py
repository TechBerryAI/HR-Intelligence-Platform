"""Unit tests for resume text inference helpers."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
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
    # Prefer a name-like line; SUMMARY / objective prose must not win
    name = extract_name_from_text(text)
    assert name.lower() != "summary"
    assert "Jane" in name
    assert "Experienced" not in name


def test_extract_name_rejects_percentage_label():
    text = """
Percentage: 75.27
anjalibansode0227@gmail.com
9527767516
"""
    name = extract_name_from_text(text)
    assert name != "Percentage: 75.27"
    assert "75.27" not in name
    # Glued email local must not invent a spaced name
    assert name == ""


def test_anjali_style_section_bleed_does_not_pollute_fields():
    text = """
Percentage: 75.27
anjalibansode0227@gmail.com
9527767516

Education
B.Tech Computer Science, Some College, 2017

Technical Skills
HTML, Core Java, SQL

PROJECT
06/2016 - 06/2017
Built a small website.

Certifications
Revolution IT Solutions: Web Development
Web Development certification focusing on front-end

Work Experience
Web Developer at Acme, Jan 2018 - Present
"""
    name = extract_name_from_text(text)
    assert name != "Percentage: 75.27"

    skills = extract_skills_from_text(text)
    skills_l = [s.lower() for s in skills]
    assert "education" not in skills_l
    assert "project" not in skills_l
    assert not any("06/2016" in s for s in skills)
    assert "HTML" in skills or "html" in skills_l
    assert any("java" in s.lower() for s in skills)
    assert "SQL" in skills or "sql" in skills_l

    edu = extract_education_from_text(text)
    institutions = [(e.get("institution") or "").lower() for e in edu]
    degrees = [(e.get("degree") or "").lower() for e in edu]
    assert not any(i in ("html", "core java") for i in institutions)
    assert any("b.tech" in d or "college" in i for d, i in zip(degrees, institutions))

    certs = extract_certifications_from_text(text)
    cert_names = []
    for c in certs:
        cert_names.append((c.get("name") if isinstance(c, dict) else str(c)).lower())
    # Company: description without cert cue should be dropped
    assert not any("revolution it solutions" in n for n in cert_names)


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


def test_extract_experience_skips_objective_prose_as_title():
    from resume_text_inference import is_plausible_job_title

    assert not is_plausible_job_title("to help the company achieve its objectiv")
    assert not is_plausible_job_title("Seeking a challenging role in HR")
    assert is_plausible_job_title("HR Intern")
    assert is_plausible_job_title("Software Engineer")

    text = """
Career Objective
To help the company achieve its objectives through dedicated work.

Experience
HR Intern at Techberry, Jun 2023 - Aug 2023

Education
"""
    exps = extract_experience_from_text(text)
    assert exps
    assert exps[0]["title"] == "HR Intern"
    assert "Techberry" in exps[0]["company"]
    assert not any("help the company" in (e.get("title") or "").lower() for e in exps)


def test_normalize_experience_drops_objective_title_without_company():
    from ai_runtime_adapter import canonicalize_resume_toon

    toon = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": ""},
        "skills": ["HR"],
        "experience": [
            {"title": "to help the company achieve its objectiv", "company": "", "from": "", "to": ""},
            {"title": "HR Intern", "company": "Acme", "from": "2023-06", "to": "2023-08"},
        ],
        "education": [],
    }
    canon, _ = canonicalize_resume_toon(toon)
    titles = [e["title"] for e in canon["experience"]]
    assert "HR Intern" in titles
    assert not any("help the company" in t.lower() for t in titles)


def test_compute_total_experience_years():
    years = compute_total_experience_years([
        {"from": "2020-01", "to": "2022-01"},
        {"from": "2022-01", "to": "Present"},
    ])
    assert years is not None
    assert years >= 4.0


def test_master_of_science_not_split_to_ma():
    text = """
Education
Master of Science, Pune University, 2015

Technical Skills
SQL
"""
    edu = extract_education_from_text(text)
    assert edu
    assert any("Master" in (e.get("degree") or "") for e in edu)
    assert not any((e.get("degree") or "").strip().lower() == "ma" for e in edu)
    assert not any("ster of science" in (e.get("institution") or "").lower() for e in edu)


def test_biodata_lines_are_not_job_titles():
    from resume_text_inference import is_plausible_job_title

    assert not is_plausible_job_title("PERSONAL DETAILS")
    assert not is_plausible_job_title("Date of Birth")
    assert not is_plausible_job_title("20 November 1992")
    assert not is_plausible_job_title("Gender")
    assert not is_plausible_job_title("Marital Status")
    assert not is_plausible_job_title(": Married")
    assert is_plausible_job_title("MSSQL DBA")
    assert is_plausible_job_title("Software Engineer")
