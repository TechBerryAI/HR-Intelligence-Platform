"""Unit tests for JD parsing normalization and validation (no Ollama required)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.adapter.runtime_adapter import (
    _ensure_array,
    _ensure_string_array,
    _repair_jd_structure,
    normalize_proposal,
    repair_jd_toon,
)
from app.ai.parser.pipelines.jd_toon_pipeline import build_jd_toon
from app.domains.recruitment.services.parsing_storage import validate_toon_format

SAMPLE_JD_RAW = {
    "title": "Senior Python Developer",
    "company": "Acme Corp",
    "location": "Remote",
    "required_skills": ["Python", "Django", "PostgreSQL"],
    "preferred_skills": ["AWS", "Docker"],
    "responsibilities": ["Build APIs", "Write tests"],
    "description": "We need a senior backend engineer.",
    "min_experience_years": 5,
    "max_experience_years": 8,
    "salary_range": "120k-150k",
}

SAMPLE_JD_TEXT = """
AI Engineer — Techberry Infotech Pvt. Ltd.
Location: Bengaluru, India

**Responsibilities:**
• Design and build RAG-based applications
• Develop Python services for model inference
• Collaborate with cross-functional teams

**Required Skills:** Python, PyTorch, LangChain
"""


def test_ensure_array_splits_pipe_and_comma():
    assert _ensure_array("Python|Django|React") == ["Python", "Django", "React"]
    # Skills still split on commas via dedicated skill tokenizer
    from app.ai.adapter.runtime_adapter import _normalize_skills
    assert _normalize_skills("Python, Django, React") == ["Python", "Django", "React"]


def test_ensure_string_array_splits_newlines_and_bullets():
    text = "• Design APIs\n- Write tests\n* Deploy services"
    assert _ensure_string_array(text) == ["Design APIs", "Write tests", "Deploy services"]


def test_ensure_string_array_keeps_commas_inside_sentences():
    """Commas must not become new bullet lines in responsibilities."""
    text = "Design, build, and ship APIs\nLead code reviews"
    assert _ensure_string_array(text) == [
        "Design, build, and ship APIs",
        "Lead code reviews",
    ]
    assert _ensure_string_array([
        "Design, build, and ship APIs",
        "Collaborate with product, design, and QA",
    ]) == [
        "Design, build, and ship APIs",
        "Collaborate with product, design, and QA",
    ]


def test_repair_preserves_comma_sentences_in_responsibilities():
    llm_output = {
        "type": "job_description",
        "title": "Backend Engineer",
        "location": "Remote",
        "skills": ["Python", "Django"],
        "responsibilities": [
            "Design, build, and maintain APIs",
            "Partner with product, design, and QA teams",
        ],
        "qualifications": ["BS in CS, or equivalent experience"],
    }
    repaired, _actions = repair_jd_toon(llm_output)
    assert repaired["responsibilities"] == [
        "Design, build, and maintain APIs",
        "Partner with product, design, and QA teams",
    ]
    assert repaired["qualifications"] == ["BS in CS, or equivalent experience"]


def test_repair_jd_structure_promotes_required_skills():
    repaired, _actions = _repair_jd_structure(SAMPLE_JD_RAW)
    assert repaired["type"] == "job_description"
    assert repaired["mandatory_skills"] == ["Python", "Django", "PostgreSQL"]
    assert repaired["preferred_skills"] == ["AWS", "Docker"]
    assert "Python" in repaired["skills"]


def test_repair_jd_structure_coerces_canonical_type_with_string_responsibilities():
    llm_output = {
        "type": "job_description",
        "title": "AI Engineer",
        "company": "Acme",
        "location": "Remote",
        "skills": ["Python"],
        "responsibilities": "Build APIs|Write tests",
    }
    repaired, actions = repair_jd_toon(llm_output)
    assert repaired["responsibilities"] == ["Build APIs", "Write tests"]
    assert "coerced_responsibilities_string" in actions


def test_repair_jd_structure_maps_duties_alias():
    llm_output = {
        "type": "job_description",
        "title": "Backend Dev",
        "location": "Remote",
        "skills": ["Python"],
        "duties": "Maintain APIs\nImprove performance",
    }
    repaired, actions = repair_jd_toon(llm_output)
    assert repaired["responsibilities"] == ["Maintain APIs", "Improve performance"]
    assert "coalesced_responsibilities_alias" in actions


def test_repair_infers_responsibilities_from_raw_jd_text():
    llm_output = {
        "type": "job_description",
        "title": "AI Engineer",
        "company": "Techberry",
        "location": "Bengaluru",
        "skills": ["Python", "PyTorch"],
        "responsibilities": [],
    }
    repaired, actions = repair_jd_toon(llm_output, raw_jd_text=SAMPLE_JD_TEXT)
    assert len(repaired["responsibilities"]) >= 2
    assert any("RAG" in r or "Python" in r for r in repaired["responsibilities"])
    assert "inferred_responsibilities_from_raw_text" in actions


def test_build_jd_toon_pipeline_passes_validation_for_repairable_llm_output():
    llm_output = {
        "type": "job_description",
        "title": "AI Engineer",
        "company": "Techberry",
        "location": "Bengaluru",
        "skills": ["Python"],
        "responsibilities": "",
    }
    toon = build_jd_toon(SAMPLE_JD_TEXT, llm_output)
    ok, err = validate_toon_format(toon, "job_description")
    assert ok, err
    assert len(toon["responsibilities"]) > 0


def test_build_jd_toon_regression_empty_responsibilities_no_longer_fails_when_recoverable():
    """Production bug: type=job_description + empty responsibilities rejected before repair."""
    llm_output = {
        "type": "job_description",
        "title": "AI Engineer",
        "location": "Remote",
        "skills": ["Python", "TensorFlow"],
        "responsibilities": [],
        "description": (
            "**Responsibilities:**\n"
            "• Architect RAG pipelines\n"
            "• Manage data pipelines\n"
        ),
    }
    toon = build_jd_toon("", llm_output)
    ok, err = validate_toon_format(toon, "job_description")
    assert ok, err
    assert err != "responsibilities must be a non-empty array"


def test_validate_toon_format_jd_still_rejects_unrecoverable():
    toon = {
        "type": "job_description",
        "title": "",
        "location": "",
        "skills": [],
        "responsibilities": [],
    }
    ok, err = validate_toon_format(toon, "job_description")
    assert not ok
    assert "title" in (err or "").lower() or "location" in (err or "").lower()


def test_normalize_proposal_jd_preserves_ats_fields():
    normalized = normalize_proposal(SAMPLE_JD_RAW, "jd")
    assert normalized["company"] == "Acme Corp"
    assert normalized["mandatory_skills"] == ["Python", "Django", "PostgreSQL"]
    assert normalized["preferred_skills"] == ["AWS", "Docker"]
    assert normalized["min_experience_years"] == 5
    assert normalized["salary_range"] == "120k-150k"
    assert normalized["employment_type"] == ""


def test_validate_toon_format_jd_rejects_empty_title():
    toon = {
        "type": "job_description",
        "title": "",
        "location": "Remote",
        "skills": ["Python"],
        "responsibilities": ["Build APIs"],
    }
    ok, err = validate_toon_format(toon, "job_description")
    assert not ok
    assert "title" in (err or "").lower()


def test_validate_toon_format_jd_accepts_complete():
    toon = build_jd_toon("", SAMPLE_JD_RAW)
    ok, err = validate_toon_format(toon, "job_description")
    assert ok, err


def test_repair_infers_experience_years_salary_and_title_from_text():
    jd_text = """
