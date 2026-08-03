"""Confidence scoring and field provenance for Intelligence Engine validation."""
from __future__ import annotations

from typing import Any


def calculate_confidence(toon: dict, doc_type: str) -> float:
    """
    Calculate confidence score based on field completeness and quality.
    Moved from parsing API so engine and routes share one implementation.
    """
    if doc_type == 'resume':
        required_fields = ['person', 'skills', 'experience', 'education']
        optional_fields = ['summary', 'certifications']

        score = 0.0
        max_score = 0.0
        required_score = 0.0
        required_max = 0.7

        for field in required_fields:
            max_score += 0.175
            if field in toon and toon[field]:
                if field == 'person':
                    person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
                    if person.get('name') or person.get('email'):
                        if person.get('name') and person.get('email'):
                            score += 0.175
                            required_score += 0.175
                        else:
                            score += 0.1
                            required_score += 0.1
                elif isinstance(toon[field], list):
                    if len(toon[field]) > 0:
                        score += 0.175
                        required_score += 0.175
                elif toon[field]:
                    score += 0.175
                    required_score += 0.175

        for field in optional_fields:
            max_score += 0.15
            if field in toon and toon[field]:
                if isinstance(toon[field], list):
                    if len(toon[field]) > 0:
                        score += 0.15
                elif toon[field]:
                    score += 0.15

        if required_score >= required_max:
            base_confidence = 1.0
        elif max_score > 0:
            base_confidence = score / max_score
            person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
            has_person = bool(person.get('name') or person.get('email'))
            has_experience = isinstance(toon.get('experience'), list) and len(
                toon.get('experience') or []
            ) > 0
            has_education = isinstance(toon.get('education'), list) and len(
                toon.get('education') or []
            ) > 0
            if has_person and (has_experience or has_education):
                base_confidence = max(base_confidence, 0.65)
            base_confidence = min(base_confidence, 1.0)
        else:
            base_confidence = 0.5

        try:
            from app.ai.parser.deterministic_resume import experience_quality_ok
            from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

            person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
            raw_name = person.get('name')
            if raw_name and not is_plausible_person_name(raw_name):
                return min(float(base_confidence), 0.45)
            if not raw_name:
                return min(float(base_confidence), 0.55)
            if not experience_quality_ok(toon):
                return min(float(base_confidence), 0.5)
        except Exception:
            pass
        return float(base_confidence)

    # JD
    required_fields = ['title', 'skills', 'responsibilities']
    optional_fields = ['company', 'location', 'qualifications']

    score = 0.0
    max_score = 0.0

    for field in required_fields:
        max_score += 0.233
        if field in toon and toon[field]:
            score += 0.233

    for field in optional_fields:
        max_score += 0.1
        if field in toon and toon[field]:
            score += 0.1

    # Bonus for skill tiers (ATS-critical)
    mandatory = toon.get('mandatory_skills') if isinstance(toon.get('mandatory_skills'), list) else []
    preferred = toon.get('preferred_skills') if isinstance(toon.get('preferred_skills'), list) else []
    tier_bonus = 0.0
    if mandatory:
        tier_bonus += 0.05
    if preferred:
        tier_bonus += 0.03

    base = (score / max_score if max_score > 0 else 0.5) + tier_bonus
    return min(base, 1.0)


def attach_field_provenance(
    toon: dict[str, Any],
    *,
    deterministic_keys: list[str] | None = None,
    llm_used: bool = False,
    knowledge_applied: bool = False,
) -> dict[str, Any]:
    """Attach non-breaking _provenance map for observability."""
    if not isinstance(toon, dict):
        return toon
    provenance: dict[str, str] = {}
    for key in deterministic_keys or []:
        provenance[key] = 'deterministic'
    if llm_used:
        provenance['_semantic'] = 'llm'
    if knowledge_applied:
        provenance['_knowledge'] = 'knowledge'
    toon['_provenance'] = provenance
    return toon


def prefer_deterministic_person(
    llm_toon: dict[str, Any],
    det_toon: dict[str, Any],
) -> dict[str, Any]:
    """
    When both LLM and deterministic produced person contact fields,
    deterministic wins for regex-friendly keys.
    """
    from app.ai.parser.engine.types import RESUME_DETERMINISTIC_PERSON_KEYS

    if not isinstance(llm_toon, dict) or not isinstance(det_toon, dict):
        return llm_toon
    person = llm_toon.get('person') if isinstance(llm_toon.get('person'), dict) else {}
    det_person = det_toon.get('person') if isinstance(det_toon.get('person'), dict) else {}
    if not isinstance(person, dict):
        person = {}
        llm_toon['person'] = person
    for key in RESUME_DETERMINISTIC_PERSON_KEYS:
        det_val = str(det_person.get(key) or '').strip()
        if det_val:
            person[key] = det_val
    # Name: prefer deterministic only when LLM empty or implausible
    det_name = str(det_person.get('name') or '').strip()
    llm_name = str(person.get('name') or '').strip()
    if det_name and not llm_name:
        person['name'] = det_name
    return llm_toon


def prefer_deterministic_jd(
    llm_toon: dict[str, Any],
    det_toon: dict[str, Any],
) -> dict[str, Any]:
    """Deterministic wins for regex-friendly JD fields when present."""
    from app.ai.parser.engine.types import JD_DETERMINISTIC_KEYS

    if not isinstance(llm_toon, dict) or not isinstance(det_toon, dict):
        return llm_toon
    for key in JD_DETERMINISTIC_KEYS:
        det_val = det_toon.get(key)
        if det_val is None:
            continue
        if isinstance(det_val, str) and not det_val.strip():
            continue
        if isinstance(det_val, list) and len(det_val) == 0:
            continue
        # Prefer det when LLM missing OR for salary/dates/urls-like structured fields
        llm_val = llm_toon.get(key)
        llm_empty = (
            llm_val is None
            or (isinstance(llm_val, str) and not str(llm_val).strip())
            or (isinstance(llm_val, list) and len(llm_val) == 0)
        )
        if llm_empty or key in (
            'salary_range',
            'employment_type',
            'min_experience_years',
            'max_experience_years',
            'location',
        ):
            llm_toon[key] = det_val

    for key in ('mandatory_skills', 'preferred_skills', 'skills'):
        det_list = det_toon.get(key)
        llm_list = llm_toon.get(key)
        if isinstance(det_list, list) and det_list:
            if not isinstance(llm_list, list) or not llm_list:
                llm_toon[key] = det_list
    return llm_toon
