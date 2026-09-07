#!/usr/bin/env python3
"""Evaluate resumes through POST /api/parse/resume/public.

Does not modify production parser code. Writes artifacts under _forensic_tmp/.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.eval.apply_public_eval.sample import (  # noqa: E402
    DEFAULT_CORPUS,
    list_corpus_files,
    list_skipped_files,
    load_reference,
    select_diverse,
)
from ai.eval.apply_public_eval.score import aggregate, evaluate_case, slim_form  # noqa: E402

DEFAULT_API = os.environ.get('APPLY_EVAL_API', 'http://127.0.0.1:3000')
DEFAULT_OUT = ROOT / '_forensic_tmp' / 'apply_public_eval'


def _health(api: str) -> dict:
    url = api.rstrip('/') + '/health'
    with urllib.request.urlopen(url, timeout=8) as resp:
        body = json.loads(resp.read().decode('utf-8'))
        body['_http_status'] = resp.status
        return body


def _extract(path: Path) -> str:
    """Same extract entry as Apply ``_run_resume`` (not a second parser)."""
    data = path.read_bytes()
    try:
        from app.ai.parser.text_extraction import extract_text

        return extract_text(data, path.name) or ''
    except Exception:
        return ''


def _inprocess_form(path: Path, raw: str) -> dict:
    from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
    from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
    from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text

    data = path.read_bytes()
    working = prepare_resume_working_text(raw, file_data=data)
    profile, coverage, *_rest = parse_resume_from_working_text(
        working,
        allow_semantic=False,
        source_filename=path.name,
    )
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    return form.to_autofill_dict()


def _post_public(api: str, path: Path, timeout: int = 120) -> tuple[int, dict]:
    boundary = '----ApplyEvalBoundary7f3a'
    data = path.read_bytes()
    filename = path.name.replace('"', '')
    parts = []
    parts.append(f'--{boundary}'.encode())
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{filename}"'.encode(),
    )
    ctype = (
        'application/pdf'
        if path.suffix.lower() == '.pdf'
        else 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
    parts.append(f'Content-Type: {ctype}'.encode())
    parts.append(b'')
    parts.append(data)
    parts.append(f'--{boundary}--'.encode())
    parts.append(b'')
    body = b'\r\n'.join(parts)
    req = urllib.request.Request(
        api.rstrip('/') + '/api/parse/resume/public',
        data=body,
        method='POST',
        headers={
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        },
    )
    token = os.environ.get('DOCUMENT_INTELLIGENCE_VALIDATION_TOKEN', '').strip()
    if token:
        req.add_header('X-Validation-Token', token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode('utf-8', errors='replace')
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {'status': 'error', 'error': raw[:500]}
        return exc.code, payload


def _post_with_retry(api: str, path: Path) -> tuple[int, dict]:
    status, payload = _post_public(api, path)
    if status != 429:
        return status, payload
    time.sleep(8)
    return _post_public(api, path)


def _pct(value: float | None) -> str:
    return '—' if value is None else f'{value:.0%}'


def _render_report(summary: dict, cases: list[dict], health: dict, skipped: list[str] | None = None) -> str:
    pf = summary['per_field']
    lines = [
        '# Public Apply resume evaluation',
        '',
        f"- API pid: {health.get('pid')}",
        f"- Total resumes: {summary['total']}",
        f"- Acceptable (no parser/API failure): {summary['acceptable']}",
        f"- Failures: {summary['failure_count']}",
        f"- Class counts (resumes with that class): {summary['class_counts_resumes']}",
        '',
        '## Phase 2 training backlog (ranked)',
        '',
        'Gold-label the example files, then fix deterministic parsers + coverage recovery. '
        'Do not train on Class C / absent fields. API clusters are not parser work.',
        '',
        '| Rank | Section | Impact | Class B | weak_missing | weak_ungrounded | Why |',
        '|---:|---|---:|---:|---:|---:|---|',
    ]
    backlog = summary.get('training_backlog') or []
    if not backlog:
        lines.append('| — | none | 0 | 0 | 0 | 0 | No parser-training targets. |')
    for i, item in enumerate(backlog, 1):
        lines.append(
            f"| {i} | {item.get('section')} | {item.get('impact')} | "
            f"{item.get('class_b')} | {item.get('weak_missing')} | "
            f"{item.get('weak_ungrounded')} | {item.get('why')} |"
        )
    lines += ['']
    for item in backlog:
        examples = ', '.join(item.get('examples') or []) or '—'
        reasons = ', '.join(
            f"{r.get('reason')} ({r.get('count')})" for r in (item.get('top_reasons') or [])
        ) or '—'
        lines.append(f"- **{item.get('section')}** — {item.get('phase2')}")
        lines.append(f"  - reasons: {reasons}")
        lines.append(f"  - examples: {examples}")
        lines.append('')

    lines += [
        '## Per-field accuracy (among scored; n/a = source does not support)',
        '',
        '| Field | pass | fail | n/a | accuracy |',
        '|---|---:|---:|---:|---:|',
    ]
    for key, st in pf.items():
        lines.append(
            f"| {key} | {st['pass']} | {st['fail']} | {st['n/a']} | {_pct(st['accuracy'])} |"
        )

    lines += [
        '',
        '## Empty rates (form blank, regardless of source support)',
        '',
        '| Field | empty | filled | empty rate |',
        '|---|---:|---:|---:|',
    ]
    for key, st in (summary.get('empty_rates') or {}).items():
        lines.append(f"| {key} | {st['empty']} | {st['filled']} | {_pct(st.get('rate'))} |")

    lines += [
        '',
        '## Coverage (`missing_with_evidence` = true weak section)',
        '',
        '| Field | filled | recovered | missing_with_evidence | missing_no_evidence | other |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    cov = summary.get('coverage_counts') or {}
    if not cov:
        lines.append('| — | 0 | 0 | 0 | 0 | 0 |')
    for field, st in cov.items():
        lines.append(
            f"| {field} | {st.get('filled', 0)} | {st.get('recovered', 0)} | "
            f"{st.get('missing_with_evidence', 0)} | {st.get('missing_no_evidence', 0)} | "
            f"{st.get('other', 0)} |"
        )

    lines += [
        '',
        '## Field Trace verdicts',
        '',
        '| Field | ok | weak_missing | weak_ungrounded | absent | fallback |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for field, st in (summary.get('verdict_counts') or {}).items():
        lines.append(
            f"| {field} | {st.get('ok', 0)} | {st.get('weak_missing', 0)} | "
            f"{st.get('weak_ungrounded', 0)} | {st.get('absent', 0)} | {st.get('fallback', 0)} |"
        )

    lines += [
        '',
        '## Failure clusters (section / reason)',
        '',
        '| Section | Class | Reason | Count | Examples |',
        '|---|---|---|---:|---|',
    ]
    clusters = summary.get('clusters') or []
    if not clusters:
        lines.append('| — | — | none | 0 | |')
    for c in clusters:
        examples = ', '.join(c.get('examples') or [])
        lines.append(
            f"| {c.get('section')} | {c.get('class')} | {c.get('reason')} | "
            f"{c.get('count')} | {examples} |"
        )

    if skipped:
        lines += ['', '## Skipped (unsupported Apply formats)', '']
        for name in skipped:
            lines.append(f'- {name}')

    lines += ['', '## Failures', '']
    fails = summary.get('failures') or []
    if not fails:
        lines.append('None.')
    for f in fails:
        lines.append(f"- **{f.get('file')}** classes={f.get('classes')} issues={f.get('issues')}")

    fail_names = {f.get('file') for f in fails}
    lines += ['', '## Recorded Form DTOs (failures only; full dump in cases.json)', '']
    dumped = 0
    for case in cases:
        if case.get('file') not in fail_names:
            continue
        dumped += 1
        ev = case.get('evaluation') or {}
        form = ev.get('form') or {}
        traces = ev.get('field_trace') or {}
        weak = ', '.join(
            f"{k}:{v.get('verdict')}"
            for k, v in traces.items()
            if isinstance(v, dict) and v.get('verdict') in ('weak_missing', 'weak_ungrounded')
        ) or '—'
        lines.append(f"### {case.get('file')}")
        lines.append(f"- acceptable: {ev.get('acceptable')} classes={ev.get('classes')}")
        lines.append(f"- Name: {form.get('name')} | Email: {form.get('email')} | Phone: {form.get('phone')}")
        lines.append(f"- Location: {form.get('location')} | LinkedIn: {form.get('linkedin')}")
        lines.append(f"- Experience: {form.get('experiences')}")
        lines.append(f"- Education: {form.get('education')}")
        lines.append(f"- Skills: {form.get('skills')}")
        summ = form.get('summary') or ''
        lines.append(f"- Summary: {summ[:220]}")
        lines.append(f"- Weak trace: {weak}")
        lines.append('')
    if dumped == 0:
        lines.append('None.')
    return '\n'.join(lines) + '\n'


def _render_training_backlog(summary: dict) -> str:
    lines = [
        '# Phase 2 training backlog',
        '',
        'From the full Apply parse diagnostic.',
        '',
        'In this repo training means gold fixtures (`expected_form.json`) plus deterministic',
        'section parsers and coverage recovery — not QLoRA / custom weights.',
        '',
        f"- Corpus: `{summary.get('corpus')}`",
        f"- Mode: {summary.get('mode')}",
        f"- Total scored: {summary.get('total')}",
        f"- Parser/API failures: {summary.get('failure_count')}",
        '',
        '## Ranked sections',
        '',
    ]
    backlog = summary.get('training_backlog') or []
    if not backlog:
        lines.append('No parser-training targets.')
        return '\n'.join(lines) + '\n'
    for i, item in enumerate(backlog, 1):
        lines.append(f"## {i}. {item.get('section')} (impact {item.get('impact')})")
        lines.append('')
        lines.append(item.get('why') or '')
        lines.append('')
        lines.append(f"- Class B resumes: {item.get('class_b')}")
        lines.append(f"- weak_missing: {item.get('weak_missing')}")
        lines.append(f"- weak_ungrounded: {item.get('weak_ungrounded')}")
        lines.append(f"- Next step: {item.get('phase2')}")
        reasons = item.get('top_reasons') or []
        if reasons:
            lines.append('- Top reasons:')
            for r in reasons:
                lines.append(f"  - `{r.get('reason')}` × {r.get('count')}")
        examples = item.get('examples') or []
        if examples:
            lines.append('- Gold-label these first:')
            for name in examples:
                lines.append(f'  - {name}')
        lines.append('')
    lines += [
        '## Suggested Phase 2 order',
        '',
        '1. Add `expected_form.json` gold for the example files of rank 1.',
        '2. Fix that section parser under `apps/backend/app/ai/document_intelligence/parsers/resume/`.',
        '3. Re-run `python ai/eval/apply_public_eval/run.py --all --out _forensic_tmp/apply_public_eval_full`.',
        '4. Repeat down the ranked list. Skip `api` and Class C / absent fields.',
        '',
    ]
    return '\n'.join(lines) + '\n'


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description='Public Apply resume evaluation (read-only)')
    parser.add_argument('--api', default=DEFAULT_API)
    parser.add_argument('--corpus', type=Path, default=DEFAULT_CORPUS)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    parser.add_argument('--n', type=int, default=16)
    parser.add_argument(
        '--all',
        action='store_true',
        help='Evaluate every PDF/DOCX in the corpus (skip 10–20 diverse sample)',
    )
    parser.add_argument('--references', type=Path, default=ROOT / 'ai' / 'eval' / 'apply_public_eval' / 'references')
    args = parser.parse_args(argv)

    print('Checking backend health...')
    try:
        health = _health(args.api)
    except Exception as exc:
        print(f'ERROR: backend not reachable at {args.api}/health ({exc})')
        return 2
    if health.get('status') != 'ok':
        print(f'ERROR: unexpected health payload: {health}')
        return 2
    print(f"Health OK pid={health.get('pid')} status={health.get('status')}")

    files = list_corpus_files(args.corpus)
    skipped = list_skipped_files(args.corpus)
    sample = files if args.all else select_diverse(files, n=args.n)
    if not sample:
        print(f'ERROR: no pdf/docx files in {args.corpus}')
        return 2
    mode = 'all' if args.all else f'diverse n={args.n}'
    print(f'Evaluating {len(sample)} resumes ({mode}) via POST /api/parse/resume/public')
    if skipped:
        print(f'Skipping {len(skipped)} unsupported files: {[p.name for p in skipped]}')

    out_dir = args.out.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cases: list[dict] = []

    for i, path in enumerate(sample, 1):
        print(f'[{i}/{len(sample)}] {path.name}', flush=True)
        raw = _extract(path)
        inproc = {}
        inproc_err = None
        try:
            inproc = _inprocess_form(path, raw)
        except Exception as exc:
            inproc_err = str(exc)
        status, payload = _post_with_retry(args.api, path)
        form = (payload or {}).get('form') if isinstance(payload, dict) else {}
        server_raw = ''
        coverage = None
        if isinstance(payload, dict):
            server_raw = payload.get('raw_text') or ''
            coverage = payload.get('coverage')
        if isinstance(form, dict) and coverage is None:
            coverage = form.get('coverage')
        if coverage is None and isinstance(inproc, dict):
            coverage = inproc.get('coverage')
        extract_for_score = server_raw or raw
        local_extract_ok = len(raw.strip()) >= 40
        ref = load_reference(path, args.references if args.references.is_dir() else None)
        evaluation = evaluate_case(
            form=form or {},
            extract=extract_for_score,
            http_status=status,
            inproc_form=(inproc or None) if local_extract_ok else None,
            reference=ref,
            extract_short=len(extract_for_score.strip()) < 40,
            coverage=coverage if isinstance(coverage, list) else None,
        )
        rec = {
            'file': path.name,
            'suffix': path.suffix.lower(),
            'http_status': status,
            'http_error': None if status == 200 else payload,
            'extract_chars': len(raw),
            'inprocess_error': inproc_err,
            'http_vs_inprocess': slim_form(form) == slim_form(inproc) if inproc else None,
            'evaluation': evaluation,
        }
        cases.append(rec)
        time.sleep(0.3)

    summary = aggregate(cases)
    summary['health_pid'] = health.get('pid')
    summary['corpus'] = str(args.corpus)
    summary['mode'] = 'all' if args.all else 'diverse'
    summary['skipped'] = [p.name for p in skipped]
    (out_dir / 'cases.json').write_text(
        json.dumps(cases, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    (out_dir / 'summary.json').write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    report = _render_report(summary, cases, health, skipped=[p.name for p in skipped])
    (out_dir / 'report.md').write_text(report, encoding='utf-8')
    backlog_md = _render_training_backlog(summary)
    (out_dir / 'training_backlog.md').write_text(backlog_md, encoding='utf-8')
    try:
        print(report)
    except UnicodeEncodeError:
        sys.stdout.buffer.write((report + '\n').encode('utf-8', errors='replace'))
    print(f'Wrote {out_dir / "report.md"}')
    print(f'Wrote {out_dir / "training_backlog.md"}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
