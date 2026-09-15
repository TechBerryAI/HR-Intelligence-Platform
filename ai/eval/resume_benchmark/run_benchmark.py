"""Run the resume parsing benchmark against the gold corpus.

    # one-time (or whenever the spreadsheet changes)
    python ai/eval/resume_benchmark/ingest.py --xlsx <book.xlsx> --resumes <dir>

    # measure
    python ai/eval/resume_benchmark/run_benchmark.py
    python ai/eval/resume_benchmark/run_benchmark.py --llm --workers 4
    python ai/eval/resume_benchmark/run_benchmark.py --case <case_id> --show

    # lock in an improvement, then guard it
    python ai/eval/resume_benchmark/run_benchmark.py --set-baseline --write-thresholds
    python ai/eval/resume_benchmark/run_benchmark.py --gate
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

if __package__ in (None, ''):  # direct script execution
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    __package__ = 'resume_benchmark'

from .config import (  # noqa: E402
    BASELINE_LINK,
    FIELDS,
    RUNS_DIR,
    THRESHOLDS_FILE,
    load_thresholds,
)
from .ingest import load_case_gold, load_manifest  # noqa: E402
from .predict import ocr_status, predict_all  # noqa: E402
from .report import (  # noqa: E402
    build_summary,
    compare_to_thresholds,
    load_baseline,
    render_console,
    render_markdown,
    suggest_thresholds,
    write_json,
)
from .scoring import case_accuracy, score_case  # noqa: E402
from .triage import build_failure_modes, field_rollup, worst_cases  # noqa: E402


def _emit_yaml(data: dict) -> str:
    """Two-level scalar mapping to YAML - no PyYAML dependency at write time."""
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f'{section}:')
        for key, value in values.items():
            lines.append(f'  {key}: {value}')
        lines.append('')
    return '\n'.join(lines)


def _write_thresholds(data: dict) -> None:
    body = _emit_yaml(data)
    THRESHOLDS_FILE.write_text(
        '# Regression floors for the resume parsing benchmark.\n'
        '# Regenerate after a verified improvement:\n'
        '#   python ai/eval/resume_benchmark/run_benchmark.py --set-baseline --write-thresholds\n'
        + body,
        encoding='utf-8',
    )


_OCR_MISSING_HELP = """
Scanned / image-only resumes yield no text without OCR, so they score zero and
drag every aggregate down. This interpreter has no OCR engine.

The backend's own environment does. Run the benchmark with it:

    wsl -d Ubuntu -- bash -lc 'cd /mnt/d/Projects/HR-Intelligence-Platform && \\
      PYTHONPATH=apps/backend ./apps/backend/venv/bin/python \\
      ai/eval/resume_benchmark/run_benchmark.py --workers 4'

