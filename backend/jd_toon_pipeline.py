"""
JD TOON pipeline: Repair → Normalize → (caller validates) → Persist.

Structured debug logging at each stage when JD_PARSE_DEBUG=1 or logger DEBUG enabled.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

from ai_runtime_adapter import normalize_proposal, repair_jd_toon

logger = logging.getLogger(__name__)

_LOG_TRUNCATE = 2000


def _debug_enabled() -> bool:
    return os.getenv("JD_PARSE_DEBUG", "").lower() in ("1", "true", "yes")


def _truncate_text(text: str, limit: int = _LOG_TRUNCATE) -> str:
    if not text:
        return ""
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [{len(text)} chars total]"


def _safe_json(obj: Any, limit: int = _LOG_TRUNCATE) -> str:
    try:
        raw = json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = str(obj)
    return _truncate_text(raw, limit)


def log_jd_toon_stage(
    stage: str,
    *,
    payload: Any = None,
    raw_jd_text: str | None = None,
    repair_actions: list[str] | None = None,
    validation_error: str | None = None,
) -> None:
    if not _debug_enabled() and not logger.isEnabledFor(logging.DEBUG):
        return
    extra: dict[str, Any] = {"stage": stage}
    if repair_actions:
        extra["repair_actions"] = repair_actions
    if validation_error:
        extra["validation_error"] = validation_error
    if raw_jd_text is not None and stage == "raw_text":
        extra["text_length"] = len(raw_jd_text)
        extra["text_preview"] = _truncate_text(raw_jd_text)
    elif payload is not None:
        extra["payload"] = _safe_json(payload)
    logger.debug("jd_toon_pipeline %s", stage, extra=extra)


def build_jd_toon(raw_jd_text: str, llm_output: dict[str, Any]) -> dict[str, Any]:
    """
    Run JD TOON repair and normalization. Caller runs validate_toon_format.
    """
    log_jd_toon_stage("raw_text", raw_jd_text=raw_jd_text or "")

    raw_toon = copy.deepcopy(llm_output) if isinstance(llm_output, dict) else {}
    log_jd_toon_stage("raw_toon", payload=raw_toon)

    repaired, repair_actions = repair_jd_toon(raw_toon, raw_jd_text=raw_jd_text or "")
    log_jd_toon_stage("repaired_toon", payload=repaired, repair_actions=repair_actions)

    normalized = normalize_proposal(repaired, "jd")
    log_jd_toon_stage("normalized_toon", payload=normalized, repair_actions=repair_actions)

    return normalized


def log_validated_jd_toon(toon: dict[str, Any], *, valid: bool, error_msg: str | None = None) -> None:
    if valid:
        log_jd_toon_stage("validated_toon", payload=toon)
    else:
        log_jd_toon_stage("validated_toon", payload=toon, validation_error=error_msg or "unknown")
