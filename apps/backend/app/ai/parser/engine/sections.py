"""Section detection stage — typed SectionSpan[] from resume/JD text."""
from __future__ import annotations

import re

from app.ai.parser.engine.types import SectionSpan
from app.ai.parser.layout.heuristic import normalize_section_header
from app.ai.parser.enrichment.resume_text_inference import is_in_job_contact_header


_CONTENT_LABELS = frozenset({'experience', 'education', 'skills'})
_EVIDENCE_SIDEBAR_LABELS = frozenset({
    'personal details',
    'personal information',
    'contact',
    'contact details',
    'achievements',
    'activities',
    'declaration',
    'hobbies',
    'strengths',
})
_DEDUP_LABELS = frozenset({
    'experience',
    'education',
    'skills',
    'certifications',
    'projects',
    'project',
    'summary',
})
_SHORT_BODY_CHARS = 40
_TOKEN_RE = re.compile(r'[a-z0-9]{2,}')


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


def _label_key(label: str) -> str:
    return (label or '').strip().lower()


def _span_body(span: SectionSpan) -> str:
    lines = (span.text or '').splitlines()
    if not lines:
        return ''
    first = lines[0].strip().rstrip(':').strip('*').strip()
    if first.lower() == _label_key(span.label) or first.lower().startswith(_label_key(span.label)):
        return '\n'.join(lines[1:]).strip()
    return (span.text or '').strip()


def _body_len(span: SectionSpan) -> int:
    return len(_span_body(span))


def _tokens(text: str) -> set[str]:
    return set(_TOKEN_RE.findall((text or '').lower()))


def _is_near_duplicate_body(later: str, earlier: str) -> bool:
    """True when later body is essentially a two-column echo of earlier."""
    later_body = (later or '').strip()
    earlier_body = (earlier or '').strip()
    if not later_body:
        return True
    later_tok = _tokens(later_body)
    earlier_tok = _tokens(earlier_body)
    if not later_tok:
        return True
    if not earlier_tok:
        return False
    overlap = len(later_tok & earlier_tok) / len(later_tok)
    extra = later_tok - earlier_tok
    return overlap >= 0.85 and len(extra) <= 3


def _content_needs_evidence(spans: list[SectionSpan], label: str) -> bool:
    matches = [s for s in spans if _label_key(s.label) == label]
    if not matches:
        return True
    return all(_body_len(s) < _SHORT_BODY_CHARS for s in matches)


def _heal_resume_sections(spans: list[SectionSpan], raw: str) -> list[SectionSpan]:
    """Preserve uncertain boundaries as Unclassified instead of dropping lines.

    Two-column near-duplicates are kept as Unclassified evidence rather than
    parsed twice. Missing or short Skills/Education copy sidebar lines into
    Unclassified; unlabeled preamble is copied when Experience is missing.
    Downstream parsers may recover Skills/Education from that evidence —
    Experience is never synthesized from it.
    """
    if not spans:
        return spans

    # Two-column echoes: keep unique extras; demote near-subsets.
    seen_bodies: dict[str, str] = {}
    deduped: list[SectionSpan] = []
    for span in spans:
        key = _label_key(span.label)
        if key not in _DEDUP_LABELS:
            deduped.append(span)
            continue
        body = _span_body(span)
        prior = seen_bodies.get(key)
        if prior is not None and _is_near_duplicate_body(body, prior):
            deduped.append(
                SectionSpan(
                    label='Unclassified',
                    start=span.start,
                    end=span.end,
                    text=span.text,
                    source='uncertain',
                )
            )
            continue
        if key not in seen_bodies or len(body) > len(seen_bodies[key]):
            seen_bodies[key] = body
        deduped.append(span)

    need_skills = _content_needs_evidence(deduped, 'skills')
    need_edu = _content_needs_evidence(deduped, 'education')
    has_experience = any(_label_key(s.label) == 'experience' for s in deduped)
    headerless = not any(_label_key(s.label) in _CONTENT_LABELS for s in deduped)
    copy_preamble = (not has_experience) or headerless
    already = '\n'.join(
        s.text for s in deduped
        if _label_key(s.label) == 'unclassified' and (s.text or '').strip()
    )

    def _emit(parts: list[tuple[SectionSpan, str]], source: str) -> None:
        blobs = [blob for _, blob in parts if blob]
        if not blobs:
            return
        evidence = '\n'.join(blobs).strip()
        if not evidence or evidence in already:
            return
        starts = [span.start for span, _ in parts]
        ends = [span.end for span, _ in parts]
        deduped.append(
            SectionSpan(
                label='Unclassified',
                start=min(starts) if starts else 0,
                end=max(ends) if ends else len(raw),
                text=evidence,
                source=source,
            )
        )

    if need_skills or need_edu:
        sidebar: list[tuple[SectionSpan, str]] = []
        for span in deduped:
            if _label_key(span.label) not in _EVIDENCE_SIDEBAR_LABELS:
                continue
            blob = (span.text or '').strip()
            if blob:
                sidebar.append((span, blob))
        _emit(sidebar, 'uncertain')

    if copy_preamble:
        preamble_parts: list[tuple[SectionSpan, str]] = []
        for span in deduped:
            if _label_key(span.label) != 'preamble':
                continue
            blob = (span.text or '').strip()
            if blob:
                preamble_parts.append((span, blob))
        # Preserve unlabeled lines; parsers must not treat this as Skills/Education.
        _emit(preamble_parts, 'unclassified-preamble')

    return deduped


