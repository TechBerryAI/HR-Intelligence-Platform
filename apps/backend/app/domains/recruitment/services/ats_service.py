"""
ATS Matching Service - consumes TOON resume + JD (dict from toon_loads_flex). Calls HR-ATS-API when configured;
JSON is used only at the external API boundary (request/response with HR-ATS-API).

REFACTORED MODEL (technical roles):
- Core Technical Skills: 60% (Mandatory 40%, Preferred 20%)
- Relevant Experience: 25%
- Education / Certifications: 10%
- Location / Availability: 5%
Total = 100%

Mandatory Skills Gate: If Mandatory Skills Match % < 40%, candidate is Not a Match (quiet talent pool).
Shortlisting: 80-100% Strong Match → auto-shortlist; 40-79% Potential Match → recruiter review (not auto-shortlisted);
              <40% or mandatory<40% → Not a Match (kept as Applied for talent pool; not auto-Rejected).
"""
import os
import json
import re
import requests

from app.core.timing import timing

ATS_API_URL = (os.getenv('ATS_API_URL') or '').rstrip('/')
ATS_API_KEY = os.getenv('ATS_API_KEY', '')
# Auto-shortlist threshold: overall match score must be ≥ this value (Strong Match).
ATS_THRESHOLD = int(os.getenv('ATS_THRESHOLD', '80'))

# ---------------------------------------------------------------------------
# Weights (technical roles) - total 100%
# ---------------------------------------------------------------------------
WEIGHT_SKILLS_TOTAL = 0.60       # Core Technical Skills
WEIGHT_MANDATORY_SKILLS = 0.40   # Mandatory/Core (part of 60%)
WEIGHT_PREFERRED_SKILLS = 0.20   # Advanced/Preferred (part of 60%)
WEIGHT_EXPERIENCE = 0.25
WEIGHT_EDUCATION = 0.10
WEIGHT_LOCATION = 0.05

# Legacy names for external compatibility (skills = mandatory + preferred combined weight)
WEIGHT_SKILLS = WEIGHT_SKILLS_TOTAL

# Thresholds
MANDATORY_SKILLS_MIN_PCT = 40.0   # Below this → Not a Match (talent pool)
VERDICT_STRONG_MIN = 80.0         # 80–100% → Strong Match (auto-shortlist)
VERDICT_POTENTIAL_MIN = 40.0      # 40–79% → Potential Match (recruiter review, NOT auto-shortlisted)
# Below 40% or mandatory < 40% → Not a Match (quiet talent pool)
AUTO_SHORTLIST_MIN = float(os.getenv('ATS_AUTO_SHORTLIST_MIN', str(VERDICT_STRONG_MIN)))

# Cap: no category above 50% when direct evidence is missing
MAX_SCORE_WITHOUT_EVIDENCE = 50.0


def _as_str(value) -> str:
    """Coerce TOON field values to stripped strings (ints/floats survive toon_loads)."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, (int, float)):
        return str(value)
    if isinstance(value, list):
        parts = [_as_str(item) for item in value]
        return " ".join(p for p in parts if p)
    if isinstance(value, dict):
        for key in ("name", "title", "role", "text", "value", "label", "email", "phone"):
            if key in value and value[key] is not None:
                return _as_str(value[key])
        return ""
    return str(value).strip()


def _split_skill_list(value) -> list:
    """Normalize a skills field (list or comma-separated string) to a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        return [s for s in (_as_str(p) for p in value.split(",")) if s]
    if isinstance(value, list):
        out = []
        for item in value:
            s = _as_str(item)
            if s:
                out.append(s)
        return out
    s = _as_str(value)
    return [s] if s else []


def _sanitize_skill_list(skills, *, max_items: int = 30) -> list:
    """Drop headers/filler from skill lists at match time (safety net for noisy TOON)."""
    # Older ATS payloads sometimes store a single skill as a bare string.
    if isinstance(skills, str):
        skills = _split_skill_list(skills)
    elif not isinstance(skills, list):
        skills = _split_skill_list(skills) if skills is not None else []
    try:
        from app.ai.parser.enrichment.jd_text_inference import normalize_skill_tokens

        return normalize_skill_tokens(skills, max_items=max_items)
    except Exception:
        return [s for s in skills if s and len(str(s).strip()) >= 2][:max_items]


def _normalize_skill(s) -> str:
    """Normalize skill for matching — share Intelligence Engine knowledge aliases."""
    text = _as_str(s)
    if not text:
        return ""
    try:
        from app.ai.parser.engine.knowledge import normalize_skill

        display, _cid = normalize_skill(text)
        text = display or text
    except Exception:
        pass
    return re.sub(r"\s+", " ", text.lower())


def _token_boundary_contains(haystack: str, needle: str) -> bool:
    """True when needle appears in haystack as a whole token/phrase (not bare substring)."""
    if not haystack or not needle:
        return False
    if haystack == needle:
        return True
    # Word-boundary style: needle as whole tokens inside haystack
    pattern = r"(?:^|[^a-z0-9+#])" + re.escape(needle) + r"(?:[^a-z0-9+#]|$)"
    return re.search(pattern, haystack) is not None


def _skill_match(required, possessed_list: list) -> bool:
    """Exact or token-boundary match after alias normalize. Avoids java⊆javascript."""
    r = _normalize_skill(required)
    if not r:
        return False
    # Very short tokens require exact equality only
    short_exact = len(r) < 3
    for p in possessed_list:
        pn = _normalize_skill(p)
        if not pn:
            continue
        if r == pn:
            return True
        if short_exact:
            continue
        if _token_boundary_contains(pn, r) or _token_boundary_contains(r, pn):
            return True
    return False


def _get_jd_skill_lists(parsed_jd: dict) -> tuple:
    """
    Return (mandatory_skills, preferred_skills), sanitized.
    JD may have: mandatory_skills, preferred_skills; or legacy single 'skills' (all treated as mandatory).
    """
    mandatory = _sanitize_skill_list(_split_skill_list(parsed_jd.get("mandatory_skills")), max_items=30)
    preferred = _sanitize_skill_list(_split_skill_list(parsed_jd.get("preferred_skills")), max_items=20)
    if not mandatory and not preferred:
        mandatory = _sanitize_skill_list(_split_skill_list(parsed_jd.get("skills")), max_items=30)
        preferred = []
    # Prefer not to double-count preferred tokens as mandatory
    pref_keys = {s.lower() for s in preferred}
    mandatory = [s for s in mandatory if s.lower() not in pref_keys]
    return mandatory, preferred


def _build_requirement_analysis(skills_result: dict, mandatory_skills: list, preferred_skills: list) -> dict:
    """Structured matched/missing checklist for UI and narrative."""
    mand_matched = set(skills_result.get("mandatory_matched") or [])
    pref_matched = set(skills_result.get("preferred_matched") or [])
    mandatory_pct = float(skills_result.get("mandatory_skills_match_pct") or 0)
    mandatory_defined = len(mandatory_skills) > 0
    gate_passed = (not mandatory_defined) or (mandatory_pct >= MANDATORY_SKILLS_MIN_PCT)
    return {
        "mandatory": [
            {"skill": s, "status": "matched" if s in mand_matched else "missing"}
            for s in mandatory_skills
        ],
        "preferred": [
            {"skill": s, "status": "matched" if s in pref_matched else "missing"}
            for s in preferred_skills
        ],
        "gate": {
            "passed": gate_passed,
            "mandatory_pct": mandatory_pct,
            "threshold": MANDATORY_SKILLS_MIN_PCT,
            "mandatory_defined": mandatory_defined,
        },
    }


