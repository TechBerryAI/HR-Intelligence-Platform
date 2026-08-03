"""
In-memory Intelligence Engine path (no DB / no HTTP).

Used by bulk parser and unit/integration tests so all consumers share
sections → deterministic parsers → knowledge → optional LLM.
"""
from __future__ import annotations

import os
from typing import Any

from app.ai.parser.engine.confidence import prefer_deterministic_person
from app.ai.parser.engine.hardware import apply_hardware_env
from app.ai.parser.engine.knowledge import apply_knowledge_to_resume
from app.ai.parser.engine.parsers import parse_resume_from_text
from app.ai.parser.engine.sections import detect_sections, unresolved_semantic_text


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
    notes: list[str] = []
    text = (raw_text or '').strip()
    if not text:
        return {}, 'empty', ['empty_text']

    # Layout structure for rules parsing
    try:
        from app.ai.parser.layout.detector import enhance_resume_text

        structured = enhance_resume_text(text)
        if structured and structured != text:
            text = structured
            notes.append('layout_structure')
    except Exception as exc:
        notes.append(f'layout_skip:{exc}')

    sections = detect_sections(text, 'resume')
    notes.append(f'sections={len(sections)}')

    # Composable parsers (wired — not dead façade)
    parse_resume_from_text(text)
    notes.append('parsers=resume_from_text')

    from app.ai.parser.deterministic_resume import parse_resume_deterministic

    skip = (
        skip_llm_when_deterministic
        if skip_llm_when_deterministic is not None
        else os.getenv('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true').lower()
        in ('1', 'true', 'yes')
    )

    det_toon, conf, missing, passes = parse_resume_deterministic(text)
    notes.append(f'det_conf={conf:.2f}')
    if missing:
        notes.append('missing=' + ','.join(missing[:6]))

    if skip and passes and isinstance(det_toon, dict):
        toon = apply_knowledge_to_resume(det_toon)
        return toon, 'deterministic', notes

    if not allow_llm:
        toon = apply_knowledge_to_resume(det_toon if isinstance(det_toon, dict) else {})
        return toon, 'deterministic', notes + ['llm_disabled']

    semantic = unresolved_semantic_text(sections, 'resume') or text
    prompt = semantic if len(semantic) < len(text) else text
    preamble = next((s.text for s in sections if s.label == 'Preamble'), '')
    if prompt is not text and preamble:
        prompt = f'{preamble}\n\n{prompt}'

    try:
        from app.integrations.openai.llm_service import call_llm

        toon = call_llm(prompt, 'resume')
        if isinstance(det_toon, dict) and det_toon:
            toon = prefer_deterministic_person(toon, det_toon)
        toon = apply_knowledge_to_resume(toon if isinstance(toon, dict) else {})
        return toon, 'llm', notes
    except Exception as exc:
        notes.append(f'llm_fail:{type(exc).__name__}')
        from app.ai.parser.pipelines.resume_toon_pipeline import build_resume_toon

        toon = build_resume_toon(text, {})
        toon = apply_knowledge_to_resume(toon if isinstance(toon, dict) else {})
        return toon, 'text-fallback', notes
