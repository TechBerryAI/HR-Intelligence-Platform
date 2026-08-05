"""
Intelligence Engine orchestrator — thin re-export to Document Intelligence pipeline.

Canonical-first path lives in app.ai.document_intelligence.pipeline.
"""
from __future__ import annotations

from app.ai.document_intelligence.pipeline import (
    run_document_intelligence,
    run_intelligence_pipeline,
    run_jd_parse_pipeline,
    run_resume_parse_pipeline,
)

__all__ = [
    'run_document_intelligence',
    'run_intelligence_pipeline',
    'run_resume_parse_pipeline',
    'run_jd_parse_pipeline',
]