def _build_decision_summary(
    verdict: str,
    overall: float,
    skills_result: dict,
    requirement_analysis: dict,
) -> str:
    """Short plain-English why for the verdict banner."""
    gate = requirement_analysis.get("gate") or {}
    missing_mand = skills_result.get("mandatory_missing") or []
    matched_mand = skills_result.get("mandatory_matched") or []
    if not gate.get("passed", True):
        missing_preview = ", ".join(missing_mand[:5])
        if missing_preview:
            return (
                f"Low match: only {gate.get('mandatory_pct')}% of mandatory skills matched "
                f"(need at least {gate.get('threshold')}%). Still missing: {missing_preview}."
            )
        return (
            f"Low match: mandatory skills match is {gate.get('mandatory_pct')}% "
            f"(below the {gate.get('threshold')}% minimum)."
        )
    if verdict == "Strong Match":
        matched_preview = ", ".join(matched_mand[:5]) or "required skills"
        return (
            f"Selected for auto-shortlist: overall {overall}% with mandatory skills at "
            f"{gate.get('mandatory_pct')}%. Strong evidence on: {matched_preview}."
        )
    if "Potential" in verdict:
        gaps = ", ".join(missing_mand[:3])
        gap_note = f" Review remaining gaps: {gaps}." if gaps else ""
        return (
            f"Hold for recruiter review: overall {overall}% passes the mandatory skills gate "
            f"({gate.get('mandatory_pct')}%) but is below the {VERDICT_STRONG_MIN}% auto-shortlist bar.{gap_note}"
        )
    gaps = ", ".join(
        (skills_result.get("mandatory_missing") or [])[:5]
        or (skills_result.get("preferred_missing") or [])[:3]
    )
    gap_note = f" Main gaps: {gaps}." if gaps else ""
    return (
        f"Low match: overall score {overall}% is below the {VERDICT_POTENTIAL_MIN}% review floor.{gap_note}"
    )


def _build_category_reasons(
    *,
    skills_result: dict,
    mandatory_skills: list,
    preferred_skills: list,
    skills_raw: float,
    exp_score: float,
    exp_summary: str,
    education_score: float,
    education_assessment: str,
    location_score: float,
    parsed_resume: dict,
    parsed_jd: dict,
) -> list:
    """Plain-English needed vs present reasons for each score category."""
    matched_mand = list(skills_result.get("mandatory_matched") or [])
    missing_mand = list(skills_result.get("mandatory_missing") or [])
    matched_pref = list(skills_result.get("preferred_matched") or [])
    missing_pref = list(skills_result.get("preferred_missing") or [])
    mand_pct = skills_result.get("mandatory_skills_match_pct")

    if not mandatory_skills and not preferred_skills:
        skills_result_label = "No clear skill checklist"
        skills_reason = (
            "The job did not yield a clean mandatory skill checklist, so skills could not be "
            "compared item-by-item. Treat the skills score cautiously."
        )
        skills_verdict = "unclear"
    elif missing_mand and not matched_mand:
        skills_result_label = "Not a skills match"
        skills_reason = (
            "Role needed: "
            + ", ".join(mandatory_skills[:8])
            + ". Candidate had none of these mandatory skills on the resume."
        )
        skills_verdict = "not_match"
    elif missing_mand:
        skills_result_label = "Partial skills match"
        skills_reason = (
            f"Role needed {len(mandatory_skills)} mandatory skill(s). "
            f"Present: {', '.join(matched_mand[:8]) or 'none'}. "
            f"Missing: {', '.join(missing_mand[:8])}. "
            f"That is a {mand_pct}% mandatory match"
            + (
                f" (below the {MANDATORY_SKILLS_MIN_PCT}% minimum)."
                if (mand_pct or 0) < MANDATORY_SKILLS_MIN_PCT
                else "."
            )
        )
        skills_verdict = "partial"
    else:
        skills_result_label = "Skills match"
        skills_reason = (
            "Role needed: "
            + (", ".join(mandatory_skills[:8]) or "no mandatory list")
            + ". Candidate has all mandatory skills"
            + (f" and preferred: {', '.join(matched_pref[:5])}" if matched_pref else "")
            + "."
        )
        skills_verdict = "match"

    if preferred_skills and missing_pref and skills_verdict != "unclear":
        skills_reason += f" Preferred still missing: {', '.join(missing_pref[:5])}."

    # Experience
    jd_title = _as_str(parsed_jd.get("title")) or "this role"
    if exp_score >= 70:
        exp_label = "Experience match"
        exp_verdict = "match"
        exp_reason = (
            f"Role needed experience relevant to “{jd_title}”. "
            f"Present: {exp_summary or 'aligned experience on the resume'}. "
            "So experience is counted as a match."
        )
    elif exp_score >= 40:
        exp_label = "Partial experience match"
        exp_verdict = "partial"
        exp_reason = (
            f"Role needed experience for “{jd_title}”. "
            f"Present: {exp_summary or 'some experience, but not a clear role/domain match'}. "
            "So experience is only a partial match."
        )
    else:
        exp_label = "Experience not a match"
        exp_verdict = "not_match"
        exp_reason = (
            f"Role needed experience for “{jd_title}”. "
            f"Present: {exp_summary or 'little or no matching experience'}. "
            "So experience does not support this role."
        )

    # Education
    jd_qualifications = list(parsed_jd.get("qualifications") or [])
    if isinstance(jd_qualifications, str):
        jd_qualifications = [jd_qualifications]
    jd_degree_bits = [
        _as_str(q) for q in jd_qualifications
        if _as_str(q) and re.search(
            r"\b(bachelor|b\.?s\.?|b\.?e\.?|m\.?s\.?|m\.?a\.?|mba|phd|degree|diploma)\b",
            _as_str(q),
            re.I,
        )
    ]
    cand_edu_bits = []
    for e in list(parsed_resume.get("education") or []):
        if not isinstance(e, dict):
            continue
        bit = _as_str(e.get("degree") or e.get("field") or e.get("institution"))
        if bit:
            cand_edu_bits.append(bit)

    if education_score >= 80:
        edu_label = "Education match"
        edu_verdict = "match"
        edu_reason = (
            f"Role needed: {education_assessment or 'stated education requirements'}. "
            "Candidate meets this, so education is a match."
        )
        if "no degree requirement" in (education_assessment or "").lower():
            edu_reason = (
                "Role needed: no degree requirement stated. "
                "Nothing missing here, so education is treated as a full match."
            )
            edu_needed = ["No degree / qualification required"]
            edu_present = ["Not required — passes by default"]
            edu_missing = []
        else:
            edu_needed = jd_degree_bits[:3] or ["Degree / qualification as stated in the job"]
            edu_present = cand_edu_bits[:3] or ["Degree or equivalent evidenced on resume"]
            edu_missing = []
    elif education_score >= 40:
        edu_label = "Partial education match"
        edu_verdict = "partial"
        edu_reason = (
            f"Role needed a degree/qualification. "
            f"Present: {education_assessment or 'education listed but unclear fit'}. "
            "So education is only a partial match."
        )
        edu_needed = jd_degree_bits[:3] or ["Degree / qualification as stated in the job"]
        edu_present = cand_edu_bits[:3] or ["Education listed, fit unclear"]
        edu_missing = []
    else:
        edu_label = "Education not a match"
        edu_verdict = "not_match"
        edu_reason = (
            f"Role needed a degree/qualification. "
            f"Present: {education_assessment or 'no matching education on the resume'}. "
            "So education is not a match."
        )
        edu_needed = jd_degree_bits[:3] or ["Degree / qualification as stated in the job"]
        edu_present = cand_edu_bits[:3]
        edu_missing = [] if edu_present else ["No matching education on resume"]

    # Location
    jd_loc = _as_str(parsed_jd.get("location"))
    cand_loc = ""
    person = parsed_resume.get("person") or {}
    if isinstance(person, dict):
        cand_loc = _as_str(person.get("location"))
    if not jd_loc:
        loc_label = "Location match"
        loc_verdict = "match"
        loc_reason = (
            "Role needed: no specific location requirement. "
            "Nothing to fail here, so location is a match."
        )
    elif location_score >= 70:
        loc_label = "Location match"
        loc_verdict = "match"
        loc_reason = (
            f"Role needed: {jd_loc}. "
            f"Present: {cand_loc or 'compatible location on the resume'}. "
            "So location is a match."
        )
    elif location_score >= 40:
        loc_label = "Partial location match"
        loc_verdict = "partial"
        loc_reason = (
            f"Role needed: {jd_loc}. "
            f"Present: {cand_loc or 'location only partly clear'}. "
            "So location is a partial match."
        )
    else:
        loc_label = "Location not a match"
        loc_verdict = "not_match"
        loc_reason = (
            f"Role needed: {jd_loc}. "
            f"Present: {cand_loc or 'no compatible location found'}. "
            "So location is not a match."
        )

    return [
        {
            "key": "skills",
            "label": "Core skills",
            "score": round(skills_raw, 1),
            "result": skills_verdict,
            "result_label": skills_result_label,
            "needed": mandatory_skills[:12],
            "present": matched_mand[:12],
            "missing": missing_mand[:12],
            "preferred_present": matched_pref[:8],
            "preferred_missing": missing_pref[:8],
            "reason": skills_reason,
        },
        {
            "key": "experience",
            "label": "Experience",
            "score": round(exp_score, 1),
            "result": exp_verdict,
            "result_label": exp_label,
            "needed": [jd_title] if jd_title else [],
            "present": [exp_summary] if exp_summary and exp_summary != "N/A" else [],
            "missing": [],
            "reason": exp_reason,
        },
        {
            "key": "education",
            "label": "Education",
            "score": round(education_score, 1),
            "result": edu_verdict,
            "result_label": edu_label,
            "needed": edu_needed,
            "present": edu_present,
            "missing": edu_missing,
            "reason": edu_reason,
        },
        {
            "key": "location",
            "label": "Location",
            "score": round(location_score, 1),
            "result": loc_verdict,
            "result_label": loc_label,
            "needed": [jd_loc] if jd_loc else [],
            "present": [cand_loc] if cand_loc else [],
            "missing": [],
            "reason": loc_reason,
        },
    ]


