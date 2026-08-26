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

from app.core.timing import timing

logger = logging.getLogger(__name__)

_ENABLED = os.getenv('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'true').lower() in ('1', 'true', 'yes')


def semantic_ai_enabled() -> bool:
    return _ENABLED


def _needs_resume_semantic(profile_dict: dict[str, Any], raw_text: str = '') -> bool:
    personal = profile_dict.get('personal') or {}
    contact = profile_dict.get('contact') or {}
    has_identity = bool(str(personal.get('full_name') or '').strip() and str(contact.get('email') or '').strip())
    has_exp = bool(profile_dict.get('experience'))
    has_edu = bool(profile_dict.get('education'))
    has_skills = bool(profile_dict.get('skills'))
    # Skip AI when deterministic coverage is strong (fresher: education+skills OK)
    if not (has_identity and has_skills and (has_exp or has_edu)):
        return True
    if raw_text:
        try:
            from app.ai.document_intelligence.experience_quality import experience_is_incomplete

            if experience_is_incomplete(profile_dict.get('experience') or [], raw_text):
                return True
        except Exception:
            pass
    # Still run residual LLM when contact/location/edu incomplete but source has evidence
    if raw_text:
        try:
            from app.ai.document_intelligence.coverage.resume_coverage import (
                resume_has_recoverable_gaps,
            )
            from app.ai.document_intelligence.models.candidate import CandidateProfile

            profile = CandidateProfile.model_validate(profile_dict)
            if resume_has_recoverable_gaps(profile, raw_text):
                return True
        except Exception:
            pass
    return False


def _needs_jd_semantic(profile_dict: dict[str, Any]) -> bool:
    from app.ai.parser.enrichment.jd_text_inference import (
        is_plausible_job_title,
        skills_look_polluted,
        skills_look_skill_like,
    )

    basic = profile_dict.get('basic') or {}
    skills = profile_dict.get('skills') or {}
    title = str(basic.get('title') or '').strip()
    mandatory = list(skills.get('mandatory') or [])
    preferred = list(skills.get('preferred') or [])
    general = list(skills.get('general') or [])
    skill_pool = mandatory or general
    # Run residual LLM when title is weak OR skills are missing/polluted
    if not is_plausible_job_title(title):
        return True
    if skills_look_polluted(skill_pool) or (preferred and skills_look_polluted(preferred)):
        return True
    if not skills_look_skill_like(skill_pool):
        return True
    desc = str(basic.get('description') or '').strip()
    resp = list((profile_dict.get('responsibilities') or {}).get('items') or [])
    if len(desc) < 40 and not resp:
        return True
    return False


@timing
def _call_section_llm(prompt: str, doc_kind: str) -> Optional[dict[str, Any]]:
    """Best-effort section LLM with a hard timeout so API/batch never hangs."""
    import concurrent.futures

    from app.core.request_context import get_timing_context, run_in_timing_context

    timeout_sec = float(os.getenv('DOCUMENT_INTELLIGENCE_SEMANTIC_TIMEOUT_SEC', '90'))
    timing_ctx = get_timing_context()

    def _invoke() -> Optional[dict[str, Any]]:
        try:
            from app.ai.adapter.runtime_adapter import parse_via_runtime
            from app.ai.parser.engine.ollama_limit import ollama_slot

            with ollama_slot():
                result = parse_via_runtime(
                    prompt,
                    'resume' if doc_kind == 'resume' else 'jd',
                    timeout_seconds=timeout_sec,
                    max_attempts=1,
                )
            if isinstance(result, dict):
                return result
        except Exception as exc:
            logger.debug('semantic AI unavailable: %s', exc)
        return None

    def _invoke_timed() -> Optional[dict[str, Any]]:
        if timing_ctx is not None:
            return run_in_timing_context(timing_ctx, _invoke)
        return _invoke()

    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    try:
        fut = pool.submit(_invoke_timed)
        return fut.result(timeout=timeout_sec)
    except concurrent.futures.TimeoutError:
        logger.warning('semantic AI timed out after %ss for %s', timeout_sec, doc_kind)
        return None
    except Exception as exc:
        logger.debug('semantic AI failed: %s', exc)
        return None
    finally:
        # wait=False: if the worker is blocked on ollama_slot (nested acquire),
        # shutdown(wait=True) would hang forever and freeze bulk parse.
        pool.shutdown(wait=False, cancel_futures=True)


@timing
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
    if not force and not _needs_resume_semantic(data, unresolved_text or ''):
        return profile
    if not unresolved_text or len(unresolved_text.strip()) < 40:
        return profile

    from app.ai.document_intelligence.experience_quality import experience_is_incomplete

    if allow_experience_fill and experience_is_incomplete(profile.experience, unresolved_text):
        from app.ai.document_intelligence.semantic.experience import extract_and_merge_experience

        profile = extract_and_merge_experience(profile, unresolved_text)
        data = profile.model_dump()
        if not force and not _needs_resume_semantic(data, unresolved_text):
            return sanitize_candidate_profile(profile, source_text=unresolved_text)

    # Same resume_parser_v1 prompt + resume_milestone_v1 schema as parse_via_runtime.
    # Do not send a competing fragment-JSON instruction.
    # Prefer summary/objective section text for the model when summary is still empty —
    # never ask the LLM to invent a summary from contact/experience noise alone.
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_summary_from_text,
        is_valid_summary,
    )

    section_summary = (profile.personal.summary or '').strip()
    if not is_valid_summary(section_summary):
        section_summary = extract_summary_from_text(unresolved_text or '')
    llm_payload = unresolved_text[:6000]
    if not section_summary:
        from app.ai.parser.enrichment.resume_text_inference import extract_summary_details

        details = extract_summary_details(unresolved_text or '')
        # If a summary heading exists but body failed validation, still scope the LLM
        # to that section only (never the contact block).
        if details.get('source_section'):
            llm_payload = (
                f"{details.get('source_section')}\n{details.get('raw_value') or ''}"
            )[:4000] or llm_payload

    raw = _call_section_llm(llm_payload, 'resume')
    if not isinstance(raw, dict):
        # Still keep deterministic section summary if we found one
        if section_summary and not profile.personal.summary:
            return sanitize_candidate_profile(
                profile.model_copy(
                    update={
                        'personal': profile.personal.model_copy(
                            update={'summary': section_summary}
                        )
                    }
                ),
                source_text=unresolved_text,
            )
        return profile

    # Merge AI only into empty gaps — convert via TOON adapter once for alias safety
    try:
        ai_summary = str(raw.get('summary') or '').strip()
        if section_summary:
            chosen_summary = section_summary
        elif is_valid_summary(ai_summary):
            chosen_summary = ai_summary
        else:
            chosen_summary = ''

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
            'summary': chosen_summary,
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
        # Fill or replace weak experience from AI when the Experience section exists
        from app.ai.document_intelligence.experience_quality import experience_is_incomplete

        exp_weak = allow_experience_fill and experience_is_incomplete(
            profile.experience, unresolved_text or ''
        )
        if exp_weak and isinstance(raw.get('experience'), list):
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
        # summary already validated above — do not re-introduce raw LLM contact blobs

        merged = candidate_profile_from_toon(partial_toon)
        from app.ai.document_intelligence.experience_quality import (
            ground_experience_rows,
            merge_experience_rows,
        )

        if not allow_experience_fill:
            exp_keep = profile.experience
        else:
            ai_exp = ground_experience_rows(list(merged.experience or []), unresolved_text or '')
            exp_keep = merge_experience_rows(list(profile.experience or []), ai_exp)
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
        return sanitize_candidate_profile(merged, source_text=unresolved_text or '')
    except Exception as exc:
        logger.debug('semantic merge failed: %s', exc)
        return profile


