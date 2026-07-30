"""Unit tests for JD parsing normalization and validation (no Ollama required)."""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ai_runtime_adapter import (
    _ensure_array,
    _ensure_string_array,
    _repair_jd_structure,
    normalize_proposal,
    repair_jd_toon,
)
from jd_toon_pipeline import build_jd_toon
from parsing_utils import validate_toon_format

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
    assert _ensure_array("Python, Django, React") == ["Python", "Django", "React"]


def test_ensure_string_array_splits_newlines_and_bullets():
    text = "• Design APIs\n- Write tests\n* Deploy services"
    assert _ensure_string_array(text) == ["Design APIs", "Write tests", "Deploy services"]


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
