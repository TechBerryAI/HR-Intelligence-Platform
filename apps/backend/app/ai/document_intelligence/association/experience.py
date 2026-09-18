"""Experience entity reconstruction: company ↔ role ↔ dates ↔ duties.

Does not re-parse jobs from scratch. It rebinds fields using record blocks
from the Experience section so duties do not leak across employment records.
"""
from __future__ import annotations

import re

from app.ai.document_intelligence.association.evidence import Evidence, contains_normalized, overlap_ratio
from app.ai.document_intelligence.association.taxonomy import CROSS_RECORD_LEAK, ENTITY_MISASSOCIATION
from app.ai.document_intelligence.bullets import is_bullet_line, looks_like_list_item, strip_bullet_prefix
from app.ai.document_intelligence.deterministic import extract_date_range
from app.ai.document_intelligence.models.candidate import ExperienceEntry
from app.ai.document_intelligence.parsers.resume import _DUTY_VERB_START, _has_job_title_cue
from app.ai.parser.enrichment.resume_text_inference import is_section_header_line

_DATE_CORE = re.compile(
    r'(?i)\b(?:'
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:19|20)\d{2}'
    r'|present|current|till\s*date|ongoing'
    r')\b'
)
_SECTION_HEADING = re.compile(
    r'(?i)^(?:experience|work\s+experience|professional\s+experience|'
    r'employment(?:\s+history)?|work\s+history|career\s+history|'
    r'internships?)\s*:?\s*$'
)


def associate_experience(
    entries: list[ExperienceEntry],
    section_text: str,
    *,
    report: list[dict] | None = None,
) -> list[ExperienceEntry]:
    """Rebind duties/dates inside existing employment records.

    Conservative: never drop a filled company/role, never invent a new job.
    """
    if not entries:
        return entries
    blocks = split_experience_blocks(section_text)
    if len(blocks) < 2:
        return entries

    used: set[int] = set()
    out: list[ExperienceEntry] = []
    for idx, entry in enumerate(entries):
        block_i = _best_block_index(entry, blocks, used)
        if block_i is None:
            out.append(entry)
            if report is not None:
                report.append({'index': idx, 'action': 'keep', 'reason': 'no_block'})
            continue
        used.add(block_i)
        block = blocks[block_i]
        updated, evidence, taxonomy = _rebind_entry(entry, block, blocks, block_i)
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
    # Do not invent additional jobs. Rebind duties/dates on existing records only.
    return out


def split_experience_blocks(section_text: str) -> list[dict]:
    """Split an experience section into record-sized blocks using boundary cues."""
    raw_lines = [(ln or '').rstrip() for ln in (section_text or '').splitlines()]
    lines = [ln for ln in raw_lines]
    while lines and _SECTION_HEADING.match(lines[0].strip()):
        lines = lines[1:]
    if not lines:
        return []

    blocks: list[list[str]] = []
    current: list[str] = []
    seen_duty = False
    for ln in lines:
        s = ln.strip()
        if not s:
            if current:
                current.append('')
            continue
        if _is_record_boundary(s, seen_duty=seen_duty, current=current):
            if current and any(x.strip() for x in current):
                blocks.append(current)
            current = [ln]
            seen_duty = False
            continue
        current.append(ln)
        if _is_duty_line(s):
            seen_duty = True
    if current and any(x.strip() for x in current):
        blocks.append(current)
    return [_block_from_lines(b) for b in blocks if any(x.strip() for x in b)]


def _block_from_lines(lines: list[str]) -> dict:
    body = '\n'.join(lines).strip()
    duties: list[str] = []
    headers: list[str] = []
    start, end, is_current = '', '', False
    for ln in lines:
        s = strip_bullet_prefix(ln).strip()
        if not s:
            continue
        ds, de = extract_date_range(s)
        if ds:
            start = start or ds
            end = end or de
            if de and re.match(r'(?i)^(present|current|now|till\s*date|ongoing)$', de):
                is_current = True
        if _is_duty_line(s):
            duties.append(s)
        elif not _is_tenure_line(s):
            headers.append(s)
    role = next((h for h in headers if _has_job_title_cue(h)), '')
    company = next((h for h in headers if h != role), '')
    if role and company and _has_job_title_cue(company) and not _has_job_title_cue(role):
        role, company = company, role
    return {
        'raw': body,
        'lines': lines,
        'duties': duties,
        'headers': headers,
        'role': role,
        'company': company,
        'start': start,
        'end': end,
        'is_current': is_current,
        'duty_text': '\n'.join(duties).strip(),
    }


def _is_duty_line(line: str) -> bool:
    s = strip_bullet_prefix(line).strip()
    if not s:
        return False
    if is_bullet_line(line) or looks_like_list_item(line):
        return True
    if _DUTY_VERB_START.match(s):
        return True
    if s[:1].islower() and len(s.split()) >= 5:
        return True
    return False


def _is_tenure_line(line: str) -> bool:
    s = strip_bullet_prefix(line).strip()
    start, _end = extract_date_range(s)
    if not start:
        return False
    remainder = _DATE_CORE.sub('', s)
    remainder = re.sub(r'[-–—to/|,.\s]+', '', remainder)
    return len(remainder) <= 8 or len(s.split()) <= 8