Senior Backend Engineer
Company: Acme Labs
Location: Remote
Employment Type: Full-time
Experience: 3-5 years
Salary: 12-18 LPA

Requirements:
• Bachelor's degree in CS
• Strong Python skills

Responsibilities:
• Build scalable APIs
"""
    llm_output = {
        "type": "job_description",
        "title": "",
        "location": "",
        "skills": [],
        "responsibilities": [],
        "min_experience_years": None,
        "max_experience_years": None,
        "salary_range": "",
    }
    repaired, actions = repair_jd_toon(llm_output, raw_jd_text=jd_text)
    assert repaired["title"]
    assert repaired["location"]
    assert repaired["min_experience_years"] == 3.0
    assert repaired["max_experience_years"] == 5.0
    assert repaired["salary_range"]
    assert "LPA" in repaired["salary_range"].upper() or "12" in repaired["salary_range"]
    assert any("inferred_min_experience" in a or "inferred_title" in a for a in actions)


def test_str_coerces_location_object_with_city_country():
    from app.ai.adapter.runtime_adapter import _str

    assert _str({"city": "Bengaluru", "country": "India"}) == "Bengaluru, India"
    assert _str({"raw": "Remote, US"}) == "Remote, US"
    assert _str({"remote": True}) == "Remote"
    assert _str({"name": "Acme Corp"}) == "Acme Corp"


def test_repair_location_object_and_experience_aliases():
    llm_output = {
        "type": "job_description",
        "job_title": "Staff Engineer",
        "employer": "Acme Labs",
        "location": {"city": "Bengaluru", "region": "KA", "country": "India"},
        "required_skills": [{"name": "Python"}, {"name": "Django"}],
        "experience": "4-7 years",
        "compensation": "18-25 LPA",
        "duties": ["Design systems", "Mentor engineers"],
        "requirements": ["Bachelor's in CS"],
    }
    repaired, actions = repair_jd_toon(llm_output)
    assert repaired["title"] == "Staff Engineer"
    assert repaired["company"] == "Acme Labs"
    assert repaired["location"] == "Bengaluru, KA, India"
    assert repaired["skills"] == ["Python", "Django"]
    assert repaired["mandatory_skills"] == ["Python", "Django"]
    assert repaired["min_experience_years"] == 4.0
    assert repaired["max_experience_years"] == 7.0
    assert "18-25 LPA" in repaired["salary_range"]
    assert repaired["responsibilities"] == ["Design systems", "Mentor engineers"]
    assert repaired["qualifications"] == ["Bachelor's in CS"]
    assert "coalesced_experience_years_alias" in actions


def test_repair_experience_range_object_alias():
    llm_output = {
        "type": "job_description",
        "title": "Data Analyst",
        "location": "Remote",
        "skills": ["SQL"],
        "responsibilities": ["Analyze data"],
        "experience_range": {"min": 2, "max": 4},
    }
    repaired, actions = repair_jd_toon(llm_output)
    assert repaired["min_experience_years"] == 2.0
    assert repaired["max_experience_years"] == 4.0
    assert "coalesced_experience_years_alias" in actions


def test_normalize_rejoins_comma_split_responsibility_fragments():
    from app.ai.adapter.runtime_adapter import _normalize_responsibility_items

    assert _normalize_responsibility_items([
        "Design",
        "build",
        "and maintain scalable GenAI applications",
        "Collaborate with product",
        "design",
        "and engineering teams",
    ]) == [
        "Design, build, and maintain scalable GenAI applications",
        "Collaborate with product, design, and engineering teams",
    ]
    assert _normalize_responsibility_items(["Build APIs", "Write tests"]) == [
        "Build APIs",
        "Write tests",
    ]


def test_description_overview_only_when_jd_has_no_responsibilities_section():
    jd_text = """
