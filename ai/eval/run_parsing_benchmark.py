#!/usr/bin/env python3
"""
Intelligence Engine gold-dataset eval harness.

IMPORTANT (accuracy honesty):
- Dataset is synthetic text from generate_gold_lake.py unless replaced with real docs.
- Scores are per-case checklist hit-rates (fuzzy/overlap), not full-TOON exact match.
- Default path runs deterministic parsers only — does NOT measure LLM or HTTP E2E accuracy.
- Do not treat mean_accuracy as production >99% field accuracy without a real-document lake.

Usage (from repo root, with backend on PYTHONPATH):
  PYTHONPATH=apps/backend python ai/eval/run_parsing_benchmark.py
  PYTHONPATH=apps/backend python ai/eval/run_parsing_benchmark.py --threshold 0.85
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'apps' / 'backend'
for p in (str(BACKEND), str(BACKEND / 'app')):
    if p not in sys.path:
        sys.path.insert(0, p)

LAKE = ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'


def _norm(s: Any) -> str:
    return re_sub(str(s or '').strip().lower())


def re_sub(s: str) -> str:
    import re

    return re.sub(r'\s+', ' ', s)


def _list_norm(vals: Any) -> set[str]:
    if not isinstance(vals, list):
        return set()
    return {_norm(v) for v in vals if str(v or '').strip()}


def score_resume_fields(actual: dict, expected: dict) -> tuple[float, list[str]]:
    misses: list[str] = []
    checks = 0
    hits = 0

    def check(path: str, ok: bool) -> None:
        nonlocal checks, hits
        checks += 1
        if ok:
            hits += 1
        else:
            misses.append(path)

    ep = expected.get('person') or {}
    ap = actual.get('person') or {}
    check('person.email', _norm(ap.get('email')) == _norm(ep.get('email')))
    check('person.name', bool(_norm(ap.get('name'))) and _norm(ep.get('name'))[:8] in _norm(ap.get('name')))
    check('person.phone', bool(_norm(ap.get('phone'))))
    if ep.get('location'):
        check('person.location', _norm(ep.get('location')) in _norm(ap.get('location')) or _norm(ap.get('location')) in _norm(ep.get('location')))

    exp_skills = _list_norm(expected.get('skills'))
    act_skills = _list_norm(actual.get('skills'))
    if exp_skills:
        overlap = len(exp_skills & act_skills) / max(1, len(exp_skills))
        check('skills', overlap >= 0.6)
    else:
        check('skills', True)

    exp_exp = expected.get('experience') or []
    act_exp = actual.get('experience') or []
    if exp_exp:
        et = _norm((exp_exp[0] or {}).get('title'))
        titles = {_norm(e.get('title') or e.get('role')) for e in act_exp if isinstance(e, dict)}
        check('experience.title', any(et and et in t for t in titles) or any(t and t in et for t in titles))
        ec = _norm((exp_exp[0] or {}).get('company'))
        companies = {_norm(e.get('company')) for e in act_exp if isinstance(e, dict)}
        check('experience.company', ec in companies or any(ec and ec in c for c in companies))
    else:
        check('experience', True)

    return (hits / checks if checks else 0.0), misses


def score_jd_fields(actual: dict, expected: dict) -> tuple[float, list[str]]:
    misses: list[str] = []
    checks = 0
    hits = 0

    def check(path: str, ok: bool) -> None:
        nonlocal checks, hits
        checks += 1
        if ok:
            hits += 1
        else:
            misses.append(path)

    check('title', _norm(expected.get('title')) in _norm(actual.get('title')) or _norm(actual.get('title')) in _norm(expected.get('title')))
    if expected.get('location'):
        check(
            'location',
            _norm(expected.get('location')) in _norm(actual.get('location'))
            or _norm(actual.get('location')) in _norm(expected.get('location')),
        )
    exp_m = _list_norm(expected.get('mandatory_skills') or expected.get('skills'))
    act_m = _list_norm(actual.get('mandatory_skills') or actual.get('skills'))
    if exp_m:
        overlap = len(exp_m & act_m) / max(1, len(exp_m))
        check('mandatory_skills', overlap >= 0.5)
    act_r = actual.get('responsibilities') or []
    check('responsibilities', isinstance(act_r, list) and len(act_r) > 0)
    return (hits / checks if checks else 0.0), misses


def run_resume_case(case_dir: Path) -> dict:
    from app.ai.parser.deterministic_resume import parse_resume_deterministic
    from app.ai.parser.engine.knowledge import apply_knowledge_to_resume
    from app.ai.parser.engine.sections import detect_sections

    text = (case_dir / 'source.txt').read_text(encoding='utf-8')
    expected = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    sections = detect_sections(text, 'resume')
    toon, conf, missing, passes = parse_resume_deterministic(text)
    toon = apply_knowledge_to_resume(toon)
    score, misses = score_resume_fields(toon, expected)
    return {
        'id': case_dir.name,
        'type': 'resume',
        'score': score,
        'passes_gate': passes,
        'confidence': conf,
        'sections': len(sections),
        'misses': misses,
    }


def run_jd_case(case_dir: Path) -> dict:
    from app.ai.parser.engine.deterministic_jd import parse_jd_deterministic
    from app.ai.parser.engine.knowledge import apply_knowledge_to_jd
    from app.ai.parser.engine.sections import detect_sections

    text = (case_dir / 'source.txt').read_text(encoding='utf-8')
    expected = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    sections = detect_sections(text, 'jd')
    toon, conf, missing, passes = parse_jd_deterministic(text)
    toon = apply_knowledge_to_jd(toon)
    score, misses = score_jd_fields(toon, expected)
    return {
        'id': case_dir.name,
        'type': 'jd',
        'score': score,
        'passes_gate': passes,
        'confidence': conf,
        'sections': len(sections),
        'misses': misses,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--threshold', type=float, default=0.95, help='Mean accuracy gate')
    parser.add_argument('--target', type=float, default=0.99, help='Aspirational target')
    args = parser.parse_args()

    if not (LAKE / 'manifest.json').exists():
        print('Gold lake missing — generating…')
        from generate_gold_lake import main as gen

        gen()

    resume_dirs = sorted((LAKE / 'resumes').glob('resume_*'))
    jd_dirs = sorted((LAKE / 'jds').glob('jd_*'))
    results = []
    for d in resume_dirs:
        try:
            results.append(run_resume_case(d))
        except Exception as exc:
            results.append({'id': d.name, 'type': 'resume', 'score': 0.0, 'misses': [str(exc)]})
    for d in jd_dirs:
        try:
            results.append(run_jd_case(d))
        except Exception as exc:
            results.append({'id': d.name, 'type': 'jd', 'score': 0.0, 'misses': [str(exc)]})

    if not results:
        print('No cases found')
        return 2

    mean = sum(r['score'] for r in results) / len(results)
    resume_mean = sum(r['score'] for r in results if r['type'] == 'resume') / max(
        1, sum(1 for r in results if r['type'] == 'resume')
    )
    jd_mean = sum(r['score'] for r in results if r['type'] == 'jd') / max(
        1, sum(1 for r in results if r['type'] == 'jd')
    )

    report = {
        'cases': len(results),
        'mean_accuracy': round(mean, 4),
        'resume_mean': round(resume_mean, 4),
        'jd_mean': round(jd_mean, 4),
        'threshold': args.threshold,
        'target': args.target,
        'pass': mean >= args.threshold,
        'toward_99': mean >= args.target,
        'worst': sorted(results, key=lambda r: r['score'])[:5],
    }
    out = LAKE / 'last_eval_report.json'
    out.write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))
    if mean < args.threshold:
        print(f'FAIL: mean {mean:.4f} < threshold {args.threshold}')
        return 1
    print(f'PASS: mean {mean:.4f} ≥ threshold {args.threshold} (target {args.target})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