def _build_score_math(
    skills_raw: float,
    exp_score: float,
    education_score: float,
    location_score: float,
    overall: float,
) -> dict:
    """Keep weighted math for APIs; UI prefers category_reasons instead."""
    rows = [
        {
            "key": "skills",
            "label": "Core technical skills",
            "raw_pct": round(skills_raw, 1),
            "weight_pct": int(WEIGHT_SKILLS_TOTAL * 100),
            "points": round(WEIGHT_SKILLS_TOTAL * skills_raw, 2),
            "how": f"{round(skills_raw, 1)}% category score × {int(WEIGHT_SKILLS_TOTAL * 100)}% weight",
        },
        {
            "key": "experience",
            "label": "Relevant experience",
            "raw_pct": round(exp_score, 1),
            "weight_pct": int(WEIGHT_EXPERIENCE * 100),
            "points": round(WEIGHT_EXPERIENCE * exp_score, 2),
            "how": f"{round(exp_score, 1)}% category score × {int(WEIGHT_EXPERIENCE * 100)}% weight",
        },
        {
            "key": "education",
            "label": "Education / certifications",
            "raw_pct": round(education_score, 1),
            "weight_pct": int(WEIGHT_EDUCATION * 100),
            "points": round(WEIGHT_EDUCATION * education_score, 2),
            "how": f"{round(education_score, 1)}% category score × {int(WEIGHT_EDUCATION * 100)}% weight",
        },
        {
            "key": "location",
            "label": "Location / availability",
            "raw_pct": round(location_score, 1),
            "weight_pct": int(WEIGHT_LOCATION * 100),
            "points": round(WEIGHT_LOCATION * location_score, 2),
            "how": f"{round(location_score, 1)}% category score × {int(WEIGHT_LOCATION * 100)}% weight",
        },
    ]
    parts = " + ".join(f"{r['points']}" for r in rows)
    return {
        "rows": rows,
        "total": overall,
        "equation": f"{parts} = {overall}",
        "explainer": (
            f"Overall match {overall}% combines how well skills, experience, education, "
            f"and location each fit the role (skills matter most)."
        ),
    }


def _build_decision_explanation(
    *,
    verdict: str,
    overall: float,
    skills_result: dict,
    requirement_analysis: dict,
    score_math: dict,
    category_reasons: list,
    exp_score: float,
    exp_summary: str,
    education_score: float,
    education_assessment: str,
    location_score: float,
    verdict_override: bool,
) -> dict:
    """Structured, recruiter-facing explanation of reject/select and score."""
    gate = requirement_analysis.get("gate") or {}
    matched_mand = skills_result.get("mandatory_matched") or []
    missing_mand = skills_result.get("mandatory_missing") or []
    matched_pref = skills_result.get("preferred_matched") or []
    missing_pref = skills_result.get("preferred_missing") or []

    if verdict == "Strong Match":
        outcome = "shortlist"
        outcome_label = "Auto-shortlist"
    elif "Potential" in verdict:
        outcome = "review"
        outcome_label = "Recruiter review"
    else:
        outcome = "reject"
        outcome_label = "Not selected"

    primary_reason = _build_decision_summary(
        verdict, overall, skills_result, requirement_analysis
    )

    rules = [
        f"A candidate must have most mandatory skills (at least {int(MANDATORY_SKILLS_MIN_PCT)}%) or they are a low match.",
        f"Strong overall fit ({int(VERDICT_STRONG_MIN)}%+) with the skills gate passed → auto-shortlist.",
        f"Overall fit ({int(VERDICT_POTENTIAL_MIN)}–{int(VERDICT_STRONG_MIN) - 1}%) with the skills gate passed → recruiter review.",
        f"Below {int(VERDICT_POTENTIAL_MIN)}% overall, or skills gate failed → low match (talent pool).",
    ]

    what_happened = []
    if verdict_override or not gate.get("passed", True):
        if missing_mand and matched_mand:
            what_happened.append(
                f"Not selected because mandatory skills are incomplete: had "
                f"{', '.join(matched_mand[:6])}, but still needed "
                f"{', '.join(missing_mand[:6])}."
            )
        elif missing_mand:
            what_happened.append(
                "Not selected because required skills were missing: "
                + ", ".join(missing_mand[:8])
                + "."
            )
        else:
            what_happened.append(
                f"Not selected because only {gate.get('mandatory_pct')}% of mandatory skills "
                f"matched (need at least {gate.get('threshold')}%)."
            )
        if exp_score >= 70:
            what_happened.append(
                "Experience looks relevant for the role title, but that cannot override missing mandatory skills."
            )
    elif outcome == "shortlist":
        what_happened.append(
            "Selected because mandatory skills are covered and overall fit is strong enough to auto-shortlist."
        )
        if matched_mand:
            what_happened.append("Present mandatory skills: " + ", ".join(matched_mand[:8]) + ".")
    elif outcome == "review":
        what_happened.append(
            "Worth a recruiter look: mandatory skills mostly pass, but overall fit is not strong enough to auto-shortlist."
        )
        if missing_mand or missing_pref:
            gaps = (missing_mand + missing_pref)[:6]
            what_happened.append("Still missing: " + ", ".join(gaps) + ".")
    else:
        what_happened.append(
            f"Not selected because overall fit ({overall}%) is below the minimum match level."
        )

    reconciliation = ""
    if exp_score >= 70 and (skills_result.get("mandatory_skills_match_pct") or 0) < MANDATORY_SKILLS_MIN_PCT:
        reconciliation = (
            "Why experience can look good while skills fail: the resume title/domain aligns "
            f"with the role ({exp_summary or 'direct role match'}), but mandatory skills are "
            f"incomplete ({skills_result.get('mandatory_skills_match_pct')}% matched"
            + (f"; missing {', '.join(missing_mand[:5])}" if missing_mand else "")
            + "). Missing skills decide the rejection."
        )
    elif exp_score >= 70 and overall < VERDICT_STRONG_MIN:
        reconciliation = (
            "Experience is strong, but overall fit is held back mainly by skills coverage "
            "(skills are the largest part of the match decision)."
        )

    next_step = {
        "shortlist": "Move this candidate to the next hiring stage.",
        "review": "Review the missing skills below, then decide to shortlist or reject.",
        "reject": "Do not shortlist on ATS rules alone. Override only with clear hiring context outside this comparison.",
    }.get(outcome, "")

    return {
        "outcome": outcome,
        "outcome_label": outcome_label,
        "verdict": verdict,
        "primary_reason": primary_reason,
        "what_happened": what_happened,
        "rules_applied": rules,
        "score_math": score_math,
        "category_reasons": category_reasons,
        "skills_evidence": {
            "mandatory_matched": matched_mand,
            "mandatory_missing": missing_mand,
            "preferred_matched": matched_pref,
            "preferred_missing": missing_pref,
            "mandatory_match_pct": skills_result.get("mandatory_skills_match_pct"),
            "gate_threshold": MANDATORY_SKILLS_MIN_PCT,
            "gate_passed": gate.get("passed", True),
            "comparisons": [
                {
                    "skill": s,
                    "needed": True,
                    "present": True,
                    "status": "present",
                }
                for s in matched_mand
            ]
            + [
                {
                    "skill": s,
                    "needed": True,
                    "present": False,
                    "status": "missing",
                }
                for s in missing_mand
            ],
        },
        "other_factors": {
            "experience": {"score": exp_score, "summary": exp_summary or ""},
            "education": {"score": education_score, "summary": education_assessment or ""},
            "location": {"score": location_score, "summary": ""},
        },
        "reconciliation": reconciliation,
        "next_step": next_step,
    }


