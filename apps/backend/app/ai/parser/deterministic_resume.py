"""
Deterministic (rules-based) resume → TOON parsing for bulk fast path.

Uses existing text inference + repair pipeline with an empty LLM payload,
then scores confidence so callers can skip Ollama when fields look complete.
"""
from __future__ import annotations

import os
import re
from typing import Any

# name + contact + one of skills/exp/edu typically passes; tune via env
RESUME_DET_CONFIDENCE = max(
    0.0, min(1.0, float(os.getenv('RESUME_DET_CONFIDENCE', '0.70')))
)

_DEGREE_FRAGMENT = re.compile(r'(?i)^(ma|ba|be|bs|ms|me|bsc|msc|mca|bca)$')


def _nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return bool(str(value).strip())


def _quality_skills(skills: Any) -> list[str]:
    from app.ai.parser.enrichment.resume_text_inference import filter_skill_items

    if not skills:
        return []
    if isinstance(skills, str):
        raw = [s.strip() for s in skills.split(',') if s.strip()]
    elif isinstance(skills, list):
        raw = []
        for item in skills:
            if isinstance(item, str):
                raw.append(item)
            elif isinstance(item, dict):
                name = item.get('name') or item.get('skill')
                if name:
                    raw.append(str(name))
            elif item is not None:
                raw.append(str(item))
    else:
        return []
    return filter_skill_items(raw)


def _is_junk_degree(degree: str) -> bool:
    d = (degree or '').strip()
    if not d:
        return False
    if len(d) < 3:
        return True
    compact = d.replace('.', '').replace(' ', '')
    if _DEGREE_FRAGMENT.match(compact) and '.' not in d:
        return True
    return False


def _quality_education(education: Any) -> list[dict]:
    from app.ai.parser.enrichment.resume_text_inference import is_institution_like

    if not isinstance(education, list):
        return []
    out: list[dict] = []
    for e in education:
        if not isinstance(e, dict):
            continue
        degree = str(e.get('degree') or '').strip()
        institution = str(e.get('institution') or e.get('school') or '').strip()
        if _is_junk_degree(degree):
            continue
        if degree or is_institution_like(institution):
            out.append(e)
    return out


def _experience_titles(experience: Any) -> list[str]:
    if not isinstance(experience, list):
        return []
    titles: list[str] = []
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        title = str(exp.get('title') or exp.get('role') or '').strip()
        if title:
            titles.append(title)
    return titles


def experience_quality_ok(toon: dict[str, Any]) -> bool:
    """
    True when experience is empty (OK for fresher) or >=50% of titles are plausible jobs
    with no biodata labels present.
    """
    from app.ai.parser.enrichment.resume_text_inference import (
        is_biodata_or_address_line,
        is_plausible_job_title,
    )

    titles = _experience_titles(toon.get('experience') if isinstance(toon, dict) else None)
    if not titles:
        return True
    if any(is_biodata_or_address_line(t) for t in titles):
        return False
    good = sum(1 for t in titles if is_plausible_job_title(t))
    return (good / len(titles)) >= 0.5


def _quality_experience(experience: Any) -> list[dict]:
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_job_title

    if not isinstance(experience, list):
        return []
    out: list[dict] = []
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        title = str(exp.get('title') or exp.get('role') or '').strip()
        if is_plausible_job_title(title):
            out.append(exp)
    return out


def score_resume_toon(toon: dict[str, Any]) -> tuple[float, list[str], bool]:
    """
    Score a resume TOON for deterministic acceptance.

    Returns (confidence 0..1, missing_field_keys, passes_gate).
    Gate: plausible name + (email or phone) + at least one of real skills / experience / education,
    and experience must not be biodata-polluted.
    """
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

    if not isinstance(toon, dict):
        return 0.0, ['toon'], False

    person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
    has_name = is_plausible_person_name(person.get('name'))
    has_email = _nonempty(person.get('email'))
    has_phone = _nonempty(person.get('phone'))
    has_contact = has_email or has_phone
    quality_skills = _quality_skills(toon.get('skills'))
    has_skills = len(quality_skills) > 0
    quality_exp = _quality_experience(toon.get('experience'))
    has_exp = len(quality_exp) > 0
    quality_edu = _quality_education(toon.get('education'))
    has_edu = len(quality_edu) > 0
    has_summary = _nonempty(toon.get('summary'))
    has_certs = _nonempty(toon.get('certifications'))
    exp_ok = experience_quality_ok(toon)

    missing: list[str] = []
    if not has_name:
        missing.append('person.name')
    if not has_contact:
        missing.append('person.contact')
    if not has_skills:
        missing.append('skills')
    if not has_exp:
        missing.append('experience')
    if not has_edu:
        missing.append('education')
    if not exp_ok:
        missing.append('experience.quality')

    score = 0.0
    if has_name:
        score += 0.25
    if has_contact:
        score += 0.25
    if has_skills:
        score += 0.15
    if has_exp:
        score += 0.25
    if has_edu:
        score += 0.10
    if has_summary:
        score += 0.05
    if has_certs:
        score += 0.05
    score = min(1.0, score)

    passes = bool(
        has_name
        and has_contact
        and (has_skills or has_exp or has_edu)
        and exp_ok
        and score >= RESUME_DET_CONFIDENCE
    )
    return score, missing, passes


def parse_resume_deterministic(
    raw_text: str,
) -> tuple[dict[str, Any], float, list[str], bool]:
    """
    Build a resume TOON from text only (no LLM).

    Returns (toon, confidence, missing_fields, passes_confidence_gate).
    """
    from app.ai.parser.pipelines.resume_toon_pipeline import build_resume_toon

    toon = build_resume_toon(raw_text or '', {})
    if not isinstance(toon, dict):
        toon = {}
    if toon.get('type') != 'resume':
        toon['type'] = 'resume'
    confidence, missing, passes = score_resume_toon(toon)
    return toon, confidence, missing, passes
