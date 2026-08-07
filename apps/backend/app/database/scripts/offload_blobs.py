"""Offload legacy Postgres BYTEA blobs to MEDIA_ROOT (media: keys).

Usage:
  cd apps/backend
  python -m app.database.scripts.offload_blobs --limit 200
  python -m app.database.scripts.offload_blobs --clear-pg  # null file_data after verify

Safe to re-run (idempotent). Does not delete media files.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[3]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from dotenv import load_dotenv

load_dotenv(_BACKEND / '.env')

from app.core import media_storage
from app.database.connection.db import db_all, db_run


def _as_bytes(value) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, (bytes, bytearray)):
        return bytes(value)
    return None


def offload_raw_files(*, limit: int, clear_pg: bool) -> int:
    rows = db_all(
        """
        SELECT id, uploader_id, original_filename, file_data, storage_url
        FROM raw_files
        WHERE file_data IS NOT NULL
        ORDER BY created_at ASC NULLS LAST
        LIMIT ?
        """,
        (limit,),
    )
    done = 0
    for row in rows or []:
        blob = _as_bytes(row.get('file_data'))
        if not blob:
            continue
        rid = row['id']
        storage_url = row.get('storage_url')
        if not storage_url or not media_storage.exists(storage_url):
            ext = Path(row.get('original_filename') or 'bin').suffix or '.bin'
            relative = f"uploads/offload/{row.get('uploader_id') or 'unknown'}_{rid}{ext}"
            storage_url = media_storage.put(relative, blob)
        if clear_pg:
            db_run(
                """
                UPDATE raw_files
                SET storage_url = ?, storage_backend = 'media', file_data = NULL
                WHERE id = ?
                """,
                (storage_url, rid),
            )
        else:
            db_run(
                """
                UPDATE raw_files
                SET storage_url = ?, storage_backend = 'media'
                WHERE id = ?
                """,
                (storage_url, rid),
            )
        done += 1
        print(f'[offload] raw_files {rid} → {storage_url} clear_pg={clear_pg}')
    return done


def offload_site_assets(*, clear_pg: bool) -> int:
    rows = db_all(
        """
        SELECT asset_key, filename, data, storage_url
        FROM site_assets
        WHERE data IS NOT NULL
        """,
        (),
    )
    done = 0
    for row in rows or []:
        blob = _as_bytes(row.get('data'))
        if not blob:
            continue
        key = row['asset_key']
        storage_url = row.get('storage_url')
        if not storage_url or not media_storage.exists(storage_url):
            fname = row.get('filename') or 'asset.bin'
            relative = f"public/site_assets/{key.replace('.', '_')}_{fname}"
            storage_url = media_storage.put(relative, blob)
        if clear_pg:
            db_run(
                """
                UPDATE site_assets
                SET storage_url = ?, storage_backend = 'media', data = NULL
                WHERE asset_key = ?
                """,
                (storage_url, key),
            )
        else:
            db_run(
                """
                UPDATE site_assets
                SET storage_url = ?, storage_backend = 'media'
                WHERE asset_key = ?
                """,
                (storage_url, key),
            )
        done += 1
        print(f'[offload] site_assets {key} → {storage_url}')
    return done


def offload_profile_resumes(*, limit: int, clear_pg: bool) -> int:
    from app.domains.recruitment.services.parsing_storage import store_raw_file

    rows = db_all(
        """
        SELECT candidate_id, resume
        FROM candidate_profiles
        WHERE resume IS NOT NULL AND resume_raw_file_id IS NULL
        LIMIT ?
        """,
        (limit,),
    )
    done = 0
    for row in rows or []:
        blob = _as_bytes(row.get('resume'))
        if not blob:
            continue
        cid = row['candidate_id']
        stored = store_raw_file(cid, 'candidate', blob, 'resume.pdf', 'application/pdf', None)
        raw_id = stored.get('id')
        if clear_pg:
            db_run(
                """
                UPDATE candidate_profiles
                SET resume_raw_file_id = ?, resume = NULL
                WHERE candidate_id = ?
                """,
                (raw_id, cid),
            )
        else:
            db_run(
                """
                UPDATE candidate_profiles
                SET resume_raw_file_id = ?
                WHERE candidate_id = ?
                """,
                (raw_id, cid),
            )
        done += 1
        print(f'[offload] profile {cid} → raw_file {raw_id}')
    return done


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument(
        '--clear-pg',
        action='store_true',
        help='NULL out BYTEA after writing to media (contract step)',
    )
    args = parser.parse_args()
    n1 = offload_raw_files(limit=args.limit, clear_pg=args.clear_pg)
    n2 = offload_site_assets(clear_pg=args.clear_pg)
    n3 = offload_profile_resumes(limit=args.limit, clear_pg=args.clear_pg)
    print(f'[offload] done raw={n1} site={n2} profiles={n3}')


if __name__ == '__main__':
    main()
