"""Deterministic (rules-based) JD → TOON parsing with skip-LLM gate."""
from __future__ import annotations

import os
from typing import Any

JD_DET_CONFIDENCE = max(
    0.0, min(1.0, float(os.getenv('JD_DET_CONFIDENCE', '0.70')))
)

def jd_skip_llm_enabled() -> bool:
    return os.getenv('JD_SKIP_LLM_WHEN_DETERMINISTIC', 'false').lower() in (
        '1',
        'true',
        'yes',
    )


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(str(value).strip())


def score_jd_toon(toon: dict[str, Any]) -> tuple[float, list[str], bool]:
    """
    Score a JD TOON for deterministic acceptance.

    Gate: title + (skills or responsibilities) + location (or remote marker),
    and score >= JD_DET_CONFIDENCE.
    """
    if not isinstance(toon, dict):
        return 0.0, ['toon'], False

    has_title = _nonempty(toon.get('title'))
    skills = toon.get('skills') if isinstance(toon.get('skills'), list) else []
    mandatory = (
        toon.get('mandatory_skills')
        if isinstance(toon.get('mandatory_skills'), list)
        else []
    )
    preferred = (
        toon.get('preferred_skills')
        if isinstance(toon.get('preferred_skills'), list)
        else []
    )
    has_skills = len(skills) > 0 or len(mandatory) > 0
    responsibilities = (
        toon.get('responsibilities')
        if isinstance(toon.get('responsibilities'), list)
        else []
    )
    has_resp = len(responsibilities) > 0
    location = str(toon.get('location') or '').strip()
    has_location = bool(location) or bool(
        location.lower() in ('remote', 'anywhere', 'hybrid') if location else False
    )
    # Accept missing location only when employment suggests remote
    emp = str(toon.get('employment_type') or '').lower()
    if not has_location and 'remote' in emp:
        has_location = True

    has_company = _nonempty(toon.get('company'))
    has_exp = toon.get('min_experience_years') is not None or toon.get(
        'max_experience_years'
    ) is not None
    has_salary = _nonempty(toon.get('salary_range'))
    has_preferred = len(preferred) > 0
    has_mandatory = len(mandatory) > 0

    missing: list[str] = []
    if not has_title:
        missing.append('title')
    if not has_skills and not has_resp:
        missing.append('skills_or_responsibilities')
    if not has_location:
        missing.append('location')
    if not has_mandatory and has_skills:
        missing.append('mandatory_skills')

    score = 0.0
    if has_title:
        score += 0.30
    if has_skills:
        score += 0.20
    if has_resp:
        score += 0.20
    if has_location:
        score += 0.15
    if has_company:
        score += 0.05
    if has_exp:
        score += 0.05
    if has_salary:
        score += 0.025
    if has_preferred or has_mandatory:
        score += 0.025
    score = min(1.0, score)

    passes = bool(
        has_title
        and (has_skills or has_resp)
        and has_location
        and score >= JD_DET_CONFIDENCE
    )
    return score, missing, passes


def parse_jd_deterministic(raw_text: str) -> tuple[dict[str, Any], float, list[str], bool]:
    """
    Build a JD TOON from text only (no LLM).

    Returns (toon, confidence, missing_fields, passes_confidence_gate).
    """
    from app.ai.parser.pipelines.jd_toon_pipeline import build_jd_toon

    toon = build_jd_toon(raw_text or '', {})
    if not isinstance(toon, dict):
        toon = {}
    if toon.get('type') != 'job_description':
        toon['type'] = 'job_description'
    confidence, missing, passes = score_jd_toon(toon)
    return toon, confidence, missing, passes
