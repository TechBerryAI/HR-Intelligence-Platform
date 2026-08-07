"""Public site assets — metadata + checksum in Postgres, bytes on MEDIA_ROOT.

Legacy BYTEA ``data`` is still read as fallback during the offload window.
"""
from __future__ import annotations

from pathlib import Path

from app.core import media_storage
from app.database.connection.db import db_get, db_run

HERO_ASSET_KEY = 'landing.hero_video'
HERO_FILENAME = 'website-hero.mp4'
HERO_CONTENT_TYPE = 'video/mp4'


def get_asset(asset_key: str, *, include_data: bool = True) -> dict | None:
    cols = (
        'asset_key, filename, content_type, byte_size, storage_url, '
        'storage_backend, content_sha256, created_at, updated_at'
    )
    if include_data:
        cols = (
            'asset_key, filename, content_type, data, byte_size, storage_url, '
            'storage_backend, content_sha256, created_at, updated_at'
        )
    row = db_get(
        f"""
        SELECT {cols}
        FROM site_assets
        WHERE asset_key = ?
        """,
        (asset_key,),
    )
    return row


def put_asset(
    asset_key: str,
    data: bytes,
    *,
    content_type: str,
    filename: str,
) -> None:
    blob = bytes(data or b'')
    digest = media_storage.sha256_hex(blob)
    relative = f'public/site_assets/{asset_key.replace(".", "_")}_{filename}'
    storage_url = media_storage.put(relative, blob, verify=True)
    db_run(
        """
        INSERT INTO site_assets (
            asset_key, filename, content_type, data, byte_size,
            storage_url, storage_backend, content_sha256, updated_at
        )
        VALUES (?, ?, ?, NULL, ?, ?, 'media', ?, CURRENT_TIMESTAMP)
        ON CONFLICT (asset_key) DO UPDATE SET
            filename = EXCLUDED.filename,
            content_type = EXCLUDED.content_type,
            data = NULL,
            byte_size = EXCLUDED.byte_size,
            storage_url = EXCLUDED.storage_url,
            storage_backend = 'media',
            content_sha256 = EXCLUDED.content_sha256,
            updated_at = CURRENT_TIMESTAMP
        """,
        (asset_key, filename, content_type, len(blob), storage_url, digest),
    )


def _read_seed_bytes() -> bytes | None:
    """Load hero MP4 from MEDIA_ROOT (or seed file once from legacy public/videos)."""
    path = media_storage.ensure_hero_video()
    if path and path.is_file():
        return path.read_bytes()
    return None


def ensure_hero_video_in_db(*, force_refresh: bool = False) -> dict | None:
    """Ensure ``landing.hero_video`` exists; seed from disk if needed."""
    if not force_refresh:
        existing = get_asset(HERO_ASSET_KEY, include_data=False)
        if existing and int(existing.get('byte_size') or 0) > 0:
            storage_url = existing.get('storage_url')
            digest = (existing.get('content_sha256') or '').strip()
            if storage_url and digest and media_storage.verify(storage_url, digest):
                return existing
            if storage_url and media_storage.exists(storage_url) and not digest:
                return existing

    blob = _read_seed_bytes()
    if not blob:
        return get_asset(HERO_ASSET_KEY, include_data=False)

    put_asset(
        HERO_ASSET_KEY,
        blob,
        content_type=HERO_CONTENT_TYPE,
        filename=HERO_FILENAME,
    )
    print(f'[MEDIA] Seeded site_assets.{HERO_ASSET_KEY} ({len(blob)} bytes)')
    return get_asset(HERO_ASSET_KEY, include_data=False)


def hero_video_bytes() -> tuple[bytes, str, str, dict] | None:
    """Return (data, content_type, filename, meta) for the landing hero, or None."""
    ensure_hero_video_in_db()
    row = get_asset(HERO_ASSET_KEY, include_data=True)
    if not row:
        return None
    data = b''
    storage_url = row.get('storage_url')
    digest = (row.get('content_sha256') or '').strip()
    if storage_url:
        try:
            if digest:
                data = media_storage.read_verified(storage_url, digest)
            elif media_storage.exists(storage_url):
                data = media_storage.read_bytes(storage_url)
        except media_storage.MediaIntegrityError as exc:
            print(f'[media] hero checksum mismatch: {exc}')
            data = b''
        except (FileNotFoundError, ValueError, OSError) as exc:
            print(f'[media] hero miss key={storage_url!r}: {exc}')
            data = b''
    if not data and row.get('data') is not None:
        data = bytes(row['data'])
        if digest and media_storage.sha256_hex(data) != digest.lower():
            print('[media] hero BYTEA checksum mismatch')
            data = b''
    if not data:
        return None
    return (
        data,
        row.get('content_type') or HERO_CONTENT_TYPE,
        row.get('filename') or HERO_FILENAME,
        row,
    )
