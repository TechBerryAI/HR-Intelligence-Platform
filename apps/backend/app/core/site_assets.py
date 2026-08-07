"""Postgres-backed public site assets (landing hero video, etc.).

**Current:** binary rows in ``site_assets`` (BYTEA). Seeded once from MEDIA_ROOT
or a legacy filesystem path when missing. The home page streams via
``GET /api/media/public/hero-video``.
"""
from __future__ import annotations

from pathlib import Path

from app.core import media_storage
from app.database.connection.db import db_get, db_run

HERO_ASSET_KEY = 'landing.hero_video'
HERO_FILENAME = 'website-hero.mp4'
HERO_CONTENT_TYPE = 'video/mp4'


def get_asset(asset_key: str, *, include_data: bool = True) -> dict | None:
    cols = 'asset_key, filename, content_type, byte_size, created_at, updated_at'
    if include_data:
        cols = 'asset_key, filename, content_type, data, byte_size, created_at, updated_at'
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
    db_run(
        """
        INSERT INTO site_assets (asset_key, filename, content_type, data, byte_size, updated_at)
        VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT (asset_key) DO UPDATE SET
            filename = EXCLUDED.filename,
            content_type = EXCLUDED.content_type,
            data = EXCLUDED.data,
            byte_size = EXCLUDED.byte_size,
            updated_at = CURRENT_TIMESTAMP
        """,
        (asset_key, filename, content_type, blob, len(blob)),
    )


def _read_seed_bytes() -> bytes | None:
    """Load hero MP4 from MEDIA_ROOT (or seed file once from legacy public/videos)."""
    path = media_storage.ensure_hero_video()
    if path and path.is_file():
        return path.read_bytes()
    return None


def ensure_hero_video_in_db(*, force_refresh: bool = False) -> dict | None:
    """Ensure ``landing.hero_video`` exists in Postgres; seed from disk if needed."""
    if not force_refresh:
        existing = get_asset(HERO_ASSET_KEY, include_data=False)
        if existing and int(existing.get('byte_size') or 0) > 0:
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
    if not row or row.get('data') is None:
        return None
    data = bytes(row['data'])
    if not data:
        return None
    return (
        data,
        row.get('content_type') or HERO_CONTENT_TYPE,
        row.get('filename') or HERO_FILENAME,
        row,
    )