def _build_deterministic_narrative(
    verdict: str,
    overall: float,
    skills_result: dict,
    requirement_analysis: dict,
    exp_summary: str,
    education_assessment: str,
    decision_explanation: dict | None = None,
) -> str:
    """Fallback multi-sentence explanation grounded only in scored evidence."""
    if decision_explanation:
        parts = [decision_explanation.get("primary_reason") or ""]
        parts.extend(decision_explanation.get("what_happened") or [])
        recon = decision_explanation.get("reconciliation") or ""
        if recon:
            parts.append(recon)
        for cat in decision_explanation.get("category_reasons") or []:
            if cat.get("reason"):
                parts.append(f"{cat.get('label')}: {cat['reason']}")
        nxt = decision_explanation.get("next_step") or ""
        if nxt:
            parts.append(nxt)
        return " ".join(p for p in parts if p)

    parts = [_build_decision_summary(verdict, overall, skills_result, requirement_analysis)]
    matched = skills_result.get("mandatory_matched") or []
    missing = skills_result.get("mandatory_missing") or []
    pref_m = skills_result.get("preferred_matched") or []
    if matched:
        parts.append("Matched mandatory skills: " + ", ".join(matched[:10]) + ".")
    if missing:
        parts.append("Missing mandatory skills: " + ", ".join(missing[:10]) + ".")
    if pref_m:
        parts.append("Also has preferred skills: " + ", ".join(pref_m[:5]) + ".")
    if exp_summary and exp_summary != "N/A":
        parts.append(exp_summary if exp_summary.endswith(".") else exp_summary + ".")
    if education_assessment:
        parts.append(education_assessment if education_assessment.endswith(".") else education_assessment + ".")
    return " ".join(parts)


@timing
def _optional_llm_narrative(evidence: dict) -> str:
    """Best-effort 2–4 sentence narrative from scored evidence; empty on failure."""
    if os.getenv("ATS_NARRATIVE_LLM", "1").strip().lower() in ("0", "false", "no", "off"):
        return ""
    try:
        from app.ai.document_intelligence.semantic import semantic_ai_enabled

        if not semantic_ai_enabled():
            return ""
    except Exception:
        pass
    try:
        import concurrent.futures

        timeout_sec = float(os.getenv("ATS_NARRATIVE_TIMEOUT_SEC", "8"))

        def _invoke() -> str:
            try:
                from app.ai.adapter.runtime_adapter import parse_via_runtime

                prompt = (
                    "You are a recruiting analyst. Using ONLY the JSON evidence below, write 2-4 short "
                    "plain-English sentences explaining why this candidate received the given verdict. "
                    "Do not invent skills, employers, or scores. Do not use markdown. "
                    "Return JSON: {\"narrative\": \"...\"}\n\n"
                    f"Evidence:\n{json.dumps(evidence, ensure_ascii=False)[:4000]}"
                )
                result = parse_via_runtime(prompt, "jd")
                if isinstance(result, dict):
                    text = (result.get("narrative") or result.get("explanation") or "").strip()
                    return text
            except Exception:
                return ""
            return ""

        from app.core.request_context import get_timing_context, run_in_timing_context

        timing_ctx = get_timing_context()

        def _invoke_timed() -> str:
            if timing_ctx is not None:
                return run_in_timing_context(timing_ctx, _invoke)
            return _invoke()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_invoke_timed)
            return (fut.result(timeout=timeout_sec) or "").strip()
    except Exception:
        return ""


def _compute_skills_scores(cand_skills_list: list, mandatory_skills: list, preferred_skills: list) -> dict:
    """
    Returns dict with:
      mandatory_matched, mandatory_missing, mandatory_raw_pct,
      preferred_matched, preferred_missing, preferred_raw_pct,
      skills_category_raw (0-100, weighted blend of mandatory 40% + preferred 20% of 60%),
      mandatory_skills_match_pct (for gating).
    """
    def match_lists(required_list, possessed):
        matched, missing = [], []
        for s in required_list:
            if _skill_match(s, possessed):
                matched.append(s)
            else:
                missing.append(s)
        return matched, missing

    mand_matched, mand_missing = match_lists(mandatory_skills, cand_skills_list)
    pref_matched, pref_missing = match_lists(preferred_skills, cand_skills_list)

    # Mandatory: raw % (for gating and for weighted score)
    if mandatory_skills:
        mandatory_raw_pct = 100.0 * len(mand_matched) / len(mandatory_skills)
    else:
        mandatory_raw_pct = 100.0

    # Preferred: raw %
    if preferred_skills:
        preferred_raw_pct = 100.0 * len(pref_matched) / len(preferred_skills)
    else:
        preferred_raw_pct = 100.0  # no preferred skills → full marks for that slice

    # Skills category score (0-100): 40% weight on mandatory, 20% on preferred (of the 60% total)
    # So as raw 0-100: (40/60)*mandatory_raw + (20/60)*preferred_raw
    if mandatory_skills or preferred_skills:
        w_m = len(mandatory_skills) and (WEIGHT_MANDATORY_SKILLS / WEIGHT_SKILLS_TOTAL) or 0
        w_p = len(preferred_skills) and (WEIGHT_PREFERRED_SKILLS / WEIGHT_SKILLS_TOTAL) or 0
        if w_m + w_p > 0:
            skills_category_raw = (w_m * mandatory_raw_pct + w_p * preferred_raw_pct) / (w_m + w_p)
        else:
            skills_category_raw = 100.0
    else:
        skills_category_raw = 100.0

    return {
        "mandatory_matched": mand_matched,
        "mandatory_missing": mand_missing,
        "mandatory_raw_pct": round(mandatory_raw_pct, 1),
        "preferred_matched": pref_matched,
        "preferred_missing": pref_missing,
        "preferred_raw_pct": round(preferred_raw_pct, 1),
        "skills_category_raw": round(min(100.0, max(0.0, skills_category_raw)), 1),
        "mandatory_skills_match_pct": round(mandatory_raw_pct, 1),
    }


