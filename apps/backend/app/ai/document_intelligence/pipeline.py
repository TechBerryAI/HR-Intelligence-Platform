"""
Document Intelligence Engine — canonical-first pipeline.

Sole production entry for Resume / JD parsing.
Frontend receives Form DTOs only. TOON is persistence/ATS serialization.
"""
from __future__ import annotations

import hashlib
import os
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
from app.ai.parser.engine.progress import complete_parse_job, create_parse_job, emit_stage
from app.ai.parser.engine.sections import unresolved_semantic_text
from app.ai.parser.engine.types import StageCallback, StageEvent
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


def _jd_deterministic_is_strong(profile) -> bool:
    """Skip LLM only when title and skills look structurally correct — not merely nonempty."""
    from app.ai.parser.enrichment.jd_text_inference import (
        is_plausible_job_title,
        skills_look_skill_like,
    )

    title = getattr(getattr(profile, 'basic', None), 'title', '') or ''
    skills = getattr(profile, 'skills', None)
    mandatory = list(getattr(skills, 'mandatory', None) or [])
    general = list(getattr(skills, 'general', None) or [])
    return bool(is_plausible_job_title(title) and skills_look_skill_like(mandatory or general))


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
    event = StageEvent(
        stage=stage,
        status=status,
        message=message,
        detail=detail or {},
        job_id=job_id,
    )
    emit_stage(job_id, event)
    trace_stage(stage, message=f'{status}:{message}')
    if on_stage:
        try:
            on_stage(event)
        except Exception:
            pass


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
    if parse_job_id is None:
        parse_job_id = create_parse_job(kind)

    try:
        if kind == 'resume':
            body, status = _run_resume(
                file_data,
                filename,
                uploader_id=uploader_id,
                uploader_role=uploader_role,
                candidate_id=candidate_id,
                parse_job_id=parse_job_id,
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
                parse_job_id=parse_job_id,
                on_stage=on_stage,
                use_content_hash_cache=use_content_hash_cache,
            )
        if status == 200:
            complete_parse_job(parse_job_id, body)
        else:
            complete_parse_job(parse_job_id, None, error=body.get('error'))
        body = dict(body)
        body['parse_job_id'] = parse_job_id
        return body, status
    except Exception as exc:
        complete_parse_job(parse_job_id, None, error=str(exc))
        return {'status': 'error', 'error': str(exc), 'parse_job_id': parse_job_id}, 500


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


