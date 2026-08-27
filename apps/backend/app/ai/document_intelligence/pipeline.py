"""
Document Intelligence Engine — canonical-first pipeline.

Sole production entry for Resume / JD parsing.
Frontend receives Form DTOs only. TOON is persistence/ATS serialization.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
from typing import Any, Optional

from app.ai.document_intelligence.knowledge import (
    apply_knowledge_to_candidate,
    apply_knowledge_to_job,
)
from app.ai.document_intelligence.mapping.jd_form import map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
from app.ai.document_intelligence.parsers.jd import parse_jd_from_sections
from app.ai.document_intelligence.parsers.resume import parse_resume_from_sections
from app.ai.document_intelligence.sections import detect_sections
from app.ai.document_intelligence.semantic import enrich_jd_semantic, enrich_resume_semantic
from app.ai.document_intelligence.serialize.toon import candidate_to_toon, job_to_toon
from app.ai.document_intelligence.trace import trace_stage
from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile
from app.ai.parser.engine.confidence import calculate_confidence
from app.ai.parser.engine.hardware import apply_hardware_env, detect_hardware_profile
from app.ai.parser.engine.parse_inflight import inflight_key, run_or_join
from app.ai.parser.engine.progress import complete_parse_job, create_parse_job, emit_stage
from app.ai.parser.engine.sections import unresolved_semantic_text
from app.ai.parser.engine.types import StageCallback, StageEvent
from app.core.timing import timing
from app.domains.recruitment.services.parsing_storage import (
    collect_toon_validation_issues,
    compute_file_hash,
    get_cached_parsing_result,
    get_cached_parsing_result_by_hash,
    store_parsed_jd,
    store_parsed_resume,
    store_raw_file,
    validate_toon_format,
)

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024

MIME_TYPE_MAP = {
    'pdf': 'application/pdf',
    'docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'doc': 'application/msword',
}

_SKIP_LLM = os.getenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true').lower() in (
    '1',
    'true',
    'yes',
)


def _jd_deterministic_is_strong(profile, coverage=None) -> bool:
    """Skip LLM only when title/skills look correct and no core coverage gaps remain."""
    from app.ai.parser.enrichment.jd_text_inference import (
        is_plausible_job_title,
        skills_look_skill_like,
    )

    title = getattr(getattr(profile, 'basic', None), 'title', '') or ''
    skills = getattr(profile, 'skills', None)
    mandatory = list(getattr(skills, 'mandatory', None) or [])
    general = list(getattr(skills, 'general', None) or [])
    if not (is_plausible_job_title(title) and skills_look_skill_like(mandatory or general)):
        return False
    if coverage is not None:
        missing = getattr(coverage, 'missing_with_evidence', None) or []
        # Core form fields that should trigger residual LLM when evidence exists
        core_gap = {'title', 'location', 'experience', 'skills', 'description'}
        if any(f in core_gap for f in missing):
            return False
    return True


_RESUME_CORE_COVERAGE = frozenset(
    {'fullName', 'email', 'phone', 'location', 'education', 'experience'}
)


def resume_deterministic_is_strong(profile, coverage=None, *, source_text: str = '') -> bool:
    """Skip residual LLM only when identity+body look solid and no core coverage gaps."""
    has_id = bool(
        (getattr(getattr(profile, 'personal', None), 'full_name', '') or '').strip()
        and (getattr(getattr(profile, 'contact', None), 'email', '') or '').strip()
    )
    has_body = bool(
        getattr(profile, 'skills', None)
        and (getattr(profile, 'experience', None) or getattr(profile, 'education', None))
    )
    if not (has_id and has_body):
        return False
    if coverage is not None:
        missing = getattr(coverage, 'missing_with_evidence', None) or []
        if any(f in _RESUME_CORE_COVERAGE for f in missing):
            return False
    try:
        from app.ai.document_intelligence.experience_quality import experience_is_incomplete

        if experience_is_incomplete(
            getattr(profile, 'experience', None) or [],
            source_text or '',
        ):
            return False
    except Exception:
        pass
    return True


# Back-compat alias used by in-module call sites
_resume_deterministic_is_strong = resume_deterministic_is_strong


def _apply_jd_repair(profile, raw_text: str):
    """Always run structural JD repair, then remap profile from repaired TOON."""
    from app.ai.adapter.runtime_adapter import repair_jd_toon
    from app.ai.document_intelligence.canonical.from_toon import job_profile_from_toon

    toon = job_to_toon(profile)
    try:
        toon, _repair_actions = repair_jd_toon(toon, raw_jd_text=raw_text)
        profile = job_profile_from_toon(toon)
    except Exception:
        pass
    return profile, toon


def _apply_resume_repair(profile, raw_text: str):
    """
    Run structural resume repair on DI path, then merge conservatively.
    Prefer already-filled deterministic contact/edu/experience over repair mutations.
    """
    from app.ai.adapter.runtime_adapter import repair_resume_toon
    from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
    from app.ai.document_intelligence.models.candidate import CandidateProfile

    original = profile
    toon = candidate_to_toon(profile)
    try:
        toon, _repair_actions = repair_resume_toon(toon, raw_resume_text=raw_text or '')
        repaired = candidate_profile_from_toon(toon)
    except Exception:
        return original, toon

    oc, rc = original.contact, repaired.contact
    contact = oc.model_copy(
        update={
            'email': (oc.email or '').strip() or (rc.email or '').strip(),
            'phone': (oc.phone or '').strip() or (rc.phone or '').strip(),
            'linkedin': (oc.linkedin or '').strip() or (rc.linkedin or '').strip(),
            'github': (oc.github or '').strip() or (rc.github or '').strip(),
            'portfolio': (oc.portfolio or '').strip() or (rc.portfolio or '').strip(),
            'location': (oc.location or '').strip() or (rc.location or '').strip(),
            'preferred_location': (oc.preferred_location or '').strip()
            or (rc.preferred_location or '').strip(),
        }
    )
    personal = original.personal.model_copy(
        update={
            'full_name': (original.personal.full_name or '').strip()
            or (repaired.personal.full_name or '').strip(),
            'summary': (original.personal.summary or '').strip()
            or (repaired.personal.summary or '').strip(),
        }
    )
    from app.ai.document_intelligence.experience_quality import merge_experience_rows

    experience = merge_experience_rows(
        list(original.experience or []),
        list(repaired.experience or []),
    )
    if not experience:
        experience = list(original.experience or repaired.experience or [])
    education = list(original.education) if original.education else list(repaired.education)
    skills = list(original.skills) if original.skills else list(repaired.skills)
    # Ignore repair-invented junk links (e.g. https://B.Tech)
    links = list(original.links) if original.links else []
    if not links:
        for link in repaired.links or []:
            url = (getattr(link, 'url', '') or '').strip()
            if url.startswith('http') and '://' in url and not re.search(
                r'(?i)https?://(?:b\.?tech|m\.?tech|bca|mca|mba)\b',
                url,
            ):
                links.append(link)

    years = original.total_experience_years
    if years is None:
        years = repaired.total_experience_years

    merged = CandidateProfile(
        schema_version=original.schema_version,
        personal=personal,
        contact=contact,
        education=education,
        experience=experience,
        projects=original.projects or repaired.projects,
        skills=skills,
        certificates=original.certificates or repaired.certificates,
        languages=original.languages or repaired.languages,
        links=links,
        preferences=original.preferences or repaired.preferences,
        total_experience_years=years,
        field_meta=dict(original.field_meta or {}),
    )
    return merged, candidate_to_toon(merged)

def _resume_core_missing(coverage) -> list[str]:
    missing = list(getattr(coverage, 'missing_with_evidence', None) or [])
    return [f for f in missing if f in _RESUME_CORE_COVERAGE]

def _mime_type(filename: str) -> str:
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_TYPE_MAP.get(ext, 'application/octet-stream')


def _model_version_label() -> str:
    if os.getenv('AI_USE_GATEWAY', 'true').lower() in ('1', 'true', 'yes'):
        try:
            from app.ai.adapter.runtime_adapter import get_model_version

            return get_model_version()
        except Exception:
            return 'document-intelligence-v1'
    return f"{os.getenv('LLM_PROVIDER', 'xai')}-di-v1"


def _emit(
    job_id: Optional[str],
    stage: str,
    status: str,
    message: str = '',
    detail: dict | None = None,
    on_stage: StageCallback | None = None,
) -> None:
    from app.core.request_context import mark_pipeline_stage_start, take_pipeline_stage_elapsed_ms

    status_l = (status or '').lower()
    elapsed_ms: float | None = None
    if stage:
        if status_l == 'started':
            mark_pipeline_stage_start(stage)
        elif status_l in ('completed', 'failed', 'skipped'):
            elapsed_ms = take_pipeline_stage_elapsed_ms(stage)
            if elapsed_ms is None and status_l in ('skipped', 'failed'):
                elapsed_ms = 0.0

    det = dict(detail or {})
    if elapsed_ms is not None:
        det['duration_ms'] = round(max(0.0, float(elapsed_ms)), 2)

    event = StageEvent(
        stage=stage,
        status=status,
        message=message,
        detail=det,
        job_id=job_id,
        duration_ms=elapsed_ms,
    )
    emit_stage(job_id, event)
    trace_stage(stage, message=f'{status}:{message}')
    if on_stage:
        try:
            on_stage(event)
        except Exception:
            pass

    # Developer Mode: record per-stage duration for the Performance Dashboard
    try:
        from app.core.developer_mode import is_developer_mode_enabled
        from app.core.timing_collector import make_timing_event, timing_collector

        if not is_developer_mode_enabled() or not stage:
            return
        if status_l not in ('completed', 'failed', 'skipped'):
            return
        if elapsed_ms is None:
            # Missing start mark (thread context gap). Do not record 0 ms —
            # @timing on extract_text / parse_via_runtime still has the real duration.
            return
        timing_collector.record(
            make_timing_event(
                function=stage,
                module='app.ai.document_intelligence.pipeline',
                duration_ms=max(0.0, float(elapsed_ms)),
                success=status_l != 'failed',
                exception_name='StageFailed' if status_l == 'failed' else None,
                depth=2,
                outcome=status_l,
            )
        )
    except Exception:
        pass


@timing
def run_document_intelligence(
    doc_type: str,
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    candidate_id: str | None = None,
    job_id: str | None = None,
    enrichment_context=None,
    parse_job_id: str | None = None,
    on_stage: StageCallback | None = None,
    use_content_hash_cache: bool = True,
) -> tuple[dict[str, Any], int]:
    """
    Unified entry. doc_type: 'resume' | 'jd' | 'job_description'.
    Returns (response_dict with toon for ATS, http_status).
    """
    apply_hardware_env()
    kind = 'resume' if doc_type == 'resume' else 'job_description'
    preexisting_job_id = parse_job_id

    def _execute() -> tuple[dict[str, Any], int]:
        # Create the progress job only for the in-flight owner. Joiners reuse
        # this function's return value (same parse_job_id); they must not
        # leave a phantom `running` row.
        owned_parse_job_id = (
            preexisting_job_id if preexisting_job_id is not None else create_parse_job(kind)
        )
        try:
            if kind == 'resume':
                body, status = _run_resume(
                    file_data,
                    filename,
                    uploader_id=uploader_id,
                    uploader_role=uploader_role,
                    candidate_id=candidate_id,
                    parse_job_id=owned_parse_job_id,
                    on_stage=on_stage,
                    use_content_hash_cache=use_content_hash_cache,
                )
            else:
                body, status = _run_jd(
                    file_data,
                    filename,
                    uploader_id=uploader_id,
                    uploader_role=uploader_role,
                    job_id=job_id,
                    parse_job_id=owned_parse_job_id,
                    on_stage=on_stage,
                    use_content_hash_cache=use_content_hash_cache,
                )
            if status == 200:
                complete_parse_job(owned_parse_job_id, body)
            else:
                complete_parse_job(owned_parse_job_id, None, error=body.get('error'))
            body = dict(body)
            body['parse_job_id'] = owned_parse_job_id
            return body, status
        except Exception as exc:
            from app.core.errors import log_unexpected

            log_unexpected('document_intelligence', exc, parse_job_id=owned_parse_job_id)
            complete_parse_job(owned_parse_job_id, None, error=type(exc).__name__)
            return {
                'status': 'error',
                'error': 'Internal server error',
                'parse_job_id': owned_parse_job_id,
            }, 500

    # Public stream → sync fallback re-uploads the same bytes with a new uploader id.
    # Join in-process so the second request waits instead of starting another LLM parse.
    # Persistent public hash cache stays disabled (cross-visitor stale TOON).
    if uploader_role == 'public' and file_data:
        cache_tag = os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG', '')
        key = inflight_key(compute_file_hash(file_data), kind, cache_tag)
        return run_or_join(key, _execute)
    return _execute()


def run_intelligence_pipeline(*args, **kwargs):
    return run_document_intelligence(*args, **kwargs)


def run_resume_parse_pipeline(
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    candidate_id: str | None = None,
    enrichment_context=None,
    parse_job_id: str | None = None,
    on_stage: StageCallback | None = None,
) -> tuple[dict[str, Any], int]:
    return run_document_intelligence(
        'resume',
        file_data,
        filename,
        uploader_id=uploader_id,
        uploader_role=uploader_role,
        candidate_id=candidate_id,
        enrichment_context=enrichment_context,
        parse_job_id=parse_job_id,
        on_stage=on_stage,
    )


def run_jd_parse_pipeline(
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    job_id: str | None = None,
    parse_job_id: str | None = None,
    on_stage: StageCallback | None = None,
) -> tuple[dict[str, Any], int]:
    return run_document_intelligence(
        'jd',
        file_data,
        filename,
        uploader_id=uploader_id,
        uploader_role=uploader_role,
        job_id=job_id,
        parse_job_id=parse_job_id,
        on_stage=on_stage,
    )


def parse_resume_text_to_canonical(
    text: str,
    *,
    max_workers: int | None = None,
    allow_semantic: bool | None = None,
):
    """In-memory resume parse for tests / gold / bulk (no DB).

    allow_semantic=False skips Ollama even when coverage looks weak (bulk fast path).
    """
    import time as _time

    from app.core.timing_collector import record_pipeline_stage

    profile_hw = detect_hardware_profile()
    workers = max_workers or min(4, max(1, profile_hw.cpu_count // 2))

    t0 = _time.perf_counter()
    sections = detect_sections(text, 'resume')
    record_pipeline_stage(
        'sections',
        'completed',
        duration_ms=(_time.perf_counter() - t0) * 1000.0,
        module='app.ai.document_intelligence.pipeline',
    )

    t0 = _time.perf_counter()
    profile = parse_resume_from_sections(sections, text, max_workers=workers)
    record_pipeline_stage(
        'deterministic',
        'completed',
        duration_ms=(_time.perf_counter() - t0) * 1000.0,
        module='app.ai.document_intelligence.pipeline',
    )

    from app.ai.document_intelligence.coverage import (
        recover_resume_profile_gaps,
    )
    from app.ai.document_intelligence.coverage.resume_coverage import (
        has_experience_section_evidence,
    )

    t0 = _time.perf_counter()
    profile, coverage = recover_resume_profile_gaps(profile, text)
    record_pipeline_stage(
        'coverage',
        'completed',
        duration_ms=(_time.perf_counter() - t0) * 1000.0,
        module='app.ai.document_intelligence.pipeline',
    )
    allow_experience_fill = bool(profile.experience) or has_experience_section_evidence(text)

    t0 = _time.perf_counter()
    profile = apply_knowledge_to_candidate(profile)
    knowledge_ms = (_time.perf_counter() - t0) * 1000.0

    skip_semantic = allow_semantic is False
    force_semantic = allow_semantic is True
    run_semantic = (not skip_semantic) and (
        force_semantic
        or (not _SKIP_LLM)
        or (not resume_deterministic_is_strong(profile, coverage, source_text=text))
    )
    if run_semantic:
        t0 = _time.perf_counter()
        unresolved = unresolved_semantic_text(sections, 'resume') or text
        profile = enrich_resume_semantic(
            profile,
            unresolved_text=unresolved,
            allow_experience_fill=allow_experience_fill
            or ('experience' in (coverage.missing_with_evidence or [])),
        )
        profile = sanitize_candidate_profile(profile, source_text=text or '')
        profile, coverage = recover_resume_profile_gaps(profile, text)
        record_pipeline_stage(
            'semantic',
            'completed',
            duration_ms=(_time.perf_counter() - t0) * 1000.0,
            module='app.ai.document_intelligence.pipeline',
        )
        t0 = _time.perf_counter()
        profile = apply_knowledge_to_candidate(profile)
        knowledge_ms += (_time.perf_counter() - t0) * 1000.0
    else:
        record_pipeline_stage(
            'semantic',
            'skipped',
            duration_ms=0.0,
            module='app.ai.document_intelligence.pipeline',
        )

    profile, toon = _apply_resume_repair(profile, text)
    profile = sanitize_candidate_profile(profile, source_text=text or '')
    profile, coverage = recover_resume_profile_gaps(profile, text)

    record_pipeline_stage(
        'knowledge',
        'completed',
        duration_ms=knowledge_ms,
        module='app.ai.document_intelligence.pipeline',
    )

    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    toon = candidate_to_toon(profile)
    return profile, form, toon


def parse_jd_text_to_canonical(text: str, *, max_workers: int | None = None):
    from app.ai.document_intelligence.coverage import recover_jd_profile_gaps
    from app.ai.parser.layout.detector import enhance_jd_text, is_jd_layout_enabled

    profile_hw = detect_hardware_profile()
    workers = max_workers or min(4, max(1, profile_hw.cpu_count // 2))
    working = text or ''
    if is_jd_layout_enabled():
        structured = enhance_jd_text(working)
        if structured and len(structured.strip()) >= 30:
            working = structured
    sections = detect_sections(working, 'jd')
    profile = parse_jd_from_sections(sections, working, max_workers=workers)
    profile = apply_knowledge_to_job(profile)
    # Coverage first so residual LLM only runs when grounded gaps remain
    profile, coverage = recover_jd_profile_gaps(profile, working)
    run_semantic = (not _SKIP_LLM) or (not _jd_deterministic_is_strong(profile, coverage))
    if run_semantic:
        unresolved = unresolved_semantic_text(sections, 'jd') or working
        profile = enrich_jd_semantic(profile, unresolved_text=unresolved, force=bool(coverage.missing_with_evidence))
        profile = apply_knowledge_to_job(profile)
    profile, toon = _apply_jd_repair(profile, working)
    profile, coverage = recover_jd_profile_gaps(profile, working)
    toon = job_to_toon(profile)
    form = map_job_to_form(profile, coverage=coverage.as_dicts(), raw_text=working)
    return profile, form, toon


def _refresh_resume_from_cached_text(raw_text: str):
    """Re-run deterministic resume parse on cached extract so parser fixes apply immediately."""
    from app.ai.document_intelligence.coverage import recover_resume_profile_gaps

    text = (raw_text or '').strip()
    if len(text) < 30:
        return None
    sections = detect_sections(text, 'resume')
    profile = parse_resume_from_sections(sections, text)
    profile = apply_knowledge_to_candidate(profile)
    profile, _ = recover_resume_profile_gaps(profile, text)
    profile = sanitize_candidate_profile(profile, source_text=text)
    form = map_candidate_to_form(profile)
    toon = candidate_to_toon(profile)
    return profile, form, toon


def _cache_hit_response(
    cached: dict,
    *,
    uploader_id: str,
    uploader_role: str,
    candidate_id: str | None,
    parse_job_id: str,
    kind: str,
) -> tuple[dict, int]:
    if kind == 'resume' and candidate_id:
        from app.database.connection.db import db_run

        db_run(
            'UPDATE parsed_resumes SET candidate_id = ? WHERE id = ?',
            (candidate_id, cached['parsed_id']),
        )
    toon = cached['toon']
    form = None
    canonical = None
    if kind == 'resume':
        try:
            refreshed = _refresh_resume_from_cached_text(cached.get('raw_text') or '')
            if refreshed:
                profile, form_dto, toon = refreshed
                canonical = profile.model_dump()
                form = form_dto.to_autofill_dict()
        except Exception:
            toon = cached['toon']
    body = {
        'status': 'ok',
        'raw_file_id': cached['raw_file_id'],
        'parsed_id': cached['parsed_id'],
        'confidence': cached['confidence'],
        'toon': toon,
        'is_duplicate': True,
        'model_version': cached['model_version'],
        'partial': 'text-fallback' in str(cached.get('model_version') or ''),
        'parse_job_id': parse_job_id,
        'cache_status': 'cache-hit',
        'raw_text': cached.get('raw_text') or '',
        'raw_text_chars': len(cached.get('raw_text') or ''),
        'raw_text_sha256': hashlib.sha256(
            (cached.get('raw_text') or '').encode('utf-8', errors='ignore')
        ).hexdigest(),
    }
    if form is not None:
        body['form'] = form
    if canonical is not None:
        body['canonical'] = canonical
    if kind == 'resume':
        body['public_uploader_id'] = uploader_id if uploader_role == 'public' else None
    return body, 200


@timing
def _run_resume(
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    candidate_id: str | None,
    parse_job_id: str,
    on_stage: StageCallback | None,
    use_content_hash_cache: bool,
) -> tuple[dict[str, Any], int]:
    mime_type = _mime_type(filename)
    if len(file_data) > MAX_FILE_SIZE:
        return {
            'status': 'error',
            'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB',
        }, 400

    _emit(parse_job_id, 'cache', 'started', 'Checking parse cache', on_stage=on_stage)
    file_hash = compute_file_hash(file_data)
    cached = get_cached_parsing_result(file_hash, uploader_id, 'resume')
    # Public apply uses a new uploader id each time. Do not reuse another
    # visitor's cached TOON — stale experience mapping survives parser fixes.
    if not cached and use_content_hash_cache and uploader_role != 'public':
        cached = get_cached_parsing_result_by_hash(file_hash, 'resume')
    if cached:
        _emit(parse_job_id, 'cache', 'completed', 'Cache hit', on_stage=on_stage)
        return _cache_hit_response(
            cached,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            candidate_id=candidate_id,
            parse_job_id=parse_job_id,
            kind='resume',
        )
    _emit(parse_job_id, 'cache', 'completed', 'Cache miss', on_stage=on_stage)

    _emit(parse_job_id, 'persist_raw', 'started', on_stage=on_stage)
    raw_file_record = store_raw_file(
        uploader_id, uploader_role, file_data, filename, mime_type, None
    )
    raw_file_id = raw_file_record['id']
    _emit(parse_job_id, 'persist_raw', 'completed', on_stage=on_stage)

    from app.ai.parser.text_extraction import extract_text

    # Time text and layout separately (layout must not include extract_text wall time)
    _emit(parse_job_id, 'text', 'started', on_stage=on_stage)
    text_done_msg = ''
    extract_err: Exception | None = None
    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        extract_err = e
        raw_text = ''

    # VALIDATION_FIX_nul_strip — PostgreSQL text columns reject NUL bytes
    if raw_text and '\x00' in raw_text:
        raw_text = raw_text.replace('\x00', '')

    text_length = len(raw_text.strip()) if raw_text else 0
    _IMAGE_EXTS = ('pdf', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp')

    def _looks_like_garbage_extract(s: str) -> bool:
        """Narrow heuristic: enough chars but almost no signal (bad OCR)."""
        t = (s or '').strip()
        if len(t) < 30:
            return True
        if len(t) > 400:
            return False
        alnum = sum(1 for c in t if c.isalnum())
        ratio = alnum / max(len(t), 1)
        has_token = bool(
            re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', t)
            or re.search(r'\b[6-9]\d{9}\b|\+\d[\d\s\-()]{8,}\d', t)
            or re.search(r'(?i)\b(?:experience|education|skills|summary)\b', t)
        )
        return ratio < 0.35 and not has_token

    # VALIDATION_FIX_ocr_dpi_retry — thin, failed, or garbage extract on scan-friendly formats
    needs_dpi_retry = filename.lower().rsplit('.', 1)[-1] in _IMAGE_EXTS and (
        extract_err is not None
        or not raw_text
        or text_length < 30
        or _looks_like_garbage_extract(raw_text)
    )
    if needs_dpi_retry:
        try:
            raw_text = extract_text(file_data, filename, dpi=300) or ''
            if raw_text and '\x00' in raw_text:
                raw_text = raw_text.replace('\x00', '')
            text_length = len(raw_text.strip()) if raw_text else 0
            text_done_msg = f'OCR DPI retry → {text_length} chars'
            extract_err = None
        except Exception as retry_err:
            if extract_err is not None and (not raw_text or text_length < 30):
                _emit(parse_job_id, 'text', 'failed', f'DPI retry: {retry_err}', on_stage=on_stage)
                return {'status': 'error', 'error': f'Text extraction failed: {retry_err}'}, 400

    if extract_err is not None and (not raw_text or text_length < 30):
        _emit(parse_job_id, 'text', 'failed', str(extract_err), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(extract_err)}'}, 400

    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
    _emit(
        parse_job_id,
        'text',
        'completed',
        text_done_msg or f'Extracted {text_length} chars',
        on_stage=on_stage,
    )

    _emit(parse_job_id, 'layout', 'started', 'Layout analysis', on_stage=on_stage)
    try:
        from app.ai.parser.layout.detector import enhance_resume_text, is_layout_enabled

        if is_layout_enabled():
            structured = enhance_resume_text(raw_text)
            if structured and len(structured.strip()) >= 30:
                raw_text = structured
                _emit(parse_job_id, 'layout', 'completed', 'Section headers structured', on_stage=on_stage)
            else:
                _emit(parse_job_id, 'layout', 'completed', 'No structure change', on_stage=on_stage)
        else:
            _emit(parse_job_id, 'layout', 'skipped', 'Layout disabled', on_stage=on_stage)
    except Exception as layout_err:
        _emit(parse_job_id, 'layout', 'failed', str(layout_err), on_stage=on_stage)

    _emit(parse_job_id, 'sections', 'started', on_stage=on_stage)
    sections = detect_sections(raw_text, 'resume')
    _emit(
        parse_job_id,
        'sections',
        'completed',
        f'{len(sections)} sections',
        detail={'labels': [s.label for s in sections]},
        on_stage=on_stage,
    )

    hw = detect_hardware_profile()
    workers = min(6, max(2, hw.cpu_count // 2))

    _emit(parse_job_id, 'deterministic', 'started', 'Section parsers', on_stage=on_stage)
    profile = parse_resume_from_sections(
        sections, raw_text, max_workers=workers, source_filename=filename or '',
    )
    _emit(parse_job_id, 'deterministic', 'completed', on_stage=on_stage)

    from app.ai.document_intelligence.coverage import recover_resume_profile_gaps
    from app.ai.document_intelligence.coverage.resume_coverage import (
        has_experience_section_evidence,
    )

    _emit(parse_job_id, 'coverage', 'started', on_stage=on_stage)
    profile, coverage = recover_resume_profile_gaps(profile, raw_text)
    _emit(
        parse_job_id,
        'coverage',
        'completed',
        f'recovered={len(coverage.recovered_fields)} missing_evidence={len(coverage.missing_with_evidence)}',
        on_stage=on_stage,
    )
    allow_experience_fill = bool(profile.experience) or has_experience_section_evidence(
        raw_text
    )

    used_llm = False
    _emit(parse_job_id, 'semantic', 'started', on_stage=on_stage)
    if _SKIP_LLM and resume_deterministic_is_strong(
        profile, coverage, source_text=raw_text
    ):
        _emit(
            parse_job_id,
            'semantic',
            'skipped',
            'Deterministic coverage sufficient',
            on_stage=on_stage,
        )
    else:
        unresolved = unresolved_semantic_text(sections, 'resume') or raw_text
        profile = enrich_resume_semantic(
            profile,
            unresolved_text=unresolved,
            allow_experience_fill=allow_experience_fill
            or ('experience' in (coverage.missing_with_evidence or [])),
        )
        profile = sanitize_candidate_profile(profile, source_text=raw_text or '')
        profile, coverage = recover_resume_profile_gaps(profile, raw_text)
        used_llm = True
        _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    profile = apply_knowledge_to_candidate(profile)
    profile, toon = _apply_resume_repair(profile, raw_text)
    profile = sanitize_candidate_profile(profile, source_text=raw_text or '')
    profile, coverage = recover_resume_profile_gaps(profile, raw_text)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    toon = candidate_to_toon(profile)
    missing_ev = _resume_core_missing(coverage)
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())

    _emit(parse_job_id, 'validate', 'started', on_stage=on_stage)
    validation_issues = collect_toon_validation_issues(toon, 'resume')
    is_valid, error_msg = validate_toon_format(toon, 'resume')
    # Never hard-fail when any usable contact/body signal exists — return partial form
    has_usable = bool(
        (profile.personal.full_name or '').strip()
        or (profile.contact.email or '').strip()
        or (profile.contact.phone or '').strip()
        or profile.skills
        or profile.experience
        or profile.education
    )
    if not is_valid and not has_usable:
        _emit(parse_job_id, 'validate', 'failed', error_msg or '', on_stage=on_stage)
        return {
            'status': 'error',
            'error': f'Invalid parse: {error_msg or "; ".join(validation_issues)}',
            'missing_fields': validation_issues,
            'coverage': coverage.as_dicts(),
        }, 400
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'resume')
    model_version = _model_version_label()
    cache_tag = os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG', 'canonical-v8-exp-layout')
    if not used_llm:
        model_version = f'{model_version}+{cache_tag}+deterministic'
    else:
        model_version = f'{model_version}+{cache_tag}+hybrid'

    _emit(parse_job_id, 'persist', 'started', on_stage=on_stage)
    parsed_id = store_parsed_resume(
        raw_file_id,
        candidate_id,
        toon,
        raw_text,
        confidence,
        model_version,
    )
    _emit(parse_job_id, 'persist', 'completed', on_stage=on_stage)

    missing_fields = list(dict.fromkeys([*missing_ev, *(validation_issues if not is_valid else [])]))
    return {
        'status': 'ok',
        'raw_file_id': raw_file_id,
        'parsed_id': parsed_id,
        'confidence': confidence,
        'toon': toon,
        'canonical': profile.model_dump(),
        'form': form.to_autofill_dict(),
        'is_duplicate': False,
        'model_version': model_version,
        'public_uploader_id': uploader_id if uploader_role == 'public' else None,
        'partial': (not is_valid) or bool(missing_ev),
        'missing_fields': missing_fields,
        'coverage': coverage.as_dicts(),
        'parse_job_id': parse_job_id,
        'raw_text': raw_text or '',
        'raw_text_chars': len(raw_text or ''),
        'raw_text_sha256': hashlib.sha256((raw_text or '').encode('utf-8', errors='ignore')).hexdigest(),
    }, 200


@timing
def _run_jd(
    file_data: bytes,
    filename: str,
    *,
    uploader_id: str,
    uploader_role: str,
    job_id: str | None,
    parse_job_id: str,
    on_stage: StageCallback | None,
    use_content_hash_cache: bool,
) -> tuple[dict[str, Any], int]:
    mime_type = _mime_type(filename)
    if len(file_data) > MAX_FILE_SIZE:
        return {
            'status': 'error',
            'error': f'File too large. Maximum size: {MAX_FILE_SIZE / 1024 / 1024}MB',
        }, 400

    _emit(parse_job_id, 'cache', 'started', on_stage=on_stage)
    file_hash = compute_file_hash(file_data)
    cached = get_cached_parsing_result(file_hash, uploader_id, 'job_description')
    if not cached and use_content_hash_cache:
        cached = get_cached_parsing_result_by_hash(file_hash, 'job_description')
    if cached:
        _emit(parse_job_id, 'cache', 'completed', 'Cache hit', on_stage=on_stage)
        return _cache_hit_response(
            cached,
            uploader_id=uploader_id,
            uploader_role=uploader_role,
            candidate_id=None,
            parse_job_id=parse_job_id,
            kind='jd',
        )
    _emit(parse_job_id, 'cache', 'completed', 'Cache miss', on_stage=on_stage)

    _emit(parse_job_id, 'persist_raw', 'started', on_stage=on_stage)
    raw_file_record = store_raw_file(
        uploader_id, uploader_role, file_data, filename, mime_type, None
    )
    raw_file_id = raw_file_record['id']
    _emit(parse_job_id, 'persist_raw', 'completed', on_stage=on_stage)

    from app.ai.parser.text_extraction import extract_text

    _emit(parse_job_id, 'text', 'started', on_stage=on_stage)
    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    if raw_text and '\x00' in raw_text:
        raw_text = raw_text.replace('\x00', '')

    text_length = len(raw_text.strip()) if raw_text else 0
    if not raw_text or text_length < 30:
        _emit(parse_job_id, 'text', 'failed', 'insufficient text', on_stage=on_stage)
        return {'status': 'error', 'error': 'Could not extract sufficient text from document'}, 400
    _emit(parse_job_id, 'text', 'completed', f'Extracted {text_length} chars', on_stage=on_stage)

    _emit(parse_job_id, 'layout', 'started', on_stage=on_stage)
    try:
        from app.ai.parser.layout.detector import enhance_jd_text, is_jd_layout_enabled

        if is_jd_layout_enabled():
            structured = enhance_jd_text(raw_text)
            if structured and len(structured.strip()) >= 30:
                raw_text = structured
                _emit(parse_job_id, 'layout', 'completed', 'JD section headers structured', on_stage=on_stage)
            else:
                _emit(parse_job_id, 'layout', 'completed', 'No structure change', on_stage=on_stage)
        else:
            _emit(parse_job_id, 'layout', 'skipped', 'JD layout disabled', on_stage=on_stage)
    except Exception as layout_err:
        _emit(parse_job_id, 'layout', 'failed', str(layout_err), on_stage=on_stage)

    _emit(parse_job_id, 'sections', 'started', on_stage=on_stage)
    sections = detect_sections(raw_text, 'jd')
    _emit(parse_job_id, 'sections', 'completed', f'{len(sections)} sections', on_stage=on_stage)

    hw = detect_hardware_profile()
    workers = min(6, max(2, hw.cpu_count // 2))

    _emit(parse_job_id, 'deterministic', 'started', on_stage=on_stage)
    profile = parse_jd_from_sections(sections, raw_text, max_workers=workers)
    _emit(parse_job_id, 'deterministic', 'completed', on_stage=on_stage)

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    profile = apply_knowledge_to_job(profile)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    from app.ai.document_intelligence.coverage import recover_jd_profile_gaps

    _emit(parse_job_id, 'coverage', 'started', on_stage=on_stage)
    profile, coverage = recover_jd_profile_gaps(profile, raw_text)
    _emit(
        parse_job_id,
        'coverage',
        'completed',
        f'recovered={len(coverage.recovered_fields)} missing_evidence={len(coverage.missing_with_evidence)}',
        on_stage=on_stage,
    )

    used_llm = False
    _emit(parse_job_id, 'semantic', 'started', on_stage=on_stage)
    if _SKIP_LLM and _jd_deterministic_is_strong(profile, coverage):
        _emit(parse_job_id, 'semantic', 'skipped', on_stage=on_stage)
    else:
        unresolved = unresolved_semantic_text(sections, 'jd') or raw_text
        profile = enrich_jd_semantic(
            profile,
            unresolved_text=unresolved,
            force=bool(coverage.missing_with_evidence),
        )
        used_llm = True
        profile = apply_knowledge_to_job(profile)
        _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)

    profile, toon = _apply_jd_repair(profile, raw_text)
    profile, coverage = recover_jd_profile_gaps(profile, raw_text)
    toon = job_to_toon(profile)
    missing_ev = coverage.missing_with_evidence
    form = map_job_to_form(profile, coverage=coverage.as_dicts(), raw_text=raw_text)

    _emit(parse_job_id, 'validate', 'started', on_stage=on_stage)
    is_valid, error_msg = validate_toon_format(toon, 'job_description')
    if not is_valid and not profile.basic.title:
        _emit(parse_job_id, 'validate', 'failed', error_msg or '', on_stage=on_stage)
        return {'status': 'error', 'error': f'Invalid JD parse: {error_msg}'}, 400
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'job_description')
    model_version = _model_version_label()
    # Bump cache tag when shipping parser accuracy fixes so stale TOON is not reused
    cache_tag = os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG', 'canonical-v6-jd-coverage')
    model_version = f'{model_version}+{cache_tag}+{"hybrid" if used_llm else "deterministic"}'

    _emit(parse_job_id, 'persist', 'started', on_stage=on_stage)
    parsed_id = store_parsed_jd(raw_file_id, job_id, toon, raw_text, confidence, model_version)
    _emit(parse_job_id, 'persist', 'completed', on_stage=on_stage)

    return {
        'status': 'ok',
        'raw_file_id': raw_file_id,
        'parsed_id': parsed_id,
        'confidence': confidence,
        'toon': toon,
        'canonical': profile.model_dump(),
        'form': form.to_autofill_dict(),
        'is_duplicate': False,
        'model_version': model_version,
        'partial': not is_valid or bool(missing_ev),
        'missing_fields': missing_ev,
        'coverage': coverage.as_dicts(),
        'parse_job_id': parse_job_id,
    }, 200
