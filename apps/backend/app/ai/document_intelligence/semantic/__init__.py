"""
Section-scoped semantic AI — only for unresolved semantic fields.

Returns canonical JSON fragments, never root TOON for the live path.
"""
from __future__ import annotations

import json
import logging
import os
import re
from typing import Any, Optional

logger = logging.getLogger(__name__)

_ENABLED = os.getenv('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'true').lower() in ('1', 'true', 'yes')


def semantic_ai_enabled() -> bool:
    return _ENABLED


def _needs_resume_semantic(profile_dict: dict[str, Any]) -> bool:
    personal = profile_dict.get('personal') or {}
    contact = profile_dict.get('contact') or {}
    has_identity = bool(str(personal.get('full_name') or '').strip() and str(contact.get('email') or '').strip())
    has_exp = bool(profile_dict.get('experience'))
    has_edu = bool(profile_dict.get('education'))
    has_skills = bool(profile_dict.get('skills'))
    # Skip AI when deterministic coverage is strong (fresher: education+skills OK)
    return not (has_identity and has_skills and (has_exp or has_edu))


def _needs_jd_semantic(profile_dict: dict[str, Any]) -> bool:
    from app.ai.parser.enrichment.jd_text_inference import (
        is_plausible_job_title,
        skills_look_skill_like,
    )

    basic = profile_dict.get('basic') or {}
    skills = profile_dict.get('skills') or {}
    title = str(basic.get('title') or '').strip()
    mandatory = list(skills.get('mandatory') or [])
    general = list(skills.get('general') or [])
    if not (is_plausible_job_title(title) and skills_look_skill_like(mandatory or general)):
        return True
    desc = str(basic.get('description') or '').strip()
    resp = list((profile_dict.get('responsibilities') or {}).get('items') or [])
    if len(desc) < 40 and not resp:
        return True
    return False


def _call_section_llm(prompt: str, doc_kind: str) -> Optional[dict[str, Any]]:
    """Best-effort section LLM with a hard timeout so API/batch never hangs."""
    import concurrent.futures

    timeout_sec = float(os.getenv('DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '25'))

    def _invoke() -> Optional[dict[str, Any]]:
        try:
            from app.ai.adapter.runtime_adapter import parse_via_runtime

            result = parse_via_runtime(prompt, 'resume' if doc_kind == 'resume' else 'jd')
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.debug('semantic AI unavailable: %s', exc)
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            fut = pool.submit(_invoke)
            return fut.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        logger.warning('semantic AI timed out after %ss for %s', timeout_sec, doc_kind)
        return None
    except Exception as exc:
        logger.debug('semantic AI failed: %s', exc)
        return None


def enrich_resume_semantic(
    profile,
    *,
    unresolved_text: str,
    force: bool = False,
    allow_experience_fill: bool = True,
):
    """Optionally fill gaps via section-scoped AI. Mutates by returning new profile.

    When allow_experience_fill is False (Experience section empty), never invent
    experience rows from project / assignment narratives.
    """
    from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
    from app.ai.document_intelligence.models.candidate import CandidateProfile
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile

    if not isinstance(profile, CandidateProfile):
        return profile
    if not semantic_ai_enabled() and not force:
        return profile
    data = profile.model_dump()
    if not force and not _needs_resume_semantic(data):
        return profile
    if not unresolved_text or len(unresolved_text.strip()) < 40:
        return profile

    exp_key = (
        'experience (list of {role,company,start,end,description}), '
        if allow_experience_fill
        else ''
    )
    prompt = (
        'Extract ONLY missing structured resume fields as JSON with keys: '
        f'{exp_key}'
        'education (list of {degree,institution,field,start,end}), '
        'skills (string list), summary (string). '
        'Do not invent email/phone/urls. Do not treat projects or assignments as jobs. '
        f'Text:\n\n{unresolved_text[:6000]}'
    )
    raw = _call_section_llm(prompt, 'resume')
    if not isinstance(raw, dict):
        return profile

    # Merge AI only into empty gaps — convert via TOON adapter once for alias safety
    try:
        partial_toon = {
            'type': 'resume',
            'person': {
                'name': profile.personal.full_name,
                'email': profile.contact.email,
                'phone': profile.contact.phone,
                'location': profile.contact.location,
                'linkedin': profile.contact.linkedin,
                'github': profile.contact.github,
                'portfolio': profile.contact.portfolio,
            },
            'summary': profile.personal.summary or raw.get('summary') or '',
            'skills': [s.canonical or s.name for s in profile.skills] or raw.get('skills') or [],
            'experience': [
                {
                    'title': e.role,
                    'company': e.company,
                    'from': e.start,
                    'to': 'Present' if e.is_current else e.end,
                    'description': e.description,
                }
                for e in profile.experience
            ],
            'education': [
                {
                    'degree': e.degree,
                    'field': e.field,
                    'institution': e.institution,
                    'from': e.start,
                    'to': e.end,
                    'gpa': e.gpa,
                }
                for e in profile.education
            ]
            or raw.get('education')
            or [],
        }
        # Only fill experience from AI when Experience section had content
        if (
            allow_experience_fill
            and not profile.experience
            and isinstance(raw.get('experience'), list)
        ):
            partial_toon['experience'] = []
            for item in raw['experience']:
                if not isinstance(item, dict):
                    continue
                partial_toon['experience'].append(
                    {
                        'title': item.get('role') or item.get('title') or '',
                        'company': item.get('company') or '',
                        'from': item.get('start') or item.get('from') or '',
                        'to': item.get('end') or item.get('to') or '',
                        'description': item.get('description') or '',
                    }
                )
        if not profile.skills and isinstance(raw.get('skills'), list):
            partial_toon['skills'] = [str(s) for s in raw['skills'] if s]
        if not profile.personal.summary and raw.get('summary'):
            partial_toon['summary'] = str(raw['summary'])

        merged = candidate_profile_from_toon(partial_toon)
        # Always prefer deterministic contact; lock experience when section was empty
        exp_keep = profile.experience if not allow_experience_fill else merged.experience
        merged = merged.model_copy(
            update={
                'personal': merged.personal.model_copy(
                    update={
                        'full_name': profile.personal.full_name or merged.personal.full_name,
                        'summary': profile.personal.summary or merged.personal.summary,
                    }
                ),
                'contact': profile.contact,
                'experience': exp_keep,
            }
        )
        return sanitize_candidate_profile(merged)
    except Exception as exc:
        logger.debug('semantic merge failed: %s', exc)
        return profile


def enrich_jd_semantic(profile, *, unresolved_text: str, force: bool = False):
    from app.ai.document_intelligence.canonical.from_toon import job_profile_from_toon
    from app.ai.document_intelligence.models.job import JobProfile

    if not isinstance(profile, JobProfile):
        return profile
    # force only bypasses the “needs residual” gate — never runs when AI is disabled
    if not semantic_ai_enabled():
        return profile
    if not force and not _needs_jd_semantic(profile.model_dump()):
        return profile
    if not unresolved_text or len(unresolved_text.strip()) < 40:
        return profile

    prompt = (
        'Extract job description fields as JSON: title, company, location, '
        'mandatory_skills, preferred_skills, responsibilities, qualifications, '
        'min_experience_years, max_experience_years, salary_range, employment_type. '
        f'Text:\n\n{unresolved_text[:6000]}'
    )
    raw = _call_section_llm(prompt, 'jd')
    if not isinstance(raw, dict):
        return profile
    try:
        toon = {
            'type': 'job_description',
            'title': profile.basic.title or raw.get('title') or '',
            'company': profile.basic.company or raw.get('company') or '',
            'location': profile.location.primary or raw.get('location') or '',
            'employment_type': profile.basic.employment_type or raw.get('employment_type') or '',
            'description': profile.basic.description,
            'mandatory_skills': profile.skills.mandatory or raw.get('mandatory_skills') or [],
            'preferred_skills': profile.skills.preferred or raw.get('preferred_skills') or [],
            'skills': profile.skills.general or [],
            'responsibilities': profile.responsibilities.items or raw.get('responsibilities') or [],
            'qualifications': profile.requirements.qualifications or raw.get('qualifications') or [],
            'min_experience_years': profile.requirements.min_experience_years
            if profile.requirements.min_experience_years is not None
            else raw.get('min_experience_years'),
            'max_experience_years': profile.requirements.max_experience_years
            if profile.requirements.max_experience_years is not None
            else raw.get('max_experience_years'),
            'salary_range': profile.compensation.salary_range or raw.get('salary_range') or '',
            'benefits': list(profile.benefits.items),
        }
        return job_profile_from_toon(toon)
    except Exception as exc:
        logger.debug('jd semantic merge failed: %s', exc)
        return profile
