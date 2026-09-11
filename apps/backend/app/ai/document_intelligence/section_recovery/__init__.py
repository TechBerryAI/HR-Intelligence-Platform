"""Experience section recovery / reading-order layer.

Runs after detect_sections and before section parsers. Rebinds section
ownership; does not construct company/role/date records.
"""
from __future__ import annotations

from app.ai.document_intelligence.section_recovery.evidence import (
    OwnershipScore,
    heading_label,
    is_duty_or_continuation,
    is_employment_record_start,
    is_summary_prose_line,
    score_experience_ownership,
    score_native_label,
)
from app.ai.parser.engine.types import SectionSpan

# Donors that commonly swallow Experience bodies after two-column / OCR order.
_DONOR_LABELS = frozenset({
    'unclassified',
    'summary',
    'projects',
    'project',
    'certifications',
    'certificates',
    'languages',
    'skills',
})
# Move only when ownership is clearly Experience and not the donor's native type.
_SCORE_FLOOR = 0.45
_SIGNAL_FLOOR = 2
_THIN_BODY = 80
_STRONG_EXISTING = 0.45


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


def recover_resume_sections(
    sections: list[SectionSpan],
    source_text: str = '',
) -> tuple[list[SectionSpan], dict]:
    """Return sections with Experience ownership repaired when evidence is strong.

    Ambiguous blobs stay on their original label (usually Unclassified).
    """
    report: dict = {
        'actions': [],
        'skipped': [],
    }
    if not sections:
        return sections, report

    out = [SectionSpan(
        label=s.label,
        start=s.start,
        end=s.end,
        text=s.text,
        source=s.source,
    ) for s in sections]

    existing_body = _experience_body(out)
    existing_score = score_experience_ownership(existing_body)
    if existing_body and existing_score.score >= _STRONG_EXISTING and len(existing_body) >= _THIN_BODY:
        report['skipped'].append({
            'reason': 'existing_experience_span_strong',
            'score': round(existing_score.score, 3),
            'signals': existing_score.signals,
        })
        return out, report

    has_heading = _has_experience_heading(out, source_text)
    recovered_parts: list[str] = []
    recovered_signals: list[str] = []
    source_indexes: list[int] = []

    for i, span in enumerate(out):
        key = _label_key(span.label)
        if key not in _DONOR_LABELS:
            continue
        body = _span_body(span)
        if not body or len(body.strip()) < 40:
            continue
        split_at = _transition_index(body, prefer_heading=True)
        taken = ''
        remainder = body
        evidence: list[str] = []
        if split_at is not None:
            lines = body.splitlines()
            prefix = '\n'.join(lines[:split_at]).strip()
            suffix = '\n'.join(lines[split_at:]).strip()
            suffix_score = score_experience_ownership(suffix)
            native_suffix = score_native_label(suffix, span.label)
            if _accept(suffix_score, native_suffix, has_heading=True):
                taken = suffix
                remainder = prefix
                evidence = ['section_transition'] + suffix_score.signals
                if 'experience_heading' not in evidence and heading_label(lines[split_at]) == 'Experience':
                    evidence.append('experience_heading')

        if not taken:
            # Whole-donor or employment windows, only if Experience heading exists
            # or a nested heading was already required above.
            if not has_heading:
                report['skipped'].append({
                    'index': i,
                    'label': span.label,
                    'reason': 'no_experience_heading',
                })
                continue
            windows = _employment_windows(body)
            blob = '\n'.join(windows).strip() if windows else ''
            use = blob or body
            score = score_experience_ownership(use)
            native = score_native_label(use, span.label)
            follows = _immediately_follows_experience(out, i)
            if follows:
                score.add('document_order', 0.10)
            if _accept(score, native, has_heading=has_heading):
                taken = use
                remainder = _subtract_text(body, use)
                evidence = score.signals[:]
                if follows:
                    evidence.append('document_order')

        if not taken:
            continue
        recovered_parts.append(taken)
        recovered_signals.extend(evidence)
        source_indexes.append(i)
        new_text = _repack_span(span, remainder)
        out[i] = SectionSpan(
            label=span.label if remainder.strip() else 'Unclassified',
            start=span.start,
            end=span.end,
            text=new_text if remainder.strip() else remainder,
            source='recovery',
        )
        report['actions'].append({
            'section': 'experience',
            'source_blocks': [i],
            'donor_label': span.label,
            'confidence': round(score_experience_ownership(taken).score, 3),
            'evidence': evidence,
        })

    if not recovered_parts:
        return out, report

    merged = '\n'.join(p for p in recovered_parts if p.strip()).strip()
    out = _attach_experience(out, merged)
    report['recovered_chars'] = len(merged)
    report['source_blocks'] = source_indexes
    report['evidence'] = list(dict.fromkeys(recovered_signals))
    return out, report


def _accept(score: OwnershipScore, native: float, *, has_heading: bool) -> bool:
    if score.score < _SCORE_FLOOR:
        return False
    if len([s for s in score.signals if s not in {'certification_like', 'education_like', 'skill_list_like'}]) < _SIGNAL_FLOOR:
        if 'experience_heading' not in score.signals:
            return False
    if native >= score.score and 'experience_heading' not in score.signals:
        return False
    if not has_heading and 'experience_heading' not in score.signals:
        return False
    return True


