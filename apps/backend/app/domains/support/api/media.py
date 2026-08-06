"""Public media routes (hero video, etc.) — files under MEDIA_ROOT."""
from __future__ import annotations

from flask import Blueprint, abort, send_file

from app.core import media_storage

media_bp = Blueprint('media', __name__)


@media_bp.get('/public/hero-video')
def hero_video():
    """Stream landing hero MP4 from MEDIA_ROOT (no auth)."""
    media_storage.ensure_hero_video()
    path = media_storage.get_media_root() / media_storage.HERO_VIDEO_REL
    if not path.is_file():
        abort(404, description='Hero video not configured on this server')
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
    hero = root / media_storage.HERO_VIDEO_REL
    return {
        'status': 'ok',
        'mediaRoot': str(root),
        'heroVideo': hero.is_file(),
    }