def _compute_experience_score(parsed_resume: dict, parsed_jd: dict) -> tuple:
    """
    Domain-relevance focused. No inflation for generic seniority.
    Returns (raw_score_0_100, summary_text, gaps_text).
    Rule: no category above 50% if direct evidence is missing → no experience list or no domain match caps at 50%.
    """
    raw_experiences = list(parsed_resume.get("experience") or [])
    cand_experiences = [exp for exp in raw_experiences if isinstance(exp, dict)]
    jd_title = _as_str(parsed_jd.get("title")).lower()
    jd_min_years = parsed_jd.get("min_experience_years")
    jd_max_years = parsed_jd.get("max_experience_years")
    if isinstance(jd_min_years, str):
        try:
            jd_min_years = float(jd_min_years)
        except ValueError:
            jd_min_years = None
    if isinstance(jd_max_years, str):
        try:
            jd_max_years = float(jd_max_years)
        except ValueError:
            jd_max_years = None
    cand_years = parsed_resume.get("total_experience_years")
    if isinstance(cand_years, str):
        try:
            cand_years = float(cand_years)
        except ValueError:
            cand_years = None

    relevance = 0.0
    summary_parts = []
    gaps_parts = []

    if not cand_experiences and cand_years is None:
        return 0.0, "No experience data provided.", "Missing experience information."

    if cand_experiences and jd_title:
        for exp in cand_experiences:
            title = _as_str(exp.get("title") or exp.get("role")).lower()
            if title and (jd_title in title or title in jd_title):
                relevance = 100.0
                summary_parts.append(
                    f"Direct role match: {_as_str(exp.get('title') or exp.get('role'))}"
                )
                break
        if relevance == 0:
            # Some experience but no domain match → cap at 50% (no direct evidence for full score)
            relevance = min(50.0, 20.0 + 10.0 * min(len(cand_experiences), 3))
            summary_parts.append("Experience present but no direct role/domain match to job title.")
            gaps_parts.append("No experience in role/domain matching job title.")
    elif cand_years is not None and (jd_min_years is not None or jd_max_years is not None):
        # Years-only comparison: treat as weak evidence, cap at 50% if no role match
        if jd_min_years is not None and jd_max_years is not None:
            if jd_min_years <= cand_years <= jd_max_years:
                relevance = 50.0  # years in range but no role evidence
            elif cand_years >= jd_min_years:
                relevance = 40.0
            else:
                relevance = max(0, 50 - 10 * (jd_min_years - cand_years))
        elif jd_min_years is not None:
            relevance = 50.0 if cand_years >= jd_min_years else max(0, 50 - 10 * (jd_min_years - cand_years))
        else:
            relevance = 40.0
        summary_parts.append(f"Experience years: {cand_years}; JD range: {jd_min_years}-{jd_max_years}. No role-level evidence.")
        gaps_parts.append("Domain/role relevance could not be verified from experience.")
    else:
        relevance = 0.0
        summary_parts.append("Insufficient experience data for role.")
        gaps_parts.append("Missing or unclear experience relative to role.")

    score = min(100.0, max(0.0, relevance))
    return round(score, 1), " ".join(summary_parts) or "N/A", "; ".join(gaps_parts) or "N/A"


def _compute_education_score(parsed_resume: dict, parsed_jd: dict) -> tuple:
    """
    Returns (raw_score_0_100, assessment_text).
    No category above 50% without direct evidence: if JD requires degree and candidate has no education list, score 0.
    """
    jd_qualifications = list(parsed_jd.get("qualifications") or [])
    if isinstance(jd_qualifications, str):
        jd_qualifications = [jd_qualifications]
    jd_requires_degree = any(
        re.search(
            r"\b(bachelor|b\.?s\.?|b\.?e\.?|m\.?s\.?|m\.?a\.?|mba|phd|degree|diploma)\b",
            _as_str(q),
            re.I,
        )
        for q in jd_qualifications
    ) if jd_qualifications else False

    cand_education = [
        e for e in list(parsed_resume.get("education") or []) if isinstance(e, dict)
    ]
    if not jd_requires_degree:
        return 100.0, "No degree requirement stated for role."
    if not cand_education:
        return 0.0, "Degree required; no education data provided."
    for e in cand_education:
        deg = _as_str(e.get("degree") or e.get("field")).lower()
        if re.search(r"\b(bachelor|b\.?s\.?|b\.?e\.?|m\.?s\.?|m\.?a\.?|mba|phd|degree|diploma)\b", deg):
            return 100.0, "Education meets or exceeds stated qualifications."
    return 50.0, "Education listed but does not clearly meet degree requirement."


def _compute_location_score(parsed_resume: dict, parsed_jd: dict) -> float:
    """No category above 50% without direct evidence: if candidate location missing, cap at 50%."""
    jd_location = _as_str(parsed_jd.get("location")).lower()
    cand_location = ""
    person = parsed_resume.get("person") or {}
    if isinstance(person, dict):
        cand_location = _as_str(
            person.get("location") or person.get("current_location")
        ).lower()
    if not jd_location:
        return 100.0
    if not cand_location:
        return MAX_SCORE_WITHOUT_EVIDENCE  # 50%
    jd_parts = set(re.findall(r"[a-z]+", jd_location))
    cand_parts = set(re.findall(r"[a-z]+", cand_location))
    overlap = len(jd_parts & cand_parts) / len(jd_parts) if jd_parts else 1.0
    return round(50.0 + 50.0 * overlap, 1)


def _verdict_from_score(overall: float, mandatory_skills_match_pct: float, mandatory_skills_defined: bool) -> str:
    """
    Verdict: Strong Match / Potential Match (Recruiter Review) / Not a Match.
    Mandatory skills < MANDATORY_SKILLS_MIN_PCT → Not a Match regardless of overall.
    Not a Match stays Applied (talent pool); it does not auto-Reject the application.
    """
    if mandatory_skills_defined and mandatory_skills_match_pct < MANDATORY_SKILLS_MIN_PCT:
        return "Not a Match"
    if overall >= VERDICT_STRONG_MIN:
        return "Strong Match"
    if overall >= VERDICT_POTENTIAL_MIN:
        return "Potential Match (Recruiter Review)"
    return "Not a Match"


def _build_recruiter_report(
    candidate_name: str,
    candidate_email: str,
    role_evaluated: str,
    overall_score: float,
    verdict: str,
    score_breakdown: list,
    skills_analysis: dict,
    experience_summary: str,
    experience_gaps: str,
    education_assessment: str,
    decision_bullets: list,
) -> dict:
    """Recruiter-ready evaluation report in the required format."""
    return {
        "candidate_header": {
            "name": candidate_name,
            "email": candidate_email,
            "role_evaluated_for": role_evaluated,
            "overall_match_score_pct": round(overall_score, 1),
            "verdict": verdict,
        },
        "score_breakdown_table": score_breakdown,
        "skills_analysis": skills_analysis,
        "experience_assessment": {
            "relevant_experience_summary": experience_summary,
            "gaps_vs_role_expectations": experience_gaps,
        },
        "education_certification_assessment": education_assessment,
        "final_decision_logic": decision_bullets,
    }