def _experience_body(sections: list[SectionSpan]) -> str:
    parts = [_span_body(s) for s in sections if _label_key(s.label) == 'experience']
    return '\n'.join(p for p in parts if p).strip()


def _has_experience_heading(sections: list[SectionSpan], source_text: str) -> bool:
    if any(_label_key(s.label) == 'experience' for s in sections):
        return True
    for span in sections:
        for ln in (span.text or '').splitlines():
            if heading_label(ln) == 'Experience':
                return True
    for ln in (source_text or '').splitlines()[:80]:
        if heading_label(ln) == 'Experience':
            return True
    return False


def _immediately_follows_experience(sections: list[SectionSpan], index: int) -> bool:
    for j in range(index - 1, -1, -1):
        key = _label_key(sections[j].label)
        if key == 'experience':
            return True
        if key in _DONOR_LABELS or key in {'preamble', 'unclassified'}:
            continue
        if len(_span_body(sections[j])) < 40:
            continue
        return False
    return False


def _transition_index(body: str, *, prefer_heading: bool) -> int | None:
    lines = (body or '').splitlines()
    if prefer_heading:
        for i, ln in enumerate(lines):
            if i == 0:
                continue
            if heading_label(ln) == 'Experience':
                return i
    prose = 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if is_summary_prose_line(s):
            prose += 1
            continue
        if prose >= 1 and is_employment_record_start(s, _next_nonempty(lines, i)):
            window = '\n'.join(x for x in lines[i:] if x.strip())
            if score_experience_ownership(window).score >= _SCORE_FLOOR:
                return i
    return None


def _next_nonempty(lines: list[str], index: int) -> str:
    for ln in lines[index + 1 :]:
        if ln.strip():
            return ln.strip()
    return ''


def _employment_windows(text: str) -> list[str]:
    lines = (text or '').splitlines()
    windows: list[list[str]] = []
    current: list[str] = []
    for i, ln in enumerate(lines):
        s = ln.strip()
        nxt = _next_nonempty(lines, i)
        if not s:
            if current:
                current.append('')
            continue
        if heading_label(s) in {'Education', 'Skills', 'Summary', 'Certifications', 'Projects'}:
            if current:
                windows.append(current)
                current = []
            continue
        if current:
            if is_duty_or_continuation(s) or is_employment_record_start(s, nxt):
                current.append(ln)
                continue
            windows.append(current)
            current = []
        if is_employment_record_start(s, nxt):
            current = [ln]
    if current:
        windows.append(current)
    kept: list[str] = []
    for w in windows:
        blob = '\n'.join(w).strip()
        if not blob:
            continue
        sc = score_experience_ownership(blob)
        if sc.score >= 0.40 and len(sc.signals) >= 2:
            kept.append(blob)
    if len(windows) >= 1:
        # One contiguous ownership region: first start through last related line,
        # including duty lines that sat above the first company header.
        first_i = None
        last_i = None
        for i, ln in enumerate(lines):
            s = ln.strip()
            nxt = _next_nonempty(lines, i)
            if not s:
                continue
            if heading_label(s) in {'Education', 'Skills', 'Summary', 'Certifications', 'Projects'}:
                if first_i is not None:
                    break
                continue
            if is_employment_record_start(s, nxt) or (
                first_i is not None and is_duty_or_continuation(s)
            ):
                if first_i is None:
                    first_i = i
                last_i = i
        if first_i is not None:
            j = first_i - 1
            while j >= 0:
                s = lines[j].strip()
                if not s:
                    j -= 1
                    continue
                if is_duty_or_continuation(s) and not heading_label(s):
                    first_i = j
                    j -= 1
                    continue
                break
            region = '\n'.join(lines[first_i: last_i + 1]).strip()
            sc = score_experience_ownership(region)
            if sc.score >= 0.40:
                return [region]
    return kept


def _subtract_text(original: str, taken: str) -> str:
    if not taken:
        return original
    if taken in original:
        return original.replace(taken, '', 1).strip()
    taken_lines = set(ln.strip() for ln in taken.splitlines() if ln.strip())
    kept = [ln for ln in original.splitlines() if ln.strip() not in taken_lines]
    return '\n'.join(kept).strip()


def _repack_span(span: SectionSpan, remainder: str) -> str:
    lines = (span.text or '').splitlines()
    header = lines[0] if lines else span.label
    first = header.strip().rstrip(':').strip('*').strip()
    if first.lower() == _label_key(span.label) or first.lower().startswith(_label_key(span.label)):
        if not remainder.strip():
            return header
        return header + '\n' + remainder
    return remainder


def _attach_experience(sections: list[SectionSpan], body: str) -> list[SectionSpan]:
    blob = (body or '').strip()
    if not blob:
        return sections
    if not blob.lower().lstrip().startswith('experience'):
        blob = 'Experience\n' + blob
    for i, span in enumerate(sections):
        if _label_key(span.label) != 'experience':
            continue
        existing = _span_body(span)
        if existing and existing.strip() and existing.strip() not in blob:
            merged = f'Experience\n{existing.strip()}\n{body}'.strip()
        else:
            merged = blob
        sections[i] = SectionSpan(
            label='Experience',
            start=span.start,
            end=span.end,
            text=merged,
            source='recovery',
        )
        return sections
    sections.append(
        SectionSpan(
            label='Experience',
            start=0,
            end=len(blob),
            text=blob,
            source='recovery',
        )
    )
    return sections
