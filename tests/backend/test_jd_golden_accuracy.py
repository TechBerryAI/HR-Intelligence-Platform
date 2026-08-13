"""Golden regression tests for JD parsing accuracy (eval failure set)."""

from __future__ import annotations

import re
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
    normalize_title_candidate,
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
    assert not is_plausible_job_title("Key Responsibilities:")
    assert not is_plausible_job_title("Certifications (Good to Have): ITIL, PMP / PRINCE2")
    assert not is_plausible_job_title("● Test and deploy the application")
    assert is_plausible_job_title("Jr. IT Solutions Associate")
    assert is_plausible_job_title("Design Engineer")
    assert is_plausible_job_title("Cloud Engineer (AWS)")
    assert is_plausible_job_title(".NET developer")


def test_normalize_title_candidate_strips_noise():
    assert normalize_title_candidate("Role Category: L2 Network Engineer") == "L2 Network Engineer"
    assert normalize_title_candidate("JD: Oracle Big Data Service (BDS) Specialist").startswith("Oracle")
    assert normalize_title_candidate("- MongoDB Database Administrator") == "MongoDB Database Administrator"
    assert normalize_title_candidate("AI Trainer – Job Description") == "AI Trainer"
    assert normalize_title_candidate("motivated Storage Engineer") == "Storage Engineer"
    assert normalize_title_candidate("results-driven Marketing Lead") == "Marketing Lead"


def test_experience_ignores_24x7_requires_years():
    assert extract_experience_years("Must be available for 24x7 support") == (None, None)
    assert extract_experience_years("on-call 24-7 windows") == (None, None)
    assert extract_experience_years("Experience: 4-7 years") == (4.0, 7.0)
    assert extract_experience_years("Fresher – 1 year") == (0.0, 1.0)


def test_javascript_does_not_emit_java():
    toks = normalize_skill_tokens(
        ["JavaScript, TypeScript, React, Node.js"],
        from_skill_section=True,
    )
    assert "JavaScript" in toks
    assert "Java" not in toks
    from app.ai.parser.enrichment.jd_text_inference import extract_tech_keywords_from_text

    assert "Java" not in extract_tech_keywords_from_text("JavaScript, TypeScript")


def test_aws_parenthetical_keeps_parent_and_children():
    toks = normalize_skill_tokens(
        ["Strong knowledge of AWS (EC2, EKS, VPC, IAM)"],
        from_skill_section=True,
    )
    joined = " ".join(toks).lower()
    assert "aws" in joined or "amazon web services" in joined, toks
    assert "ec2" in joined or "eks" in joined