AI Engineer
Location: Remote

About the role:
We are seeking a skilled AI Engineer to build RAG systems.

Required Skills: Python, RAG, GenAI
"""
    repaired, actions = repair_jd_toon(
        {
            "type": "job_description",
            "title": "AI Engineer",
            "location": "Remote",
            "skills": ["Python", "RAG"],
            "responsibilities": ["Hallucinated duty from model"],
            "description": "We are seeking a skilled AI Engineer to build RAG systems.",
        },
        raw_jd_text=jd_text,
    )
    assert "Key Responsibilities" not in repaired["description"]
    assert "Hallucinated" not in repaired["description"]
    assert repaired.get("has_key_responsibilities") is False


def test_rebuilds_own_bullets_from_jd_responsibility_sentences():
    jd_text = """
Backend Engineer
Location: Remote

About the role:
We need a backend engineer for APIs.

Key Responsibilities:
- Design, build, and maintain APIs
* Partner with product, design, and QA
1. Own production reliability

Required Skills: Python, Django
"""
    repaired, _actions = repair_jd_toon(
        {
            "type": "job_description",
            "title": "Backend Engineer",
            "location": "Remote",
            "skills": ["Python"],
            "responsibilities": [],
            "description": "",
        },
        raw_jd_text=jd_text,
    )
    assert repaired.get("has_key_responsibilities") is True
    assert "Key Responsibilities" in repaired["description"]
    bullets = [ln.strip() for ln in repaired["description"].splitlines() if ln.strip().startswith("•")]
    assert any("Design, build, and maintain APIs" in b for b in bullets)
    assert "- Design" not in repaired["description"]
    assert "* Partner" not in repaired["description"]
    assert "1. Own" not in repaired["description"]


def test_description_falls_back_to_required_skills_when_missing():
    repaired, actions = repair_jd_toon(
        {
            "type": "job_description",
            "title": "Python Developer",
            "location": "Remote",
            "skills": ["Python", "Django", "PostgreSQL"],
            "mandatory_skills": ["Python", "Django", "PostgreSQL"],
            "responsibilities": [],
            "description": "",
        },
        raw_jd_text="Python Developer\nLocation: Remote\nRequired Skills: Python, Django, PostgreSQL\n",
    )
    assert "**Required Skills:**" in repaired["description"]
    assert "Python" in repaired["description"]
    assert "Key Responsibilities" not in repaired["description"]
    assert "filled_description_from_required_skills" in actions