@timing
def _internal_match(
    parsed_resume: dict,
    parsed_jd: dict,
    *,
    narrative_llm: bool | None = None,
) -> dict:
    """
    Evaluate candidate (TOON resume) vs job (TOON JD). Deterministic, no inflation.
    Returns JSON with: overall_match_score, decision, verdict, evaluation_report, score_breakdown,
    key_strengths, key_gaps, final_reasoning; and mandatory_skills_match_pct for gating.

    narrative_llm:
      None → honor ATS_NARRATIVE_LLM env (default on)
      False → skip blocking LLM narrative (apply submit path)
      True → force LLM narrative attempt
    """
    cand_skills = _split_skill_list(parsed_resume.get("skills"))

    mandatory_skills, preferred_skills = _get_jd_skill_lists(parsed_jd)
    skills_result = _compute_skills_scores(cand_skills, mandatory_skills, preferred_skills)

    mandatory_match_pct = skills_result["mandatory_skills_match_pct"]
    mandatory_defined = len(mandatory_skills) > 0

    # Auto-disqualify: mandatory skills < 60%
    if mandatory_defined and mandatory_match_pct < MANDATORY_SKILLS_MIN_PCT:
        overall = 0.0  # Will be overridden below with computed score for transparency, but verdict forced
        verdict_override = True
    else:
        verdict_override = False

    skills_raw = skills_result["skills_category_raw"]

    exp_score, exp_summary, exp_gaps = _compute_experience_score(parsed_resume, parsed_jd)
    education_score, education_assessment = _compute_education_score(parsed_resume, parsed_jd)
    location_score = _compute_location_score(parsed_resume, parsed_jd)

    # Weighted score = (Category Score × Category Weight); each category 0-100 raw
    weighted_skills = (WEIGHT_SKILLS_TOTAL * skills_raw)
    weighted_exp = (WEIGHT_EXPERIENCE * exp_score)
    weighted_edu = (WEIGHT_EDUCATION * education_score)
    weighted_loc = (WEIGHT_LOCATION * location_score)

    overall = weighted_skills + weighted_exp + weighted_edu + weighted_loc
    overall = round(min(100.0, max(0.0, overall)), 1)

    verdict = _verdict_from_score(overall, mandatory_match_pct, mandatory_defined)
    if verdict_override:
        verdict = "Not a Match"

    # Score breakdown table: Category, Weight, Raw Score (%), Weighted Score
    score_breakdown = [
        {"category": "Core Technical Skills", "weight_pct": int(WEIGHT_SKILLS_TOTAL * 100), "raw_score_pct": skills_raw, "weighted_score": round(weighted_skills, 2)},
        {"category": "Relevant Experience", "weight_pct": int(WEIGHT_EXPERIENCE * 100), "raw_score_pct": exp_score, "weighted_score": round(weighted_exp, 2)},
        {"category": "Education / Certifications", "weight_pct": int(WEIGHT_EDUCATION * 100), "raw_score_pct": education_score, "weighted_score": round(weighted_edu, 2)},
        {"category": "Location / Availability", "weight_pct": int(WEIGHT_LOCATION * 100), "raw_score_pct": location_score, "weighted_score": round(weighted_loc, 2)},
    ]
    score_math = _build_score_math(skills_raw, exp_score, education_score, location_score, overall)

    # Candidate identity for report
    person = parsed_resume.get("person") or {}
    if isinstance(person, dict):
        candidate_name = _as_str(person.get("name") or person.get("full_name")) or "Candidate"
        candidate_email = _as_str(person.get("email"))
    else:
        candidate_name = "Candidate"
        candidate_email = ""
    role_evaluated = _as_str(parsed_jd.get("title")) or "Role"

    skills_analysis = {
        "skills_matched": skills_result["mandatory_matched"] + skills_result["preferred_matched"],
        "missing_mandatory_skills": skills_result["mandatory_missing"],
        "missing_preferred_skills": skills_result["preferred_missing"],
        "mandatory_skills_match_pct": mandatory_match_pct,
        "mandatory_matched_skills": skills_result["mandatory_matched"],
        "preferred_matched_skills": skills_result["preferred_matched"],
    }

    requirement_analysis = _build_requirement_analysis(
        skills_result, mandatory_skills, preferred_skills
    )
    decision_summary = _build_decision_summary(
        verdict, overall, skills_result, requirement_analysis
    )
    category_reasons = _build_category_reasons(
        skills_result=skills_result,
        mandatory_skills=mandatory_skills,
        preferred_skills=preferred_skills,
        skills_raw=skills_raw,
        exp_score=exp_score,
        exp_summary=exp_summary,
        education_score=education_score,
        education_assessment=education_assessment,
        location_score=location_score,
        parsed_resume=parsed_resume,
        parsed_jd=parsed_jd,
    )
    decision_explanation = _build_decision_explanation(
        verdict=verdict,
        overall=overall,
        skills_result=skills_result,
        requirement_analysis=requirement_analysis,
        score_math=score_math,
        category_reasons=category_reasons,
        exp_score=exp_score,
        exp_summary=exp_summary,
        education_score=education_score,
        education_assessment=education_assessment,
        location_score=location_score,
        verdict_override=verdict_override,
    )
    # Human decision bullets (needed vs present, not formula arrows)
    decision_bullets = list(decision_explanation.get("what_happened") or [])
    if decision_explanation.get("reconciliation"):
        decision_bullets.append(decision_explanation["reconciliation"])
    for cat in category_reasons:
        if cat.get("reason"):
            decision_bullets.append(f"{cat['label']}: {cat['reason']}")
    if decision_explanation.get("next_step"):
        decision_bullets.append(decision_explanation["next_step"])

    deterministic_narrative = _build_deterministic_narrative(
        verdict,
        overall,
        skills_result,
        requirement_analysis,
        exp_summary,
        education_assessment,
        decision_explanation,
    )
    llm_narrative = ""
    run_narrative = narrative_llm
    if run_narrative is None:
        run_narrative = os.getenv("ATS_NARRATIVE_LLM", "1").strip().lower() not in (
            "0",
            "false",
            "no",
            "off",
        )
    if run_narrative:
        llm_narrative = _optional_llm_narrative(
            {
                "verdict": verdict,
                "overall_match_score": overall,
                "mandatory_skills_match_pct": mandatory_match_pct,
                "requirement_analysis": requirement_analysis,
                "decision_explanation": decision_explanation,
                "score_breakdown": {
                    "skills": round(skills_raw, 1),
                    "experience": round(exp_score, 1),
                    "education": round(education_score, 1),
                    "location": round(location_score, 1),
                },
                "experience_summary": exp_summary,
                "education_assessment": education_assessment,
                "decision_summary": decision_summary,
            }
        )
    else:
        try:
            from app.core.timing_collector import record_pipeline_stage

            record_pipeline_stage(
                "_optional_llm_narrative",
                "skipped",
                duration_ms=0.0,
                module="app.domains.recruitment.services.ats_service",
            )
        except Exception:
            pass
    narrative = llm_narrative or deterministic_narrative

    evaluation_report = _build_recruiter_report(
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        role_evaluated=role_evaluated,
        overall_score=overall,
        verdict=verdict,
        score_breakdown=score_breakdown,
        skills_analysis=skills_analysis,
        experience_summary=exp_summary,
        experience_gaps=exp_gaps,
        education_assessment=education_assessment,
        decision_bullets=decision_bullets,
    )

    # Strengths/gaps as skill chips (and short non-skill phrases) for clear UI
    key_strengths = list(skills_result["mandatory_matched"][:10])
    key_strengths.extend(skills_result["preferred_matched"][:5])
    if exp_score >= 70:
        key_strengths.append("Experience aligns with role/domain")
    if education_score >= 80:
        key_strengths.append("Education meets or exceeds requirements")
    if location_score >= 70:
        key_strengths.append("Location compatible with role")

    key_gaps = list(skills_result["mandatory_missing"][:10])
    key_gaps.extend(skills_result["preferred_missing"][:5])
    if exp_score < 50:
        key_gaps.append("Experience below or not clearly aligned with role")
    if education_score < 80 and education_score != 100:
        key_gaps.append("Education does not clearly meet stated qualifications")
    if location_score < 50:
        key_gaps.append("Location may not align with job location")

    final_reasoning = narrative

    # Map verdict to legacy decision for API/shortlisting
    if verdict == "Strong Match":
        decision = "strong_match"
    elif verdict == "Potential Match (Recruiter Review)":
        decision = "partial_match"
    else:
        decision = "not_a_match"

    return {
        "overall_match_score": overall,
        "decision": decision,
        "verdict": verdict,
        "mandatory_skills_match_pct": mandatory_match_pct,
        "evaluation_report": evaluation_report,
        "score_breakdown": {
            "skills": round(skills_raw, 1),
            "experience": round(exp_score, 1),
            "education": round(education_score, 1),
            "location": round(location_score, 1),
        },
        "score_math": score_math,
        "requirement_analysis": requirement_analysis,
        "decision_summary": decision_summary,
        "decision_explanation": decision_explanation,
        "category_reasons": category_reasons,
        "narrative": narrative,
        "key_strengths": key_strengths,
        "key_gaps": key_gaps,
        "final_reasoning": final_reasoning,
    }


