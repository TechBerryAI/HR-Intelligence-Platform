"""Public site assets — metadata + checksum in Postgres, bytes on MEDIA_ROOT.

Legacy BYTEA ``data`` is still read as fallback during the offload window.
Hero video uses the canonical key ``media:public/website-hero.mp4``.
"""
from __future__ import annotations

import shutil
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
    relative: str | None = None,
) -> None:
    blob = bytes(data or b'')
    digest = media_storage.sha256_hex(blob)
    if relative is None:
        if asset_key == HERO_ASSET_KEY:
            relative = media_storage.HERO_VIDEO_REL
        else:
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


def _catalog_bytes_readable(row: dict | None) -> bool:
    """True when catalog row points at bytes that exist (and match checksum if set)."""
    if not row or int(row.get('byte_size') or 0) <= 0:
        return False
    storage_url = row.get('storage_url')
    digest = (row.get('content_sha256') or '').strip()
    if storage_url:
        if digest:
            return media_storage.verify(storage_url, digest)
        return media_storage.exists(storage_url)
    # Legacy BYTEA still present
    return False


def _read_seed_bytes() -> bytes | None:
    """Load hero MP4 from MEDIA_ROOT (seeded from committed public/videos if needed)."""
    path = media_storage.ensure_hero_video()
    if path and path.is_file():
        return path.read_bytes()
    return None


def ensure_hero_video_in_db(*, force_refresh: bool = False) -> dict | None:
    """Ensure ``landing.hero_video`` exists; seed from disk / git seed if needed."""
    # Always try to materialize the canonical disk file first (self-heal).
    media_storage.ensure_hero_video()

    if not force_refresh:
        existing = get_asset(HERO_ASSET_KEY, include_data=False)
        if _catalog_bytes_readable(existing):
            storage_url = (existing or {}).get('storage_url') or ''
            rel = media_storage.key_to_relative(storage_url) if storage_url else None
            if rel == media_storage.HERO_VIDEO_REL:
                return existing
            # Migrate legacy public/site_assets/… onto the canonical hero path.
            try:
                src = media_storage.get_path(storage_url)
                dest = media_storage.get_media_root() / media_storage.HERO_VIDEO_REL
                if src.is_file():
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if src.resolve() != dest.resolve():
                        shutil.copy2(src, dest)
                    put_asset(
                        HERO_ASSET_KEY,
                        dest.read_bytes(),
                        content_type=HERO_CONTENT_TYPE,
                        filename=HERO_FILENAME,
                        relative=media_storage.HERO_VIDEO_REL,
                    )
                    return get_asset(HERO_ASSET_KEY, include_data=False)
            except (FileNotFoundError, ValueError, OSError) as exc:
                print(f'[MEDIA] hero canonical migrate skipped: {exc}')
            return existing

    blob = _read_seed_bytes()
    if not blob:
        return get_asset(HERO_ASSET_KEY, include_data=False)

    put_asset(
        HERO_ASSET_KEY,
        blob,
        content_type=HERO_CONTENT_TYPE,
        filename=HERO_FILENAME,
        relative=media_storage.HERO_VIDEO_REL,
    )
    print(f'[MEDIA] Seeded site_assets.{HERO_ASSET_KEY} ({len(blob)} bytes)')
    return get_asset(HERO_ASSET_KEY, include_data=False)


def hero_video_path() -> tuple[Path, str, str, dict | None] | None:
    """Return (path, content_type, filename, meta) for streaming, or None.

    Self-heals disk + catalog from the committed frontend seed when missing.
    """
    try:
        meta = ensure_hero_video_in_db()
    except Exception as exc:
        print(f'[MEDIA] hero catalog ensure failed: {exc}')
        meta = None

    path = media_storage.ensure_hero_video()
    if path and path.is_file() and path.stat().st_size > 0:
        return (
            path,
            (meta or {}).get('content_type') or HERO_CONTENT_TYPE,
            (meta or {}).get('filename') or HERO_FILENAME,
            meta,
        )

    # Last resort: catalog points elsewhere and seed copy failed
    if meta:
        storage_url = meta.get('storage_url')
        if storage_url and media_storage.exists(storage_url):
            try:
                alt = media_storage.get_path(storage_url)
                if alt.is_file() and alt.stat().st_size > 0:
                    return (
                        alt,
                        meta.get('content_type') or HERO_CONTENT_TYPE,
                        meta.get('filename') or HERO_FILENAME,
                        meta,
                    )
            except (FileNotFoundError, ValueError, OSError):
                pass
    return None


def hero_video_bytes() -> tuple[bytes, str, str, dict] | None:
    """Return (data, content_type, filename, meta) for the landing hero, or None.

    Prefer ``hero_video_path`` for HTTP serving (Range / streaming).
    """
    packed = hero_video_path()
    if not packed:
        return None
    path, content_type, filename, meta = packed
    data = path.read_bytes()
    if not data:
        return None
    return (data, content_type, filename, meta or {})


def hero_catalog_healthy() -> tuple[bool, dict | None]:
    """Return (ok, row) — ok means catalog row and readable media bytes."""
    try:
        row = get_asset(HERO_ASSET_KEY, include_data=False)
    except Exception:
        return False, None
    return _catalog_bytes_readable(row), row
