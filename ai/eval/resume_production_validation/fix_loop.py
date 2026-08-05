"""Cluster failures and drive fix/rerun iterations."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any, Callable


# Signatures we treat as known fixable product bugs (vs genuine edge cases).
FIXABLE_SIGNATURE_PREFIXES = (
    'recall:email_in_source_not_filled',
    'recall:phone_in_source_not_filled',
    'apply:preferredLocation',
    'apply:currentLocation',
    'apply:education',
    'apply:fullName',
    'parity:',
    'short_text:',
    'ungrounded:email',
    'ungrounded:phone',
    'ungrounded:fullName',
    'nul',
    '0x00',
)


def cluster_failures(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    failed = [r for r in results if not r.get('passed') and not r.get('unsupported')]
    counter: Counter[str] = Counter()
    examples: dict[str, list[str]] = {}
    for r in failed:
        key = f"{r.get('category') or 'Other'}::{r.get('signature') or 'unknown'}"
        counter[key] += 1
        examples.setdefault(key, []).append(str(r.get('filename')))
    clusters = []
    for key, count in counter.most_common():
        cat, _, sig = key.partition('::')
        clusters.append({
            'key': key,
            'category': cat,
            'signature': sig,
            'count': count,
            'fixable': is_fixable_signature(sig),
            'examples': examples.get(key, [])[:10],
        })
    return clusters


def is_fixable_signature(signature: str) -> bool:
    sig = signature or ''
    return any(sig.startswith(p) or p in sig for p in FIXABLE_SIGNATURE_PREFIXES)


def mark_edge_cases(results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out = []
    for r in results:
        row = dict(r)
        if row.get('passed') or row.get('unsupported'):
            row['fixable'] = False
            row['genuine_edge_case'] = False
        else:
            fixable = is_fixable_signature(str(row.get('signature') or ''))
            row['fixable'] = fixable
            row['genuine_edge_case'] = not fixable
        out.append(row)
    return out


def write_fix_plan(out_dir: Path, clusters: list[dict[str, Any]]) -> Path:
    path = out_dir / 'grouped-failures' / 'fix-plan.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    plan = {
        'fixable_clusters': [c for c in clusters if c.get('fixable')],
        'edge_case_clusters': [c for c in clusters if not c.get('fixable')],
        'recommended_actions': [
            {
                'when': 'apply:preferredLocation / apply:currentLocation',
                'action': 'Map preferredLocation from currentLocation when only one location exists',
            },
            {
                'when': 'recall:email / phone',
                'action': 'Strengthen deterministic contact extractors / section headers',
            },
            {
                'when': 'apply:education',
                'action': 'Improve education degree/institution pairing in resume parsers',
            },
            {
                'when': 'short_text',
                'action': 'OCR DPI retry / layout enhance for scanned PDFs',
            },
        ],
    }
    path.write_text(json.dumps(plan, indent=2), encoding='utf-8')
    return path


def failed_case_ids(results: list[dict[str, Any]], *, only_fixable: bool = True) -> set[str]:
    ids = set()
    for r in results:
        if r.get('passed') or r.get('unsupported'):
            continue
        if only_fixable and not is_fixable_signature(str(r.get('signature') or '')):
            continue
        if r.get('case_id'):
            ids.add(r['case_id'])
    return ids


def merge_results(previous: list[dict], updates: list[dict]) -> list[dict]:
    by_id = {r['case_id']: r for r in previous if r.get('case_id')}
    for u in updates:
        if u.get('case_id'):
            by_id[u['case_id']] = u
    return list(by_id.values())


def run_fix_iterations(
    *,
    apply_code_fixes: Callable[[list[dict]], list[str]],
    rerun: Callable[[set[str]], list[dict]],
    results: list[dict],
    out_dir: Path,
    max_iterations: int = 5,
) -> list[dict]:
    current = mark_edge_cases(results)
    for i in range(1, max_iterations + 1):
        clusters = cluster_failures(current)
        write_fix_plan(out_dir, clusters)
        fixable_ids = failed_case_ids(current, only_fixable=True)
        if not fixable_ids:
            break
        notes = apply_code_fixes(clusters)
        (out_dir / 'logs' / f'fix_iteration_{i}.log').write_text(
            '\n'.join(notes) + f'\nrerun_count={len(fixable_ids)}\n',
            encoding='utf-8',
        )
        if not notes:
            # No automated code changes this round — stop looping
            break
        updates = rerun(fixable_ids)
        current = mark_edge_cases(merge_results(current, updates))
    return current
