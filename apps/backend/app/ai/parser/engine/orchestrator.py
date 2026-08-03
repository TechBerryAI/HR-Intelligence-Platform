"""
Intelligence Engine orchestrator.

Single entry for Resume and JD: stages emit progress events; APIs stay thin.
Reuses existing extract_text, build_*_toon, call_llm, storage — no parallel builders.
"""
from __future__ import annotations

import os
from typing import Any, Optional

from app.ai.parser.engine.confidence import (
    attach_field_provenance,
    calculate_confidence,
    prefer_deterministic_jd,
    prefer_deterministic_person,
)
from app.ai.parser.engine.hardware import apply_hardware_env
from app.ai.parser.engine.knowledge import apply_knowledge_to_jd, apply_knowledge_to_resume
from app.ai.parser.engine.progress import complete_parse_job, create_parse_job, emit_stage
from app.ai.parser.engine.sections import detect_sections, unresolved_semantic_text
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

_RESUME_SKIP_LLM = os.getenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true').lower() in (
    '1',
    'true',
    'yes',
)


def _mime_type(filename: str) -> str:
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    return MIME_TYPE_MAP.get(ext, 'application/octet-stream')


def _model_version_label() -> str:
    if os.getenv('AI_USE_GATEWAY', 'true').lower() in ('1', 'true', 'yes'):
        try:
            from app.ai.adapter.runtime_adapter import get_model_version

            return get_model_version()
        except Exception:
            return 'ai-runtime-v1'
    return f"{os.getenv('LLM_PROVIDER', 'xai')}-v1"


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
    if on_stage:
        try:
            on_stage(event)
        except Exception:
            pass