def _is_record_boundary(line: str, *, seen_duty: bool, current: list[str]) -> bool:
    if not current or not any(x.strip() for x in current):
        return False
    if not seen_duty and not any(_is_duty_line(x) for x in current):
        # Still in the header of the first/current job.
        return False
    if _is_duty_line(line):
        return False
    if _is_tenure_line(line) and seen_duty:
        return True
    if _has_job_title_cue(line) and seen_duty:
        return True
    s = strip_bullet_prefix(line).strip()
    if (
        seen_duty
        and s
        and s[0].isupper()
        and 1 <= len(s.split()) <= 8
        and not _DUTY_VERB_START.match(s)
        and not _is_tenure_line(s)
    ):
        return True
    return False


def _plausible_employer_label(value: str) -> bool:
    s = (value or '').strip()
    if not s or is_section_header_line(s) or is_section_header_line(s.rstrip(':')):
        return False
    if _DUTY_VERB_START.match(s) or _is_duty_line(s):
        return False
    if len(s.split()) > 10:
        return False
    return True


def _plausible_role_label(value: str) -> bool:
    s = (value or '').strip()
    if not s or is_section_header_line(s):
        return False
    if _is_duty_line(s) and not _has_job_title_cue(s):
        return False
    return True


def _best_block_index(
    entry: ExperienceEntry,
    blocks: list[dict],
    used: set[int],
) -> int | None:
    identity = f'{entry.company or ""} {entry.role or ""} {entry.start or ""}'
    best_i, best_score = None, 0.12
    for i, block in enumerate(blocks):
        if i in used:
            continue
        score = max(
            overlap_ratio(identity, block.get('raw') or ''),
            overlap_ratio(entry.company or '', block.get('company') or ''),
            overlap_ratio(entry.role or '', block.get('role') or ''),
        )
        if entry.start and contains_normalized(block.get('raw') or '', entry.start[:7]):
            score += 0.15
        if score > best_score:
            best_score, best_i = score, i
    if best_i is not None:
        return best_i
    # No document-order fallback: the first unused block is often a
    # summary/education fragment when section bounds are weak.
    return None


def _rebind_entry(
    entry: ExperienceEntry,
    block: dict,
    blocks: list[dict],
    block_i: int,
) -> tuple[ExperienceEntry, Evidence, str | None]:
    evidence = Evidence()
    evidence.add('section_boundary', 'experience section block')
    evidence.add('same_block')
    evidence.add('record_boundary')
    updates: dict = {}
    taxonomy = None
    desc = (entry.description or '').strip()
    duty_text = (block.get('duty_text') or '').strip()
    leaked = _description_leaks_to_other_blocks(desc, blocks, block_i)
    if leaked:
        taxonomy = CROSS_RECORD_LEAK
        if duty_text:
            updates['description'] = duty_text[:2000]
            evidence.add('neighbor_consistency', 'duties rebound to owning record')
        elif desc:
            stripped = _strip_foreign_duties(desc, blocks, block_i)[:2000]
            # Never wipe a filled description to empty (scorer then fails the field).
            if stripped.strip():
                updates['description'] = stripped
    elif not desc and duty_text:
        updates['description'] = duty_text[:2000]
        evidence.add('same_block', 'empty description filled from owning block')

    cand_company = (block.get('company') or '').strip()
    cand_role = (block.get('role') or '').strip()
    if not (entry.company or '').strip() and cand_company and _plausible_employer_label(cand_company):
        updates['company'] = cand_company[:200]
        evidence.add('entity_pattern')
        taxonomy = taxonomy or ENTITY_MISASSOCIATION
    if not (entry.role or '').strip() and cand_role and _plausible_role_label(cand_role):
        updates['role'] = cand_role[:200]
        evidence.add('entity_pattern')
        taxonomy = taxonomy or ENTITY_MISASSOCIATION

    if not (entry.start or '').strip() and block.get('start'):
        updates['start'] = block['start']
        evidence.add('date_proximity')
    if not (entry.end or '').strip() and not entry.is_current and block.get('end'):
        updates['end'] = block['end']
        evidence.add('date_proximity')
    if block.get('is_current') and not entry.is_current:
        updates['is_current'] = True

    if not updates:
        return entry, evidence, None
    return entry.model_copy(update=updates), evidence, taxonomy


def _description_leaks_to_other_blocks(desc: str, blocks: list[dict], own_i: int) -> bool:
    if not desc or len(blocks) < 2:
        return False
    for i, block in enumerate(blocks):
        if i == own_i:
            continue
        for cue in (block.get('company'), block.get('role')):
            if cue and len(str(cue).split()) >= 2 and contains_normalized(desc, str(cue)):
                return True
        for duty in block.get('duties') or []:
            if len(duty.split()) >= 4 and contains_normalized(desc, duty):
                return True
    return False


def _strip_foreign_duties(desc: str, blocks: list[dict], own_i: int) -> str:
    kept: list[str] = []
    for ln in desc.splitlines():
        s = ln.strip()
        if not s:
            continue
        foreign = False
        for i, block in enumerate(blocks):
            if i == own_i:
                continue
            cue = ' '.join(
                x for x in (block.get('company'), block.get('role')) if x
            )
            if cue and contains_normalized(s, cue):
                foreign = True
                break
        if not foreign:
            kept.append(s)
    return '\n'.join(kept)
