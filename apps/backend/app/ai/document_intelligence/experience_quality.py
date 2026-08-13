"""Experience row quality — used by coverage, semantic AI, and repair merge."""
from __future__ import annotations

import re
from typing import Any, Iterable

from app.ai.document_intelligence.deterministic import extract_date_range
from app.ai.document_intelligence.models.candidate import ExperienceEntry

_TITLE_CUE = re.compile(
    r'(?i)\b(?:intern|engineer|developer|analyst|trainee|manager|officer|'
    r'associate|consultant|lead|executive|specialist|administrator|admin|'
    r'architect|dba|designer|scientist|director|head|programmer|'
    r'coordinator|supervisor)\b'
)
_ORG_CUE = re.compile(
    r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies|solutions|labs|systems)\b'
)


def _parts(row: Any) -> tuple[str, str, str, str]:
    if isinstance(row, dict):
        return (
            str(row.get('role') or row.get('title') or '').strip(),
            str(row.get('company') or '').strip(),
            str(row.get('start') or row.get('from') or '').strip(),
            str(row.get('description') or '').strip(),
        )
    return (
        (getattr(row, 'role', '') or '').strip(),
        (getattr(row, 'company', '') or '').strip(),
        (getattr(row, 'start', '') or '').strip(),
        (getattr(row, 'description', '') or '').strip(),
    )


def row_is_complete(row: Any) -> bool:
    role, company, _start, _desc = _parts(row)
    return bool(role and company)


def complete_experience_count(rows: Iterable[Any] | None) -> int:
    return sum(1 for row in (rows or []) if row_is_complete(row))


def score_experience_row(row: Any) -> int:
    role, company, start, desc = _parts(row)
    score = 0
    if role and company:
        score += 3
    elif role or company:
        score += 1
    if start:
        score += 1
    if len(desc) >= 40:
        score += 1
    return score


def experience_date_signal_count(section_or_full_text: str) -> int:
    """Unique dated ranges in text (proxy for how many jobs the resume lists)."""
    seen: set[tuple[str, str]] = set()
    for line in (section_or_full_text or '').splitlines():
        start, end = extract_date_range(line)
        if start:
            seen.add((start, (end or 'present').lower()))
    return len(seen)


def row_looks_swapped(row: Any) -> bool:
    role, company, _s, _d = _parts(row)
    if not role:
        return False
    role_is_title = bool(_TITLE_CUE.search(role))
    company_is_title = bool(_TITLE_CUE.search(company))
    role_is_org = bool(_ORG_CUE.search(role)) and not role_is_title
    if company and company_is_title and not role_is_title:
        return True
    if role_is_org and (not company or company_is_title):
        return True
    if not company and not role_is_title and len(role.split()) <= 3:
        return True
    return False


def experience_is_incomplete(rows: Iterable[Any] | None, source_text: str = '') -> bool:
    """True when apply-form experience should not be trusted yet."""
    rows = list(rows or [])
    from app.ai.document_intelligence.coverage.resume_coverage import (
        has_experience_section_evidence,
        _experience_section_text,
    )

    if has_experience_section_evidence(source_text) and not rows:
        return True
    complete = complete_experience_count(rows)
    if rows and complete == 0:
        return True
    if any(row_looks_swapped(row) for row in rows):
        return True
    xor = any(
        (bool(_parts(r)[0]) ^ bool(_parts(r)[1])) for r in rows
    )
    if xor and complete < max(1, len(rows)):
        return True
    body = _experience_section_text(source_text) or source_text
    dates = experience_date_signal_count(body)
    # Allow one extra dated line (training / professional development)
    if dates >= 2 and complete < dates and (complete <= dates - 2 or xor):
        return True
    return False


def _value_in_source(value: str, source: str) -> bool:
    v = re.sub(r'\s+', ' ', (value or '').strip().lower())
    if len(v) < 2:
        return False
    src = (source or '').lower()
    if v in src:
        return True
    tokens = [t for t in re.findall(r'[a-z0-9]+', v) if len(t) > 2]
    if not tokens:
        return False
    hits = sum(1 for t in tokens if t in src)
    return hits >= max(1, len(tokens) - 1)


def ground_experience_rows(
    rows: list[ExperienceEntry],
    source_text: str,
) -> list[ExperienceEntry]:
    """Keep AI/det rows whose role or company actually appears in the resume."""
    src = source_text or ''
    out: list[ExperienceEntry] = []
    for row in rows:
        role, company, _s, _d = _parts(row)
        if company and not _value_in_source(company, src):
            continue
        if role and not _value_in_source(role, src) and not _TITLE_CUE.search(role):
            continue
        if not (role or company):
            continue
        out.append(row)
    return out


def merge_experience_rows(
    deterministic: list[ExperienceEntry],
    ai_rows: list[ExperienceEntry],
) -> list[ExperienceEntry]:
    """Prefer the set with more complete (role+company) jobs; else higher score."""
    det = list(deterministic or [])
    ai = list(ai_rows or [])
    if not ai:
        return det
    if not det:
        return ai
    det_c, ai_c = complete_experience_count(det), complete_experience_count(ai)
    if ai_c > det_c:
        return ai
    if ai_c == det_c and ai_c > 0:
        if sum(score_experience_row(r) for r in ai) > sum(score_experience_row(r) for r in det):
            return ai
        if len(ai) > len(det):
            return ai
    return det
