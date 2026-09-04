"""Stage trace logging for Document Intelligence.

Development-only. Never enabled in production unless DOCUMENT_INTELLIGENCE_DEBUG
or RESUME_PARSE_DEBUG is set. Snapshots are kept in-process and optionally
written to a local directory — they are never added to the public API payload.
"""
from __future__ import annotations

import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger('document_intelligence.trace')

_DEBUG = os.getenv('DOCUMENT_INTELLIGENCE_DEBUG', os.getenv('RESUME_PARSE_DEBUG', '')).lower() in (
    '1',
    'true',
    'yes',
)

_SNAPSHOT: dict[str, Any] = {}


def debug_enabled() -> bool:
    return _DEBUG


def reset_snapshot() -> None:
    _SNAPSHOT.clear()


def record_snapshot(stage: str, payload: Any) -> None:
    """Store a stage snapshot in memory when debug is on. Never logs full PII."""
    if not _DEBUG:
        return
    _SNAPSHOT[stage] = payload


def get_snapshot() -> dict[str, Any]:
    return dict(_SNAPSHOT)


def write_snapshot_file(filename: str = '') -> Path | None:
    """Write the in-memory snapshot to a local debug dir. No-op in production."""
    if not _DEBUG:
        return None
    dest_dir = os.getenv('DOCUMENT_INTELLIGENCE_TRACE_DIR', '').strip()
    if not dest_dir:
        return None
    path = Path(dest_dir)
    try:
        path.mkdir(parents=True, exist_ok=True)
        safe = re.sub(r'[^\w.\-]+', '_', filename or 'resume')[:80]
        out = path / f'{safe}.trace.json'
        out.write_text(json.dumps(_SNAPSHOT, default=str, ensure_ascii=False, indent=2), encoding='utf-8')
        return out
    except Exception:
        logger.debug('trace snapshot write skipped', exc_info=True)
        return None


def trace_stage(
    stage: str,
    *,
    section: str = '',
    field_path: str = '',
    value_preview: Any = '',
    source: str = '',
    confidence: float | None = None,
    message: str = '',
) -> None:
    if not _DEBUG:
        return
    preview = value_preview
    if isinstance(preview, str) and len(preview) > 120:
        preview = preview[:117] + '...'
    logger.info(
        'stage=%s section=%s field=%s source=%s conf=%s msg=%s value=%r',
        stage,
        section,
        field_path,
        source,
        confidence,
        message,
        preview,
    )
