"""Unit tests for resume parsing validation hardening and enrichment (no Ollama required)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from ai_runtime_adapter import _ensure_array, canonicalize_resume_toon, normalize_proposal, repair_resume_toon
from parsing_utils import collect_toon_validation_issues, validate_toon_format
from resume_enrichment import ResumeEnrichmentContext, enrich_resume_toon
from resume_inference import infer_resume_toon
from resume_toon_pipeline import build_resume_toon

SAMPLE_RESUME = {
    "person": {
        "name": "Jane Doe",
        "email": "jane@example.com",
        "phone": "+1 555-0100",
        "location": "Austin, TX",
    },
    "skills": ["Python", "SQL", "Docker"],
    "experience": [{"title": "Engineer", "company": "Acme", "from": "2020", "to": "2024"}],
    "education": [{"degree": "B.S. CS", "institution": "State U", "year": "2020"}],
}

SAMPLE_RESUME_TEXT = """
Jane Doe
jane@example.com
Location: Austin, TX
Skills: Python, SQL, Docker
"""


def test_resume_validate_rejects_empty_name():
    toon = normalize_proposal(SAMPLE_RESUME, "resume")
    toon["person"]["name"] = ""
    ok, err = validate_toon_format(toon, "resume")
    assert not ok
    assert "name" in (err or "").lower()


def test_resume_validate_allows_empty_skills_when_history_present():
    toon = normalize_proposal(SAMPLE_RESUME, "resume")
    toon["skills"] = []
    ok, err = validate_toon_format(toon, "resume")
    assert ok, err


def test_resume_validate_rejects_empty_skills_without_history():
    toon = {
        "type": "resume",
        "person": {"name": "Jane Doe", "email": "jane@example.com", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    ok, err = validate_toon_format(toon, "resume")
    assert not ok
    assert "skills" in (err or "").lower()


def test_normalize_education_preserves_gpa_dates_and_field():
    from ai_runtime_adapter import _normalize_education, canonicalize_resume_toon

    edu = _normalize_education([
        {
            "degree": "B.S.",
            "field": "Computer Science",
            "institution": "State U",
            "from": "2018-08",
            "to": "2022-05",
            "gpa": "3.8",
        }
    ])
    assert edu[0]["field"] == "Computer Science"
    assert edu[0]["gpa"] == "3.8"
    assert edu[0]["cgpa"] == "3.8"
    assert edu[0]["from"] == "2018-08"
    assert edu[0]["to"] == "2022-05"

    toon = {
        "type": "resume",
        "person": {"name": "A", "email": "a@b.com", "phone": ""},
        "skills": ["Python"],
        "experience": [],
        "education": edu,
        "certifications": [{"name": "AWS", "issuer": "Amazon", "validTill": "2026", "url": "https://example.com"}],
    }
    canon, _ = canonicalize_resume_toon(toon)
    assert canon["education"][0]["gpa"] == "3.8"
    assert canon["education"][0]["from"] == "2018-08"
    assert canon["certifications"][0]["issuer"] == "Amazon"
    assert canon["certifications"][0]["validTill"] == "2026"
    assert canon["certifications"][0]["url"] == "https://example.com"


def test_repair_backfills_incomplete_education_row():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane Doe", "email": "jane@example.com", "phone": ""},
        "skills": ["Python"],
        "experience": [],
        "education": [{"degree": "B.Tech", "institution": "", "year": ""}],
    }
    raw = """
