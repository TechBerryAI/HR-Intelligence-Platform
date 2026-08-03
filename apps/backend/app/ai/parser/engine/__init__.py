"""
Human Capital Intelligence Engine.

Canonical-first Document Intelligence pipeline for Resume and JD parsing.
"""
from __future__ import annotations

from app.ai.parser.engine.progress import (
    get_parse_job,
    list_stage_events,
)
from app.ai.parser.engine.types import SectionSpan, StageEvent

__all__ = [
    'run_intelligence_pipeline',
    'run_resume_parse_pipeline',
    'run_jd_parse_pipeline',
    'parse_resume_text_via_engine',
    'get_parse_job',
    'list_stage_events',
    'SectionSpan',
    'StageEvent',
]


def __getattr__(name: str):
    if name in (
        'run_intelligence_pipeline',
        'run_resume_parse_pipeline',
        'run_jd_parse_pipeline',
    ):
        from app.ai.document_intelligence import pipeline as _pipeline

        return getattr(_pipeline, name)
    if name == 'parse_resume_text_via_engine':
        from app.ai.parser.engine.text_pipeline import parse_resume_text_via_engine

        return parse_resume_text_via_engine
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
