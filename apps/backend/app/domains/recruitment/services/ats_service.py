"""
ATS Matching Service - consumes TOON resume + JD (dict from toon_loads_flex). Calls HR-ATS-API when configured;
JSON is used only at the external API boundary (request/response with HR-ATS-API).

REFACTORED MODEL (technical roles):
- Core Technical Skills: 60% (Mandatory 40%, Preferred 20%)
- Relevant Experience: 25%
- Education / Certifications: 10%
- Location / Availability: 5%
Total = 100%

Mandatory Skills Gate: If Mandatory Skills Match % < 60%, candidate is AUTO-DISQUALIFIED (Not a Match).
Shortlisting: 75-100% Strong Match, 60-74% Potential Match, <60% or mandatory<60% Not a Match.
"""
import os
import json
import re
import requests

ATS_API_URL = (os.getenv('ATS_API_URL') or '').rstrip('/')
ATS_API_KEY = os.getenv('ATS_API_KEY', '')
ATS_THRESHOLD = int(os.getenv('ATS_THRESHOLD', '60'))

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
MANDATORY_SKILLS_MIN_PCT = 60.0   # Below this → auto Not a Match
VERDICT_STRONG_MIN = 75.0         # 75–100% → Strong Match
VERDICT_POTENTIAL_MIN = 60.0      # 60–74% → Potential Match (Recruiter Review)
# Below 60% or mandatory < 60% → Not a Match

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


def _normalize_skill(s) -> str:
    text = _as_str(s)
    if not text:
        return ""
    return re.sub(r"\s+", " ", text.lower())


def _skill_match(required, possessed_list: list) -> bool:
    """Exact or close match (possessed contains required or vice versa)."""
    r = _normalize_skill(required)
    if not r:
        return False
    for p in possessed_list:
        pn = _normalize_skill(p)
        if not pn:
            continue
        if r == pn or r in pn or pn in r:
            return True
    return False


def _get_jd_skill_lists(parsed_jd: dict) -> tuple:
    """
    Return (mandatory_skills, preferred_skills).
    JD may have: mandatory_skills, preferred_skills; or legacy single 'skills' (all treated as mandatory).
    """
    mandatory = _split_skill_list(parsed_jd.get("mandatory_skills"))
    preferred = _split_skill_list(parsed_jd.get("preferred_skills"))
    if not mandatory and not preferred:
        mandatory = _split_skill_list(parsed_jd.get("skills"))
        preferred = []
    return mandatory, preferred


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
    Mandatory skills < 60% → Not a Match regardless of overall.
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


def _internal_match(parsed_resume: dict, parsed_jd: dict) -> dict:
    """
    Evaluate candidate (TOON resume) vs job (TOON JD). Deterministic, no inflation.
    Returns JSON with: overall_match_score, decision, verdict, evaluation_report, score_breakdown,
    key_strengths, key_gaps, final_reasoning; and mandatory_skills_match_pct for gating.
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

    # Decision logic bullets
    decision_bullets = []
    if mandatory_defined and mandatory_match_pct < MANDATORY_SKILLS_MIN_PCT:
        decision_bullets.append(f"Mandatory Skills Match ({mandatory_match_pct}%) is below threshold ({MANDATORY_SKILLS_MIN_PCT}%). Candidate is auto-disqualified.")
    decision_bullets.append(f"Overall weighted score: {overall}%.")
    if overall >= VERDICT_STRONG_MIN and not verdict_override:
        decision_bullets.append(f"Score ≥ {VERDICT_STRONG_MIN}% → Strong Match.")
    elif overall >= VERDICT_POTENTIAL_MIN and not verdict_override:
        decision_bullets.append(f"Score in range {VERDICT_POTENTIAL_MIN}%–{VERDICT_STRONG_MIN - 0.1}% → Potential Match (Recruiter Review).")
    else:
        decision_bullets.append(f"Score < {VERDICT_POTENTIAL_MIN}% or mandatory skills below threshold → Not a Match.")

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
    }

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

    key_strengths = []
    if skills_result["mandatory_matched"]:
        key_strengths.append("Possesses mandatory skills: " + ", ".join(skills_result["mandatory_matched"][:10]))
    if skills_result["preferred_matched"]:
        key_strengths.append("Possesses preferred skills: " + ", ".join(skills_result["preferred_matched"][:5]))
    if exp_score >= 70:
        key_strengths.append("Experience aligns with role/domain")
    if education_score >= 80:
        key_strengths.append("Education meets or exceeds requirements")
    if location_score >= 70:
        key_strengths.append("Location compatible with role")

    key_gaps = []
    if skills_result["mandatory_missing"]:
        key_gaps.append("Missing mandatory skills: " + ", ".join(skills_result["mandatory_missing"][:10]))
    if skills_result["preferred_missing"]:
        key_gaps.append("Missing preferred skills: " + ", ".join(skills_result["preferred_missing"][:5]))
    if exp_score < 50:
        key_gaps.append("Experience below or not clearly aligned with role")
    if education_score < 80 and education_score != 100:
        key_gaps.append("Education does not clearly meet stated qualifications")
    if location_score < 50:
        key_gaps.append("Location may not align with job location")

    if verdict == "Not a Match" and mandatory_defined and mandatory_match_pct < MANDATORY_SKILLS_MIN_PCT:
        final_reasoning = f"Verdict: Not a Match. Mandatory Skills Match is {mandatory_match_pct}% (below {MANDATORY_SKILLS_MIN_PCT}%). " + "; ".join(key_gaps[:3]) if key_gaps else ""
    elif verdict == "Not a Match":
        final_reasoning = f"Overall score {overall}% (Not a Match). " + "; ".join(key_gaps[:3]) if key_gaps else f"Overall score {overall}% (Not a Match)."
    else:
        final_reasoning = f"Overall score {overall}% ({verdict}). " + "; ".join(key_strengths[:3]) if key_strengths else f"Overall score {overall}% ({verdict})."

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
        "key_strengths": key_strengths,
        "key_gaps": key_gaps,
        "final_reasoning": final_reasoning,
    }


def match_candidate_to_job(candidate_id: str, job_id: str, parsed_resume: dict, parsed_jd: dict, apply_id: str = None):
    """
    Call HR-ATS-API /api/match when configured; otherwise run internal weighted matcher.
    Returns (success, result_or_error).
    result: dict with json_output (final_score or overall_match_score, decision, verdict, evaluation_report, rationale or final_reasoning), etc.
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
        try:
            resp = requests.post(f"{ATS_API_URL}/api/match", json=payload, headers=headers, timeout=60)
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

    json_output = _internal_match(parsed_resume, parsed_jd)
    return True, {
        "json_output": {
            "final_score": json_output["overall_match_score"],
            "decision": "shortlist" if json_output["decision"] in ("strong_match", "partial_match") else "reject",
            "verdict": json_output["verdict"],
            "rationale": json_output["final_reasoning"],
            "evaluation_report": json_output["evaluation_report"],
            "mandatory_skills_match_pct": json_output["mandatory_skills_match_pct"],
            **json_output,
        },
        "toon_output": json_output["final_reasoning"],
    }