Or install the engine here:  pip install rapidocr-onnxruntime onnxruntime
Pass --allow-no-ocr to score anyway and mark the run as OCR-degraded.
"""


def preflight_ocr(args: argparse.Namespace) -> tuple[bool, str]:
    """Refuse to produce a silently degraded score when OCR is missing."""
    available, detail = ocr_status()
    if available:
        print(f'OCR engine: {detail}')
        return available, detail
    print(f'OCR engine: UNAVAILABLE - {detail}')
    if not args.allow_no_ocr:
        print(_OCR_MISSING_HELP)
        raise SystemExit(2)
    print('Continuing without OCR (--allow-no-ocr): results are not comparable '
          'to an OCR-enabled baseline.')
    return available, detail


def run(args: argparse.Namespace) -> dict:
    ocr_available, ocr_detail = preflight_ocr(args)
    manifest = load_manifest()
    cases = manifest['cases']
    if args.case:
        wanted = set(args.case)
        cases = [c for c in cases if c['case_id'] in wanted or c['file_name'] in wanted]
        if not cases:
            raise SystemExit(f'no case matched {sorted(wanted)}')
    if args.limit:
        cases = cases[: args.limit]

    case_ids = [c['case_id'] for c in cases]
    by_id = {c['case_id']: c for c in cases}

    print(f'Running {len(case_ids)} cases '
          f'(llm residual {"on" if args.llm else "off"}, workers {args.workers})')
    predictions = predict_all(
        case_ids,
        allow_semantic=bool(args.llm),
        reextract=bool(args.reextract),
        workers=max(1, args.workers),
        progress=not args.quiet,
    )

    case_results: list[dict] = []
    parse_times: list[float] = []
    for pred in predictions:
        case_id = pred['case_id']
        gold = load_case_gold(case_id)
        results = score_case(gold, pred.get('prediction') or {}, FIELDS)
        accuracy = case_accuracy(results, FIELDS)
        if pred.get('parse_ms'):
            parse_times.append(float(pred['parse_ms']))
        extract = pred.get('extract', {}) or {}
        case_results.append({
            'case_id': case_id,
            'file_name': by_id[case_id]['file_name'],
            'accuracy': accuracy,
            'error': pred.get('error', ''),
            'parse_ms': pred.get('parse_ms'),
            'used_llm': pred.get('used_llm'),
            'used_ocr': bool(extract.get('used_ocr')),
            'extract': extract,
            'missing_with_evidence': pred.get('missing_with_evidence', []),
            'fields': [r.to_dict() for r in results],
        })

    ocr_cases = [c for c in case_results if c['used_ocr']]
    ocr_scored = [c['accuracy'] for c in ocr_cases if not c['error']]
    meta = {
        'allow_semantic': bool(args.llm),
        'workers': args.workers,
        'mean_parse_ms': round(sum(parse_times) / len(parse_times), 1) if parse_times else None,
        'corpus_manifest': str(manifest.get('xlsx', '')),
        'ocr_available': ocr_available,
        'ocr_engine': ocr_detail,
        'ocr_cases': len(ocr_cases),
        'ocr_mean_accuracy': round(sum(ocr_scored) / len(ocr_scored), 4) if ocr_scored else None,
        'python': sys.executable,
    }
    payload = {
        'summary': build_summary(case_results, meta),
        'fields': field_rollup(case_results),
        'failure_modes': [m.to_dict() for m in build_failure_modes(case_results)],
        'worst_cases': worst_cases(case_results, limit=args.worst),
        'gold_issues': manifest.get('gold_issues', {}),
        'cases': case_results,
    }

    stamp = datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')
    run_dir = RUNS_DIR / stamp
    write_json(run_dir / 'results.json', payload)
    baseline = load_baseline()
    markdown = render_markdown(payload, baseline)
    (run_dir / 'report.md').write_text(markdown, encoding='utf-8')
    with (run_dir / 'predictions.jsonl').open('w', encoding='utf-8') as fh:
        for pred in predictions:
            fh.write(json.dumps(pred, ensure_ascii=False) + '\n')

    # Stable paths for the newest run, so tooling can always find it.
    write_json(RUNS_DIR / 'latest.json', payload)
    (RUNS_DIR / 'LATEST_REPORT.md').write_text(markdown, encoding='utf-8')

    print(render_console(payload, baseline))
    print(f'\nreport  : {run_dir / "report.md"}')
    print(f'results : {run_dir / "results.json"}')

    if args.show:
        for case in case_results:
            print(f'\n--- {case["case_id"]}  acc={case["accuracy"]:.3f}')
            for res in case['fields']:
                if res['verdict'] in ('match', 'blank_ok'):
                    continue
                print(f'  {res["verdict"]:<14} {res["field"]:<16} score={res["score"]:.2f}')
                print(f'      gold: {res["gold"][:160]}')
                print(f'      pred: {res["pred"][:160]}')

    # An OCR-degraded run must never become the reference: it would ratchet the
    # floors down and hide the regression it caused.
    if (args.set_baseline or args.write_thresholds) and not ocr_available:
        print('\nRefusing to record a baseline or thresholds from an OCR-degraded run.')
        print('Re-run with an OCR engine available, then record.')
        raise SystemExit(2)

    if args.set_baseline:
        write_json(BASELINE_LINK, payload)
        print(f'baseline set -> {BASELINE_LINK}')
    if args.write_thresholds:
        _write_thresholds(suggest_thresholds(payload, slack=args.slack))
        print(f'thresholds written -> {THRESHOLDS_FILE}')

    if args.gate:
        violations = compare_to_thresholds(payload, load_thresholds())
        if violations:
            print('\nREGRESSION GATE FAILED:')
            for v in violations:
                print(f'  - {v}')
            raise SystemExit(1)
        print('\nregression gate: PASS')

    return payload


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--limit', type=int, default=0, help='first N cases only')
    ap.add_argument('--case', action='append', help='case id or file name (repeatable)')
    ap.add_argument('--llm', action='store_true', help='allow the semantic residual pass')
    ap.add_argument('--workers', type=int, default=1)
    ap.add_argument('--reextract', action='store_true', help='ignore cached extracted text')
    ap.add_argument('--allow-no-ocr', action='store_true',
                    help='score even when no OCR engine is installed (degraded run)')
    ap.add_argument('--worst', type=int, default=15)
    ap.add_argument('--show', action='store_true', help='print every non-matching field')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--gate', action='store_true', help='fail on threshold regression')
    ap.add_argument('--set-baseline', action='store_true')
    ap.add_argument('--write-thresholds', action='store_true')
    ap.add_argument('--slack', type=float, default=0.02,
                    help='tolerance below the current run when writing thresholds')
    run(ap.parse_args())
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