@timing
def match_candidate_to_job(
    candidate_id: str,
    job_id: str,
    parsed_resume: dict,
    parsed_jd: dict,
    apply_id: str = None,
    *,
    narrative_llm: bool | None = None,
):
    """
    Call HR-ATS-API /api/match when configured; otherwise run internal weighted matcher.
    Returns (success, result_or_error).
    result: dict with json_output (final_score or overall_match_score, decision, verdict, evaluation_report, rationale or final_reasoning), etc.

    narrative_llm is honored only for the internal matcher (apply submit passes False).
    """
    if ATS_API_URL and ATS_API_KEY:
        parsed_resume_str = json.dumps(parsed_resume) if isinstance(parsed_resume, dict) else str(parsed_resume)
        parsed_jd_str = json.dumps(parsed_jd) if isinstance(parsed_jd, dict) else str(parsed_jd)
        payload = {
            "candidate_id": candidate_id,
            "job_id": job_id,
            "parsed_resume": parsed_resume_str,
            "parsed_jd": parsed_jd_str,
            "threshold": ATS_THRESHOLD,
        }
        if apply_id:
            payload["apply_id"] = apply_id
        headers = {"Content-Type": "application/json", "x-api-key": ATS_API_KEY}
        # Keep apply submit responsive — connect/read timeouts (was a single 60s that felt hung)
        try:
            ats_timeout = float(os.getenv("ATS_API_TIMEOUT_SEC", "25"))
        except (TypeError, ValueError):
            ats_timeout = 25.0
        try:
            resp = requests.post(
                f"{ATS_API_URL}/api/match",
                json=payload,
                headers=headers,
                timeout=(min(10.0, ats_timeout), ats_timeout),
            )
            resp.raise_for_status()
            return True, resp.json()
        except requests.exceptions.Timeout:
            return False, {"error": "ATS request timed out"}
        except requests.exceptions.RequestException as e:
            err_msg = str(e)
            if hasattr(e, "response") and e.response is not None:
                try:
                    body = e.response.json()
                    err_msg = body.get("detail", body.get("error", err_msg))
                except Exception:
                    pass
            return False, {"error": err_msg}

    json_output = _internal_match(
        parsed_resume, parsed_jd, narrative_llm=narrative_llm
    )
    overall = float(json_output.get("overall_match_score") or 0)
    # Auto-shortlist only Strong Match (≥ AUTO_SHORTLIST_MIN, default 80%).
    # Potential Match (40–79%) stays for recruiter review — not auto-shortlisted.
    auto_shortlist = (
        json_output["decision"] == "strong_match"
        and overall >= AUTO_SHORTLIST_MIN
    )
    merged = {
        **json_output,
        "final_score": json_output["overall_match_score"],
        "decision": "shortlist" if auto_shortlist else "reject",
        "verdict": json_output["verdict"],
        "rationale": json_output["final_reasoning"],
        "evaluation_report": json_output["evaluation_report"],
        "mandatory_skills_match_pct": json_output["mandatory_skills_match_pct"],
        # Keep internal decision label for explainability / UI breakdowns
        "match_tier": json_output["decision"],
    }
    return True, {
        "json_output": merged,
        "toon_output": json_output["final_reasoning"],
    }


def _filter_requirement_rows(rows: list) -> list:
    """Keep only displayable skills from requirement_analysis rows."""
    if not isinstance(rows, list):
        return []
    skills = [_as_str(r.get("skill")) for r in rows if isinstance(r, dict)]
    keep = {s.lower() for s in _sanitize_skill_list(skills, max_items=40)}
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        skill = _as_str(r.get("skill"))
        if not skill or skill.lower() not in keep:
            continue
        out.append({
            "skill": skill,
            "status": "matched" if r.get("status") == "matched" else "missing",
        })
    return out


def _requirement_rows_from_skills_analysis(json_out: dict) -> tuple:
    """Build (mandatory_rows, preferred_rows) from legacy skills_analysis / strengths / gaps."""
    skills_analysis = ((json_out.get("evaluation_report") or {}).get("skills_analysis") or {})

    def _as_skill_list(value) -> list:
        return _sanitize_skill_list(_split_skill_list(value), max_items=30)

    mand_matched = _as_skill_list(
        skills_analysis.get("mandatory_matched_skills")
        or skills_analysis.get("skills_matched")
        or []
    )
    mand_missing = _as_skill_list(skills_analysis.get("missing_mandatory_skills") or [])
    pref_matched = _as_skill_list(skills_analysis.get("preferred_matched_skills") or [])
    pref_missing = _as_skill_list(skills_analysis.get("missing_preferred_skills") or [])

    # Recover skills buried in prose chips from older analyses
    soft = {
        "experience aligns with role/domain",
        "education meets or exceeds requirements",
        "location compatible with role",
        "experience below or not clearly aligned with role",
        "education does not clearly meet stated qualifications",
        "location may not align with job location",
    }

    def _chips_from(value) -> list:
        items = value if isinstance(value, list) else ([value] if value else [])
        out = []
        for item in items:
            s = _as_str(item)
            if not s:
                continue
            if ":" in s:
                # e.g. "Possesses mandatory skills: PostgreSQL" / "Missing mandatory skills: A, B"
                _, _, rhs = s.partition(":")
                out.extend(_split_skill_list(rhs))
            elif s.lower() not in soft:
                out.append(s)
        return _sanitize_skill_list(out, max_items=30)

    recovered_present = _chips_from(json_out.get("key_strengths"))
    recovered_missing = _chips_from(json_out.get("key_gaps"))

    if not mand_matched and recovered_present:
        mand_matched = list(recovered_present)
    if not mand_missing and recovered_missing:
        # Only keep recovered missing that aren't already matched
        matched_l = {s.lower() for s in mand_matched}
        mand_missing = [s for s in recovered_missing if s.lower() not in matched_l]

    matched_l = {s.lower() for s in mand_matched}
    mand_missing = [s for s in mand_missing if s.lower() not in matched_l]
    pref_matched_l = {s.lower() for s in pref_matched}
    pref_missing = [s for s in pref_missing if s.lower() not in pref_matched_l]
    mandatory = (
        [{"skill": s, "status": "matched"} for s in mand_matched]
        + [{"skill": s, "status": "missing"} for s in mand_missing]
    )
    preferred = (
        [{"skill": s, "status": "matched"} for s in pref_matched]
        + [{"skill": s, "status": "missing"} for s in pref_missing]
    )
    return mandatory, preferred