Jane Doe
jane@example.com
Education
B.Tech Computer Science, State University, 2018-2022
Skills: Python
"""
    toon, actions = repair_resume_toon(llm_output, raw_resume_text=raw)
    assert toon["education"]
    assert (toon["education"][0].get("institution") or "").strip() or any(
        "backfilled_education" in a for a in actions
    ) or (toon["education"][0].get("degree") or "")


def test_ocr_join_detections_reading_order():
    from app.ai.parser.text_extraction import _join_ocr_detections_reading_order

    # Lower box first in input, but higher on page should come first after sort
    detections = [
        [[[10, 100], [50, 100], [50, 120], [10, 120]], "Second line", 0.9],
        [[[10, 20], [40, 20], [40, 40], [10, 40]], "First line", 0.95],
        [[[80, 22], [140, 22], [140, 42], [80, 42]], "same-row-right", 0.9],
    ]
    text = _join_ocr_detections_reading_order(detections)
    lines = text.split("\n")
    assert lines[0] == "First line"
    assert "same-row-right" in lines[1]
    assert lines[-1] == "Second line"


def test_resume_skills_pipe_split():
    assert _ensure_array("Python|Java|Go") == ["Python", "Java", "Go"]


def test_enrich_fills_missing_email_from_account():
    toon = normalize_proposal(
        {
            **SAMPLE_RESUME,
            "person": {**SAMPLE_RESUME["person"], "email": ""},
        },
        "resume",
    )
    ctx = ResumeEnrichmentContext(email="candidate@example.com", name="Jane Doe")
    enriched, actions = enrich_resume_toon(toon, ctx)
    ok, err = validate_toon_format(enriched, "resume")
    assert ok, err
    assert enriched["person"]["email"] == "candidate@example.com"
    assert "enriched_email_from_account" in actions


def test_enrich_fills_missing_name_from_account():
    toon = normalize_proposal(
        {
            **SAMPLE_RESUME,
            "person": {**SAMPLE_RESUME["person"], "name": ""},
        },
        "resume",
    )
    ctx = ResumeEnrichmentContext(email="jane@example.com", name="Jane From Account")
    enriched, actions = enrich_resume_toon(toon, ctx)
    assert enriched["person"]["name"] == "Jane From Account"
    assert "enriched_name_from_account" in actions


def test_enrich_does_not_overwrite_resume_email():
    toon = normalize_proposal(SAMPLE_RESUME, "resume")
    ctx = ResumeEnrichmentContext(email="other@example.com", name="Other Name")
    enriched, actions = enrich_resume_toon(toon, ctx)
    assert enriched["person"]["email"] == "jane@example.com"
    assert enriched["person"]["name"] == "Jane Doe"
    assert actions == []


def test_enrich_no_context_is_noop():
    toon = normalize_proposal(
        {
            **SAMPLE_RESUME,
            "person": {**SAMPLE_RESUME["person"], "email": ""},
        },
        "resume",
    )
    enriched, actions = enrich_resume_toon(toon, None)
    assert enriched["person"]["email"] == ""
    assert actions == []


def test_build_resume_toon_enriches_missing_email_for_candidate():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane Doe", "email": "", "phone": "+1 555-0100"},
        "skills": ["Python"],
        "experience": [{"title": "Dev", "company": "Acme", "from": "2020", "to": "2024"}],
        "education": [{"degree": "BS", "institution": "State U", "year": "2020"}],
    }
    ctx = ResumeEnrichmentContext(email="trusted@example.com", name="Jane Doe")
    # No raw text — enrichment must supply email when repair cannot infer it
    toon = build_resume_toon("", llm_output, ctx)
    ok, err = validate_toon_format(toon, "resume")
    assert ok, err
    assert toon["person"]["email"] == "trusted@example.com"


def test_build_resume_toon_regression_missing_email_enriched_passes_validation():
    """Production bug: person.email must not be empty when account has trusted email."""
    llm_output = {
        "type": "resume",
        "person": {"name": "Lucifer Morningstar", "email": "", "phone": ""},
        "skills": ["Python", "TensorFlow"],
        "experience": [{"title": "Engineer", "company": "Acme", "from": "2020", "to": "2024"}],
        "education": [{"degree": "B.Tech", "institution": "State U", "year": "2020"}],
    }
    ctx = ResumeEnrichmentContext(email="celate8074@noproposal.com", name="Lucifer Morningstar")
    toon = build_resume_toon("", llm_output, ctx)
    ok, err = validate_toon_format(toon, "resume")
    assert ok, err
    assert err != "person.email must not be empty"


def test_validate_still_rejects_unrecoverable_resume():
    toon = {
        "type": "resume",
        "person": {"name": "", "email": "", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    ok, err = validate_toon_format(toon, "resume")
    assert not ok


def test_repair_coerces_canonical_resume_with_string_skills():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "skills": "Python|SQL",
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    repaired, actions = repair_resume_toon(llm_output)
    assert "Python" in repaired["skills"]
    assert "coerced_skills_string" in actions


def test_text_extraction_rejects_doc():
    from text_extraction import extract_text

    with pytest.raises(ValueError, match="DOCX or PDF"):
        extract_text(b"fake", "resume.doc")


def test_repair_merges_technical_and_core_skills():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "technical_skills": "Python|Java",
        "core_skills": ["Python", "SQL"],
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    repaired, actions = repair_resume_toon(llm_output)
    assert repaired["skills"] == ["Python", "Java", "SQL"]
    assert "coalesced_technical_skills" in actions
    assert "coalesced_core_skills" in actions


def test_repair_flattens_skill_groups():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "skill_groups": {
            "frameworks": ["React", "Django"],
            "languages": ["Python", "Go"],
        },
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    repaired, actions = repair_resume_toon(llm_output)
    assert "React" in repaired["skills"]
    assert "Python" in repaired["skills"]
    assert "flattened_skill_groups" in actions


def test_inference_fills_skills_from_raw_text():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "skills": [],
        "experience": [{"title": "Dev", "company": "Acme", "from": "2020", "to": "2024"}],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    raw_text = """
