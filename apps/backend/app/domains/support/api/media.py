"""Public media routes — landing hero video from MEDIA_ROOT + ``site_assets`` catalog."""
from __future__ import annotations

from flask import Blueprint, abort, send_file

from app.core import media_storage, site_assets
from app.core.errors import log_unexpected

media_bp = Blueprint('media', __name__)


@media_bp.get('/public/hero-video')
def hero_video():
    """Stream landing hero MP4 from disk (no auth).

    Self-heals ``MEDIA_ROOT/public/website-hero.mp4`` from the committed
    frontend seed and upserts the ``site_assets`` catalog when missing.
    """
    packed = None
    try:
        packed = site_assets.hero_video_path()
    except Exception as e:
        log_unexpected('hero_video_resolve', e)

    if packed:
        path, content_type, filename, meta = packed
        resp = send_file(
            path,
            mimetype=content_type,
            conditional=True,
            max_age=86400,
            download_name=filename,
            etag=True,
            last_modified=(meta or {}).get('updated_at'),
        )
        resp.headers['Accept-Ranges'] = 'bytes'
        return resp

    # Direct disk fallback if catalog helpers raised earlier
    path = media_storage.ensure_hero_video()
    if not path or not path.is_file():
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
    # Self-heal so health reflects a post-boot / post-pull reality
    try:
        media_storage.ensure_hero_video()
        site_assets.ensure_hero_video_in_db()
    except Exception as e:
        log_unexpected('hero_video_health_ensure', e)

    disk_hero = root / media_storage.HERO_VIDEO_REL
    disk_ok = disk_hero.is_file() and disk_hero.stat().st_size > 0
    db_ok = False
    db_row = None
    db_err = None
    try:
        db_ok, db_row = site_assets.hero_catalog_healthy()
    except Exception as e:
        db_err = str(e)
    return {
        'status': 'ok',
        'mediaRoot': str(root),
        'heroVideoDisk': disk_ok,
        'heroVideoDb': db_ok,
        'heroVideoBytes': int(db_row.get('byte_size') or 0) if db_row else 0,
        'dbError': db_err,
        # Back-compat for older probes
        'heroVideo': db_ok or disk_ok,
    }
