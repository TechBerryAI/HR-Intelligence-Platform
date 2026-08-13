"""Unit tests for ATS matching verdict gates (internal matcher only)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / 'apps' / 'backend'
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Force internal matcher for deterministic unit tests
os.environ['ATS_API_URL'] = ''
os.environ['ATS_API_KEY'] = ''
os.environ['ATS_NARRATIVE_LLM'] = '0'
os.environ['DOCUMENT_INTELLIGENCE_SEMANTIC_AI'] = 'false'
os.environ['ATS_THRESHOLD'] = '80'
os.environ['ATS_AUTO_SHORTLIST_MIN'] = '80'

from app.domains.recruitment.services.ats_service import (
    _internal_match,
    _skill_match,
    _sanitize_skill_list,
    MANDATORY_SKILLS_MIN_PCT,
)

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
    assert result["overall_match_score"] >= 80
    assert result["verdict"] == "Strong Match"
    assert result["mandatory_skills_match_pct"] >= MANDATORY_SKILLS_MIN_PCT


def test_auto_shortlist_only_strong_match():
    """≥80% Strong Match → shortlist; Potential Match must not auto-shortlist."""
    from app.domains.recruitment.services.ats_service import match_candidate_to_job
    from app.domains.recruitment.api.applications import _shortlisted_from_decision

    ok, payload = match_candidate_to_job("c1", "j1", BASE_RESUME, BASE_JD)
    assert ok
    out = payload["json_output"]
    assert out["overall_match_score"] >= 80
    assert out["decision"] == "shortlist"
    assert out["match_tier"] == "strong_match"
    assert _shortlisted_from_decision(out["decision"]) is True

    # Weaker preferred skills → often Potential tier; must not auto-shortlist
    resume = {**BASE_RESUME, "skills": ["Python", "Django", "PostgreSQL"]}
    jd = {**BASE_JD, "preferred_skills": ["Kubernetes", "Terraform", "GraphQL", "Kafka", "Redis"]}
    ok2, payload2 = match_candidate_to_job("c2", "j2", resume, jd)
    assert ok2
    out2 = payload2["json_output"]
    if out2.get("verdict") == "Potential Match (Recruiter Review)" or out2.get("match_tier") == "partial_match":
        assert out2["decision"] == "reject"
        assert _shortlisted_from_decision(out2["decision"]) is False
    assert _shortlisted_from_decision("partial_match") is False
    assert _shortlisted_from_decision("strong_match") is True


def test_good_match_potential_verdict():
    resume = {**BASE_RESUME, "skills": ["Python", "Django", "PostgreSQL"]}
    jd = {**BASE_JD, "preferred_skills": ["Kubernetes", "Terraform", "GraphQL"]}
    result = _internal_match(resume, jd)
    assert result["mandatory_skills_match_pct"] >= MANDATORY_SKILLS_MIN_PCT
    assert result["overall_match_score"] >= 40
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
    assert result["overall_match_score"] < 40


def test_empty_mandatory_skills_no_auto_gate():
    jd = {**BASE_JD, "mandatory_skills": [], "preferred_skills": [], "skills": []}
    result = _internal_match(BASE_RESUME, jd)
    assert result["mandatory_skills_match_pct"] == 100.0


def test_numeric_experience_title_role_does_not_crash():
    """TOON round-trip can reload numeric-looking titles/roles as ints."""
    resume = {
        **BASE_RESUME,
        "experience": [
            {"title": 2021, "role": 3, "company": "Acme", "from": "2019", "to": "2021"},
            {"title": "MSSQL DBA", "company": "Tech Co", "from": "2021", "to": "2024"},
        ],
        "education": [
            {"degree": 2018, "field": "Computer Science", "institution": "State U"},
        ],
    }
    jd = {
        **BASE_JD,
        "title": "MSSQL DBA",
        "location": 400001,  # numeric postal-style location from TOON
    }
    result = _internal_match(resume, jd)
    assert "overall_match_score" in result
    assert isinstance(result["overall_match_score"], (int, float))
    assert result["verdict"] in (
        "Strong Match",
        "Potential Match (Recruiter Review)",
        "Not a Match",
    )


def test_skill_match_token_boundary_not_substring():
    """java must not match javascript; short tokens require exact equality."""
    assert _skill_match("Java", ["JavaScript"]) is False
    assert _skill_match("Java", ["Java", "Spring"]) is True
    assert _skill_match("SQL", ["PostgreSQL"]) is False
    assert _skill_match("React", ["React Native"]) is True
    assert _skill_match("C", ["C++"]) is False


def test_sanitize_skill_list_drops_noise():
    cleaned = _sanitize_skill_list(
        ["PostgreSQL", "Preferred Qualifications", "plus", "Azure Database for", "management", "Azure"]
    )
    lower = {s.lower() for s in cleaned}
    assert "postgresql" in lower or "PostgreSQL" in cleaned
    assert "preferred qualifications" not in lower
    assert "plus" not in lower
    assert "management" not in lower
    assert "azure database for" not in lower


def test_noisy_mandatory_skills_sanitized_at_match():
    """Garbage mandatory tokens from old TOON should not invent fake gaps."""
    jd = {
        **BASE_JD,
        "mandatory_skills": ["Python", "Preferred Qualifications", "plus", "management"],
        "preferred_skills": [],
        "skills": [],
    }
    result = _internal_match(BASE_RESUME, jd)
    req = result["requirement_analysis"]
    mand_skills = [r["skill"].lower() for r in req["mandatory"]]
    assert "preferred qualifications" not in mand_skills
    assert "plus" not in mand_skills
    assert "management" not in mand_skills
    assert result["verdict"] == "Strong Match" or result["mandatory_skills_match_pct"] >= MANDATORY_SKILLS_MIN_PCT


def test_requirement_analysis_and_decision_summary_shape():
    result = _internal_match(BASE_RESUME, BASE_JD)
    assert "requirement_analysis" in result
    assert "decision_summary" in result
    assert "narrative" in result
    req = result["requirement_analysis"]
    assert "mandatory" in req and "preferred" in req and "gate" in req
    assert req["gate"]["threshold"] == MANDATORY_SKILLS_MIN_PCT
    assert all("skill" in row and row["status"] in ("matched", "missing") for row in req["mandatory"])
    assert isinstance(result["decision_summary"], str) and result["decision_summary"]
    assert isinstance(result["narrative"], str) and result["narrative"]
    # Strengths/gaps are skill chips, not "Missing mandatory skills: a, b" blobs
    assert not any(str(s).lower().startswith("missing mandatory") for s in result["key_gaps"])
    assert not any(str(s).lower().startswith("possesses mandatory") for s in result["key_strengths"])


def test_category_reasons_needed_vs_present():
    result = _internal_match(BASE_RESUME, BASE_JD)
    assert "category_reasons" in result
    reasons = result["category_reasons"]
    assert len(reasons) == 4
    skills = next(r for r in reasons if r["key"] == "skills")
    assert skills["result"] in ("match", "partial", "not_match", "unclear")
    assert "needed" in skills and "present" in skills
    assert "reason" in skills and len(skills["reason"]) > 20
    assert "weight" not in skills["reason"].lower() or "matters" in skills["reason"].lower()
    expl = result["decision_explanation"]
    assert expl.get("category_reasons")
    assert any("Present" in b or "present" in b or "needed" in b.lower() or "Missing" in b for b in expl["what_happened"] + [skills["reason"]])


def test_gate_fail_explains_experience_vs_skills():
    resume = {
        **BASE_RESUME,
        "skills": ["Java", "Spring"],
        "experience": [
            {"title": "Senior Python Developer", "company": "Tech Co", "from": "2018", "to": "2024", "years": 6},
        ],
    }
    result = _internal_match(resume, BASE_JD)
    expl = result["decision_explanation"]
    assert expl["outcome"] == "reject"
    assert expl["reconciliation"]
    assert "experience" in expl["reconciliation"].lower()
    assert "skills" in expl["reconciliation"].lower()
    assert "low match" in expl["primary_reason"].lower() or "reject" in expl["outcome"]


def test_reconcile_match_score_from_polluted_analysis():
    from app.domains.recruitment.services.ats_service import reconcile_match_score_from_analysis

    ats = {
        "json_output": {
            "overall_match_score": 52,
            "verdict": "Not a Match",
            "score_breakdown": {"skills": 20, "experience": 100, "education": 100, "location": 100},
            "requirement_analysis": {
                "mandatory": [
                    {"skill": "PostgreSQL", "status": "matched"},
                    {"skill": "Preferred Qualifications", "status": "missing"},
                    {"skill": "plus", "status": "missing"},
                    {"skill": "Azure Database for", "status": "missing"},
                ],
                "preferred": [],
                "gate": {"passed": False, "mandatory_pct": 20, "threshold": 40, "mandatory_defined": True},
            },
            "evaluation_report": {
                "skills_analysis": {
                    "mandatory_matched_skills": ["PostgreSQL"],
                    "missing_mandatory_skills": ["Preferred Qualifications", "plus"],
                },
                "experience_assessment": {"relevant_experience_summary": "Direct role match"},
                "education_certification_assessment": "No degree requirement stated for role.",
            },
        }
    }
    recon = reconcile_match_score_from_analysis(ats, 52)
    assert recon["adjusted"] is True
    assert recon["match_score"] >= 95
    assert recon["verdict"] == "Strong Match"
    assert recon["score_breakdown"]["skills"] >= 95


def test_reconcile_legacy_string_skills_matched():
    """Older payloads store skills_matched as a bare string and gaps as prose."""
    from app.domains.recruitment.services.ats_service import reconcile_match_score_from_analysis

    ats = {
        "json_output": {
            "overall_match_score": 52,
            "verdict": "Not a Match",
            "score_breakdown": {"skills": 20, "experience": 100, "education": 100, "location": 100},
            "key_strengths": [
                "Possesses mandatory skills: PostgreSQL",
                "Experience aligns with role/domain",
            ],
            "key_gaps": "Missing mandatory skills: Preferred Qualifications, plus, Azure Database for, management",
            "evaluation_report": {
                "skills_analysis": {
                    "skills_matched": "PostgreSQL",
                    "missing_mandatory_skills": [
                        "Preferred Qualifications",
                        "plus",
                        "Azure Database for",
                        "management",
                    ],
                    "mandatory_skills_match_pct": 20.0,
                },
                "experience_assessment": {"relevant_experience_summary": "Direct role match"},
                "education_certification_assessment": "No degree requirement stated for role.",
            },
        }
    }
    recon = reconcile_match_score_from_analysis(ats, 52)
    assert recon["adjusted"] is True
    assert recon["match_score"] >= 95
    assert recon["verdict"] == "Strong Match"


def test_skip_narrative_does_not_call_llm(monkeypatch):
    """Public apply sets skip_narrative=True so submit never waits on Ollama."""
    called = {"n": 0}

    def _boom(_evidence):
        called["n"] += 1
        raise AssertionError("LLM narrative must not run when skip_narrative=True")

    monkeypatch.setenv("ATS_NARRATIVE_LLM", "1")
    monkeypatch.setattr(
        "app.domains.recruitment.services.ats_service._optional_llm_narrative",
        _boom,
    )
    result = _internal_match(BASE_RESUME, BASE_JD, skip_narrative=True)
    assert called["n"] == 0
    assert result["overall_match_score"] >= 80
    assert result.get("narrative") or result.get("final_reasoning")
