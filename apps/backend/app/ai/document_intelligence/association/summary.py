"""Summary boundary: keep professional prose, drop header/contact bleed."""
from __future__ import annotations

import re

from app.ai.document_intelligence.association.evidence import Evidence
from app.ai.document_intelligence.association.taxonomy import FIELD_CONTAMINATION
from app.ai.parser.enrichment.resume_text_inference import (
    _is_contactish_summary_line,
    _normalize_summary_body,
    is_valid_summary,
)

_CONTACT_TOKEN = re.compile(
    r'(?i)\b(?:email|phone|mobile|linkedin|github|portfolio|address)\s*:'
    r'|[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}'
    r'|(?:https?://)?(?:www\.)?linkedin\.com/\S+'
    r'|\+?\d[\d\s\-()]{8,}\d',
    re.I,
)
_SUMMARY_CUE = re.compile(
    r'(?i)\b(?:seeking|years?|professional|skilled|dedicated|motivated|'
    r'aspiring|objective|experience\s+as|proficient|graduate|summary|'
    r'results?-driven|seasoned)\b'
)


def associate_summary(
    summary: str,
    *,
    contact_email: str = '',
    contact_phone: str = '',
    contact_linkedin: str = '',
    location: str = '',
    full_name: str = '',
    report: list[dict] | None = None,
) -> str:
    raw = (summary or '').strip()
    if not raw:
        return ''
    cleaned = _normalize_summary_body(raw, max_len=2000)
    kept: list[str] = []
    for line in cleaned.splitlines():
        s = line.strip()
        if not s:
            continue
        if _is_contactish_summary_line(s):
            continue
        if _CONTACT_TOKEN.search(s):
            continue
        if contact_email and contact_email.lower() in s.lower():
            continue
        if contact_phone and _digits(contact_phone) and _digits(contact_phone) in _digits(s):
            continue
        if contact_linkedin and contact_linkedin.lower() in s.lower():
            continue
        if location and s.lower() == location.lower():
            continue
        if full_name and s.lower() == full_name.lower():
            continue
        kept.append(s)
    out = '\n'.join(kept).strip()
    if out and not is_valid_summary(out):
        out = ''
    if out and not _SUMMARY_CUE.search(out) and _CONTACT_TOKEN.search(raw):
        # Name + leftover paragraph without summary evidence is not a summary.
        if len(out.split()) < 12:
            out = ''
    evidence = Evidence()
    evidence.add('section_boundary')
    if out != raw:
        evidence.add('explicit_label', 'stripped contact/header from summary')
        if report is not None:
            report.append(
                {
                    'field': 'summary',
                    'action': 'scrub' if out else 'clear',
                    'taxonomy': FIELD_CONTAMINATION if raw and not out else None,
                    'evidence': evidence.as_dict(),
                }
            )
    elif report is not None:
        report.append({'field': 'summary', 'action': 'keep', 'evidence': evidence.as_dict()})
    return out


def _digits(value: str) -> str:
    return re.sub(r'\D+', '', value or '')
