"""Durable HCIP data home — outside the git/project tree.

Default layout (survives deleting the repo folder)::

    {HCIP_DATA_HOME}/
      media/                 ← MEDIA_ROOT (resumes, JDs, hero, …)

Override with env ``HCIP_DATA_HOME``. Optional ``MEDIA_ROOT`` still wins when set.
Database backups are owned by the DB team — this app does not dump Postgres.
"""
from __future__ import annotations

import os
from pathlib import Path

# apps/backend/app/core/data_home.py → parents[4] = repo root
_REPO_ROOT = Path(__file__).resolve().parents[4]


def get_data_home() -> Path:
    """Resolve durable data root (not inside the project folder)."""
    raw = (os.getenv('HCIP_DATA_HOME') or '').strip()
    if raw:
        home = Path(raw).expanduser().resolve()
    else:
        home = _default_data_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


def _default_data_home() -> Path:
    """Stable path next to the repo (not inside it).

    Example: ``…/Projects/HR-Intelligence-Platform`` → ``…/Projects/hcip-data``
    so deleting the project folder does not delete media.
    """
    sibling = (_REPO_ROOT.parent / 'hcip-data').resolve()
    try:
        sibling.mkdir(parents=True, exist_ok=True)
        return sibling
    except OSError:
        home = (Path.home() / 'hcip-data').resolve()
        home.mkdir(parents=True, exist_ok=True)
        return home


def get_media_root_default() -> Path:
    return get_data_home() / 'media'


def ensure_data_layout() -> dict[str, Path]:
    """Create media dirs; return resolved paths."""
    data = get_data_home()
    media = get_media_root_default()
    for sub in ('uploads', 'feedback', 'bulk_uploads', 'bulk_exports', 'public'):
        (media / sub).mkdir(parents=True, exist_ok=True)
    return {'data_home': data, 'media': media}
