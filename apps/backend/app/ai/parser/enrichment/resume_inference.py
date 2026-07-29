"""
Resume TOON inference — deprecated; text recovery now runs inside repair.

Kept as a thin wrapper for backward compatibility with existing imports/tests.
"""
from __future__ import annotations

from typing import Any

from app.ai.adapter.runtime_adapter import _apply_resume_text_recovery


def infer_resume_toon(toon: dict[str, Any], raw_resume_text: str) -> tuple[dict[str, Any], list[str]]:
    """
    Deprecated: use repair_resume_toon which includes text recovery.
    Fills empty/missing fields from raw text without overwriting non-empty values.
    """
    actions: list[str] = []
    if not isinstance(toon, dict):
        return toon, actions
    _apply_resume_text_recovery(toon, raw_resume_text or "", actions)
    return toon, actions
