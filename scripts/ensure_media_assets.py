#!/usr/bin/env python3
"""Ensure MEDIA_ROOT exists and seed hero video from legacy frontend public/videos."""
from __future__ import annotations

import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1] / 'apps' / 'backend'
sys.path.insert(0, str(_BACKEND))

from app.core import media_storage  # noqa: E402


def main() -> int:
    root = media_storage.get_media_root()
    print(f'MEDIA_ROOT={root}')
    for sub in ('uploads', 'feedback', 'bulk_uploads', 'bulk_exports', 'public'):
        (root / sub).mkdir(parents=True, exist_ok=True)
    path = media_storage.ensure_hero_video()
    if path and path.is_file():
        print(f'Hero video OK: {path} ({path.stat().st_size} bytes)')
        return 0
    print(
        'Hero video not found. Copy website-hero.mp4 to '
        f'{root / media_storage.HERO_VIDEO_REL}'
    )
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
