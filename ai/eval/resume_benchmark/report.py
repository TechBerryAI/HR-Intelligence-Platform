"""Scorecard rendering and baseline comparison."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import BASELINE_LINK, FIELD_BY_KEY

_ARROW = {1: 'up', 0: 'flat', -1: 'down'}


def _delta(current: float | None, previous: float | None) -> str:
    if current is None or previous is None:
        return '-'
    diff = current - previous
    if abs(diff) < 0.0005:
        return 'flat'
    return f'{diff:+.3f}'


def _pct(value: float | None) -> str:
    return '-' if value is None else f'{value * 100:.1f}%'


def build_summary(case_results: list[dict], meta: dict) -> dict:
    scored = [c for c in case_results if not c.get('error')]
    accuracies = [c.get('accuracy', 0.0) for c in scored]
    field_scores = [
        float(r['score'])
        for c in case_results
        for r in c.get('fields', [])
        if r.get('verdict') in ('match', 'partial', 'miss')
    ]
    verdicts: dict[str, int] = {}
    for c in case_results:
        for r in c.get('fields', []):
            verdicts[r['verdict']] = verdicts.get(r['verdict'], 0) + 1
    return {
        'generated_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
        'cases': len(case_results),
        'cases_parsed': len(scored),
        'cases_failed': len(case_results) - len(scored),
        'mean_case_accuracy': round(sum(accuracies) / len(accuracies), 4) if accuracies else 0.0,
        'mean_field_score': round(sum(field_scores) / len(field_scores), 4) if field_scores else 0.0,
        'field_observations': len(field_scores),
        'exact_match_rate': round(
            verdicts.get('match', 0) / len(field_scores), 4
        ) if field_scores else 0.0,
        'verdicts': verdicts,
        **meta,
    }


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding='utf-8')


def load_baseline() -> dict | None:
    if not BASELINE_LINK.exists():
        return None
    try:
        return json.loads(BASELINE_LINK.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return None


def render_markdown(payload: dict, baseline: dict | None = None) -> str:
    summary = payload['summary']
    fields = payload['fields']
    modes = payload['failure_modes']
    worst = payload['worst_cases']
    gold_issues = payload.get('gold_issues') or {}

    base_summary = (baseline or {}).get('summary') or {}
    base_fields = {f['field']: f for f in (baseline or {}).get('fields', [])}

    lines: list[str] = []
    add = lines.append

    add('# Resume Parsing Benchmark')
    add('')
    add(f'Run: `{summary["generated_at"]}` | corpus: **{summary["cases"]} cases** | '
        f'LLM residual: **{"on" if summary.get("allow_semantic") else "off"}** | '
        f'OCR: **{summary.get("ocr_engine") if summary.get("ocr_available") else "UNAVAILABLE"}**')
    if baseline:
        add(f'Baseline: `{base_summary.get("generated_at", "?")}`')
    add('')
    if not summary.get('ocr_available', True):
        add('> **OCR-degraded run.** No OCR engine was available, so scanned and '
            'image-only resumes produced no text and scored zero. These numbers are '
            'not comparable to an OCR-enabled baseline.')
        add('')

    add('## Headline')
    add('')
    add('| Metric | Value | vs baseline |')
    add('|---|---|---|')
    add(f'| Mean field score | {_pct(summary["mean_field_score"])} | '
        f'{_delta(summary["mean_field_score"], base_summary.get("mean_field_score"))} |')
    add(f'| Mean case accuracy | {_pct(summary["mean_case_accuracy"])} | '
        f'{_delta(summary["mean_case_accuracy"], base_summary.get("mean_case_accuracy"))} |')
    add(f'| Clean-match rate | {_pct(summary["exact_match_rate"])} | '
        f'{_delta(summary["exact_match_rate"], base_summary.get("exact_match_rate"))} |')
    add(f'| Cases that failed to parse | {summary["cases_failed"]} | '
        f'{_delta(float(summary["cases_failed"]), float(base_summary["cases_failed"])) if "cases_failed" in base_summary else "-"} |')
    add(f'| Scored field observations | {summary["field_observations"]} | - |')
    if summary.get('mean_parse_ms'):
        add(f'| Mean parse time | {summary["mean_parse_ms"]:.0f} ms | - |')
    ocr_n = summary.get('ocr_cases')
    if ocr_n is not None:
        ocr_mean = summary.get('ocr_mean_accuracy')
        add(f'| Resumes needing OCR | {ocr_n} | '
            f'{_delta(float(ocr_n), float(base_summary["ocr_cases"])) if "ocr_cases" in base_summary else "-"} |')
        if ocr_n:
            add(f'| Mean accuracy on OCR resumes | {_pct(ocr_mean)} | '
                f'{_delta(ocr_mean, base_summary.get("ocr_mean_accuracy"))} |')
    add('')
    add('Scores only count fields where the spreadsheet has a value. Fields the '
        'spreadsheet leaves blank are tracked separately as false positives.')
    add('')

    add('## Per-field scorecard')
    add('')
    add('| Field | W | Scored | Mean | Match | Partial | Miss | Blank gold | False pos | vs baseline |')
    add('|---|--:|--:|--:|--:|--:|--:|--:|--:|---|')
    for row in fields:
        prev = base_fields.get(row['field'], {})
        star = '*' if row['critical'] else ''
        add(
            f'| {row["label"]}{star} | {row["weight"]:g} | {row["scored_cases"]} | '
            f'{_pct(row["mean_score"])} | {row["match"]} | {row["partial"]} | {row["miss"]} | '
            f'{row["blank_gold"]} | {row["false_positive"]} | '
            f'{_delta(row["mean_score"], prev.get("mean_score"))} |'
        )
    add('')
    add('`*` = critical field (regression gate blocks on any drop).')
    add('')

    add('## Fix next (ranked by recoverable score)')
    add('')
    if not modes:
        add('No failure modes recorded.')
    else:
        add('| # | Failure mode | Field | Cases | Score lost |')
        add('|--:|---|---|--:|--:|')
        for i, mode in enumerate(modes[:15], 1):
            add(f'| {i} | `{mode["tag"]}` | {mode["field"]} | {mode["count"]} | '
                f'{mode["lost_score"]:.2f} |')
        add('')
        for i, mode in enumerate(modes[:8], 1):
            add(f'### {i}. `{mode["tag"]}`')
            add('')
            add(f'{mode["guidance"]}')
            add('')
            add(f'Affects {mode["count"]} case(s), {mode["lost_score"]:.2f} weighted score.')
            add('')
            for ex in mode['examples']:
                add(f'- **{ex["case_id"]}**')
                if ex.get('gold'):
                    add(f'  - gold: `{ex["gold"]}`')
                if ex.get('pred'):
                    add(f'  - pred: `{ex["pred"]}`')
                if ex.get('detail'):
                    add(f'  - detail: `{json.dumps(ex["detail"], ensure_ascii=False)[:400]}`')
            add('')

    add('## Weakest cases')
    add('')
    add('| Case | Accuracy | Weak fields |')
    add('|---|--:|---|')
    for case in worst:
        weak = ', '.join(case['weak_fields'][:8]) or '-'
        note = f' **[{case["error"]}]**' if case.get('error') else ''
        add(f'| `{case["case_id"]}`{note} | {_pct(case["accuracy"])} | {weak} |')
    add('')

    if gold_issues:
        add('## Benchmark quality warnings')
        add('')
        add('These gold cells look mis-authored. Every one of them caps the score the '
            'parser can reach, so correct the spreadsheet before chasing them in code.')
        add('')
        add('| Case | Issue |')
        add('|---|---|')
        for case_id, issues in list(gold_issues.items())[:30]:
            for issue in issues:
                add(f'| `{case_id}` | {issue} |')
        add('')

    add('## Method')
    add('')
    add('- Prediction path: `extract_document` -> `prepare_resume_working_text` -> '
        '`parse_resume_from_working_text` -> `map_candidate_to_form`, i.e. exactly the '
        'payload the Apply form receives.')
    add('- Scalar fields score by type-aware comparison (email set, last-10 phone digits, '
        'URL path key, name token set, location token containment, level enum).')
    add('- Skills score as set F1 after alias normalization.')
    add('- Education / Experience / Certifications score as **fact recall** (did every '
        'entity in the gold cell reach some form row?) combined with **row precision** '
        '(did any row match nothing in gold?) and date recall. Fact-level scoring is used '
        'because the gold cells are hand-written and split entries inconsistently.')
    add('')
    return '\n'.join(lines)


def render_console(payload: dict, baseline: dict | None = None) -> str:
    summary = payload['summary']
    base_summary = (baseline or {}).get('summary') or {}
    out = [
        '',
        '=' * 72,
        f'  Resume benchmark  |  {summary["cases"]} cases  |  '
        f'LLM residual {"on" if summary.get("allow_semantic") else "off"}',
        '=' * 72,
        f'  mean field score    {_pct(summary["mean_field_score"])}'
        f'   ({_delta(summary["mean_field_score"], base_summary.get("mean_field_score"))})',
        f'  mean case accuracy  {_pct(summary["mean_case_accuracy"])}'
        f'   ({_delta(summary["mean_case_accuracy"], base_summary.get("mean_case_accuracy"))})',
        f'  clean-match rate    {_pct(summary["exact_match_rate"])}',
        f'  failed to parse     {summary["cases_failed"]}',
        f'  OCR                 {summary.get("ocr_engine") if summary.get("ocr_available") else "UNAVAILABLE"}'
        f'   ({summary.get("ocr_cases", 0)} resumes needed it'
        + (f', mean {_pct(summary.get("ocr_mean_accuracy"))}' if summary.get('ocr_cases') else '')
        + ')',
        '-' * 72,
        '  field                 scored   mean    miss   falsepos',
    ]
    for row in payload['fields']:
        out.append(
            f'  {row["label"][:20]:<20} {row["scored_cases"]:>6}  '
            f'{_pct(row["mean_score"]):>6}  {row["miss"]:>6}  {row["false_positive"]:>8}'
        )
    out.append('-' * 72)
    out.append('  top fixes:')
    for mode in payload['failure_modes'][:6]:
        out.append(f'   {mode["lost_score"]:>6.2f}  {mode["tag"]}  ({mode["count"]} cases)')
    out.append('=' * 72)
    return '\n'.join(out)


def compare_to_thresholds(payload: dict, thresholds: dict[str, Any]) -> list[str]:
    """Return human-readable gate violations (empty means the gate passes)."""
    failures: list[str] = []
    summary = payload['summary']
    overall = thresholds.get('overall') or {}
    for key in ('mean_field_score', 'mean_case_accuracy'):
        floor = overall.get(key)
        if floor is not None and summary.get(key, 0.0) + 1e-9 < float(floor):
            failures.append(f'{key} {summary.get(key):.4f} < floor {float(floor):.4f}')
    max_failed = overall.get('max_cases_failed')
    if max_failed is not None and summary.get('cases_failed', 0) > int(max_failed):
        failures.append(f'cases_failed {summary["cases_failed"]} > max {max_failed}')

    per_field = thresholds.get('fields') or {}
    actual = {f['field']: f for f in payload['fields']}
    for key, floor in per_field.items():
        row = actual.get(key)
        if row is None or row.get('mean_score') is None:
            continue
        if row['mean_score'] + 1e-9 < float(floor):
            label = FIELD_BY_KEY[key].label if key in FIELD_BY_KEY else key
            failures.append(f'{label} {row["mean_score"]:.4f} < floor {float(floor):.4f}')
    return failures


MIN_SCORED_CASES_TO_GATE = 5
"""A field scored on a handful of resumes is too noisy to gate on."""


def suggest_thresholds(payload: dict, slack: float = 0.02) -> dict:
    """Thresholds that lock in the current run, minus a small tolerance."""
    summary = payload['summary']
    return {
        'overall': {
            'mean_field_score': round(max(0.0, summary['mean_field_score'] - slack), 4),
            'mean_case_accuracy': round(max(0.0, summary['mean_case_accuracy'] - slack), 4),
            'max_cases_failed': summary['cases_failed'],
        },
        'fields': {
            row['field']: round(max(0.0, row['mean_score'] - slack), 4)
            for row in payload['fields']
            if row['mean_score'] is not None
            and row['scored_cases'] >= MIN_SCORED_CASES_TO_GATE
        },
    }
