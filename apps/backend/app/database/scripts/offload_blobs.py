"""Offload legacy Postgres BYTEA blobs to MEDIA_ROOT with checksum verification.

Catalog stays in Postgres (ids, hashes, storage_url). Bytes move to the media
volume. ``--clear-pg`` NULLs BYTEA only after on-disk SHA-256 matches.

Usage:
  cd apps/backend
  python -m app.database.scripts.offload_blobs --limit 200
  python -m app.database.scripts.offload_blobs --clear-pg
  python -m app.database.scripts.offload_blobs --verify-only

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


def _ensure_media(relative: str, blob: bytes, existing_url: str | None) -> str:
    """Write (or reuse) bytes under MEDIA_ROOT; always return a ``media:`` key."""
    digest = media_storage.sha256_hex(blob)
    url = (existing_url or '').strip()
    if url.startswith(media_storage.KEY_PREFIX) and media_storage.verify(url, digest):
        return url
    # Legacy file:// or missing keys: copy into the media volume
    return media_storage.put(relative, blob, verify=True)


def offload_raw_files(*, limit: int, clear_pg: bool) -> int:
    rows = db_all(
        """
        SELECT id, uploader_id, original_filename, file_data, storage_url, file_hash
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
        digest = media_storage.sha256_hex(blob)
        catalog_hash = (row.get('file_hash') or '').strip().lower()
        if catalog_hash and catalog_hash != digest:
            print(
                f'[offload] SKIP raw_files {rid}: BYTEA hash {digest} '
                f'!= catalog {catalog_hash}'
            )
            continue
        ext = Path(row.get('original_filename') or 'bin').suffix or '.bin'
        relative = f"uploads/offload/{row.get('uploader_id') or 'unknown'}_{rid}{ext}"
        try:
            storage_url = _ensure_media(relative, blob, row.get('storage_url'))
        except media_storage.MediaIntegrityError as exc:
            print(f'[offload] SKIP raw_files {rid}: {exc}')
            continue
        if not media_storage.verify(storage_url, digest):
            print(f'[offload] SKIP raw_files {rid}: post-write verify failed')
            continue
        if clear_pg:
            db_run(
                """
                UPDATE raw_files
                SET storage_url = ?, storage_backend = 'media',
                    file_hash = ?, size_bytes = ?, file_data = NULL
                WHERE id = ?
                """,
                (storage_url, digest, len(blob), rid),
            )
        else:
            db_run(
                """
                UPDATE raw_files
                SET storage_url = ?, storage_backend = 'media',
                    file_hash = ?, size_bytes = ?
                WHERE id = ?
                """,
                (storage_url, digest, len(blob), rid),
            )
        done += 1
        print(f'[offload] raw_files {rid} → {storage_url} clear_pg={clear_pg}')
    return done