def detect_sections(text: str, doc_type: str = 'resume') -> list[SectionSpan]:
    """
    Split document text into typed section spans.
    Unlabeled leading content becomes section 'Preamble'.
    Weak/uncertain resume boundaries are preserved as 'Unclassified'
    rather than discarded.
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
            # In-job Contact/References must not split Experience
            if headers and is_in_job_contact_header(label, headers[-1][2]):
                continue
            headers.append((start, start + len(line), label))

    if not headers:
        preamble = SectionSpan(
            label='Preamble',
            start=0,
            end=len(raw),
            text=raw,
            source='heuristic',
        )
        if doc_type == 'resume':
            return _heal_resume_sections([preamble], raw)
        return [preamble]

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
        body_only = raw[h_end:body_end].strip()
        source = 'heuristic'
        if label in {'Skills', 'Education', 'Experience'} and len(body_only) < _SHORT_BODY_CHARS:
            # Header-only / crumb sections stay visible as uncertain evidence.
            # Parsers must harvest rather than discard the body.
            source = 'uncertain'
        spans.append(
            SectionSpan(
                label=label,
                start=h_start,
                end=body_end,
                text=section_text,
                source=source,
            )
        )

    if doc_type == 'resume':
        return _heal_resume_sections(spans, raw)
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
    Never includes Contact / Preamble contact blocks — those pollute summary/experience.
    """
    _CONTACTISH = {
        'contact', 'contact details', 'personal details', 'personal information',
        'biodata', 'bio data', 'preamble',
    }
    if doc_type == 'resume':
        # Never include Projects — LLM must not invent experience from project narratives
        keys = (
            'Experience',
            'Work Experience',
            'Internship',
            'Internships',
            'Summary',
            'Professional Summary',
            'Career Objective',
            'Profile Summary',
            'Objective',
            'Profile',
            'About Me',
            'Career Profile',
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
    # Fallback: everything except contact-like / preamble sections
    non_contact = [
        s for s in sections
        if s.label.lower() not in _CONTACTISH
    ]
    if non_contact:
        return '\n'.join(s.text for s in non_contact).strip()
    return '\n'.join(s.text for s in sections).strip()


def summary_section_text(sections: list[SectionSpan]) -> str:
    """Return only summary/objective section bodies for LLM cleanup."""
    return section_text_by_labels(
        sections,
        'Summary',
        'Professional Summary',
        'Career Objective',
        'Profile Summary',
        'Objective',
        'Profile',
        'About Me',
        'Career Profile',
        'Career Summary',
    )
