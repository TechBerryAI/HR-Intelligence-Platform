"""Field-level golden format and scorer for semantic association tests."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.ai.document_intelligence.association.taxonomy import (
    CORRECT,
    INCORRECT,
    MISASSOCIATED,
    MISSING,
    NOT_STATED,
    PARTIAL,
)

FIXTURE_DIR = Path(__file__).resolve().parents[1] / 'fixtures' / 'association_gold'


def load_golden_case(stem: str) -> tuple[str, dict[str, Any]]:
    text = (FIXTURE_DIR / f'{stem}.txt').read_text(encoding='utf-8')
    expected = json.loads((FIXTURE_DIR / f'{stem}.expected.json').read_text(encoding='utf-8'))
    return text, expected


def list_golden_stems() -> list[str]:
    return sorted(p.stem.replace('.expected', '') for p in FIXTURE_DIR.glob('*.expected.json'))


def _norm(value: Any) -> str:
    return re.sub(r'\s+', ' ', str(value or '').strip().lower())


def _status(actual: str, expected: str, other_expected: list[str] | None = None) -> str:
    exp = _norm(expected)
    act = _norm(actual)
    if not exp:
        return NOT_STATED if not act else CORRECT
    if not act:
        return MISSING
    if exp == act or exp in act or act in exp:
        return CORRECT
    if other_expected:
        for other in other_expected:
            o = _norm(other)
            if o and (o == act or o in act or act in o):
                return MISASSOCIATED
    tokens_e = {t for t in exp.split() if len(t) > 2}
    tokens_a = {t for t in act.split() if len(t) > 2}
    if tokens_e and tokens_a and tokens_e & tokens_a:
        return PARTIAL
    return INCORRECT


def score_profile(profile, expected: dict[str, Any]) -> dict[str, Any]:
    """Compare a CandidateProfile to golden semantic values."""
    verdicts: list[dict[str, str]] = []

    exp_rows = list(expected.get('experience') or [])
    got_jobs = list(profile.experience or [])
    job_order = _align_rows(
        got_jobs,
        exp_rows,
        lambda g: f'{g.company} {g.role}',
        lambda w: f'{w.get("company") or ""} {w.get("role") or ""}',
    )
    for i, want in enumerate(exp_rows):
        got = job_order[i]
        others_company = [r.get('company') or '' for j, r in enumerate(exp_rows) if j != i]
        others_role = [r.get('role') or '' for j, r in enumerate(exp_rows) if j != i]
        others_duty = [' '.join(r.get('duties') or []) for j, r in enumerate(exp_rows) if j != i]
        verdicts.append(_field(f'experience[{i}].company', got.company if got else '', want.get('company'), others_company))
        verdicts.append(_field(f'experience[{i}].role', got.role if got else '', want.get('role'), others_role))
        verdicts.append(_field(f'experience[{i}].start_date', got.start if got else '', want.get('start_date'), None))
        verdicts.append(_field(f'experience[{i}].end_date', got.end if got else '', want.get('end_date'), None))
        duty_actual = got.description if got else ''
        duty_expected = ' '.join(want.get('duties') or [])
        verdicts.append(_field(f'experience[{i}].duties', duty_actual, duty_expected, others_duty))

    edu_rows = list(expected.get('education') or [])
    got_edu = list(profile.education or [])
    edu_order = _align_rows(
        got_edu,
        edu_rows,
        lambda g: f'{g.degree} {g.institution}',
        lambda w: f'{w.get("degree") or ""} {w.get("institution") or ""}',
    )
    for i, want in enumerate(edu_rows):
        got = edu_order[i]
        others_inst = [r.get('institution') or '' for j, r in enumerate(edu_rows) if j != i]
        others_deg = [r.get('degree') or '' for j, r in enumerate(edu_rows) if j != i]
        verdicts.append(_field(f'education[{i}].degree', got.degree if got else '', want.get('degree'), others_deg))
        verdicts.append(_field(f'education[{i}].institution', got.institution if got else '', want.get('institution'), others_inst))
        verdicts.append(_field(f'education[{i}].field_of_study', got.field if got else '', want.get('field_of_study'), None))
        verdicts.append(_field(f'education[{i}].start_year', got.start if got else '', want.get('start_year'), None))
        verdicts.append(_field(f'education[{i}].end_year', got.end if got else '', want.get('end_year'), None))

    if 'summary' in expected:
        verdicts.append(_field('summary', profile.personal.summary if profile.personal else '', expected.get('summary'), None))

    want_certs = [c.get('name') if isinstance(c, dict) else str(c) for c in (expected.get('certifications') or [])]
    got_certs = [(c.name or '') for c in (profile.certificates or [])]
    if 'certifications' in expected:
        for name in want_certs:
            hit = next((g for g in got_certs if _norm(name) in _norm(g) or _norm(g) in _norm(name)), '')
            verdicts.append(_field(f'certifications:{name}', hit, name, None))
        forbid = list(expected.get('forbidden_certifications') or [])
        for name in forbid:
            hit = next((g for g in got_certs if _norm(name) == _norm(g) or _norm(name) in _norm(g)), '')
            verdicts.append(
                {
                    'field': f'forbidden_cert:{name}',
                    'expected': '',
                    'actual': hit,
                    'status': INCORRECT if hit else CORRECT,
                }
            )

    want_skills = [s.lower() for s in (expected.get('skills') or [])]
    got_skills = [(s.canonical or s.name or '').lower() for s in (profile.skills or [])]
    for name in want_skills:
        hit = next((g for g in got_skills if name in g or g in name), '')
        verdicts.append(_field(f'skills:{name}', hit, name, None))

    counts = {CORRECT: 0, MISSING: 0, PARTIAL: 0, INCORRECT: 0, MISASSOCIATED: 0, NOT_STATED: 0}
    for row in verdicts:
        counts[row['status']] = counts.get(row['status'], 0) + 1
    return {'verdicts': verdicts, 'counts': counts}


def _align_rows(got_rows: list, want_rows: list, got_key, want_key) -> list:
    used: set[int] = set()
    ordered: list = []
    for want in want_rows:
        best_i, best = None, 0.0
        target = _norm(want_key(want))
        for i, got in enumerate(got_rows):
            if i in used:
                continue
            score = 0.0
            gk = _norm(got_key(got))
            if target and gk:
                if target == gk or target in gk or gk in target:
                    score = 1.0
                else:
                    te, tg = set(target.split()), set(gk.split())
                    if te and tg:
                        score = len(te & tg) / len(te | tg)
            if score > best:
                best, best_i = score, i
        if best_i is None or best < 0.15:
            ordered.append(None)
            continue
        used.add(best_i)
        ordered.append(got_rows[best_i])
    return ordered


def _field(path: str, actual: str, expected: str, others: list[str] | None) -> dict[str, str]:
    return {
        'field': path,
        'expected': expected or '',
        'actual': actual or '',
        'status': _status(actual, expected or '', others),
    }