@timing
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

    raw = _call_section_llm(unresolved_text[:6000], 'jd')
    if not isinstance(raw, dict):
        return profile
    try:
        from app.ai.parser.enrichment.jd_text_inference import (
            normalize_skill_tokens,
            skills_look_polluted,
        )

        existing_mand = list(profile.skills.mandatory or [])
        existing_pref = list(profile.skills.preferred or [])
        llm_mand = normalize_skill_tokens(
            raw.get('mandatory_skills') if isinstance(raw.get('mandatory_skills'), list) else [],
            max_items=30,
        )
        llm_pref = normalize_skill_tokens(
            raw.get('preferred_skills') if isinstance(raw.get('preferred_skills'), list) else [],
            max_items=20,
        )
        # Prefer LLM skills when deterministic lists are polluted; never invent empty over good lists
        if skills_look_polluted(existing_mand) and llm_mand:
            merged_mand = llm_mand
        else:
            merged_mand = existing_mand or llm_mand
        if skills_look_polluted(existing_pref) and llm_pref:
            merged_pref = llm_pref
        else:
            merged_pref = existing_pref or llm_pref

        toon = {
            'type': 'job_description',
            'title': profile.basic.title or raw.get('title') or '',
            'company': profile.basic.company or raw.get('company') or '',
            'location': profile.location.primary or raw.get('location') or '',
            'employment_type': profile.basic.employment_type or raw.get('employment_type') or '',
            'description': profile.basic.description,
            'mandatory_skills': merged_mand,
            'preferred_skills': merged_pref,
            'skills': profile.skills.general or merged_mand,
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
