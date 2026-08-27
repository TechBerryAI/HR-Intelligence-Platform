"""
Section-scoped semantic AI — only for unresolved semantic fields.

Returns canonical JSON fragments, never root TOON for the live path.

Invariant: enrich_resume_semantic issues at most one full `resume` Ollama call.
"""
from __future__ import annotations

import logging
import os
import threading
import time
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
    cancel_event = threading.Event()

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
                    metadata={'cancel_event': cancel_event},
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
        cancel_event.set()
        cancelled = 0
        try:
            from providers.ollama.client import abort_in_flight_requests

            cancelled = abort_in_flight_requests()
        except Exception:
            logger.debug('ollama abort_in_flight_requests failed', exc_info=True)
        logger.warning(
            'semantic AI timed out after %ss for %s; cancelled_in_flight=%s',
            timeout_sec,
            doc_kind,
            cancelled,
        )
        return None
    except Exception as exc:
        logger.debug('semantic AI failed: %s', exc)
        return None
    finally:
        # wait=False: if the worker is blocked on ollama_slot (nested acquire),
        # shutdown(wait=True) would hang forever and freeze bulk parse.
        pool.shutdown(wait=False, cancel_futures=True)


def _filled_text(deterministic: str, ai: str) -> str:
    det = (deterministic or '').strip()
    return det if det else (ai or '').strip()


def _prefer_list(deterministic, ai):
    return list(deterministic) if deterministic else list(ai or [])


def _semantic_reason(
    profile,
    unresolved_text: str,
    *,
    force: bool,
    allow_experience_fill: bool,
) -> str:
    from app.ai.document_intelligence.experience_quality import experience_is_incomplete

    parts: list[str] = []
    if force:
        parts.append('force')
    if allow_experience_fill and experience_is_incomplete(
        getattr(profile, 'experience', None), unresolved_text or ''
    ):
        parts.append('experience_incomplete')
    if _needs_resume_semantic(profile.model_dump(), unresolved_text or ''):
        parts.append('coverage_gaps')
    return ','.join(parts) or 'requested'


def _record_semantic_meta(*, llm_calls: int, duration_ms: float) -> None:
    try:
        from app.core.request_context import get_timing_context

        ctx = get_timing_context()
        if ctx is None:
            return
        ctx.meta['semantic_llm_calls'] = int(llm_calls)
        ctx.meta['semantic_llm_duration_ms'] = round(float(duration_ms), 2)
    except Exception:
        pass


