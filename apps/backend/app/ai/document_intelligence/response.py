"""
Client response builders.

Frontend receives Form DTOs only. Raw TOON is stripped from client payloads
(kept in DB for ATS). Internal callers may still access `toon` via attach_form_dto.
"""
from __future__ import annotations

from typing import Any

from app.ai.document_intelligence.canonical.from_toon import (
    candidate_profile_from_toon,
    job_profile_from_toon,
)
from app.ai.document_intelligence.mapping.jd_form import map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.models.job import JobProfile


def attach_form_dto(body: dict[str, Any], doc_kind: str) -> dict[str, Any]:
    """
    Attach canonical + form DTO to an engine response body.
    Prefer precomputed canonical/form from the pipeline when present.
    """
    out = dict(body)
    if out.get('form') and out.get('canonical'):
        return out

    if isinstance(out.get('canonical'), dict) and not out.get('form'):
        if doc_kind == 'resume':
            profile = CandidateProfile.model_validate(out['canonical'])
            out['form'] = map_candidate_to_form(profile).to_autofill_dict()
        else:
            profile = JobProfile.model_validate(out['canonical'])
            out['form'] = map_job_to_form(profile).to_autofill_dict()
        return out

    toon = out.get('toon')
    if not isinstance(toon, dict):
        out['form'] = out.get('form')
        out['canonical'] = out.get('canonical')
        return out

    if doc_kind == 'resume':
        profile = candidate_profile_from_toon(toon)
        form = map_candidate_to_form(profile)
        out['canonical'] = profile.model_dump()
        out['form'] = form.to_autofill_dict()
    else:
        profile = job_profile_from_toon(toon)
        form = map_job_to_form(profile)
        out['canonical'] = profile.model_dump()
        out['form'] = form.to_autofill_dict()
    return out


def build_resume_client_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Public/API payload for React — Form DTO only (no raw TOON)."""
    enriched = attach_form_dto(body, 'resume')
    return {
        'status': enriched.get('status'),
        'raw_file_id': enriched.get('raw_file_id'),
        'parsed_id': enriched.get('parsed_id'),
        'confidence': enriched.get('confidence'),
        'form': enriched.get('form'),
        'is_duplicate': enriched.get('is_duplicate'),
        'model_version': enriched.get('model_version'),
        'public_uploader_id': enriched.get('public_uploader_id'),
        'partial': enriched.get('partial'),
        'parse_job_id': enriched.get('parse_job_id'),
        'error': enriched.get('error'),
        'missing_fields': enriched.get('missing_fields'),
        'engine': 'document_intelligence',
        'schema_version': '1.0.0',
    }


def build_jd_client_payload(body: dict[str, Any]) -> dict[str, Any]:
    """Recruiter API payload for React — Form DTO only (no raw TOON)."""
    enriched = attach_form_dto(body, 'jd')
    form = enriched.get('form') or {}
    coverage = enriched.get('coverage') or form.get('coverage') or []
    return {
        'status': enriched.get('status'),
        'raw_file_id': enriched.get('raw_file_id'),
        'parsed_id': enriched.get('parsed_id'),
        'confidence': enriched.get('confidence'),
        'form': form,
        'is_duplicate': enriched.get('is_duplicate'),
        'model_version': enriched.get('model_version'),
        'partial': enriched.get('partial'),
        'parse_job_id': enriched.get('parse_job_id'),
        'error': enriched.get('error'),
        'missing_fields': enriched.get('missing_fields') or [],
        'coverage': coverage,
        'engine': 'document_intelligence',
        'schema_version': '1.0.0',
    }
