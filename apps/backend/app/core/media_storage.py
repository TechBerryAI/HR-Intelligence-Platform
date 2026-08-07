"""Configurable media volume storage (outside the git tree).

Files live under MEDIA_ROOT. Postgres / callers store opaque keys like
``media:uploads/{name}`` or relative paths under that root — never absolute
repo paths. Swap this module later for S3 without changing callers.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import BinaryIO
from urllib.parse import unquote, urlparse

# apps/backend/app/core/media_storage.py → parents[2]=apps/backend, parents[4]=repo root
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_REPO_ROOT = Path(__file__).resolve().parents[4]

KEY_PREFIX = 'media:'
HERO_VIDEO_REL = 'public/website-hero.mp4'
HERO_VIDEO_KEY = f'{KEY_PREFIX}{HERO_VIDEO_REL}'


def get_media_root() -> Path:
    """Resolve MEDIA_ROOT. Prefer env; else <repo>/.media (gitignored)."""
    raw = (os.getenv('MEDIA_ROOT') or '').strip()
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        # Fallback: UPLOAD_FOLDER parent if set to a non-package path, else repo/.media
        upload = (os.getenv('UPLOAD_FOLDER') or '').strip()
        if upload:
            # Relative legacy defaults must not depend on process CWD
            # (repo-root vs apps/backend would otherwise pick different roots).
            norm = upload.replace('\\', '/').rstrip('/')
            if norm in ('./uploads', 'uploads', 'backend/uploads', 'apps/backend/uploads'):
                root = (_REPO_ROOT / '.media').resolve()
            else:
                up = Path(upload).expanduser()
                try:
                    resolved = up.resolve()
                    if resolved == (_BACKEND_DIR / 'uploads').resolve():
                        root = (_REPO_ROOT / '.media').resolve()
                    else:
                        root = resolved.parent if resolved.name == 'uploads' else resolved
                except OSError:
                    root = (_REPO_ROOT / '.media').resolve()
        else:
            root = (_REPO_ROOT / '.media').resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def uploads_dir() -> Path:
    """Legacy UPLOAD_FOLDER compatibility → MEDIA_ROOT/uploads."""
    d = get_media_root() / 'uploads'
    d.mkdir(parents=True, exist_ok=True)
    return d


def feedback_dir() -> Path:
    d = get_media_root() / 'feedback'
    d.mkdir(parents=True, exist_ok=True)
    return d


def bulk_uploads_dir() -> Path:
    d = get_media_root() / 'bulk_uploads'
    d.mkdir(parents=True, exist_ok=True)
    return d


def bulk_exports_dir() -> Path:
    d = get_media_root() / 'bulk_exports'
    d.mkdir(parents=True, exist_ok=True)
    return d


def _normalize_rel(relative_key: str) -> str:
    rel = (relative_key or '').replace('\\', '/').lstrip('/')
    if rel.startswith(KEY_PREFIX):
        rel = rel[len(KEY_PREFIX) :]
    if not rel or rel.startswith('..') or '/../' in f'/{rel}/' or rel.startswith('/'):
        raise ValueError('Invalid media key')
    parts = Path(rel).parts
    if '..' in parts or parts[:1] == ('',):
        raise ValueError('Invalid media key')
    return '/'.join(parts)


def to_storage_key(relative_key: str) -> str:
    return f'{KEY_PREFIX}{_normalize_rel(relative_key)}'


def key_to_relative(key_or_url: str) -> str | None:
    """Map stored storage_url / key to a relative path under MEDIA_ROOT, if possible."""
    raw = (key_or_url or '').strip()
    if not raw:
        return None
    if raw.startswith(KEY_PREFIX):
        return _normalize_rel(raw)
    if raw.startswith('file://'):
        parsed = urlparse(raw)
        path = unquote(parsed.path)
        # Windows file:///C:/... → path may start with /
        p = Path(path)
        try:
            root = get_media_root()
            return str(p.resolve().relative_to(root)).replace('\\', '/')
        except Exception:
            # Legacy abs path under old uploads/
            try:
                legacy = (_BACKEND_DIR / 'uploads').resolve()
                return f"uploads/{p.resolve().relative_to(legacy)}".replace('\\', '/')
            except Exception:
                return None
    # Bare relative path
    if not raw.startswith('/') and '://' not in raw:
        return _normalize_rel(raw)
    return None


def get_path(key_or_url: str) -> Path:
    rel = key_to_relative(key_or_url)
    if not rel:
        raise FileNotFoundError(f'Cannot resolve media key: {key_or_url!r}')
    root = get_media_root()
    path = (root / rel).resolve()
    if not str(path).startswith(str(root)):
        raise ValueError('Path escapes MEDIA_ROOT')
    return path


def put(relative_key: str, data: bytes) -> str:
    """Write bytes; return opaque ``media:...`` key."""
    rel = _normalize_rel(relative_key)
    path = get_media_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return to_storage_key(rel)


def put_file(relative_key: str, source: Path | str) -> str:
    rel = _normalize_rel(relative_key)
    dest = get_media_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source), str(dest))
    return to_storage_key(rel)


def open_stream(key_or_url: str) -> BinaryIO:
    path = get_path(key_or_url)
    if not path.is_file():
        raise FileNotFoundError(path)
    return open(path, 'rb')


def exists(key_or_url: str) -> bool:
    try:
        return get_path(key_or_url).is_file()
    except (FileNotFoundError, ValueError, OSError):
        return False


def resolve_url_for_api(key_or_url: str) -> str | None:
    """Stable API path for known public assets."""
    rel = key_to_relative(key_or_url)
    if rel == HERO_VIDEO_REL:
        return '/api/media/public/hero-video'
    if rel and rel.startswith('uploads/'):
        return None  # staff raw download uses raw_file id
    return None


def ensure_hero_video() -> Path | None:
    """Ensure hero MP4 under MEDIA_ROOT; seed once from legacy frontend public/videos."""
    dest = get_media_root() / HERO_VIDEO_REL
    if dest.is_file():
        return dest

    candidates = [
        _REPO_ROOT / 'apps' / 'frontend' / 'public' / 'videos' / 'website-hero.mp4',
        _BACKEND_DIR.parent / 'frontend' / 'public' / 'videos' / 'website-hero.mp4',
    ]
    for src in candidates:
        if src.is_file():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            print(f'[MEDIA] Seeded hero video from {src} → {dest}')
            return dest

    print(f'[MEDIA] Hero video missing at {dest} (place website-hero.mp4 under MEDIA_ROOT/public/)')
    return None
