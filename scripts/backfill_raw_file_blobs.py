#!/usr/bin/env python3
"""Backfill raw_files.file_data from MEDIA_ROOT disk cache for legacy rows.

Usage (from apps/backend, with .env loaded):
  python ../../scripts/backfill_raw_file_blobs.py                # dry run (default, no writes)
  python ../../scripts/backfill_raw_file_blobs.py --execute      # actually perform the UPDATEs
  python ../../scripts/backfill_raw_file_blobs.py --execute --limit 100
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'apps' / 'backend'
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv

load_dotenv(BACKEND / '.env')
os.chdir(BACKEND)


def main() -> int:
    parser = argparse.ArgumentParser(description='Backfill raw_files.file_data from disk')
    parser.add_argument('--limit', type=int, default=0, help='Max rows to process (0 = all)')
    parser.add_argument(
        '--execute',
        action='store_true',
        help='Actually perform the UPDATEs. Without this flag the script only reports '
             'what it would change (dry run) and writes nothing.',
    )
    args = parser.parse_args()

    from app.core import media_storage
    from app.database.connection.db import DATABASE_URL, db_all, db_run, init_db
    from app.domains.recruitment.services.parsing_storage import _as_bytes

    parsed = urlsplit(DATABASE_URL) if DATABASE_URL else None
    target = f'{parsed.hostname}:{parsed.port or "?"}{parsed.path}' if parsed else '(unknown — DATABASE_URL not set)'
    print(f'Target database: {target}')
    if args.execute:
        print('Mode: EXECUTE — rows will be written.')
    else:
        print('Mode: DRY RUN — no rows will be written. Pass --execute to apply changes.')

    init_db()
    sql = '''
        SELECT id, storage_url, size_bytes
        FROM raw_files
        WHERE file_data IS NULL
        ORDER BY created_at ASC
    '''
    if args.limit and args.limit > 0:
        sql += f' LIMIT {int(args.limit)}'
    rows = db_all(sql, ())
    print(f'Rows missing file_data: {len(rows)}')
    ok = fail = 0
    for row in rows:
        rid = row['id']
        url = row.get('storage_url')
        try:
            if not url or not media_storage.exists(url):
                print(f'  skip {rid}: no disk file for {url!r}')
                fail += 1
                continue
            with media_storage.open_stream(url) as fh:
                blob = fh.read()
            blob = _as_bytes(blob) or blob
            if not blob:
                print(f'  skip {rid}: empty file')
                fail += 1
                continue
            if args.execute:
                db_run(
                    'UPDATE raw_files SET file_data = ?, size_bytes = ? WHERE id = ?',
                    (blob, len(blob), rid),
                )
                ok += 1
                print(f'  ok {rid} ({len(blob)} bytes)')
            else:
                ok += 1
                print(f'  would-update {rid} ({len(blob)} bytes)')
        except Exception as exc:
            fail += 1
            print(f'  fail {rid}: {exc}')
    print(f'Done. backfilled={ok} failed_or_skipped={fail}')
    return 0 if fail == 0 or ok > 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