def run_intelligence_pipeline(
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
    Returns (response_dict, http_status).
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
                enrichment_context=enrichment_context,
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
    """API-compatible resume entry (thin wrapper)."""
    return run_intelligence_pipeline(
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
    """API-compatible JD entry."""
    return run_intelligence_pipeline(
        'jd',
        file_data,
        filename,
        uploader_id=uploader_id,
        uploader_role=uploader_role,
        job_id=job_id,
        parse_job_id=parse_job_id,
        on_stage=on_stage,
    )


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
    enrichment_context,
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
        # Content-hash cache for public applies (unique PUB* uploader otherwise never hits)
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
    from app.integrations.openai.llm_service import call_llm, classify_document

    _emit(parse_job_id, 'layout', 'started', 'Layout + text extraction', on_stage=on_stage)
    _emit(parse_job_id, 'text', 'started', on_stage=on_stage)
    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    text_length = len(raw_text.strip()) if raw_text else 0
    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        if text_length > 0:
            error_msg += (
                f'. Only extracted {text_length} characters. '
                'The document may be image-based (scanned) or corrupted.'
            )
        else:
            error_msg += (
                '. The document may be image-based (scanned), corrupted, '
                'or in an unsupported format.'
            )
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
    _emit(
        parse_job_id,
        'text',
        'completed',
        f'Extracted {text_length} chars',
        on_stage=on_stage,
    )
    _emit(parse_job_id, 'layout', 'completed', on_stage=on_stage)

    doc_type = classify_document(raw_text)
    if doc_type == 'unknown':
        print('[WARNING] Document type unclear, proceeding as resume')

    _emit(parse_job_id, 'sections', 'started', on_stage=on_stage)
    sections = detect_sections(raw_text, 'resume')
    semantic_text = unresolved_semantic_text(sections, 'resume') or raw_text
    _emit(
        parse_job_id,
        'sections',
        'completed',
        f'{len(sections)} sections',
        detail={'labels': [s.label for s in sections]},
        on_stage=on_stage,
    )

    from app.ai.parser.deterministic_resume import (
        experience_quality_ok,
        parse_resume_deterministic,
    )
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name
    from app.ai.parser.pipelines.resume_toon_pipeline import (
        build_resume_toon,
        log_validated_resume_toon,
    )

    llm_error = None
    toon = None
    used_text_fallback = False
    used_deterministic = False
    used_llm = False
    det_toon: dict[str, Any] = {}

    _emit(parse_job_id, 'deterministic', 'started', on_stage=on_stage)
    try:
        det_toon, _det_conf, _missing, passes = parse_resume_deterministic(raw_text)
        det_person = (
            det_toon.get('person') if isinstance(det_toon.get('person'), dict) else {}
        )
        det_name_ok = is_plausible_person_name(det_person.get('name'))
        det_has_identity = bool(
            det_name_ok and str(det_person.get('email') or '').strip()
        )
        exp_ok = experience_quality_ok(det_toon) if isinstance(det_toon, dict) else False
        public_ok = True
        if uploader_role == 'public':
            public_ok = exp_ok
        if (
            _RESUME_SKIP_LLM
            and passes
            and det_has_identity
            and public_ok
            and isinstance(det_toon, dict)
        ):
            toon = det_toon
            used_deterministic = True
            print(
                f'[INFO] Resume parse using deterministic path '
                f'(conf={_det_conf:.2f}, missing={_missing[:4]})'
            )
            _emit(
                parse_job_id,
                'deterministic',
                'completed',
                'Accepted — skipping LLM',
                on_stage=on_stage,
            )
            _emit(parse_job_id, 'semantic', 'skipped', 'Deterministic gate passed', on_stage=on_stage)
        else:
            _emit(
                parse_job_id,
                'deterministic',
                'completed',
                'Gate not passed — semantic AI required',
                on_stage=on_stage,
            )
    except Exception as det_err:
        print(f'[WARN] Deterministic resume parse failed: {det_err}')
        _emit(parse_job_id, 'deterministic', 'failed', str(det_err), on_stage=on_stage)

    if toon is None:
        _emit(parse_job_id, 'semantic', 'started', 'LLM semantic parse', on_stage=on_stage)
        try:
            # Section-scoped LLM input when shorter than full doc
            prompt_text = semantic_text if len(semantic_text) < len(raw_text) else raw_text
            # Keep contact context: prepend preamble if section-scoped
            if prompt_text is not raw_text and sections:
                preamble = next((s.text for s in sections if s.label == 'Preamble'), '')
                if preamble:
                    prompt_text = f'{preamble}\n\n{prompt_text}'
            toon = call_llm(prompt_text, 'resume', enrichment_context=enrichment_context)
            used_llm = True
            # Prefer deterministic contact over LLM hallucinations
            if isinstance(det_toon, dict) and det_toon:
                toon = prefer_deterministic_person(toon, det_toon)
            _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)
        except (KeyError, TypeError, ValueError, Exception) as e:
            llm_error = e
            print(
                f'[WARN] LLM resume parse failed ({type(e).__name__}: {e}); '
                'trying text-only fallback'
            )
            _emit(parse_job_id, 'semantic', 'failed', str(e), on_stage=on_stage)
            try:
                toon = build_resume_toon(raw_text, {}, enrichment_context)
                used_text_fallback = True
            except Exception as fallback_err:
                return {
                    'status': 'error',
                    'error': (
                        'Could not parse resume. '
                        f'LLM error: {llm_error}. Fallback error: {fallback_err}'
                    ),
                }, 400

    if not isinstance(toon, dict):
        return {'status': 'error', 'error': 'Resume parse returned invalid structure'}, 400

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    toon = apply_knowledge_to_resume(toon)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    attach_field_provenance(
        toon,
        deterministic_keys=['person.email', 'person.phone', 'person.linkedin', 'person.github']
        if used_deterministic or used_llm
        else [],
        llm_used=used_llm,
        knowledge_applied=True,
    )

    _emit(parse_job_id, 'validate', 'started', on_stage=on_stage)
    validation_issues = collect_toon_validation_issues(toon, 'resume')
    is_valid, error_msg = validate_toon_format(toon, 'resume')
    log_validated_resume_toon(
        toon,
        valid=is_valid,
        error_msg=error_msg,
        validation_issues=validation_issues,
    )

    person = toon.get('person') if isinstance(toon.get('person'), dict) else {}
    has_identity = bool(
        str(person.get('name') or '').strip() and str(person.get('email') or '').strip()
    )

    if not is_valid and not has_identity:
        _emit(parse_job_id, 'validate', 'failed', error_msg or '', on_stage=on_stage)
        return {
            'status': 'error',
            'error': f'Invalid TOON format: {error_msg or "; ".join(validation_issues)}',
            'missing_fields': validation_issues,
        }, 400

    if not is_valid and has_identity:
        print(f'[WARN] Accepting partial resume TOON after recovery: {error_msg}')
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'resume')
    if used_text_fallback:
        confidence = min(1.0, float(confidence or 0) * 0.95)
    model_version = _model_version_label()
    if used_deterministic:
        model_version = f'{model_version}+deterministic'
    elif used_text_fallback:
        model_version = f'{model_version}+text-fallback'

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
        'is_duplicate': False,
        'model_version': model_version,
        'public_uploader_id': uploader_id if uploader_role == 'public' else None,
        'partial': (not is_valid) or used_text_fallback,
        'parse_job_id': parse_job_id,
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
    from app.integrations.openai.llm_service import call_llm

    _emit(parse_job_id, 'text', 'started', on_stage=on_stage)
    try:
        raw_text = extract_text(file_data, filename)
    except Exception as e:
        _emit(parse_job_id, 'text', 'failed', str(e), on_stage=on_stage)
        return {'status': 'error', 'error': f'Text extraction failed: {str(e)}'}, 400

    text_length = len(raw_text.strip()) if raw_text else 0
    if not raw_text or text_length < 30:
        error_msg = 'Could not extract sufficient text from document'
        if text_length > 0:
            error_msg += (
                f'. Only extracted {text_length} characters. '
                'The document may be image-based (scanned) or corrupted.'
            )
        else:
            error_msg += (
                '. The document may be image-based (scanned), corrupted, '
                'or in an unsupported format.'
            )
        _emit(parse_job_id, 'text', 'failed', error_msg, on_stage=on_stage)
        return {'status': 'error', 'error': error_msg}, 400
    _emit(parse_job_id, 'text', 'completed', f'{text_length} chars', on_stage=on_stage)

    _emit(parse_job_id, 'sections', 'started', on_stage=on_stage)
    sections = detect_sections(raw_text, 'jd')
    semantic_text = unresolved_semantic_text(sections, 'jd') or raw_text
    _emit(
        parse_job_id,
        'sections',
        'completed',
        f'{len(sections)} sections',
        on_stage=on_stage,
    )

    from app.ai.parser.engine.deterministic_jd import (
        jd_skip_llm_enabled,
        parse_jd_deterministic,
    )
    from app.ai.parser.pipelines.jd_toon_pipeline import (
        build_jd_toon,
        log_validated_jd_toon,
    )

    used_text_fallback = False
    used_deterministic = False
    used_llm = False
    toon = None
    det_toon: dict[str, Any] = {}

    _emit(parse_job_id, 'deterministic', 'started', on_stage=on_stage)
    try:
        det_toon, _det_conf, _missing, passes = parse_jd_deterministic(raw_text)
        if jd_skip_llm_enabled() and passes and isinstance(det_toon, dict):
            toon = det_toon
            used_deterministic = True
            print(
                f'[INFO] JD parse using deterministic path '
                f'(conf={_det_conf:.2f}, missing={_missing[:4]})'
            )
            _emit(
                parse_job_id,
                'deterministic',
                'completed',
                'Accepted — skipping LLM',
                on_stage=on_stage,
            )
            _emit(parse_job_id, 'semantic', 'skipped', on_stage=on_stage)
        else:
            _emit(
                parse_job_id,
                'deterministic',
                'completed',
                'Gate not passed',
                on_stage=on_stage,
            )
    except Exception as det_err:
        print(f'[WARN] Deterministic JD parse failed: {det_err}')
        _emit(parse_job_id, 'deterministic', 'failed', str(det_err), on_stage=on_stage)

    if toon is None:
        _emit(parse_job_id, 'semantic', 'started', on_stage=on_stage)
        try:
            prompt_text = semantic_text if len(semantic_text) < len(raw_text) else raw_text
            toon = call_llm(prompt_text, 'jd')
            used_llm = True
            if isinstance(det_toon, dict) and det_toon:
                toon = prefer_deterministic_jd(toon, det_toon)
            _emit(parse_job_id, 'semantic', 'completed', on_stage=on_stage)
        except (KeyError, TypeError, ValueError, Exception) as e:
            print(f'[WARN] LLM JD parse failed ({type(e).__name__}: {e}); text fallback')
            _emit(parse_job_id, 'semantic', 'failed', str(e), on_stage=on_stage)
            try:
                toon = build_jd_toon(raw_text, {})
                used_text_fallback = True
            except Exception as fallback_err:
                return {
                    'status': 'error',
                    'error': (
                        'Could not parse job description. '
                        f'LLM error: {e}. Fallback error: {fallback_err}'
                    ),
                }, 400

    if not isinstance(toon, dict):
        return {
            'status': 'error',
            'error': 'Job description parse returned invalid structure',
        }, 400

    _emit(parse_job_id, 'knowledge', 'started', on_stage=on_stage)
    toon = apply_knowledge_to_jd(toon)
    _emit(parse_job_id, 'knowledge', 'completed', on_stage=on_stage)

    attach_field_provenance(
        toon,
        deterministic_keys=['title', 'location', 'salary_range', 'employment_type'],
        llm_used=used_llm,
        knowledge_applied=True,
    )

    _emit(parse_job_id, 'validate', 'started', on_stage=on_stage)
    is_valid, error_msg = validate_toon_format(toon, 'job_description')
    log_validated_jd_toon(toon, valid=is_valid, error_msg=error_msg)

    has_core = bool(
        str(toon.get('title') or '').strip()
        and (
            (isinstance(toon.get('skills'), list) and len(toon.get('skills') or []) > 0)
            or (
                isinstance(toon.get('responsibilities'), list)
                and len(toon.get('responsibilities') or []) > 0
            )
        )
    )
    # Harden: require location when soft-accepting
    has_location = bool(str(toon.get('location') or '').strip())
    if not is_valid and not has_core:
        _emit(parse_job_id, 'validate', 'failed', error_msg or '', on_stage=on_stage)
        return {
            'status': 'error',
            'error': f'Invalid TOON format: {error_msg}',
            'missing_fields': collect_toon_validation_issues(toon, 'job_description'),
        }, 400
    if not is_valid and has_core:
        if not has_location:
            # Soft-accept still allowed but mark partial and cap confidence later
            print(f'[WARN] Accepting partial JD TOON missing location: {error_msg}')
        else:
            print(f'[WARN] Accepting partial JD TOON after recovery: {error_msg}')
    _emit(parse_job_id, 'validate', 'completed', on_stage=on_stage)

    confidence = calculate_confidence(toon, 'jd')
    if used_text_fallback:
        confidence = min(1.0, float(confidence or 0) * 0.95)
    if not has_location:
        confidence = min(float(confidence or 0), 0.55)
    model_version = _model_version_label()
    if used_deterministic:
        model_version = f'{model_version}+deterministic'
    elif used_text_fallback:
        model_version = f'{model_version}+text-fallback'

    _emit(parse_job_id, 'persist', 'started', on_stage=on_stage)
    parsed_id = store_parsed_jd(
        raw_file_id,
        job_id,
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
        'is_duplicate': False,
        'model_version': model_version,
        'partial': (not is_valid) or used_text_fallback or (not has_location),
        'parse_job_id': parse_job_id,
    }, 200
