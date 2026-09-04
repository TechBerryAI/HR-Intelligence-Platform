"""Shared resume text preparation — Apply and tests use the same steps."""
from __future__ import annotations

import re

_BARE_FIELD_LABEL = re.compile(
    r'(?i)^(company(?:\s+name)?|employer|organization(?:[\'’]s)?(?:\s+name)?|'
    r'organisation(?:[\'’]s)?(?:\s+name)?|client(?:\s+name)?|role|title|'
    r'designation|position|job\s+title|duration|period|tenure|dates?|'
    r'e[\-\s]?mail|email|mail|phone|mobile|mob\.?|contact|place|location|'
    r'address|linkedin|website)\s*$'
)
_COLON_ONLY_VALUE = re.compile(r'^[:\-–—]\s*(.+)$')
_DUTY_BLOCK_HEAD = re.compile(
    r'(?i)^(?:roles?\s+and\s+responsibilities|responsibilities|duties|key\s+responsibilities)\s*$'
)


def join_labeled_resume_fields(text: str) -> str:
    """Join ``Role`` / ``: value`` wraps without inventing fields."""
    if not (text or '').strip():
        return text or ''
    lines = (text or '').splitlines()
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i]
        nxt = lines[i + 1] if i + 1 < len(lines) else None
        if nxt is not None and _BARE_FIELD_LABEL.match(cur.strip()):
            n = nxt.strip()
            colon = _COLON_ONLY_VALUE.match(n)
            if colon and not _DUTY_BLOCK_HEAD.match(colon.group(1)):
                out.append(f'{cur.strip()}: {colon.group(1).strip()}')
                i += 2
                continue
            if (
                n
                and not _BARE_FIELD_LABEL.match(n)
                and not _DUTY_BLOCK_HEAD.match(n)
                and not n[:1] in '•·*●▪▸►'
                and len(n.split()) <= 12
            ):
                out.append(f'{cur.strip()}: {n}')
                i += 2
                continue
        out.append(cur)
        i += 1
    return '\n'.join(out)


def prepare_resume_working_text(
    raw_text: str,
    *,
    enhance_layout: bool = True,
    file_data: bytes | None = None,
) -> str:
    """Layout (optional) → glued-heading split → normalize → bullet restore.

    This is the single preprocessing path for Apply ``_run_resume`` and
    ``parse_resume_text_to_canonical``.
    """
    from app.ai.document_intelligence.layout_doc import normalize_extracted_resume_text

    text = raw_text or ''
    if file_data:
        try:
            from app.ai.document_intelligence.layout_doc import maybe_reorder_two_column

            reordered = maybe_reorder_two_column(text, file_data)
            if reordered and len(reordered.strip()) >= 30:
                text = reordered
        except Exception:
            pass
    if enhance_layout:
        try:
            from app.ai.parser.layout.detector import enhance_resume_text, is_layout_enabled

            if is_layout_enabled():
                structured = enhance_resume_text(text)
                if structured and len(structured.strip()) >= 30:
                    text = structured
        except Exception:
            pass
    try:
        from app.ai.parser.layout.heuristic import (
            compact_letter_spaced_section_headings,
            separate_glued_resume_headings,
        )

        text = compact_letter_spaced_section_headings(text)
        text = separate_glued_resume_headings(text)
    except Exception:
        pass
    try:
        text = join_labeled_resume_fields(text)
    except Exception:
        pass
    return normalize_extracted_resume_text(text)
