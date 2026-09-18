"""Eval-only Field Trace + weak-section clustering. Not production parser rules."""
from __future__ import annotations

import re
from collections import defaultdict
from typing import Any

CLASS_B = 'B'

TRACE_CORE = (
    'name',
    'email',
    'phone',
    'location',
    'linkedin',
    'skills',
    'summary',
    'education',
    'experience',
)

COVERAGE_FIELD = {
    'name': 'fullName',
    'email': 'email',
    'phone': 'phone',
    'location': 'location',
    'education': 'education',
    'experience': 'experience',
}

FIELD_TO_SECTION = {
    'name': 'contact',
    'email': 'contact',
    'phone': 'contact',
    'location': 'contact',
    'linkedin': 'contact',
    '*': 'api',
    'experience': 'experience',
    'company': 'experience',
    'role': 'experience',
    'start': 'experience',
    'end': 'experience',
    'isCurrent': 'experience',
    'description': 'experience',
    'education': 'education',
    'degree': 'education',
    'institution': 'education',
    'edu_start': 'education',
    'edu_end': 'education',
    'skills': 'skills',
    'summary': 'summary',
    'certifications': 'certifications',
}


def coverage_map(coverage: list[dict] | None) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in coverage or []:
        if not isinstance(row, dict):
            continue
        field = str(row.get('field') or '')
        if field:
            out[field] = row
    return out


def slim_value_for_trace(slim: dict[str, Any], field: str) -> str:
    if field == 'experience':
        rows = slim.get('experiences') or []
        return ' | '.join(
            ' '.join(filter(None, [r.get('company', ''), r.get('role', '')]))
            for r in rows
            if isinstance(r, dict)
        )
    if field == 'education':
        rows = slim.get('education') or []
        return ' | '.join(
            ' '.join(filter(None, [r.get('degree', ''), r.get('institution', '')]))
            for r in rows
            if isinstance(r, dict)
        )
    return str(slim.get(field) or '').strip()