def parse_resume_text_to_canonical(text: str, *, max_workers: int | None = None):
    """In-memory resume parse for tests / gold (no DB)."""
    profile_hw = detect_hardware_profile()
    workers = max_workers or min(4, max(1, profile_hw.cpu_count // 2))
    sections = detect_sections(text, 'resume')
    profile = parse_resume_from_sections(sections, text, max_workers=workers)
    profile = apply_knowledge_to_candidate(profile)
    if not _SKIP_LLM:
        unresolved = unresolved_semantic_text(sections, 'resume') or text
        profile = enrich_resume_semantic(
            profile,
            unresolved_text=unresolved,
            allow_experience_fill=bool(profile.experience),
        )
        profile = sanitize_candidate_profile(profile)
        profile = apply_knowledge_to_candidate(profile)
    else:
        # Gate: only call AI if critical gaps (fresher OK with education+skills)
        has_id = bool(profile.personal.full_name and profile.contact.email)
        has_body = bool(profile.skills and (profile.experience or profile.education))
        if not (has_id and has_body):
            unresolved = unresolved_semantic_text(sections, 'resume') or text
            profile = enrich_resume_semantic(
                profile,
                unresolved_text=unresolved,
                allow_experience_fill=bool(profile.experience),
            )
            profile = sanitize_candidate_profile(profile)
            profile = apply_knowledge_to_candidate(profile)
    form = map_candidate_to_form(profile)
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
    if not _SKIP_LLM:
        unresolved = unresolved_semantic_text(sections, 'jd') or working
        profile = enrich_jd_semantic(profile, unresolved_text=unresolved)
        profile = apply_knowledge_to_job(profile)
    else:
        if not _jd_deterministic_is_strong(profile):
            unresolved = unresolved_semantic_text(sections, 'jd') or working
            profile = enrich_jd_semantic(profile, unresolved_text=unresolved)
            profile = apply_knowledge_to_job(profile)
    profile, coverage = recover_jd_profile_gaps(profile, working)
    profile, toon = _apply_jd_repair(profile, working)
    profile, coverage = recover_jd_profile_gaps(profile, working)
    toon = job_to_toon(profile)
    form = map_job_to_form(profile, coverage=coverage.as_dicts(), raw_text=working)
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
    body = {
        'status': 'ok',
        'raw_file_id': cached['raw_file_id'],
        'parsed_id': cached['parsed_id'],
        'confidence': cached['confidence'],
        'toon': cached['toon'],
        'is_duplicate': True,
        'model_version': cached['model_version'],
        'partial': 'text-fallback' in str(cached.get('model_version') or ''),
        'parse_job_id': parse_job_id,
        'raw_text': cached.get('raw_text') or '',
        'raw_text_chars': len(cached.get('raw_text') or ''),
        'raw_text_sha256': hashlib.sha256(
            (cached.get('raw_text') or '').encode('utf-8', errors='ignore')
        ).hexdigest(),
    }
    if kind == 'resume':
        body['public_uploader_id'] = uploader_id if uploader_role == 'public' else None
    return body, 200


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
    if not cached and use_content_hash_cache and uploader_role == 'public':
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

    _emit(parse_job_id, 'layout', 'started', 'Layout + text extraction', on_stage=on_stage)
    _emit(parse_job_id, 'text', 'started', on_stage=on_stage)
    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    # PostgreSQL text columns reject NUL bytes from some PDF/DOCX extractors
    if raw_text and '\x00' in raw_text:
        raw_text = raw_text.replace('\x00', '')

    text_length = len(raw_text.strip()) if raw_text else 0
    # VALIDATION_FIX_ocr_dpi_retry
    if (not raw_text or text_length < 30) and filename.lower().rsplit('.', 1)[-1] in (
        'pdf', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp',
    ):
        try:
            raw_text = extract_text(file_data, filename, dpi=300) or ''
            if raw_text and '\x00' in raw_text:
                raw_text = raw_text.replace('\x00', '')
            text_length = len(raw_text.strip()) if raw_text else 0
            _emit(parse_job_id, 'text', 'completed', f'OCR DPI retry → {text_length} chars', on_stage=on_stage)
        except Exception as retry_err:
            _emit(parse_job_id, 'text', 'failed', f'DPI retry: {retry_err}', on_stage=on_stage)

    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
    _emit(parse_job_id, 'text', 'completed', f'Extracted {text_length} chars', on_stage=on_stage)

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

    used_llm = False
    has_id = bool(profile.personal.full_name and profile.contact.email)
    has_body = bool(profile.skills and (profile.experience or profile.education))
    _emit(parse_job_id, 'semantic', 'started', on_stage=on_stage)
    if _SKIP_LLM and has_id and has_body:
        _emit(parse_job_id, 'semantic', 'skipped', 'Deterministic coverage sufficient', on_stage=on_stage)
    else:
        unresolved = unresolved_semantic_text(sections, 'resume') or raw_text
        profile = enrich_resume_semantic(
            profile,
            unresolved_text=unresolved,
            allow_experience_fill=bool(profile.experience),
        )
        profile = sanitize_candidate_profile(profile)
        used_llm = True
        _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    profile = apply_knowledge_to_candidate(profile)
    profile = sanitize_candidate_profile(profile)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    toon = candidate_to_toon(profile)
    form = map_candidate_to_form(profile)

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
        }, 400
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'resume')
    model_version = _model_version_label()
    cache_tag = os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG', 'canonical-v5')
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
        'partial': (not is_valid),
        'missing_fields': validation_issues if not is_valid else [],
        'parse_job_id': parse_job_id,
        'raw_text': raw_text or '',
        'raw_text_chars': len(raw_text or ''),
        'raw_text_sha256': hashlib.sha256((raw_text or '').encode('utf-8', errors='ignore')).hexdigest(),
    }, 200


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

    used_llm = False
    _emit(parse_job_id, 'semantic', 'started', on_stage=on_stage)
    if _SKIP_LLM and _jd_deterministic_is_strong(profile):
        _emit(parse_job_id, 'semantic', 'skipped', on_stage=on_stage)
    else:
        unresolved = unresolved_semantic_text(sections, 'jd') or raw_text
        profile = enrich_jd_semantic(profile, unresolved_text=unresolved)
        used_llm = True
        _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    profile = apply_knowledge_to_job(profile)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    from app.ai.document_intelligence.coverage import recover_jd_profile_gaps

    _emit(parse_job_id, 'coverage', 'started', on_stage=on_stage)
    profile, coverage = recover_jd_profile_gaps(profile, raw_text)
    profile, toon = _apply_jd_repair(profile, raw_text)
    profile, coverage = recover_jd_profile_gaps(profile, raw_text)
    toon = job_to_toon(profile)
    missing_ev = coverage.missing_with_evidence
    _emit(
        parse_job_id,
        'coverage',
        'completed',
        f'recovered={len(coverage.recovered_fields)} missing_evidence={len(missing_ev)}',
        on_stage=on_stage,
    )
    form = map_job_to_form(profile, coverage=coverage.as_dicts(), raw_text=raw_text)

    _emit(parse_job_id, 'validate', 'started', on_stage=on_stage)
    is_valid, error_msg = validate_toon_format(toon, 'job_description')
    if not is_valid and not profile.basic.title:
        _emit(parse_job_id, 'validate', 'failed', error_msg or '', on_stage=on_stage)
        return {'status': 'error', 'error': f'Invalid JD parse: {error_msg}'}, 400
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'job_description')
    model_version = _model_version_label()
    cache_tag = os.getenv('DOCUMENT_INTELLIGENCE_CACHE_TAG', 'canonical-v5')
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
