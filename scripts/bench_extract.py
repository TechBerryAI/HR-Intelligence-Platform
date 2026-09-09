#!/usr/bin/env python3
"""
Benchmark resume text extraction (apps/backend extract_document).

Usage (from repo root, using the backend venv):
    apps/backend/venv/bin/python scripts/bench_extract.py <folder-with-resumes> \
        [--workers N] [--dpi D] [--limit K]

Runs extract_document over every PDF/DOCX/image in the folder, in parallel like
the bulk worker, and prints per-file timing plus totals. Use --workers 1 vs
--workers 6 (and different OCR_MAX_CONCURRENT env values) to compare configs.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND = REPO_ROOT / 'apps' / 'backend'
sys.path.insert(0, str(BACKEND))

SUPPORTED = {'pdf', 'docx', 'png', 'jpg', 'jpeg', 'webp', 'tif', 'tiff', 'bmp'}


def _load_env() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(BACKEND / '.env', override=False)
    except Exception:
        pass


def bench_one(path: Path, dpi: int | None) -> dict:
    from app.ai.parser.text_extraction import extract_document

    data = path.read_bytes()
    start = time.perf_counter()
    row = {'file': path.name, 'ms': 0.0, 'chars': 0, 'status': '', 'ocr_pages': 0, 'error': ''}
    try:
        result = extract_document(data, path.name, dpi=dpi)
        row.update(
            chars=len((result.text or '').strip()),
            status=result.status,
            ocr_pages=len(result.ocr_pages),
        )
    except Exception as exc:
        row['error'] = f'{type(exc).__name__}: {exc}'[:120]
        row['status'] = 'error'
    row['ms'] = (time.perf_counter() - start) * 1000.0
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('folder', type=Path)
    parser.add_argument('--workers', type=int, default=int(os.getenv('BULK_PARSE_MAX_WORKERS', '6')))
    parser.add_argument('--dpi', type=int, default=None)
    parser.add_argument('--limit', type=int, default=0)
    args = parser.parse_args()

    _load_env()
    from app.ai.parser.engine.hardware import apply_hardware_env

    apply_hardware_env()

    files = sorted(
        p for p in args.folder.iterdir()
        if p.is_file() and p.suffix.lower().lstrip('.') in SUPPORTED
    )
    if args.limit:
        files = files[: args.limit]
    if not files:
        print(f'No supported files in {args.folder}')
        return 1

    print(
        f'files={len(files)} workers={args.workers} dpi={args.dpi or "auto"} '
        f'OCR_MAX_CONCURRENT={os.getenv("OCR_MAX_CONCURRENT", "unset")} '
        f'OCR_PREPROCESS={os.getenv("OCR_PREPROCESS", "true")}'
    )

    wall_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        rows = list(pool.map(lambda p: bench_one(p, args.dpi), files))
    wall_ms = (time.perf_counter() - wall_start) * 1000.0

    rows.sort(key=lambda r: -r['ms'])
    print(f'\n{"ms":>9}  {"chars":>7}  {"ocr_pg":>6}  {"status":<15}  file')
    for r in rows:
        print(
            f'{r["ms"]:>9.0f}  {r["chars"]:>7}  {r["ocr_pages"]:>6}  {r["status"]:<15}  '
            f'{r["file"]}{"  !! " + r["error"] if r["error"] else ""}'
        )

    ok = [r for r in rows if not r['error']]
    total_cpu_ms = sum(r['ms'] for r in rows)
    print(
        f'\nwall={wall_ms / 1000.0:.1f}s  sum_per_file={total_cpu_ms / 1000.0:.1f}s  '
        f'ok={len(ok)}/{len(rows)}  '
        f'avg={total_cpu_ms / max(1, len(rows)) / 1000.0:.2f}s/file  '
        f'throughput={len(rows) / max(0.001, wall_ms / 1000.0) * 60.0:.1f} files/min'
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
