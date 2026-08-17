#!/usr/bin/env python3
"""
Comparative AI parse performance harness.

Measures deterministic vs semantic/Ollama time separately. Does not invent SLAs.
Default: LLM off (deterministic gold path). Use --with-llm only when Ollama is reachable.

Usage (repo root):
  PYTHONPATH=apps/backend python ai/eval/run_ai_performance_benchmark.py
  PYTHONPATH=apps/backend python ai/eval/run_ai_performance_benchmark.py --with-llm
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'apps' / 'backend'
for p in (str(BACKEND), str(BACKEND / 'app')):
    if p not in sys.path:
        sys.path.insert(0, p)

LAKE = ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'
FIXTURE_RESUMES = ROOT / 'tests' / 'backend' / 'fixtures' / 'resume_gold'
CAPABILITY_MAX_TOKENS = 8192


def _norm(s: Any) -> str:
    import re

    return re.sub(r'\s+', ' ', str(s or '').strip().lower())


def _score_resume(actual: dict, expected: dict) -> tuple[float, list[str]]:
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
    if ep.get('email'):
        check('person.email', _norm(ap.get('email')) == _norm(ep.get('email')))
    if ep.get('name'):
        check('person.name', _norm(ep.get('name'))[:6] in _norm(ap.get('name')))
    exp_skills = {_norm(v) for v in (expected.get('skills') or []) if str(v).strip()}
    act_skills = {_norm(v) for v in (actual.get('skills') or []) if str(v).strip()}
    if exp_skills:
        check('skills', (len(exp_skills & act_skills) / max(1, len(exp_skills))) >= 0.5)
    return (hits / checks if checks else 1.0), misses


def _cases() -> list[tuple[str, str, dict]]:
    out: list[tuple[str, str, dict]] = []
    lake_resumes = LAKE / 'resumes'
    if lake_resumes.exists():
        for d in sorted(lake_resumes.glob('resume_*')):
            src = d / 'source.txt'
            exp = d / 'expected_toon.json'
            if src.exists() and exp.exists():
                out.append(
                    (d.name, src.read_text(encoding='utf-8'), json.loads(exp.read_text(encoding='utf-8')))
                )
    if not out and FIXTURE_RESUMES.exists():
        for src in sorted(FIXTURE_RESUMES.glob('*.txt')):
            out.append((src.stem, src.read_text(encoding='utf-8'), {}))
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--with-llm', action='store_true', help='Allow residual Ollama (live)')
    parser.add_argument('--limit', type=int, default=12, help='Max gold/fixture cases')
    parser.add_argument('--json', action='store_true', help='Print JSONL only')
    args = parser.parse_args()

    if args.with_llm:
        os.environ['DOCUMENT_INTELLIGENCE_SEMANTIC_AI'] = 'true'
        os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = 'false'
    else:
        os.environ['RESUME_SKIP_LLM_WHEN_DETERMINISTIC'] = 'true'
        os.environ['DOCUMENT_INTELLIGENCE_SEMANTIC_AI'] = 'false'

    from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
    from app.ai.document_intelligence.serialize.toon import candidate_to_toon
    from app.ai.parser.engine.hardware import apply_hardware_env, detect_hardware_profile

    hw = apply_hardware_env()
    profile = detect_hardware_profile()
    model = profile.preferred_model_hint
    rows: list[dict[str, Any]] = []
    ollama_calls = {'n': 0, 'chars': 0, 'ms': 0.0}

    if args.with_llm:
        import app.ai.adapter.runtime_adapter as adapter

        orig = adapter.parse_via_runtime

        def _wrap(text, doc_type, **kwargs):
            ollama_calls['n'] += 1
            st = time.perf_counter()
            result = orig(text, doc_type, **kwargs)
            ollama_calls['ms'] += (time.perf_counter() - st) * 1000.0
            if isinstance(result, dict):
                ollama_calls['chars'] = max(ollama_calls['chars'], len(json.dumps(result)))
            elif isinstance(result, str):
                ollama_calls['chars'] = max(ollama_calls['chars'], len(result))
            return result

        adapter.parse_via_runtime = _wrap

    cases = _cases()[: max(1, args.limit)]
    if not cases:
        print('No gold/fixture cases found', file=sys.stderr)
        return 2

    for case_id, text, expected in cases:
        ollama_calls['n'] = 0
        ollama_calls['chars'] = 0
        ollama_calls['ms'] = 0.0
        t0 = time.perf_counter()
        try:
            profile_obj, form, toon = parse_resume_text_to_canonical(text, max_workers=2)
            total_ms = (time.perf_counter() - t0) * 1000.0
            semantic_ms = ollama_calls['ms']
            det_ms = max(0.0, total_ms - semantic_ms)
            invoked = ollama_calls['n'] > 0
            toon_dict = toon if isinstance(toon, dict) else candidate_to_toon(profile_obj)
            score, misses = _score_resume(toon_dict, expected) if expected else (1.0, [])
            row = {
                'hardware_profile': hw.name,
                'model': model,
                'case_id': case_id,
                'deterministic_ms': round(det_ms, 2),
                'semantic_ms': round(semantic_ms, 2),
                'total_ms': round(total_ms, 2),
                'cache_status': 'miss',
                'ollama_invoked': invoked,
                'success': True,
                'correctness': round(score, 4),
                'misses': misses,
                'output_chars': ollama_calls['chars'],
                'max_tokens': CAPABILITY_MAX_TOKENS,
                'near_token_limit': ollama_calls['chars'] > int(CAPABILITY_MAX_TOKENS * 3.5),
            }
        except Exception as exc:
            row = {
                'hardware_profile': hw.name,
                'model': model,
                'case_id': case_id,
                'deterministic_ms': None,
                'semantic_ms': None,
                'total_ms': round((time.perf_counter() - t0) * 1000.0, 2),
                'cache_status': 'error',
                'ollama_invoked': ollama_calls['n'] > 0,
                'success': False,
                'correctness': 0.0,
                'misses': [str(exc)],
                'output_chars': 0,
                'max_tokens': CAPABILITY_MAX_TOKENS,
                'near_token_limit': False,
            }
        rows.append(row)
        if args.json:
            print(json.dumps(row))

    # Second pass on first case: runtime should already be warm (not a content-hash cache).
    if cases and args.with_llm:
        case_id, text, expected = cases[0]
        t0 = time.perf_counter()
        parse_resume_text_to_canonical(text, max_workers=2)
        warm_ms = (time.perf_counter() - t0) * 1000.0
        rows.append({
            'hardware_profile': hw.name,
            'model': model,
            'case_id': f'{case_id}:warm-runtime',
            'deterministic_ms': None,
            'semantic_ms': None,
            'total_ms': round(warm_ms, 2),
            'cache_status': 'runtime-reuse',
            'ollama_invoked': True,
            'success': True,
            'correctness': None,
            'misses': [],
            'output_chars': 0,
            'max_tokens': CAPABILITY_MAX_TOKENS,
            'near_token_limit': False,
        })

    if not args.json:
        print(f'profile={hw.name} source={hw.detection_source} model={model} with_llm={args.with_llm}')
        print(json.dumps(rows, indent=2))
        print(
            'Note: numbers are for THIS machine only. Do not treat them as universal SLAs. '
            'max_tokens remains 8192 unless output_chars approaches the cap on --with-llm runs.'
        )
    return 0 if all(r.get('success') for r in rows) else 1


if __name__ == '__main__':
    raise SystemExit(main())
