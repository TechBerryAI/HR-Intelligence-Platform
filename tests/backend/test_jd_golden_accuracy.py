"""Golden regression tests for JD parsing accuracy (eval failure set)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2] / "apps" / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.ai.document_intelligence import parse_jd_text_to_canonical
from app.ai.parser.enrichment.jd_text_inference import (
    extract_experience_years,
    extract_title_from_text,
    is_plausible_job_title,
    normalize_skill_tokens,
)

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "jd_gold"


def _parse(name: str):
    text = (FIXTURES / name).read_text(encoding="utf-8")
    profile, form, _toon = parse_jd_text_to_canonical(text, max_workers=2)
    return text, profile, form


def test_is_plausible_rejects_section_labels_allows_jr():
    assert not is_plausible_job_title("Role Overview")
    assert not is_plausible_job_title("Job Summary")
    assert not is_plausible_job_title("PUBLIC")
    assert not is_plausible_job_title("Notice period-   Immediate to 45 days")
    assert not is_plausible_job_title("● Participate in requirement analysis")
    assert is_plausible_job_title("Jr. IT Solutions Associate")
    assert is_plausible_job_title("Design Engineer")
    assert is_plausible_job_title("Cloud Engineer (AWS)")


def test_experience_ignores_24x7_requires_years():
    assert extract_experience_years("Must be available for 24x7 support") == (None, None)
    assert extract_experience_years("on-call 24-7 windows") == (None, None)
    assert extract_experience_years("Experience: 4-7 years") == (4.0, 7.0)
    assert extract_experience_years("Fresher – 1 year") == (0.0, 1.0)


def test_normalize_skills_drops_sentences_and_qualifications():
    toks = normalize_skill_tokens(
        [
            "We are seeking a highly skilled AI Engineer to join our team",
            "Qualification :-",
            "Weblogic",
            "Preferred Skills:",
            "Kubernetes",
        ]
    )
    assert "Weblogic" in toks
    assert "Kubernetes" in toks
    assert not any("seeking" in t.lower() for t in toks)
    assert not any("qualification" in t.lower() for t in toks)


@pytest.mark.parametrize(
    "fixture,title_substr",
    [
        ("aws_cloud_engineer.txt", "Cloud Engineer"),
        ("junior_it_solutions.txt", "IT Solutions"),
        ("sre_public_banner.txt", "Site Reliability"),
        ("java_fullstack.txt", "Java Full Stack"),
        ("storage_admin.txt", "Storage Admin"),
        ("middleware_admin_24x7.txt", "Middleware Admin"),
    ],
)
def test_golden_titles(fixture, title_substr):
    _text, profile, form = _parse(fixture)
    title = form.title or profile.basic.title
    assert title_substr.lower() in title.lower(), f"got title={title!r}"
    assert is_plausible_job_title(title)
    assert title.lower() not in {
        "role overview",
        "job summary",
        "public",
        "jd",
    }


def test_golden_aws_not_role_overview():
    _text, _profile, form = _parse("aws_cloud_engineer.txt")
    assert "overview" not in form.title.lower()
    skills = form.mandatorySkills or form.skillsList or []
    joined = " ".join(skills).lower()
    assert any(
        tok in joined
        for tok in ("aws", "amazon web services", "ec2", "terraform", "cloudformation")
    )


def test_golden_middleware_experience_not_24x7():
    _text, profile, form = _parse("middleware_admin_24x7.txt")
    assert form.experienceFrom in ("4", "4.0", 4, 4.0) or float(form.experienceFrom or 0) == 4.0
    assert float(form.experienceTo or profile.requirements.max_experience_years or 0) == 7.0
    assert float(form.experienceFrom or 0) != 24.0
    skills = form.mandatorySkills or form.skillsList or []
    assert any("Weblogic" in s or "weblogic" in s.lower() for s in skills)


def test_golden_junior_keeps_jr_title_and_location():
    _text, _profile, form = _parse("junior_it_solutions.txt")
    assert "jr" in form.title.lower() or "junior" in form.title.lower() or "IT Solutions" in form.title
    assert "Mumbai" in (form.location or "")
    # Qualifications should not dominate skills as sentence blobs
    for sk in form.mandatorySkills or []:
        assert "bachelor" not in sk.lower()


def test_golden_sre_skips_public_banner():
    _text, _profile, form = _parse("sre_public_banner.txt")
    assert form.title.lower() != "public"
    assert "sre" in form.title.lower() or "reliability" in form.title.lower()


def test_extract_title_labeled_patterns():
    assert "Cloud Engineer" in extract_title_from_text(
        "Job Description: Cloud Engineer (AWS) – Mumbai\nRole Overview\nWe seek..."
    )
    assert "Site Reliability Engineer" in extract_title_from_text(
        "PUBLIC\nRole – Site Reliability Engineer\nWork Experience – 5 Years +"
    )


def test_table_kv_jd_fills_core_fields():
    text, profile, form = _parse("table_kv_jd.txt")
    assert "Storage Capacity" in form.title
    assert "Pune" in (form.location or "")
    assert float(form.experienceFrom or 0) == 3.0
    assert float(form.experienceTo or 0) == 6.0
    skills = " ".join(form.mandatorySkills or form.skillsList or []).lower()
    assert "netapp" in skills or "san" in skills
    assert form.description
    assert form.coverage
    missing = [c for c in form.coverage if c.get("status") == "missing_with_evidence"]
    core = {"title", "location", "experience", "skills", "description"}
    assert not any(c.get("field") in core for c in missing)


def test_multicolumn_unlabeled_title_and_skills():
    _text, _profile, form = _parse("multicolumn_unlabeled.txt")
    assert "UX" in form.title or "Lead" in form.title
    assert "Bangalore" in (form.location or "") or "bengaluru" in (form.location or "").lower()
    joined = " ".join(form.mandatorySkills or form.skillsList or []).lower()
    assert any(tok in joined for tok in ("figma", "wireframing", "prototyping"))


def test_paragraph_unlabeled_recovers_grounded_fields():
    text, _profile, form = _parse("paragraph_unlabeled.txt")
    assert form.title
    assert is_plausible_job_title(form.title)
    assert form.experienceFrom or form.experienceTo
    joined = " ".join(form.mandatorySkills or form.skillsList or []).lower()
    assert any(tok in joined for tok in ("kubernetes", "linux", "terraform", "prometheus"))
    # Keywords stay grounded in source
    for kw in (form.keywordsList or []):
        assert any(tok.lower() in text.lower() for tok in kw.split() if len(tok) >= 3) or kw.lower() in text.lower()


def test_extract_kv_fields_from_table_lines():
    from app.ai.parser.enrichment.jd_text_inference import extract_kv_fields_from_text

    kv = extract_kv_fields_from_text(
        "Job Title: Platform Engineer\nLocation | Hyderabad\nExperience: 2-4 years\n"
    )
    assert kv.get("title") == "Platform Engineer"
    assert "Hyderabad" in (kv.get("location") or "")
    assert "2-4" in (kv.get("experience") or "")