def offload_site_assets(*, clear_pg: bool) -> int:
    rows = db_all(
        """
        SELECT asset_key, filename, data, storage_url, content_sha256
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
        digest = media_storage.sha256_hex(blob)
        catalog_hash = (row.get('content_sha256') or '').strip().lower()
        if catalog_hash and catalog_hash != digest:
            print(
                f'[offload] SKIP site_assets {key}: BYTEA hash {digest} '
                f'!= catalog {catalog_hash}'
            )
            continue
        fname = row.get('filename') or 'asset.bin'
        relative = f"public/site_assets/{key.replace('.', '_')}_{fname}"
        try:
            storage_url = _ensure_media(relative, blob, row.get('storage_url'))
        except media_storage.MediaIntegrityError as exc:
            print(f'[offload] SKIP site_assets {key}: {exc}')
            continue
        if not media_storage.verify(storage_url, digest):
            print(f'[offload] SKIP site_assets {key}: post-write verify failed')
            continue
        if clear_pg:
            db_run(
                """
                UPDATE site_assets
                SET storage_url = ?, storage_backend = 'media',
                    content_sha256 = ?, byte_size = ?, data = NULL
                WHERE asset_key = ?
                """,
                (storage_url, digest, len(blob), key),
            )
        else:
            db_run(
                """
                UPDATE site_assets
                SET storage_url = ?, storage_backend = 'media',
                    content_sha256 = ?, byte_size = ?
                WHERE asset_key = ?
                """,
                (storage_url, digest, len(blob), key),
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
        try:
            stored = store_raw_file(cid, 'candidate', blob, 'resume.pdf', 'application/pdf', None)
        except Exception as exc:
            print(f'[offload] SKIP profile {cid}: {exc}')
            continue
        raw_id = stored.get('id')
        storage_url = stored.get('storage_url')
        file_hash = stored.get('file_hash') or media_storage.sha256_hex(blob)
        if storage_url and not media_storage.verify(storage_url, file_hash):
            print(f'[offload] SKIP profile {cid}: media verify failed')
            continue
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


def normalize_legacy_urls(*, limit: int) -> int:
    """Rewrite non-``media:`` storage_url rows onto MEDIA_ROOT keys when bytes exist."""
    rows = db_all(
        """
        SELECT id, uploader_id, original_filename, storage_url, file_hash, file_data
        FROM raw_files
        WHERE storage_url IS NOT NULL
          AND storage_url NOT LIKE ?
        ORDER BY created_at ASC NULLS LAST
        LIMIT ?
        """,
        ('media:%', limit),
    )
    done = 0
    for row in rows or []:
        rid = row['id']
        blob = _as_bytes(row.get('file_data'))
        url = row.get('storage_url')
        if blob is None and url:
            try:
                blob = media_storage.read_bytes(url)
            except Exception:
                # Basename fallback for foreign Windows file:// paths
                name = Path(str(url).replace('\\', '/').split('/')[-1]).name
                for base in (
                    media_storage.get_media_root() / 'uploads',
                    Path(__file__).resolve().parents[3] / 'uploads',
                ):
                    candidate = base / name
                    if candidate.is_file():
                        blob = candidate.read_bytes()
                        break
        if not blob:
            print(f'[normalize] SKIP raw_files {rid}: no bytes for {url!r}')
            continue
        digest = media_storage.sha256_hex(blob)
        catalog_hash = (row.get('file_hash') or '').strip().lower()
        if catalog_hash and catalog_hash != digest:
            print(f'[normalize] SKIP raw_files {rid}: hash mismatch')
            continue
        ext = Path(row.get('original_filename') or 'bin').suffix or '.bin'
        relative = f"uploads/offload/{row.get('uploader_id') or 'unknown'}_{rid}{ext}"
        try:
            storage_url = media_storage.put(relative, blob, verify=True)
        except media_storage.MediaIntegrityError as exc:
            print(f'[normalize] SKIP raw_files {rid}: {exc}')
            continue
        db_run(
            """
            UPDATE raw_files
            SET storage_url = ?, storage_backend = 'media',
                file_hash = ?, size_bytes = ?
            WHERE id = ?
            """,
            (storage_url, digest, len(blob), rid),
        )
        done += 1
        print(f'[normalize] raw_files {rid} → {storage_url}')
    return done


def verify_catalog(*, limit: int) -> tuple[int, int]:
    """Check media keys against catalog hashes. Returns (ok, bad)."""
    ok = bad = 0
    raw_rows = db_all(
        """
        SELECT id, storage_url, file_hash, storage_backend,
               (file_data IS NOT NULL) AS has_bytea
        FROM raw_files
        WHERE storage_url IS NOT NULL
          AND (storage_backend = 'media' OR storage_url LIKE ?)
        ORDER BY created_at ASC NULLS LAST
        LIMIT ?
        """,
        ('media:%', limit),
    )
    for row in raw_rows or []:
        rid = row['id']
        digest = (row.get('file_hash') or '').strip().lower()
        url = row.get('storage_url')
        if not digest:
            print(f'[verify] BAD raw_files {rid}: missing file_hash')
            bad += 1
            continue
        if not media_storage.exists(url):
            hint = 'has BYTEA — run offload_blobs' if row.get('has_bytea') else 'no BYTEA fallback'
            print(f'[verify] MISSING raw_files {rid} ({hint}) key={url!r}')
            bad += 1
            continue
        if media_storage.verify(url, digest):
            ok += 1
        else:
            print(f'[verify] HASH_MISMATCH raw_files {rid} key={url!r}')
            bad += 1

    site_rows = db_all(
        """
        SELECT asset_key, storage_url, content_sha256,
               (data IS NOT NULL) AS has_bytea
        FROM site_assets
        WHERE storage_url IS NOT NULL
          AND (storage_backend = 'media' OR storage_url LIKE ?)
        """,
        ('media:%',),
    )
    for row in site_rows or []:
        key = row['asset_key']
        digest = (row.get('content_sha256') or '').strip().lower()
        url = row.get('storage_url')
        if not media_storage.exists(url):
            hint = 'has BYTEA — run offload_blobs' if row.get('has_bytea') else 'no BYTEA fallback'
            print(f'[verify] MISSING site_assets {key} ({hint})')
            bad += 1
            continue
        if not digest:
            print(f'[verify] WARN site_assets {key}: missing content_sha256 (file present)')
            ok += 1
            continue
        if media_storage.verify(url, digest):
            ok += 1
        else:
            print(f'[verify] HASH_MISMATCH site_assets {key} key={url!r}')
            bad += 1

    print(f'[verify] ok={ok} bad={bad}')
    return ok, bad


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--limit', type=int, default=100)
    parser.add_argument(
        '--clear-pg',
        action='store_true',
        help='NULL out BYTEA only after media SHA-256 matches catalog',
    )
    parser.add_argument(
        '--verify-only',
        action='store_true',
        help='Check existing media keys against catalog hashes; no writes',
    )
    parser.add_argument(
        '--normalize-keys',
        action='store_true',
        help='Rewrite legacy file:// storage_url values to media: keys',
    )
    args = parser.parse_args()
    if args.verify_only:
        _, bad = verify_catalog(limit=args.limit)
        raise SystemExit(1 if bad else 0)
    if args.normalize_keys:
        n = normalize_legacy_urls(limit=args.limit)
        print(f'[normalize] done={n}')
        verify_catalog(limit=max(args.limit, 100))
        return
    n1 = offload_raw_files(limit=args.limit, clear_pg=args.clear_pg)
    n2 = offload_site_assets(clear_pg=args.clear_pg)
    n3 = offload_profile_resumes(limit=args.limit, clear_pg=args.clear_pg)
    print(f'[offload] done raw={n1} site={n2} profiles={n3}')
    verify_catalog(limit=max(args.limit, 500))


if __name__ == '__main__':
    main()
