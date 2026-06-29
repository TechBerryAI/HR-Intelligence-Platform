"""Unit tests for ATS matching verdict gates (internal matcher only)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Force internal matcher for deterministic unit tests
os.environ['ATS_API_URL'] = ''
os.environ['ATS_API_KEY'] = ''

from services.ats_service import _internal_match, MANDATORY_SKILLS_MIN_PCT

BASE_RESUME = {
    "type": "resume",
    "person": {"name": "Alex Dev", "email": "alex@example.com", "phone": "555", "location": "Remote"},
    "skills": ["Python", "Django", "PostgreSQL", "Docker", "AWS"],
    "experience": [
        {"title": "Senior Engineer", "company": "Tech Co", "from": "2018", "to": "2024", "years": 6},
    ],
    "education": [{"degree": "B.S. Computer Science", "institution": "State U", "year": "2018"}],
    "total_experience_years": 6,
}

BASE_JD = {
    "type": "job_description",
    "title": "Senior Python Developer",
    "location": "Remote",
    "mandatory_skills": ["Python", "Django", "PostgreSQL"],
    "preferred_skills": ["AWS", "Docker"],
    "skills": ["Python", "Django", "PostgreSQL", "AWS", "Docker"],
    "responsibilities": ["Build APIs"],
    "qualifications": ["Bachelor degree in Computer Science"],
    "min_experience_years": 5,
    "max_experience_years": 10,
}


def test_excellent_match_strong_verdict():
    result = _internal_match(BASE_RESUME, BASE_JD)
    assert result["overall_match_score"] >= 75
    assert result["verdict"] == "Strong Match"
    assert result["mandatory_skills_match_pct"] >= MANDATORY_SKILLS_MIN_PCT


def test_good_match_potential_verdict():
    resume = {**BASE_RESUME, "skills": ["Python", "Django", "PostgreSQL"]}
    jd = {**BASE_JD, "preferred_skills": ["Kubernetes", "Terraform", "GraphQL"]}
    result = _internal_match(resume, jd)
    assert result["mandatory_skills_match_pct"] >= MANDATORY_SKILLS_MIN_PCT
    assert result["overall_match_score"] >= 60
    assert "Match" in result["verdict"]


def test_below_mandatory_gate_not_a_match():
    resume = {**BASE_RESUME, "skills": ["Java", "Spring"]}
    result = _internal_match(resume, BASE_JD)
    assert result["mandatory_skills_match_pct"] < MANDATORY_SKILLS_MIN_PCT
    assert result["verdict"] == "Not a Match"


def test_poor_match_not_a_match():
    resume = {
        **BASE_RESUME,
        "skills": ["Excel", "Word"],
        "experience": [],
        "education": [],
        "total_experience_years": 1,
    }
    jd = {**BASE_JD, "min_experience_years": 8}
    result = _internal_match(resume, jd)
    assert result["verdict"] == "Not a Match"
    assert result["overall_match_score"] < 60


def test_empty_mandatory_skills_no_auto_gate():
    jd = {**BASE_JD, "mandatory_skills": [], "preferred_skills": [], "skills": []}
    result = _internal_match(BASE_RESUME, jd)
    assert result["mandatory_skills_match_pct"] == 100.0