def _merge_resume_semantic_profile(
    profile,
    raw: dict[str, Any],
    *,
    unresolved_text: str,
    allow_experience_fill: bool,
):
    """Reconcile one full resume_parsing JSON into the deterministic profile.

    Deterministic non-empty scalars and populated lists win. AI fills gaps.
    Experience uses the existing grounded merge when the det set is incomplete.
    """
    from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
    from app.ai.document_intelligence.experience_quality import experience_is_incomplete
    from app.ai.document_intelligence.semantic.experience import merge_experience_from_ai

    payload = dict(raw)
    if not payload.get('type'):
        payload['type'] = 'resume'
    ai = candidate_profile_from_toon(payload)

    merged_experience = False
    working = profile
    if allow_experience_fill and experience_is_incomplete(
        profile.experience, unresolved_text or ''
    ):
        working = merge_experience_from_ai(profile, raw, unresolved_text or '')
        merged_experience = working.experience is not profile.experience

    contact = working.contact.model_copy(
        update={
            'email': _filled_text(working.contact.email, ai.contact.email),
            'phone': _filled_text(working.contact.phone, ai.contact.phone),
            'location': _filled_text(working.contact.location, ai.contact.location),
            'preferred_location': _filled_text(
                working.contact.preferred_location, ai.contact.preferred_location
            ),
            'linkedin': _filled_text(working.contact.linkedin, ai.contact.linkedin),
            'github': _filled_text(working.contact.github, ai.contact.github),
            'portfolio': _filled_text(working.contact.portfolio, ai.contact.portfolio),
            'other_links': _prefer_list(working.contact.other_links, ai.contact.other_links),
        }
    )
    personal = working.personal.model_copy(
        update={
            'full_name': _filled_text(working.personal.full_name, ai.personal.full_name),
            'summary': _filled_text(working.personal.summary, ai.personal.summary),
        }
    )
    merged = working.model_copy(
        update={
            'personal': personal,
            'contact': contact,
            'education': _prefer_list(working.education, ai.education),
            'skills': _prefer_list(working.skills, ai.skills),
            'projects': _prefer_list(working.projects, ai.projects),
            'certificates': _prefer_list(working.certificates, ai.certificates),
            'languages': _prefer_list(working.languages, ai.languages),
            'links': _prefer_list(working.links, ai.links),
            'total_experience_years': working.total_experience_years
            if working.total_experience_years is not None
            else ai.total_experience_years,
        }
    )
    return merged, merged_experience


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

    Issues at most one full ``resume`` capability Ollama call. The complete JSON
    is reused for experience merge and residual gap fill.
    """
    from app.ai.document_intelligence.models.candidate import CandidateProfile
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile

    if not isinstance(profile, CandidateProfile):
        return profile
    if not semantic_ai_enabled() and not force:
        return profile
    data = profile.model_dump()
    if not force and not _needs_resume_semantic(data, unresolved_text or ''):
        logger.info('[semantic] skipped reason=deterministic_coverage')
        _record_semantic_meta(llm_calls=0, duration_ms=0.0)
        return profile
    if not unresolved_text or len(unresolved_text.strip()) < 40:
        return profile

    reason = _semantic_reason(
        profile,
        unresolved_text,
        force=force,
        allow_experience_fill=allow_experience_fill,
    )
    logger.info('[semantic] started reason=%s', reason)

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

    # One full resume_parser_v1 + resume_milestone_v1 call. Never a second.
    llm_calls = 0
    duration_ms = 0.0
    t0 = time.perf_counter()
    logger.info('[semantic] ollama_call=1')
    raw = _call_section_llm(llm_payload, 'resume')
    llm_calls = 1
    duration_ms = (time.perf_counter() - t0) * 1000.0
    _record_semantic_meta(llm_calls=llm_calls, duration_ms=duration_ms)

    if not isinstance(raw, dict):
        logger.info(
            '[semantic] completed llm_calls=%s duration_ms=%.0f response=empty',
            llm_calls,
            duration_ms,
            extra={
                'event': 'semantic_enrichment',
                'semantic_llm_calls': llm_calls,
                'semantic_llm_duration_ms': round(duration_ms, 2),
            },
        )
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

    logger.info('[semantic] response_received')
    try:
        if section_summary and not is_valid_summary((profile.personal.summary or '').strip()):
            profile = profile.model_copy(
                update={
                    'personal': profile.personal.model_copy(
                        update={'summary': section_summary}
                    )
                }
            )
        merged, merged_experience = _merge_resume_semantic_profile(
            profile,
            raw,
            unresolved_text=unresolved_text,
            allow_experience_fill=allow_experience_fill,
        )
        logger.info(
            '[semantic] merged_experience=%s merged_other_fields=true',
            str(merged_experience).lower(),
        )
        logger.info('[semantic] ollama_call=2 SKIPPED')
        logger.info(
            '[semantic] completed llm_calls=%s duration_ms=%.0f',
            llm_calls,
            duration_ms,
            extra={
                'event': 'semantic_enrichment',
                'semantic_llm_calls': llm_calls,
                'semantic_llm_duration_ms': round(duration_ms, 2),
            },
        )
        return sanitize_candidate_profile(merged, source_text=unresolved_text or '')
    except Exception as exc:
        logger.debug('semantic merge failed: %s', exc)
        logger.info('[semantic] ollama_call=2 SKIPPED')
        logger.info(
            '[semantic] completed llm_calls=%s duration_ms=%.0f merge=failed',
            llm_calls,
            duration_ms,
            extra={
                'event': 'semantic_enrichment',
                'semantic_llm_calls': llm_calls,
                'semantic_llm_duration_ms': round(duration_ms, 2),
            },
        )
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
