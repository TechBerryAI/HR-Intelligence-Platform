"""
Document Intelligence Engine — public API.

Canonical models, Form DTOs, explicit form mapping, and canonical-first pipeline.
Frontend clients must consume Form DTOs only — never raw AI/TOON.
"""
from __future__ import annotations

from app.ai.document_intelligence.canonical.from_toon import (
    candidate_profile_from_toon,
    job_profile_from_toon,
    toon_from_candidate_profile,
    toon_from_job_profile,
)
from app.ai.document_intelligence.mapping.jd_form import map_job_to_form
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.models.fields import TraceableField
from app.ai.document_intelligence.models.form_dtos import ApplicationFormDTO, JobCreateFormDTO
from app.ai.document_intelligence.models.job import JobProfile
from app.ai.document_intelligence.pipeline import (
    parse_jd_text_to_canonical,
    parse_resume_text_to_canonical,
    run_document_intelligence,
    run_jd_parse_pipeline,
    run_resume_parse_pipeline,
)
from app.ai.document_intelligence.response import (
    attach_form_dto,
    build_jd_client_payload,
    build_resume_client_payload,
)

__all__ = [
    'ApplicationFormDTO',
    'CandidateProfile',
    'JobCreateFormDTO',
    'JobProfile',
    'TraceableField',
    'attach_form_dto',
    'build_jd_client_payload',
    'build_resume_client_payload',
    'candidate_profile_from_toon',
    'job_profile_from_toon',
    'map_candidate_to_form',
    'map_job_to_form',
    'parse_jd_text_to_canonical',
    'parse_resume_text_to_canonical',
    'run_document_intelligence',
    'run_jd_parse_pipeline',
    'run_resume_parse_pipeline',
    'toon_from_candidate_profile',
    'toon_from_job_profile',
]
