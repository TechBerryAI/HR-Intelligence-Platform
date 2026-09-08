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


def _company_looks_fragment(company: str) -> bool:
    """True when company is leftover prose, not an employer name."""
    s = (company or '').strip()
    if not s:
        return False
    if re.search(r'(?i)\b(?:as|from|currently|working with|worked with)\b', s):
        return True
    if len(s.split()) >= 6 and not _ORG_CUE.search(s):
        return True
    return False


def row_is_complete(row: Any) -> bool:
    """Role+dates (or role+plausible company) — not merely two non-empty strings."""
    role, company, start, _desc = _parts(row)
    if role and start:
        return True
    if role and company and not _company_looks_fragment(company):
        return True
    return False


def row_is_anchored(row: Any) -> bool:
    """Role+company, or either field with employment dates — keep conservative rows."""
    role, company, start, _desc = _parts(row)
    if _company_looks_fragment(company):
        company = ''
    return bool((role and company) or ((role or company) and start))


def complete_experience_count(rows: Iterable[Any] | None) -> int:
    return sum(1 for row in (rows or []) if row_is_complete(row))


def score_experience_row(row: Any) -> int:
    """Structural evidence score — Role+dates beats Role+garbage company."""
    role, company, start, desc = _parts(row)
    if _company_looks_fragment(company):
        company = ''
    score = 0
    if role and start:
        score += 4
    elif role or company:
        score += 1
    if company and role:
        score += 2
    elif company and start:
        score += 2
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
    anchored = sum(1 for r in rows if row_is_anchored(r))
    if rows and anchored == 0:
        return True
    if any(row_looks_swapped(row) for row in rows):
        return True
    undated_xor = any(
        (bool(_parts(r)[0]) ^ bool(_parts(r)[1])) and not _parts(r)[2]
        for r in rows
    )
    if undated_xor and complete == 0 and anchored == 0:
        return True
    if anchored > 0:
        return False
    body = _experience_section_text(source_text) or source_text
    dates = experience_date_signal_count(body)
    # Allow one extra dated line (training / professional development)
    if dates >= 2 and anchored < dates and (anchored <= dates - 2 or undated_xor):
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


def _split_role_company(role: str, company: str) -> tuple[str, str]:
    """Undo Role — Company packed into one field so merge keys match sanitize."""
    role, company = (role or '').strip(), (company or '').strip()
    packed = company if (company and not role) else (role if (role and not company) else '')
    if packed:
        for dash in ('—', '–', '-'):
            if dash in packed:
                left, _, right = packed.partition(dash)
                if left.strip() and right.strip() and len(left.split()) <= 8:
                    return left.strip(), right.strip()
    return role, company


def _companies_compatible(left: str, right: str) -> bool:
    a, b = (left or '').strip().lower(), (right or '').strip().lower()
    if not a or not b:
        return True
    if a == b:
        return True
    # Unsanitized "Role — Company" blob vs split company
    return a in b or b in a


def _same_job(left: Any, right: Any) -> bool:
    """True only when identity keys agree. Same title at two companies is not one job."""
    lr, lc, ls, _ = _parts(left)
    rr, rc, rs, _ = _parts(right)
    lr, lc = _split_role_company(lr, lc)
    rr, rc = _split_role_company(rr, rc)
    lr, rr = lr.lower(), rr.lower()
    lc, rc = lc.lower(), rc.lower()
    if ls and rs and ls != rs:
        return False
    if lc and rc and not _companies_compatible(lc, rc):
        return False
    start_compat = not ls or not rs or ls == rs
    company_compat = _companies_compatible(lc, rc)
    role_compat = not lr or not rr or lr == rr
    if ls and rs and ls == rs and company_compat:
        return True
    if lr and rr and lr == rr and company_compat and start_compat:
        return True
    if lc and rc and company_compat and role_compat and start_compat:
        return True
    return False


def _incoming_role_is_stronger(cur: Any, other: Any) -> bool:
    other_role = (_parts(other)[0] or '').strip()
    if not other_role:
        return False
    if not (_parts(cur)[0] or '').strip():
        return True
    if row_looks_swapped(cur) and (
        _TITLE_CUE.search(other_role) or not row_looks_swapped(other)
    ):
        return True
    return False


def merge_experience_field_level(
    existing: list[ExperienceEntry],
    incoming: list[ExperienceEntry],
) -> list[ExperienceEntry]:
    """Fill empty / low-confidence slots only. Never replace a valid field."""
    if not incoming:
        return list(existing or [])
    if not existing:
        return [r for r in incoming if row_is_anchored(r) and not row_looks_swapped(r)]
    out: list[ExperienceEntry] = []
    for cur in existing:
        nxt = cur
        for other in incoming:
            if not _same_job(cur, other):
                continue
            updates: dict[str, Any] = {}
            other_company = (other.company or '').strip()
            if other_company and not _company_looks_fragment(other_company):
                if not (cur.company or '').strip() or _company_looks_fragment(cur.company or ''):
                    updates['company'] = other_company[:200]
            if _incoming_role_is_stronger(cur, other):
                other_role = (other.role or '').strip()
                if other_role and not (
                    not _TITLE_CUE.search(other_role) and len(other_role.split()) > 8
                ):
                    updates['role'] = other_role[:200]
            if not (cur.start or '').strip() and (other.start or '').strip():
                updates['start'] = other.start
            if not (cur.end or '').strip() and not cur.is_current and (
                (other.end or '').strip() or other.is_current
            ):
                updates['end'] = other.end or ''
            if other.is_current and not cur.is_current:
                same_company = (
                    not (cur.company or '').strip()
                    or not (other.company or '').strip()
                    or (cur.company or '').strip().lower()
                    == (other.company or '').strip().lower()
                )
                same_start = (
                    not (cur.start or '').strip()
                    or not (other.start or '').strip()
                    or (cur.start or '').strip() == (other.start or '').strip()
                )
                if same_company and same_start:
                    updates['is_current'] = True
                    if not (cur.end or '').strip():
                        updates['end'] = ''
            if not (cur.description or '').strip() and (other.description or '').strip():
                updates['description'] = (other.description or '')[:2000]
            if updates:
                nxt = nxt.model_copy(update=updates)
            break
        out.append(nxt)
    for other in incoming:
        if not row_is_anchored(other) or row_looks_swapped(other):
            continue
        if _company_looks_fragment(other.company or ''):
            continue
        if any(_same_job(cur, other) for cur in out):
            continue
        out.append(other)
    return out


def merge_experience_rows(
    deterministic: list[ExperienceEntry],
    ai_rows: list[ExperienceEntry],
) -> list[ExperienceEntry]:
    """Keep deterministic rows; fill missing fields from incoming when stronger."""
    det = list(deterministic or [])
    ai = list(ai_rows or [])
    if not ai:
        return det
    if not det:
        return [r for r in ai if row_is_anchored(r) and not row_looks_swapped(r)]
    if sum(1 for r in det if row_is_anchored(r)) > 0:
        return merge_experience_field_level(det, ai)
    incoming_score = sum(score_experience_row(r) for r in ai)
    det_score = sum(score_experience_row(r) for r in det)
    if incoming_score > det_score and all(row_is_anchored(r) for r in ai):
        return ai
    return det
