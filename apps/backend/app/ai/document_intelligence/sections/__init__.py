"""Section detection for Document Intelligence — typed isolated spans."""
from __future__ import annotations

from app.ai.parser.engine.sections import (
    detect_sections,
    section_text_by_labels,
    summary_section_text,
    unresolved_semantic_text,
)
from app.ai.parser.engine.types import SectionSpan

__all__ = [
    'SectionSpan',
    'detect_sections',
    'section_text_by_labels',
    'pick_section',
    'summary_section_text',
    'unresolved_semantic_text',
]


def pick_section(sections: list[SectionSpan], *labels: str) -> str:
    """Return first matching section body (header line stripped when possible)."""
    text = section_text_by_labels(sections, *labels)
    if not text:
        return ''
    lines = text.splitlines()
    if not lines:
        return ''
    # Drop the header line itself
    first = lines[0].strip().rstrip(':').strip('*').strip()
    wanted = {lab.lower() for lab in labels}
    if first.lower() in wanted or any(first.lower().startswith(w) for w in wanted):
        return '\n'.join(lines[1:]).strip()
    return text.strip()