def test_aws_and_amazon_web_services_are_equivalent():
    from app.ai.parser.engine.knowledge import skill_csv_equivalent, skill_values_equivalent

    assert skill_values_equivalent("AWS", "Amazon Web Services")
    assert skill_csv_equivalent(
        "PostgreSQL, MongoDB, Docker, Kubernetes, AWS",
        "PostgreSQL, MongoDB, Docker, Kubernetes, Amazon Web Services",
    )
    assert not skill_values_equivalent("AWS", "Azure")


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
        ("it_sales_executive.txt", "IT Sales Executive"),
        ("technical_delivery_manager.txt", "Technical Delivery Manager"),
        ("dot_net_developer.txt", ".NET"),
        ("storage_engineer_motivated.txt", "Storage Engineer"),
        ("marketing_lead_results_driven.txt", "Marketing Lead"),
        ("role_category_network.txt", "Network Engineer"),
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
    assert not title.lower().startswith(("key responsibilities", "certifications", "motivated", "results"))
    assert not title.strip().startswith(("●", "-", "JD:"))


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
    assert "IT Sales Executive" in extract_title_from_text(
        "Job Description – IT Sales Executive (Inside Sales)\nKey Responsibilities:\n• Sell"
    )
    assert "Technical Delivery Manager" in extract_title_from_text(
        "Job Description: Technical Delivery Manager (IT\nInfrastructure & Cloud)\n"
        "Certifications (Good to Have): ITIL, PMP / PRINCE2\nRole Summary:\nWe are looking"
    )
    title = extract_title_from_text(
        "Seeking a skilled .NET developer to join our team and contribute to the development\n"
        "Responsibilities\n● Test and deploy the application\n"
    )
    assert ".NET" in title or "developer" in title.lower()
    assert "test and deploy" not in title.lower()
    assert "Storage Engineer" == extract_title_from_text(
        "We are looking for a motivated Storage Engineer to join Managed Services operations team"
    )
    assert "Marketing Lead" == extract_title_from_text(
        "We are seeking a results-driven Marketing Lead to lead the global marketing strategy"
    )
    assert "L2 Network Engineer" == extract_title_from_text(
        "Role Category: L2 Network Engineer\n• Hands-on experience with SD-WAN"
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


def test_detailed_skills_section_retains_tech_and_phrases():
    _text, _profile, form = _parse("detailed_skills_softwrap.txt")
    skills = form.mandatorySkills or form.skillsList or []
    joined = " ".join(skills).lower()
    for tok in ("kubernetes", "aws", "terraform", "prometheus", "docker", "python"):
        assert tok in joined, f"missing {tok} in {skills!r}"
    # Education must not dominate skills
    assert not any("bachelor" in s.lower() for s in skills)
    # Dense section should keep more than a handful of items
    assert len(skills) >= 6


def test_softwrapped_responsibility_not_one_bullet_per_line():
    from app.ai.parser.enrichment.jd_text_inference import (
        _split_list_items,
        extract_responsibilities_from_text,
    )

    wrapped = (
        "Key Responsibilities\n"
        "• Design and operate multi-region Kubernetes clusters for customer workloads\n"
        "  across production and staging environments\n"
        "• Respond to incidents and drive root-cause analysis\n"
    )
    items = extract_responsibilities_from_text(wrapped)
    assert len(items) == 2, f"expected 2 merged bullets, got {items!r}"
    assert "across production" in items[0].lower()
    assert "incidents" in items[1].lower()

    soft = _split_list_items(
        "Design and operate multi-region Kubernetes clusters for customer workloads\n"
        "across production and staging environments"
    )
    assert len(soft) == 1
    assert "across production" in soft[0].lower()


def test_keywords_from_overall_jd_not_mandatory_copy():
    text, _profile, form = _parse("detailed_skills_softwrap.txt")
    skills = list(form.mandatorySkills or [])
    keywords = form.keywordsList or []
    assert skills, "expected mandatory skills from JD section"
    assert keywords, "expected overall-JD keywords"
    # Keywords must not be forced equal to mandatory skills
    assert keywords != skills, "keywords must not be a mandatory-skills copy"
    src = text.lower()
    for tok in keywords:
        tl = tok.lower()
        parts = [p for p in re.findall(r"[a-z0-9+#.]{2,}", tl) if len(p) >= 3]
        assert tl in src or any(p in src for p in parts), f"{tok!r} not grounded in JD"
    # Overall JD tech terms should appear in keywords
    joined = " ".join(keywords).lower()
    assert any(tok in joined for tok in ("kubernetes", "aws", "terraform", "prometheus", "docker", "python"))



def test_location_mumbai_without_colon():
    _text, _profile, form = _parse("location_mumbai_unlabeled.txt")
    assert "Mumbai" in (form.location or ""), f"got location={form.location!r}"
    skills = " ".join(form.mandatorySkills or form.skillsList or []).lower()
    assert "weblogic" in skills or "websphere" in skills or "ohs" in skills, skills
    missing = [
        c
        for c in (form.coverage or [])
        if c.get("status") == "missing_with_evidence" and c.get("field") == "location"
    ]
    assert not missing, f"location still missing_with_evidence: {form.coverage}"


def test_video_editor_rejects_job_token_and_stops_at_education():
    _text, profile, form = _parse("video_editor_skills.txt")
    assert "Video Editor" in (form.title or "")
    skills = [s.lower() for s in (form.mandatorySkills or form.skillsList or [])]
    assert "job" not in skills
    joined = " ".join(skills)
    assert any(
        tok in joined for tok in ("premiere", "adobe", "final", "cut", "editing", "figma")
    ) or any(
        tok in " ".join(profile.skills.mandatory or []).lower()
        for tok in ("premiere", "adobe", "final")
    ), f"skills={skills}"
    for r in form.responsibilitiesList or []:
        assert r.strip().lower() not in {"education", "key responsibilities", "key responsibilities:"}


def test_wireframing_strips_o_bullets_and_prefers_figma():
    _text, _profile, form = _parse("wireframing_bullet_o.txt")
    skills = form.mandatorySkills or form.skillsList or []
    assert skills, "expected skills"
    assert not any(re.match(r"^[oO]\s+", s) for s in skills), skills
    assert not any(s.strip().lower() == "job" for s in skills)
    joined = " ".join(skills).lower()
    assert "figma" in joined or "prototyping" in joined, skills
    # Soft-skill-only rows should not dominate when Figma/prototyping present
    soft_only = [
        s
        for s in skills
        if re.search(r"(?i)communication|collaboration|problem-solving|critical thinking", s)
        and "figma" not in s.lower()
    ]
    assert len(soft_only) < len(skills) or "figma" in joined
    assert not form.salary or re.search(r"\d|lpa|lakh|negotiable", form.salary, re.I), form.salary

