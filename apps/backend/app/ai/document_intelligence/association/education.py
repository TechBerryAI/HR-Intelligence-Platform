"""Education entity reconstruction with cross-record isolation.

Does not invent a degree from an institution, a field of study, or dates
that belong to a neighboring education record.
"""
from __future__ import annotations

import re

from app.ai.document_intelligence.association.evidence import Evidence, contains_normalized, overlap_ratio
from app.ai.document_intelligence.association.taxonomy import CROSS_RECORD_LEAK, UNSUPPORTED_INFERENCE
from app.ai.document_intelligence.deterministic import extract_date_range
from app.ai.document_intelligence.models.candidate import EducationEntry
from app.ai.document_intelligence.parsers.resume import _looks_like_degree_line

_SECTION_HEADING = re.compile(
    r'(?i)^(?:education|academic(?:\s+background|\s+qualifications?)?|'
    r'educational\s+(?:qualifications?|background)|qualifications|'
    r'scholastic\s+record|academics)\s*:?\s*$'
)
_GENERIC_DEGREE = re.compile(
    r"(?i)^(bachelor'?s?(?:\s+degree)?|master'?s?(?:\s+degree)?|"
    r'degree|education|graduate|diploma)$'
)
_YEAR = re.compile(r'(?:19|20)\d{2}')


def associate_education(
    entries: list[EducationEntry],
    section_text: str,
    *,
    report: list[dict] | None = None,
) -> list[EducationEntry]:
    if not entries:
        return entries
    blocks = split_education_blocks(section_text)
    out: list[EducationEntry] = []
    used: set[int] = set()
    for idx, entry in enumerate(entries):
        if len(blocks) >= 2:
            block_i = _best_edu_block(entry, blocks, used)
        else:
            block_i = 0 if blocks else None
        block = blocks[block_i] if block_i is not None and block_i < len(blocks) else None
        if block_i is not None:
            used.add(block_i)
        updated, evidence, taxonomy = _rebind_education(entry, block, blocks, section_text)
        out.append(updated)
        if report is not None:
            report.append(
                {
                    'index': idx,
                    'action': 'rebind' if updated != entry else 'keep',
                    'taxonomy': taxonomy,
                    'evidence': evidence.as_dict(),
                }
            )
    return out


def split_education_blocks(section_text: str) -> list[dict]:
    lines = [(ln or '').strip() for ln in (section_text or '').splitlines()]
    lines = [ln for ln in lines if ln]
    while lines and _SECTION_HEADING.match(lines[0]):
        lines = lines[1:]
    if not lines:
        return []
    blocks: list[list[str]] = []
    current: list[str] = []
    for ln in lines:
        if current and _looks_like_degree_line(ln):
            already_has_degree = any(_looks_like_degree_line(x) for x in current)
            if already_has_degree:
                blocks.append(current)
                current = [ln]
                continue
        current.append(ln)
    if current:
        blocks.append(current)
    return [_edu_block(b) for b in blocks]


def _edu_block(lines: list[str]) -> dict:
    raw = '\n'.join(lines)
    degree = next((ln for ln in lines if _looks_like_degree_line(ln)), '')
    start, end = '', ''
    for ln in lines:
        s, e = extract_date_range(ln)
        if s and not e:
            end, s = s, ''
        start = start or s
        end = end or e
        years = _YEAR.findall(ln)
        if years and not end:
            end = years[-1]
            if len(years) >= 2 and not start:
                start = years[0]
    institution = ''
    field = ''
    for ln in lines:
        if ln == degree:
            continue
        if extract_date_range(ln)[0] and len(ln.split()) <= 4:
            continue
        if re.search(r'(?i)\b(?:university|college|institute|school|vidyalaya|board)\b', ln):
            institution = institution or ln
            continue
        if not field and not _looks_like_degree_line(ln) and len(ln.split()) <= 6:
            field = ln
    return {
        'raw': raw,
        'lines': lines,
        'degree': degree,
        'institution': institution,
        'field': field,
        'start': start,
        'end': end,
    }


