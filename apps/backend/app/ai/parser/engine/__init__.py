"""
Human Capital Intelligence Engine.

Single orchestrated pipeline for Resume and JD parsing:
Document → Layout → Text → Sections → Deterministic parsers →
Knowledge → Semantic AI (gaps only) → TOON → Validate → Persist.
"""
from app.ai.parser.engine.orchestrator import (
    run_intelligence_pipeline,
    run_jd_parse_pipeline,
    run_resume_parse_pipeline,
)
from app.ai.parser.engine.progress import (
    get_parse_job,
    list_stage_events,
)
from app.ai.parser.engine.text_pipeline import parse_resume_text_via_engine
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
