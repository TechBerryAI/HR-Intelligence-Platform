"""Public media routes — landing hero video from Postgres ``site_assets``."""
from __future__ import annotations

import io

from flask import Blueprint, abort, send_file

from app.core import media_storage, site_assets

media_bp = Blueprint('media', __name__)


@media_bp.get('/public/hero-video')
def hero_video():
    """Stream landing hero MP4 from Postgres ``site_assets`` BYTEA (no auth).

    Seeded into ``landing.hero_video`` from MEDIA_ROOT / legacy disk when missing.
    Falls back to disk under MEDIA_ROOT if the DB row is unavailable.
    """
    packed = None
    try:
        packed = site_assets.hero_video_bytes()
    except Exception as e:
        print(f'[MEDIA] DB hero read failed, trying disk: {e}')

    if packed:
        data, content_type, filename, meta = packed
        buf = io.BytesIO(data)
        resp = send_file(
            buf,
            mimetype=content_type,
            conditional=True,
            max_age=86400,
            download_name=filename,
            etag=True,
            last_modified=meta.get('updated_at'),
        )
        resp.headers['Accept-Ranges'] = 'bytes'
        return resp

    # Disk fallback (seed source / offline recovery)
    media_storage.ensure_hero_video()
    path = media_storage.get_media_root() / media_storage.HERO_VIDEO_REL
    if not path.is_file():
        abort(404, description='Hero video not configured (site_assets.landing.hero_video)')
    return send_file(
        path,
        mimetype='video/mp4',
        conditional=True,
        max_age=86400,
        download_name='website-hero.mp4',
    )


@media_bp.get('/health')
def media_health():
    root = media_storage.get_media_root()
    disk_hero = root / media_storage.HERO_VIDEO_REL
    db_row = None
    db_err = None
    try:
        db_row = site_assets.get_asset(site_assets.HERO_ASSET_KEY, include_data=False)
    except Exception as e:
        db_err = str(e)
    db_ok = bool(db_row and int(db_row.get('byte_size') or 0) > 0)
    return {
        'status': 'ok',
        'mediaRoot': str(root),
        'heroVideoDisk': disk_hero.is_file(),
        'heroVideoDb': db_ok,
        'heroVideoBytes': int(db_row.get('byte_size') or 0) if db_row else 0,
        'dbError': db_err,
        # Back-compat for older probes
        'heroVideo': db_ok or disk_hero.is_file(),
    }
