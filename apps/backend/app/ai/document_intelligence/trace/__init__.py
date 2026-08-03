"""Stage trace logging for Document Intelligence."""
from __future__ import annotations

import logging
import os
from typing import Any

logger = logging.getLogger('document_intelligence.trace')

_DEBUG = os.getenv('DOCUMENT_INTELLIGENCE_DEBUG', os.getenv('RESUME_PARSE_DEBUG', '')).lower() in (
    '1',
    'true',
    'yes',
)


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