def _best_edu_block(
    entry: EducationEntry,
    blocks: list[dict],
    used: set[int],
) -> int | None:
    degree = (entry.degree or '').strip()
    institution = (entry.institution or '').strip()
    best_i, best = None, 0.12
    for i, block in enumerate(blocks):
        if i in used:
            continue
        if degree:
            score = max(
                overlap_ratio(degree, block.get('degree') or ''),
                overlap_ratio(degree, block.get('raw') or '') * 0.8,
            )
            # Institution is only a tie-break — it may already be misassociated.
            score += 0.15 * overlap_ratio(institution, block.get('institution') or '')
        else:
            score = overlap_ratio(institution, block.get('institution') or block.get('raw') or '')
        if score > best:
            best, best_i = score, i
    if best_i is not None:
        return best_i
    for i in range(len(blocks)):
        if i not in used:
            return i
    return None


def _rebind_education(
    entry: EducationEntry,
    block: dict | None,
    blocks: list[dict],
    section_text: str,
) -> tuple[EducationEntry, Evidence, str | None]:
    evidence = Evidence()
    evidence.add('section_boundary')
    taxonomy = None
    updates: dict = {}
    source = (block or {}).get('raw') or section_text or ''

    degree = (entry.degree or '').strip()
    if degree and _GENERIC_DEGREE.match(degree) and not _value_supported(degree, section_text):
        updates['degree'] = ''
        taxonomy = UNSUPPORTED_INFERENCE
        evidence.add('entity_pattern', 'cleared unsupported generic degree')
    field = (entry.field or '').strip()
    if field and not _value_supported(field, section_text):
        updates['field'] = ''
        taxonomy = taxonomy or UNSUPPORTED_INFERENCE

    if block:
        evidence.add('same_block')
        evidence.add('record_boundary')
        b_end = (block.get('end') or '').strip()
        b_start = (block.get('start') or '').strip()
        cur_end = (entry.end or '').strip()
        cur_start = (entry.start or '').strip()
        if cur_end and b_end and _value_owned_elsewhere(cur_end[:4], block, blocks):
            updates['end'] = b_end
            taxonomy = taxonomy or CROSS_RECORD_LEAK
            evidence.add('date_proximity', 'end rebound to owning education record')
        elif not cur_end and b_end:
            updates['end'] = b_end
            evidence.add('date_proximity')
        if cur_start and b_start and _value_owned_elsewhere(cur_start[:4], block, blocks):
            updates['start'] = b_start
            taxonomy = taxonomy or CROSS_RECORD_LEAK
            evidence.add('date_proximity')
        elif not cur_start and b_start:
            updates['start'] = b_start
            evidence.add('date_proximity')
        inst = (entry.institution or '').strip()
        if not inst and block.get('institution'):
            updates['institution'] = str(block['institution'])[:200]
            evidence.add('entity_pattern')
        elif inst and block.get('institution') and _institution_owned_elsewhere(inst, block, blocks):
            updates['institution'] = str(block['institution'])[:200]
            taxonomy = taxonomy or CROSS_RECORD_LEAK
            evidence.add('entity_pattern', 'institution rebound to owning record')
        if not (updates.get('degree', degree) or '').strip() and block.get('degree'):
            if _looks_like_degree_line(str(block['degree'])):
                updates['degree'] = str(block['degree'])[:200]
                evidence.add('explicit_label')

    if not updates:
        return entry, evidence, None
    return entry.model_copy(update=updates), evidence, taxonomy


def _value_owned_elsewhere(value: str, own: dict, blocks: list[dict]) -> bool:
    if not value:
        return False
    if contains_normalized(own.get('raw') or '', value):
        return False
    return any(
        b is not own and contains_normalized(b.get('raw') or '', value)
        for b in blocks
    )


def _institution_owned_elsewhere(inst: str, own: dict, blocks: list[dict]) -> bool:
    if contains_normalized(own.get('raw') or '', inst):
        return False
    return any(
        overlap_ratio(inst, (b.get('institution') or '')) >= 0.5
        for b in blocks
        if b is not own
    )


def _value_supported(value: str, text: str) -> bool:
    if not value or not text:
        return False
    if contains_normalized(text, value):
        return True
    tokens = [t for t in re.split(r'[\s,./\-]+', value.lower()) if len(t) > 2]
    if not tokens:
        return contains_normalized(text, value)
    hay = text.lower()
    return sum(1 for t in tokens if t in hay) >= max(1, (len(tokens) + 1) // 2)
