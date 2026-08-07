"""Configurable media volume storage (outside the git tree).

Catalog model
-------------
Postgres holds the source of truth for *what* exists (id, mime, size,
``file_hash`` / ``content_sha256``, ``storage_url``). Bytes live under
``MEDIA_ROOT``. Keys look like ``media:uploads/{name}`` — never absolute
repo paths. Swap this module later for S3 without changing callers.

Integrity
---------
Writes verify the on-disk SHA-256 matches the payload before returning.
Reads can require an expected digest via ``read_verified``.
"""
from __future__ import annotations

import hashlib
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


class MediaIntegrityError(Exception):
    """On-disk bytes do not match the catalog checksum."""


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, *, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        while True:
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def get_media_root() -> Path:
    """Resolve MEDIA_ROOT.

    Prefer ``MEDIA_ROOT`` env; else durable ``{HCIP_DATA_HOME}/media``
    (outside the project). Legacy ``<repo>/.media`` is copied once if needed.
    """
    from app.core.data_home import get_media_root_default

    raw = (os.getenv('MEDIA_ROOT') or '').strip()
    if raw:
        root = Path(raw).expanduser().resolve()
    else:
        upload = (os.getenv('UPLOAD_FOLDER') or '').strip()
        if upload:
            norm = upload.replace('\\', '/').rstrip('/')
            if norm in ('./uploads', 'uploads', 'backend/uploads', 'apps/backend/uploads'):
                root = get_media_root_default()
            else:
                up = Path(upload).expanduser()
                try:
                    resolved = up.resolve()
                    if resolved == (_BACKEND_DIR / 'uploads').resolve():
                        root = get_media_root_default()
                    else:
                        root = resolved.parent if resolved.name == 'uploads' else resolved
                except OSError:
                    root = get_media_root_default()
        else:
            root = get_media_root_default()
    root.mkdir(parents=True, exist_ok=True)
    _maybe_migrate_legacy_repo_media(root)
    return root


def _maybe_migrate_legacy_repo_media(new_root: Path) -> None:
    """One-time copy from <repo>/.media into the durable media root."""
    legacy = (_REPO_ROOT / '.media').resolve()
    try:
        if not legacy.is_dir() or legacy == new_root.resolve():
            return
    except OSError:
        return
    marker = new_root / '.migrated_from_repo_dot_media'
    if marker.is_file():
        return
    try:
        has_payload = any(
            p.is_file()
            for p in legacy.rglob('*')
            if p.is_file() and not p.name.startswith('.')
        )
    except OSError:
        return
    if not has_payload:
        marker.write_text('empty-legacy\n', encoding='utf-8')
        return
    print(f'[MEDIA] Migrating legacy {legacy} → {new_root} (one-time copy)')
    for src in legacy.rglob('*'):
        if not src.is_file():
            continue
        rel = src.relative_to(legacy)
        dest = new_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.is_file() and dest.stat().st_size == src.stat().st_size:
            continue
        shutil.copy2(src, dest)
    marker.write_text(f'from={legacy}\n', encoding='utf-8')
    readme = legacy / 'MOVED.txt'
    if not readme.is_file():
        readme.write_text(
            f'Media files were copied to durable MEDIA_ROOT:\n  {new_root}\n'
            'Safe to delete this .media folder after verifying the app.\n',
            encoding='utf-8',
        )
    print(f'[MEDIA] Migration complete → {new_root}')


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
        # Windows file:///C:/... or file://C:\... → strip leading slash before drive
        if len(path) >= 3 and path[0] == '/' and path[2] == ':':
            path = path[1:]
        path = path.replace('\\', '/')
        p = Path(path)
        try:
            root = get_media_root()
            return str(p.resolve().relative_to(root)).replace('\\', '/')
        except Exception:
            pass
        # Legacy abs path under old uploads/ (Linux or Windows)
        try:
            legacy = (_BACKEND_DIR / 'uploads').resolve()
            resolved = p if p.is_absolute() else Path(path)
            # Match by basename under legacy uploads when path is a foreign Windows path
            name = resolved.name
            candidate = legacy / name
            if candidate.is_file():
                return f'uploads/{name}'
            return f"uploads/{resolved.resolve().relative_to(legacy)}".replace('\\', '/')
        except Exception:
            name = Path(path.replace('\\', '/')).name
            if name:
                candidate = (_BACKEND_DIR / 'uploads' / name).resolve()
                if candidate.is_file():
                    return f'uploads/{name}'
                media_candidate = get_media_root() / 'uploads' / name
                if media_candidate.is_file():
                    return f'uploads/{name}'
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


def put(relative_key: str, data: bytes, *, verify: bool = True) -> str:
    """Write bytes; return opaque ``media:...`` key.

    When ``verify`` is True (default), re-hash the on-disk file and raise
    ``MediaIntegrityError`` if it does not match the payload SHA-256.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError('data must be bytes')
    payload = bytes(data)
    expected = sha256_hex(payload)
    rel = _normalize_rel(relative_key)
    path = get_media_root() / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(payload)
    if verify:
        actual = sha256_file(path)
        if actual != expected:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise MediaIntegrityError(
                f'Write verify failed for {rel}: expected {expected}, got {actual}'
            )
    return to_storage_key(rel)


def put_file(relative_key: str, source: Path | str, *, verify: bool = True) -> str:
    rel = _normalize_rel(relative_key)
    dest = get_media_root() / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = Path(source)
    expected = sha256_file(src) if verify else None
    shutil.copy2(str(src), str(dest))
    if verify and expected is not None:
        actual = sha256_file(dest)
        if actual != expected:
            try:
                dest.unlink(missing_ok=True)
            except OSError:
                pass
            raise MediaIntegrityError(
                f'Copy verify failed for {rel}: expected {expected}, got {actual}'
            )
    return to_storage_key(rel)


def open_stream(key_or_url: str) -> BinaryIO:
    path = get_path(key_or_url)
    if not path.is_file():
        raise FileNotFoundError(path)
    return open(path, 'rb')


def read_bytes(key_or_url: str) -> bytes:
    path = get_path(key_or_url)
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.read_bytes()


def verify(key_or_url: str, expected_sha256: str) -> bool:
    """Return True when on-disk SHA-256 matches ``expected_sha256``."""
    expected = (expected_sha256 or '').strip().lower()
    if not expected or len(expected) != 64:
        return False
    try:
        path = get_path(key_or_url)
        if not path.is_file():
            return False
        return sha256_file(path) == expected
    except (FileNotFoundError, ValueError, OSError):
        return False


def read_verified(key_or_url: str, expected_sha256: str) -> bytes:
    """Read bytes and require SHA-256 match; raise ``MediaIntegrityError`` on mismatch."""
    expected = (expected_sha256 or '').strip().lower()
    data = read_bytes(key_or_url)
    actual = sha256_hex(data)
    if not expected or actual != expected:
        raise MediaIntegrityError(
            f'Checksum mismatch for {key_or_url!r}: expected {expected or "(missing)"}, got {actual}'
        )
    return data


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
