"""
ATS Matching Service - calls HR-ATS-API when configured; otherwise uses internal weighted matcher.
Weights: Skills 50%, Experience 25%, Education 15%, Location 10%.
"""
import os
import json
import re
import requests

ATS_API_URL = (os.getenv('ATS_API_URL') or '').rstrip('/')
ATS_API_KEY = os.getenv('ATS_API_KEY', '')
ATS_THRESHOLD = int(os.getenv('ATS_THRESHOLD', '60'))

# Internal matcher weights (strict priority order)
WEIGHT_SKILLS = 0.50
WEIGHT_EXPERIENCE = 0.25
WEIGHT_EDUCATION = 0.15
WEIGHT_LOCATION = 0.10


def _normalize_skill(s: str) -> str:
    if not s or not isinstance(s, str):
        return ""
    return re.sub(r"\s+", " ", s.lower().strip())


def _skill_match(required: str, possessed_list: list) -> bool:
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


def _internal_match(parsed_resume: dict, parsed_jd: dict) -> dict:
    """
    Evaluate candidate (TOON resume) vs job (TOON JD). No hallucination; compare only provided fields.
    Returns JSON with: overall_match_score, decision, score_breakdown, key_strengths, key_gaps, final_reasoning.
    """
    jd_skills = list(parsed_jd.get("skills") or [])
    if isinstance(jd_skills, str):
        jd_skills = [s.strip() for s in jd_skills.split(",") if s.strip()]
    cand_skills = list(parsed_resume.get("skills") or [])
    if isinstance(cand_skills, str):
        cand_skills = [s.strip() for s in cand_skills.split(",") if s.strip()]

    matched_skills = []
    missing_skills = []
    for s in jd_skills:
        if _skill_match(s, cand_skills):
            matched_skills.append(s)
        else:
            missing_skills.append(s)

    skills_score = 100.0 * (len(matched_skills) / len(jd_skills)) if jd_skills else 100.0
    if jd_skills and missing_skills:
        skills_score = max(0, skills_score - 10 * min(len(missing_skills), 5))

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
    cand_experiences = list(parsed_resume.get("experience") or [])
    jd_title = (parsed_jd.get("title") or "").lower()
    relevance = 0.0
    if cand_experiences and jd_title:
        for exp in cand_experiences:
            title = (exp.get("title") or exp.get("role") or "").lower()
            if title and (jd_title in title or title in jd_title):
                relevance = 100.0
                break
        if relevance == 0 and cand_experiences:
            relevance = 50.0
    elif cand_years is not None and (jd_min_years is not None or jd_max_years is not None):
        if jd_min_years is not None and jd_max_years is not None:
            if jd_min_years <= cand_years <= jd_max_years:
                relevance = 100.0
            elif cand_years >= jd_min_years:
                relevance = 80.0
            else:
                relevance = max(0, 100 - 20 * (jd_min_years - cand_years))
        elif jd_min_years is not None:
            relevance = 100.0 if cand_years >= jd_min_years else max(0, 100 - 20 * (jd_min_years - cand_years))
        else:
            relevance = 70.0
    else:
        relevance = 70.0 if cand_experiences or cand_years else 0.0
    experience_score = min(100.0, relevance)

    jd_qualifications = list(parsed_jd.get("qualifications") or [])
    if isinstance(jd_qualifications, str):
        jd_qualifications = [jd_qualifications]
    jd_requires_degree = any(
        re.search(r"\b(bachelor|b\.?s\.?|b\.?e\.?|m\.?s\.?|m\.?a\.?|mba|phd|degree|diploma)\b", q, re.I)
        for q in jd_qualifications
    ) if jd_qualifications else False
    cand_education = list(parsed_resume.get("education") or [])
    if not jd_requires_degree:
        education_score = 100.0
    elif not cand_education:
        education_score = 0.0
    else:
        education_score = 80.0
        for e in cand_education:
            deg = (e.get("degree") or e.get("field") or "").lower()
            if re.search(r"\b(bachelor|b\.?s\.?|b\.?e\.?|m\.?s\.?|m\.?a\.?|mba|phd|degree|diploma)\b", deg):
                education_score = 100.0
                break

    jd_location = (parsed_jd.get("location") or "").strip().lower()
    cand_location = ""
    person = parsed_resume.get("person") or {}
    if isinstance(person, dict):
        cand_location = (person.get("location") or person.get("current_location") or "").strip().lower()
    if not jd_location:
        location_score = 100.0
    elif not cand_location:
        location_score = 50.0
    else:
        jd_parts = set(re.findall(r"[a-z]+", jd_location))
        cand_parts = set(re.findall(r"[a-z]+", cand_location))
        overlap = len(jd_parts & cand_parts) / len(jd_parts) if jd_parts else 1.0
        location_score = 50.0 + 50.0 * overlap

    overall = (
        WEIGHT_SKILLS * skills_score
        + WEIGHT_EXPERIENCE * experience_score
        + WEIGHT_EDUCATION * education_score
        + WEIGHT_LOCATION * location_score
    )
    overall = round(min(100.0, max(0.0, overall)), 1)

    if overall >= 80:
        decision = "strong_match"
    elif overall >= 60:
        decision = "partial_match"
    elif overall >= 40:
        decision = "weak_match"
    else:
        decision = "not_a_match"

    key_strengths = []
    if matched_skills:
        key_strengths.append("Possesses required skills: " + ", ".join(matched_skills[:10]))
    if experience_score >= 70:
        key_strengths.append("Experience level aligns with job requirements")
    if education_score >= 80:
        key_strengths.append("Education meets or exceeds requirements")
    if location_score >= 70:
        key_strengths.append("Location compatible with role")

    key_gaps = []
    if missing_skills:
        key_gaps.append("Missing required or preferred skills: " + ", ".join(missing_skills[:10]))
    if experience_score < 50:
        key_gaps.append("Experience level below or not clearly aligned with job")
    if education_score < 80 and jd_requires_degree:
        key_gaps.append("Education does not meet stated qualifications")
    if location_score < 50 and jd_location:
        key_gaps.append("Location may not align with job location")

    if overall >= 60:
        final_reasoning = f"Overall score {overall} ({decision}). Skills carry the highest weight; candidate matches {len(matched_skills)} of {len(jd_skills)} required skills. " + (
            "Key strengths: " + "; ".join(key_strengths[:3]) if key_strengths else ""
        )
    else:
        final_reasoning = f"Overall score {overall} ({decision}). Gaps: " + "; ".join(key_gaps[:3]) if key_gaps else f"Overall score {overall} ({decision})."

    return {
        "overall_match_score": overall,
        "decision": decision,
        "score_breakdown": {
            "skills": round(skills_score, 1),
            "experience": round(experience_score, 1),
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
    result: dict with json_output (final_score or overall_match_score, decision, rationale or final_reasoning), etc.
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
            "rationale": json_output["final_reasoning"],
            **json_output,
        },
        "toon_output": json_output["final_reasoning"],
    }
