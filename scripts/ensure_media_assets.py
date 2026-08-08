#!/usr/bin/env python3
"""Ensure MEDIA_ROOT dirs exist and seed landing hero video into Postgres site_assets."""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / 'apps' / 'backend'
sys.path.insert(0, str(_BACKEND))

# Load backend .env so DATABASE_URL / MEDIA_ROOT resolve like the Flask app
_env = _BACKEND / '.env'
if _env.is_file():
    try:
        from dotenv import load_dotenv

        load_dotenv(_env)
    except ImportError:
        pass

from app.core import media_storage, site_assets  # noqa: E402
from app.database.connection.db import init_db  # noqa: E402


def main() -> int:
    force = '--force' in sys.argv
    init_db()
    root = media_storage.get_media_root()
    print(f'MEDIA_ROOT={root}')
    for sub in ('uploads', 'feedback', 'bulk_uploads', 'bulk_exports', 'public'):
        (root / sub).mkdir(parents=True, exist_ok=True)

    path = media_storage.ensure_hero_video()
    if path and path.is_file():
        print(f'Disk seed OK: {path} ({path.stat().st_size} bytes)')
    else:
        print(
            'Warning: no disk hero at '
            f'{root / media_storage.HERO_VIDEO_REL} — '
            'expected apps/frontend/public/videos/website-hero.mp4 in the repo'
        )

    row = site_assets.ensure_hero_video_in_db(force_refresh=force)
    if row and int(row.get('byte_size') or 0) > 0:
        print(
            f'DB site_assets.{site_assets.HERO_ASSET_KEY} OK: '
            f'{int(row["byte_size"])} bytes'
        )
        return 0
    print('Hero video not in DB. Place website-hero.mp4 under MEDIA_ROOT/public/ then re-run.')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