def reconcile_match_score_from_analysis(ats_analysis, stored_score=None) -> dict:
    """
    Recalculate skills + overall when the cleaned checklist disagrees with a
    polluted stored skills score. Used so list/detail APIs stay in sync.
    """
    if not isinstance(ats_analysis, dict):
        try:
            score = float(stored_score) if stored_score is not None else None
        except (TypeError, ValueError):
            score = None
        return {
            "adjusted": False,
            "match_score": score,
            "verdict": None,
            "score_breakdown": None,
            "ats_analysis": ats_analysis,
        }

    json_out = ats_analysis.get("json_output") if isinstance(ats_analysis.get("json_output"), dict) else ats_analysis
    if not isinstance(json_out, dict):
        json_out = {}

    breakdown = dict(json_out.get("score_breakdown") or {})
    try:
        stored_skills = float(breakdown.get("skills")) if breakdown.get("skills") is not None else None
    except (TypeError, ValueError):
        stored_skills = None
    try:
        exp = float(breakdown.get("experience") or 0)
        edu = float(breakdown.get("education") or 0)
        loc = float(breakdown.get("location") or 0)
    except (TypeError, ValueError):
        exp = edu = loc = 0.0

    try:
        original_overall = float(stored_score) if stored_score is not None else float(
            json_out.get("overall_match_score") or json_out.get("final_score") or 0
        )
    except (TypeError, ValueError):
        original_overall = None

    req = json_out.get("requirement_analysis") or {}
    mandatory = _filter_requirement_rows(req.get("mandatory") or [])
    preferred = _filter_requirement_rows(req.get("preferred") or [])
    filtered_noise = False
    raw_mand = req.get("mandatory") if isinstance(req.get("mandatory"), list) else []
    if raw_mand and len(raw_mand) > len(mandatory):
        filtered_noise = True

    if not mandatory and not preferred:
        mandatory, preferred = _requirement_rows_from_skills_analysis(json_out)
        if mandatory or preferred:
            filtered_noise = True

    skills_score = stored_skills if stored_skills is not None else 0.0
    adjusted = False

    if mandatory or preferred:
        mand_pct = (
            (100.0 * sum(1 for r in mandatory if r["status"] == "matched") / len(mandatory))
            if mandatory else 100.0
        )
        pref_pct = (
            (100.0 * sum(1 for r in preferred if r["status"] == "matched") / len(preferred))
            if preferred else 100.0
        )
        wm = (WEIGHT_MANDATORY_SKILLS / WEIGHT_SKILLS_TOTAL) if mandatory else 0.0
        wp = (WEIGHT_PREFERRED_SKILLS / WEIGHT_SKILLS_TOTAL) if preferred else 0.0
        cleaned_skills = round((wm * mand_pct + wp * pref_pct) / (wm + wp), 1) if (wm + wp) > 0 else 100.0
        diverges = stored_skills is None or abs(cleaned_skills - stored_skills) >= 5
        if filtered_noise or diverges:
            skills_score = cleaned_skills
            adjusted = abs(cleaned_skills - (stored_skills or 0.0)) >= 1

        mandatory_pct = round(mand_pct, 1)
    else:
        try:
            mandatory_pct = float(json_out.get("mandatory_skills_match_pct") or 100)
        except (TypeError, ValueError):
            mandatory_pct = 100.0

    overall = round(skills_score * WEIGHT_SKILLS_TOTAL + exp * WEIGHT_EXPERIENCE + edu * WEIGHT_EDUCATION + loc * WEIGHT_LOCATION, 1)
    gate_failed = bool(mandatory) and mandatory_pct < MANDATORY_SKILLS_MIN_PCT
    if gate_failed:
        verdict = "Not a Match"
    elif overall >= VERDICT_STRONG_MIN:
        verdict = "Strong Match"
    elif overall >= VERDICT_POTENTIAL_MIN:
        verdict = "Potential Match (Recruiter Review)"
    else:
        verdict = "Not a Match"

    if not adjusted:
        return {
            "adjusted": False,
            "match_score": round(original_overall, 1) if original_overall is not None else overall,
            "verdict": _as_str(json_out.get("verdict")) or verdict,
            "score_breakdown": {
                "skills": stored_skills if stored_skills is not None else skills_score,
                "experience": exp,
                "education": edu,
                "location": loc,
            },
            "ats_analysis": ats_analysis,
            "mandatory_skills_match_pct": mandatory_pct,
        }

    new_breakdown = {
        "skills": skills_score,
        "experience": exp,
        "education": edu,
        "location": loc,
    }

    # Patch analysis copy so detail views also see the synced score
    import copy
    patched = copy.deepcopy(ats_analysis)
    target = patched.get("json_output") if isinstance(patched.get("json_output"), dict) else patched
    if isinstance(target, dict):
        target["score_breakdown"] = new_breakdown
        target["overall_match_score"] = overall
        target["final_score"] = overall
        target["verdict"] = verdict
        target["mandatory_skills_match_pct"] = mandatory_pct
        target["requirement_analysis"] = {
            "mandatory": mandatory,
            "preferred": preferred,
            "gate": {
                "passed": not gate_failed,
                "mandatory_pct": mandatory_pct,
                "threshold": MANDATORY_SKILLS_MIN_PCT,
                "mandatory_defined": bool(mandatory),
            },
        }
        # Force decision text to rebuild from fresh scores
        target.pop("decision_explanation", None)
        target.pop("decision_summary", None)
        if verdict == "Strong Match":
            target["decision"] = "strong_match"
            target["match_tier"] = "strong_match"
        elif "Potential" in verdict:
            target["decision"] = "partial_match"
            target["match_tier"] = "partial_match"
        else:
            target["decision"] = "not_a_match"
            target["match_tier"] = "not_a_match"

    return {
        "adjusted": True,
        "match_score": overall,
        "verdict": verdict,
        "score_breakdown": new_breakdown,
        "ats_analysis": patched,
        "mandatory_skills_match_pct": mandatory_pct,
        "note": (
            f"Skills recalculated from cleaned checklist ({skills_score}% vs stored "
            f"{stored_skills if stored_skills is not None else '—'}%). "
            f"Overall moved from {round(original_overall) if original_overall is not None else '—'}% "
            f"to {round(overall)}%."
        ),
    }


def sync_application_match_score(application_id, ats_analysis, stored_score=None, *, persist=True) -> dict:
    """
    Reconcile score from ats_analysis and optionally persist to applications
    and the linked matches row (latest_match_id) so every API surface stays synced.
    """
    recon = reconcile_match_score_from_analysis(ats_analysis, stored_score)
    if not persist or not recon.get("adjusted") or application_id is None:
        return recon

    try:
        from app.ai.toon.runtime import toon_dumps
        from app.database.connection.db import db_get, db_run

        analysis_toon = toon_dumps(recon["ats_analysis"]) if isinstance(recon.get("ats_analysis"), dict) else None
        new_score = float(recon["match_score"])
        if analysis_toon is not None:
            db_run(
                """
                UPDATE applications
                SET match_score = ?,
                    matching_percentage = ?,
                    ats_analysis = ?
                WHERE id = ?
                """,
                (new_score, new_score, analysis_toon, application_id),
            )
        else:
            db_run(
                """
                UPDATE applications
                SET match_score = ?,
                    matching_percentage = ?
                WHERE id = ?
                """,
                (new_score, new_score, application_id),
            )
        app = db_get(
            'SELECT latest_match_id FROM applications WHERE id = ?',
            (application_id,),
        )
        match_id = (app or {}).get('latest_match_id')
        if match_id:
            if analysis_toon is not None:
                db_run(
                    """
                    UPDATE matches
                    SET match_score = ?, matching_percentage = ?, analysis_toon = ?
                    WHERE id = ?
                    """,
                    (new_score, new_score, analysis_toon, match_id),
                )
            else:
                db_run(
                    """
                    UPDATE matches
                    SET match_score = ?, matching_percentage = ?
                    WHERE id = ?
                    """,
                    (new_score, new_score, match_id),
                )
        recon["persisted"] = True
    except Exception as exc:
        recon["persisted"] = False
        recon["persist_error"] = str(exc)
    return recon

