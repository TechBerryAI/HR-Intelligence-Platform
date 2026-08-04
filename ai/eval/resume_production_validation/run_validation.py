#!/usr/bin/env python3
"""
Production E2E validation for Resume Intelligence autofill.

Uploads every supported resume through the validation harness (same public
parse/SSE path as ApplyJobModal), verifies form correctness, writes
validation-report/, then optionally fix/rerun failed clusters.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ai.eval.resume_production_validation.artifacts import (  # noqa: E402
    ensure_report_dirs,
    invalidate_infra_checkpoint,
    load_checkpoint,
)
from ai.eval.resume_production_validation.corpus import discover_corpus  # noqa: E402
from ai.eval.resume_production_validation.fix_loop import (  # noqa: E402
    cluster_failures,
    mark_edge_cases,
    run_fix_iterations,
    write_fix_plan,
)
from ai.eval.resume_production_validation.playwright_runner import run_corpus  # noqa: E402
from ai.eval.resume_production_validation.report import write_reports  # noqa: E402


def _health(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _require_services(api_url: str, base_url: str, *, allow_offline: bool = False) -> None:
    api_ok = _health(f'{api_url.rstrip("/")}/health') or _health(api_url)
    fe_ok = _health(base_url)
    if allow_offline:
        if not api_ok:
            print(f'WARNING: API not reachable at {api_url} — continuing anyway')
        if not fe_ok:
            print(f'WARNING: Frontend not reachable at {base_url}')
        return
    if not api_ok:
        print(f'ERROR: API not reachable at {api_url}. Start backend on :3000 first.')
        raise SystemExit(2)
    if not fe_ok:
        print(f'ERROR: Frontend not reachable at {base_url}. Start Vite with VITE_VALIDATION_HARNESS=true.')
        raise SystemExit(2)
    print(f'Services OK: API={api_url} FE={base_url}')


def _apply_known_code_fixes(clusters: list[dict]) -> list[str]:
    notes: list[str] = []
    sigs = ' '.join(f"{c.get('signature')}|{c.get('category')}" for c in clusters[:40])
    from ai.eval.resume_production_validation import apply_fixes

    if 'preferredLocation' in sigs or 'currentLocation' in sigs:
        mapping = ROOT / 'apps/backend/app/ai/document_intelligence/mapping/resume_form.py'
        if apply_fixes.ensure_preferred_location_fallback(mapping):
            notes.append('Applied preferredLocation fallback from currentLocation')
        else:
            notes.append('preferredLocation fallback already present — rerun location failures')
        if apply_fixes.ensure_location_header_cities():
            notes.append('Expanded location city list / header scan')
        else:
            notes.append('location city list already expanded — rerun location failures')

    if 'email_in_source_not_filled' in sigs or 'phone_in_source_not_filled' in sigs:
        if apply_fixes.ensure_whole_doc_phone_scan():
            notes.append('Phone extractor now scans whole document')
        else:
            notes.append('whole-doc phone scan already present — rerun phone recall failures')
        if apply_fixes.ensure_contact_header_scan():
            notes.append('Contact whole-doc scan marker applied')

    if 'apply:education' in sigs or 'Academic' in sigs or 'ungrounded:education' in sigs:
        if apply_fixes.ensure_academic_details_alias():
            notes.append('Added Academic Details education section aliases')
        else:
            notes.append('education aliases already present — rerun education failures')
        if apply_fixes.ensure_education_degree_institution_fallback():
            notes.append('Education mapper degree/institution fallback strengthened')

    if 'apply:fullName' in sigs or 'ungrounded:fullName' in sigs:
        if apply_fixes.ensure_personal_name_fulltext_fallback():
            notes.append('parse_personal falls back to full document for name')
        else:
            notes.append('name fulltext fallback already present — rerun fullName failures')

    if 'nul' in sigs.lower() or '0x00' in sigs:
        if apply_fixes.ensure_nul_byte_strip():
            notes.append('NUL-byte strip added to pipeline')
        else:
            notes.append('NUL-byte strip already present — restart backend to load')

    if 'short_text' in sigs or 'OCR/Text extraction' in sigs:
        if apply_fixes.ensure_ocr_dpi_retry():
            notes.append('OCR DPI retry on insufficient text')
        else:
            notes.append('OCR DPI retry already present — rerun short_text failures')

    return notes


def invalidate_fixable_product_failures(checkpoint_path: Path) -> tuple[dict[str, dict], int]:
    """Drop fixable product-failure rows so they are retested after code fixes."""
    from ai.eval.resume_production_validation.fix_loop import is_fixable_signature

    if not checkpoint_path.exists():
        return {}, 0
    kept: dict[str, dict] = {}
    dropped = 0
    lines_out: list[str] = []
    with checkpoint_path.open(encoding='utf-8') as fh:
        for line in fh:
            raw = line.strip()
            if not raw:
                continue
            try:
                row = json.loads(raw)
            except json.JSONDecodeError:
                continue
            cid = row.get('case_id')
            if not cid:
                continue
            if (
                not row.get('passed')
                and not row.get('unsupported')
                and is_fixable_signature(str(row.get('signature') or ''))
            ):
                dropped += 1
                continue
            kept[cid] = row
            lines_out.append(json.dumps(row, default=str))
    checkpoint_path.write_text(
        ('\n'.join(lines_out) + '\n') if lines_out else '',
        encoding='utf-8',
    )
    return kept, dropped


def main(argv: list[str] | None = None) -> int:
    import os

    # Prefer repo-local Playwright browsers (stable across sandbox/process pools)
    browsers = ROOT / '.playwright-browsers'
    if browsers.is_dir() and not os.environ.get('PLAYWRIGHT_BROWSERS_PATH'):
        os.environ['PLAYWRIGHT_BROWSERS_PATH'] = str(browsers)

    parser = argparse.ArgumentParser(description='Resume production E2E validation')
    parser.add_argument('--corpus', type=Path, default=ROOT / 'Resumes')
    parser.add_argument('--out', type=Path, default=ROOT / 'validation-report')
    parser.add_argument('--base-url', default='http://127.0.0.1:5173')
    parser.add_argument('--api-url', default='http://127.0.0.1:3000')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--timeout-ms', type=int, default=180_000)
    parser.add_argument('--limit', type=int, default=0, help='Limit supported files (0=all)')
    parser.add_argument('--smoke', type=int, default=0, help='Run N mixed smoke files then exit')
    parser.add_argument('--fix-loop', action='store_true')
    parser.add_argument('--max-fix-iterations', type=int, default=5)
    parser.add_argument('--headed', action='store_true')
    parser.add_argument('--resume', action='store_true', help='Resume from checkpoint.jsonl')
    parser.add_argument(
        '--invalidate-infra',
        action='store_true',
        default=False,
        help='Drop Frontend/Timeout infra failures from checkpoint so they are retested',
    )
    parser.add_argument(
        '--allow-offline',
        action='store_true',
        help='Warn instead of aborting when API/FE are unreachable',
    )
    args = parser.parse_args(argv)

    # With --resume, invalidate infra failures by default unless explicitly skipped
    invalidate = args.invalidate_infra or args.resume

    out_dir = args.out.resolve()
    ensure_report_dirs(out_dir)
    checkpoint = out_dir / 'checkpoint.jsonl'

    print('Checking services...')
    _require_services(args.api_url, args.base_url, allow_offline=args.allow_offline)

    supported, unsupported_items = discover_corpus(args.corpus.resolve())
    unsupported_rows = [
        {
            'filename': u.rel_name,
            'ext': u.ext,
            'size': u.size,
            'skip_reason': u.skip_reason,
            'unsupported': True,
            'passed': False,
            'case_id': u.case_id,
        }
        for u in unsupported_items
    ]

    if args.smoke:
        by_ext: dict[str, list] = {}
        for it in supported:
            by_ext.setdefault(it.ext, []).append(it)
        sample = []
        for ext in ('pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp'):
            for it in by_ext.get(ext, [])[: max(1, args.smoke // 4)]:
                if it not in sample:
                    sample.append(it)
                if len(sample) >= args.smoke:
                    break
            if len(sample) >= args.smoke:
                break
        supported = sample[: args.smoke]
        print(f'Smoke mode: {len(supported)} files')
    elif args.limit and args.limit > 0:
        supported = supported[: args.limit]
        print(f'Limited to {len(supported)} supported files')

    already: dict[str, dict] = {}
    if args.resume and checkpoint.exists():
        if invalidate:
            already, dropped = invalidate_infra_checkpoint(checkpoint)
            print(f'Invalidated {dropped} infra failure rows from checkpoint')
        else:
            already = load_checkpoint(checkpoint)
        if args.fix_loop:
            already, dropped_fixable = invalidate_fixable_product_failures(checkpoint)
            print(f'Invalidated {dropped_fixable} fixable product failure rows for retest')
    print(
        f'Supported={len(supported)} unsupported={len(unsupported_rows)} '
        f'checkpointed={len(already)}'
    )

    def on_result(row: dict) -> None:
        status = 'PASS' if row.get('passed') else f"FAIL[{row.get('category')}]"
        print(f"[{status}] {row.get('filename')} ({row.get('elapsed_ms')} ms)", flush=True)

    results = run_corpus(
        supported,
        out_dir=out_dir,
        base_url=args.base_url.rstrip('/'),
        workers=max(1, args.workers),
        timeout_ms=args.timeout_ms,
        checkpoint_path=checkpoint,
        already_done=already,
        on_result=on_result,
        headless=not args.headed,
    )

    results = mark_edge_cases(results)

    if args.fix_loop:
        def apply_fixes(clusters):
            return _apply_known_code_fixes(clusters)

        def rerun(case_ids: set[str]):
            subset = [it for it in supported if it.case_id in case_ids]
            if checkpoint.exists():
                lines = []
                for line in checkpoint.read_text(encoding='utf-8').splitlines():
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get('case_id') not in case_ids:
                        lines.append(line)
                checkpoint.write_text('\n'.join(lines) + ('\n' if lines else ''), encoding='utf-8')
            print(f'Rerunning {len(subset)} failed cases after fixes...', flush=True)
            return run_corpus(
                subset,
                out_dir=out_dir,
                base_url=args.base_url.rstrip('/'),
                workers=max(1, args.workers),
                timeout_ms=args.timeout_ms,
                checkpoint_path=checkpoint,
                already_done={},
                on_result=on_result,
                headless=not args.headed,
            )

        results = run_fix_iterations(
            apply_code_fixes=apply_fixes,
            rerun=rerun,
            results=results,
            out_dir=out_dir,
            max_iterations=args.max_fix_iterations,
        )
    else:
        write_fix_plan(out_dir, cluster_failures(results))

    write_reports(out_dir, results=results, unsupported=unsupported_rows)
    print(f'Report written to {out_dir / "summary.html"}')
    passed = sum(1 for r in results if r.get('passed'))
    total = sum(1 for r in results if not r.get('unsupported'))
    pct = (100.0 * passed / total) if total else 0.0
    print(f'Pass: {passed}/{total} ({pct:.2f}%)')
    return 0 if passed == total else 1


if __name__ == '__main__':
    raise SystemExit(main())
