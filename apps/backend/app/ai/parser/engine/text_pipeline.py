"""
In-memory Intelligence Engine path (no DB / no HTTP).

Used by bulk parser and unit/integration tests.
Canonical-first: sections → parsers → CandidateProfile → TOON serialize.
"""
from __future__ import annotations

import os
from typing import Any

from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
from app.ai.parser.engine.hardware import apply_hardware_env


def parse_resume_text_via_engine(
    raw_text: str,
    *,
    allow_llm: bool = True,
    skip_llm_when_deterministic: bool | None = None,
) -> tuple[dict[str, Any], str, list[str]]:
    """
    Run the core resume intelligence stages on already-extracted text.

    Returns (toon, source_tag, stage_notes).
    source_tag: deterministic | llm | text-fallback
    """
    apply_hardware_env()
    notes: list[str] = ['canonical_pipeline']
    text = (raw_text or '').strip()
    if not text:
        return {}, 'empty', ['empty_text']

    # Temporarily honor skip/allow via env for nested parse
    prev = os.environ.get('RESUME_SKIP_LLM_WHEN_DETERMINISTIC')
    skip = (
        skip_llm_when_deterministic
        if skip_llm_when_deterministic is not None
        else os.getenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true').lower()
        in ('1', 'true', 'yes')
    )
    if not allow_llm:
        os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = 'true'
    elif skip:
        os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = 'true'
    else:
        os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = 'false'

    try:
        # Keep engine.parsers façade reachable for audit/integration tests.
        from app.ai.parser.engine.parsers import parse_resume_from_text  # noqa: F401

        profile, _form, toon = parse_resume_text_to_canonical(text)
        has_id = bool(profile.personal.full_name and profile.contact.email)
        has_body = bool(profile.skills and (profile.experience or profile.education))
        tag = 'deterministic' if (has_id and has_body) else 'llm'
        notes.append(f'name={profile.personal.full_name!r}')
        notes.append(f'skills={len(profile.skills)}')
        notes.append(f'exp={len(profile.experience)}')
        notes.append(f'sections=canonical')
        notes.append('parsers=resume_from_text')
        return toon if isinstance(toon, dict) else {}, tag, notes
    finally:
        if prev is None:
            os.environ.pop('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', None)
        else:
            os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = prev