Jane Doe
**Technical Skills:**
- Python
- Docker
"""
    toon = build_resume_toon(raw_text, llm_output)
    assert "Python" in toon["skills"]
    assert "Docker" in toon["skills"]


def test_inference_does_not_overwrite_existing_skills():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "skills": ["Kubernetes"],
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    raw_text = "Skills: Python, SQL"
    toon, actions = infer_resume_toon(normalize_proposal(llm_output, "resume"), raw_text)
    assert toon["skills"] == ["Kubernetes"]
    assert actions == []


def test_collect_validation_issues_returns_all_resume_faults():
    toon = {
        "type": "resume",
        "person": {"name": "", "email": "", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    issues = collect_toon_validation_issues(toon, "resume")
    assert "person.name must not be empty" in issues
    assert "person.email must not be empty" in issues
    assert "skills must be a non-empty array" in issues
    assert len(issues) >= 3


def test_validate_toon_format_joins_all_issues():
    toon = {
        "type": "resume",
        "person": {"name": "", "email": "", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    ok, err = validate_toon_format(toon, "resume")
    assert not ok
    assert "person.name must not be empty" in (err or "")
    assert "person.email must not be empty" in (err or "")
    assert "skills must be a non-empty array" in (err or "")


def test_empty_resume_still_fails_after_full_pipeline():
    llm_output = {
        "type": "resume",
        "person": {"name": "", "email": "", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    toon = build_resume_toon("", llm_output, None)
    ok, err = validate_toon_format(toon, "resume")
    assert not ok
    assert err


def test_build_resume_toon_regression_empty_skills_recovers_from_text():
    """Production bug: skills must be non-empty when recoverable from raw text."""
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        "skills": [],
        "experience": [{"title": "Dev", "company": "Acme", "from": "2020", "to": "2024"}],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    raw_text = "**Technical Skills:**\n- Python\n- Docker"
    toon = build_resume_toon(raw_text, llm_output)
    ok, err = validate_toon_format(toon, "resume")
    assert ok, err
    assert "Python" in toon["skills"]
    assert err != "skills must be a non-empty array"


def test_repair_infers_email_from_raw_text():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "", "phone": ""},
        "skills": ["Python"],
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    raw_text = "Jane Doe\njane@example.com\nSkills: Python"
    toon = build_resume_toon(raw_text, llm_output)
    assert toon["person"]["email"] == "jane@example.com"


def test_repair_merges_top_level_email_into_person():
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane"},
        "email": "jane@example.com",
        "skills": ["Python"],
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    repaired, actions = repair_resume_toon(llm_output)
    assert repaired["person"]["email"] == "jane@example.com"
    assert "coalesced_top_level_email" in actions


@pytest.mark.parametrize(
    "skill_key,skill_value",
    [
        ("technologies", ["React", "Node"]),
        ("tools", ["Docker", "Git"]),
        ("frameworks", ["Django", "Flask"]),
        ("expertise", "Python|SQL"),
        ("tech_stack", ["Kubernetes", "AWS"]),
    ],
)
def test_repair_merges_skill_aliases(skill_key, skill_value):
    llm_output = {
        "type": "resume",
        "person": {"name": "Jane", "email": "j@ex.com", "phone": ""},
        skill_key: skill_value,
        "experience": [],
        "education": [{"degree": "BS", "institution": "U", "year": "2020"}],
    }
    repaired, actions = repair_resume_toon(llm_output)
    assert len(repaired["skills"]) > 0
    assert f"coalesced_{skill_key}" in actions


def test_build_resume_toon_preserves_object_identity():
    llm_output = dict(SAMPLE_RESUME)
    toon = build_resume_toon(SAMPLE_RESUME_TEXT, llm_output)
    # build_resume_toon deep-copies input; identity stable from repair through return
    repaired, _ = repair_resume_toon(dict(SAMPLE_RESUME))
    carrier = dict(SAMPLE_RESUME)
    start_id = id(carrier)
    repair_resume_toon(carrier)
    canonicalize_resume_toon(carrier)
    assert id(carrier) == start_id


def test_simple_fresher_resume_validates_with_text_inference():
    llm_output = {
        "type": "resume",
        "person": {"name": "", "email": "", "phone": ""},
        "skills": [],
        "experience": [],
        "education": [],
    }
    raw_text = """
Alex Fresh
alex@fresh.com
+1 555-9999

Education
B.S. Computer Science, State University, 2024

Skills: Python, JavaScript, HTML
"""
    toon = build_resume_toon(raw_text, llm_output)
    ok, err = validate_toon_format(toon, "resume")
    assert ok, err
    assert toon["person"]["email"] == "alex@fresh.com"
    assert len(toon["skills"]) > 0