def value_in_extract(value: str, extract: str, field: str) -> bool:
    v = (value or '').strip()
    src = extract or ''
    if not v or not src:
        return False
    hay = src.casefold()
    if field == 'phone':
        digits = re.sub(r'\D', '', v)
        src_digits = re.sub(r'\D', '', src)
        return len(digits) >= 8 and digits[-10:] in src_digits
    if field == 'email':
        return v.casefold() in hay
    if field == 'linkedin':
        token = v.casefold().replace('https://', '').replace('http://', '').rstrip('/')
        return bool(token) and token[:24] in hay
    if field == 'skills':
        toks = [t.strip() for t in re.split(r'[,;/|]', v) if t.strip()]
        if not toks:
            return False
        hits = sum(1 for t in toks if t.casefold()[:8] in hay or t.casefold() in hay)
        return hits >= max(1, (len(toks) + 1) // 2)
    folded = v.casefold()
    if folded[:12] in hay or folded in hay:
        return True
    tokens = [t for t in re.findall(r'[a-z0-9]{3,}', folded) if t]
    if not tokens:
        return False
    return sum(1 for t in tokens if t in hay) >= max(1, len(tokens) // 2)


def field_trace_verdicts(
    *,
    slim: dict[str, Any],
    extract: str,
    coverage: list[dict] | None,
    support: dict[str, bool],
) -> dict[str, dict[str, str]]:
    """Bulk-style verdicts: ok / weak_missing / weak_ungrounded / absent / fallback."""
    cov = coverage_map(coverage)
    loc = str(slim.get('location') or '')
    pref = str(slim.get('preferredLocation') or '')
    out: dict[str, dict[str, str]] = {}
    for field in TRACE_CORE:
        value = slim_value_for_trace(slim, field)
        cov_key = COVERAGE_FIELD.get(field)
        cov_row = cov.get(cov_key or '', {}) if cov_key else {}
        cov_status = str(cov_row.get('status') or '')
        in_resume = value_in_extract(value, extract, field)
        supported = bool(support.get(field)) or cov_status == 'missing_with_evidence'
        if field == 'location' and pref and loc and pref.casefold() == loc.casefold() and value:
            verdict = 'fallback'
            note = 'preferred_equals_current'
        elif not value:
            if cov_status == 'missing_with_evidence' or (supported and cov_status != 'missing_no_evidence'):
                verdict = 'weak_missing'
                note = cov_status or 'evidence_in_resume'
            else:
                verdict = 'absent'
                note = cov_status or 'missing_no_evidence'
        elif value and not in_resume:
            verdict = 'weak_ungrounded'
            note = 'value_not_in_resume'
        else:
            verdict = 'ok'
            note = cov_status or 'grounded'
        out[field] = {
            'verdict': verdict,
            'coverage': cov_status,
            'note': note,
            'in_resume': 'yes' if in_resume else 'no',
        }
    return out


def apply_coverage_gaps(
    *,
    slim: dict[str, Any],
    coverage: list[dict] | None,
    field_ok: dict[str, str],
    issues: list[dict[str, str]],
    mark,
) -> None:
    """If coverage says missing_with_evidence and the form value is empty, mark parser fail."""
    cov = coverage_map(coverage)
    mapping = (
        ('fullName', 'name', lambda: not slim.get('name')),
        ('email', 'email', lambda: not slim.get('email')),
        ('phone', 'phone', lambda: not slim.get('phone')),
        ('location', 'location', lambda: not slim.get('location')),
        ('education', 'education', lambda: not slim.get('education')),
        ('experience', 'experience', lambda: not slim.get('experiences')),
    )
    for cov_field, form_field, empty in mapping:
        row = cov.get(cov_field) or {}
        if str(row.get('status') or '') != 'missing_with_evidence':
            continue
        if not empty():
            continue
        if field_ok.get(form_field) == 'fail':
            continue
        mark(form_field, 'fail')
        issues.append({
            'class': CLASS_B,
            'field': form_field,
            'reason': 'coverage_missing_with_evidence',
        })


def cluster_issues(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], dict[str, Any]] = {}
    for case in cases:
        ev = case.get('evaluation') or {}
        fname = str(case.get('file') or '')
        seen: set[tuple[str, str, str]] = set()
        for issue in ev.get('issues') or []:
            if not isinstance(issue, dict):
                continue
            field = str(issue.get('field') or '*')
            reason = str(issue.get('reason') or 'unspecified')
            cls = str(issue.get('class') or '')
            section = FIELD_TO_SECTION.get(field, field)
            key = (section, reason, cls)
            if key in seen:
                continue
            seen.add(key)
            rec = buckets.setdefault(key, {
                'section': section,
                'reason': reason,
                'class': cls,
                'count': 0,
                'examples': [],
            })
            rec['count'] += 1
            if fname and fname not in rec['examples'] and len(rec['examples']) < 8:
                rec['examples'].append(fname)
        traces = ev.get('field_trace') or {}
        for field, tr in traces.items():
            if not isinstance(tr, dict):
                continue
            verdict = str(tr.get('verdict') or '')
            if verdict not in ('weak_missing', 'weak_ungrounded'):
                continue
            section = FIELD_TO_SECTION.get(field, field)
            reason = f'trace_{verdict}'
            cls = CLASS_B
            key = (section, reason, cls)
            if key in seen:
                continue
            seen.add(key)
            rec = buckets.setdefault(key, {
                'section': section,
                'reason': reason,
                'class': cls,
                'count': 0,
                'examples': [],
            })
            rec['count'] += 1
            if fname and fname not in rec['examples'] and len(rec['examples']) < 8:
                rec['examples'].append(fname)
    return sorted(buckets.values(), key=lambda r: (-int(r['count']), r['section'], r['reason']))


def rank_training_backlog(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    stats: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'section': '',
        'class_b': 0,
        'weak_missing': 0,
        'weak_ungrounded': 0,
        'examples': [],
        'reasons': defaultdict(int),
    })
    for case in cases:
        ev = case.get('evaluation') or {}
        fname = str(case.get('file') or '')
        section_hit: dict[str, set[str]] = defaultdict(set)
        for issue in ev.get('issues') or []:
            if not isinstance(issue, dict) or issue.get('class') != CLASS_B:
                continue
            field = str(issue.get('field') or '*')
            section = FIELD_TO_SECTION.get(field, field)
            reason = str(issue.get('reason') or 'unspecified')
            section_hit[section].add('class_b')
            stats[section]['reasons'][reason] += 1
            if fname and fname not in stats[section]['examples'] and len(stats[section]['examples']) < 8:
                stats[section]['examples'].append(fname)
        for field, tr in (ev.get('field_trace') or {}).items():
            if not isinstance(tr, dict):
                continue
            verdict = str(tr.get('verdict') or '')
            if verdict not in ('weak_missing', 'weak_ungrounded'):
                continue
            section = FIELD_TO_SECTION.get(field, field)
            section_hit[section].add(verdict)
            stats[section]['reasons'][f'trace_{verdict}'] += 1
            if fname and fname not in stats[section]['examples'] and len(stats[section]['examples']) < 8:
                stats[section]['examples'].append(fname)
        for section, kinds in section_hit.items():
            rec = stats[section]
            rec['section'] = section
            if 'class_b' in kinds:
                rec['class_b'] += 1
            if 'weak_missing' in kinds:
                rec['weak_missing'] += 1
            if 'weak_ungrounded' in kinds:
                rec['weak_ungrounded'] += 1

    WHY = {
        'experience': 'Parser drops or mis-splits job rows (company/role/dates).',
        'education': 'Degree/institution rows incomplete or unmapped.',
        'skills': 'Skills heading present but tokens empty or polluted with prose.',
        'contact': 'Name/email/phone/location/LinkedIn in source but form empty or ungrounded.',
        'summary': 'Summary heading present but body not mapped (often source-ambiguous).',
        'certifications': 'Certification cues in source not mapped to form rows.',
        'api': 'HTTP/API drift — not a parser training target.',
    }
    ranked = []
    for section, rec in stats.items():
        if not rec['section']:
            rec['section'] = section
        impact = rec['class_b'] + rec['weak_missing'] + rec['weak_ungrounded']
        if impact <= 0:
            continue
        top_reasons = sorted(rec['reasons'].items(), key=lambda kv: -kv[1])[:5]
        ranked.append({
            'section': section,
            'impact': impact,
            'class_b': rec['class_b'],
            'weak_missing': rec['weak_missing'],
            'weak_ungrounded': rec['weak_ungrounded'],
            'top_reasons': [{'reason': r, 'count': c} for r, c in top_reasons],
            'examples': rec['examples'],
            'why': WHY.get(section, 'Parser gap on this section.'),
            'phase2': (
                'Do not train — API/UI class.'
                if section == 'api'
                else 'Gold-label worst examples, then fix parsers/resume + coverage recovery.'
            ),
        })
    ranked.sort(key=lambda r: (-int(r['impact']), r['section']))
    return ranked
