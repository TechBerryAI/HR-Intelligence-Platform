"""Section detection stage — typed SectionSpan[] from resume/JD text."""
from __future__ import annotations

from app.ai.parser.engine.types import SectionSpan
from app.ai.parser.layout.heuristic import normalize_section_header


# JD-oriented header aliases mapped to canonical labels
_JD_ALIASES = {
    'responsibilities': 'Responsibilities',
    'key responsibilities': 'Responsibilities',
    'duties': 'Responsibilities',
    'role responsibilities': 'Responsibilities',
    'requirements': 'Requirements',
    'qualifications': 'Qualifications',
    'required skills': 'Required Skills',
    'mandatory skills': 'Required Skills',
    'core skills': 'Required Skills',
    'primary skills': 'Required Skills',
    'technical skills': 'Required Skills',
    'key skills': 'Required Skills',
    'must have': 'Required Skills',
    'must-have': 'Required Skills',
    'tech stack': 'Required Skills',
    'skills': 'Skills',
    'preferred skills': 'Preferred Skills',
    'nice to have': 'Preferred Skills',
    'nice-to-have': 'Preferred Skills',
    'benefits': 'Benefits',
    'about the role': 'Summary',
    'job description': 'Summary',
    'job summary': 'Summary',
    'role overview': 'Summary',
    'overview': 'Summary',
    'position summary': 'Summary',
    'experience': 'Experience',
    'work experience': 'Experience',
    'location': 'Location',
    'work location': 'Location',
}


def detect_sections(text: str, doc_type: str = 'resume') -> list[SectionSpan]:
    """
    Split document text into typed section spans.
    Unlabeled leading content becomes section 'Preamble'.
    """
    raw = text or ''
    if not raw.strip():
        return []

    lines = raw.splitlines(keepends=True)
    # Track character offsets
    offsets: list[tuple[int, str]] = []
    pos = 0
    for line in lines:
        offsets.append((pos, line))
        pos += len(line)

    headers: list[tuple[int, int, str]] = []  # start_offset, line_end, label
    for start, line in offsets:
        stripped = line.strip()
        if not stripped:
            continue
        label = normalize_section_header(stripped)
        if not label and doc_type in ('jd', 'job_description'):
            low = stripped.lower().strip().strip(':').strip('*').strip()
            label = _JD_ALIASES.get(low)
            if not label and low.endswith(':'):
                label = _JD_ALIASES.get(low[:-1].strip())
        if label:
            headers.append((start, start + len(line), label))

    if not headers:
        return [
            SectionSpan(
                label='Preamble',
                start=0,
                end=len(raw),
                text=raw,
                source='heuristic',
            )
        ]

    spans: list[SectionSpan] = []
    # Preamble before first header
    first_start = headers[0][0]
    if first_start > 0:
        preamble = raw[:first_start]
        if preamble.strip():
            spans.append(
                SectionSpan(
                    label='Preamble',
                    start=0,
                    end=first_start,
                    text=preamble,
                    source='heuristic',
                )
            )

    for i, (h_start, h_end, label) in enumerate(headers):
        body_end = headers[i + 1][0] if i + 1 < len(headers) else len(raw)
        # Include header line + body
        section_text = raw[h_start:body_end]
        spans.append(
            SectionSpan(
                label=label,
                start=h_start,
                end=body_end,
                text=section_text,
                source='heuristic',
            )
        )

    return spans


def section_text_by_labels(sections: list[SectionSpan], *labels: str) -> str:
    """Concatenate text for sections whose labels match (case-insensitive)."""
    wanted = {lab.lower() for lab in labels}
    parts = [s.text for s in sections if s.label.lower() in wanted]
    return '\n'.join(parts).strip()


def unresolved_semantic_text(sections: list[SectionSpan], doc_type: str) -> str:
    """
    Build a reduced prompt payload for LLM: only sections that need semantic reasoning.
    Falls back to full document if no semantic sections found.
    """
    if doc_type == 'resume':
        # Never include Projects — LLM must not invent experience from project narratives
        keys = (
            'Experience',
            'Work Experience',
            'Summary',
            'Professional Summary',
            'Objective',
            'Skills',
            'Technical Skills',
            'Education',
        )
    else:
        keys = (
            'Responsibilities',
            'Requirements',
            'Qualifications',
            'Summary',
            'Preferred Skills',
            'Required Skills',
            'Skills',
        )
    text = section_text_by_labels(sections, *keys)
    if text and len(text.strip()) >= 40:
        return text
    # Fallback: everything except contact-like preamble if we have other sections
    non_preamble = [s for s in sections if s.label.lower() != 'preamble']
    if non_preamble:
        return '\n'.join(s.text for s in non_preamble).strip()
    return '\n'.join(s.text for s in sections).strip()
