"""
Resume TOON pipeline: Repair → Normalize → Enrich → Infer → (caller validates) → Persist.

Structured debug logging at each stage when RESUME_PARSE_DEBUG=1 or logger DEBUG enabled.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

from ai_runtime_adapter import normalize_proposal, repair_resume_toon
from resume_enrichment import ResumeEnrichmentContext, enrich_resume_toon
from resume_inference import infer_resume_toon

logger = logging.getLogger(__name__)

_LOG_TRUNCATE = 2000


def _debug_enabled() -> bool:
    return os.getenv("RESUME_PARSE_DEBUG", "").lower() in ("1", "true", "yes")


def _safe_json(obj: Any, limit: int = _LOG_TRUNCATE) -> str:
    try:
        raw = json.dumps(obj, default=str, ensure_ascii=False)
    except (TypeError, ValueError):
        raw = str(obj)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + f"... [{len(raw)} chars total]"


def log_resume_toon_stage(
    stage: str,
    *,
    payload: Any = None,
    repair_actions: list[str] | None = None,
    enrich_actions: list[str] | None = None,
    infer_actions: list[str] | None = None,
    validation_issues: list[str] | None = None,
    validation_error: str | None = None,
) -> None:
    if not _debug_enabled() and not logger.isEnabledFor(logging.DEBUG):
        return
    extra: dict[str, Any] = {"stage": stage}
    if repair_actions:
        extra["repair_actions"] = repair_actions
    if enrich_actions:
        extra["enrich_actions"] = enrich_actions
    if infer_actions:
        extra["infer_actions"] = infer_actions
    if validation_issues is not None:
        extra["validation_issues"] = validation_issues
    if validation_error:
        extra["validation_error"] = validation_error
    if payload is not None:
        extra["payload"] = _safe_json(payload)
    logger.debug("resume_toon_pipeline %s", stage, extra=extra)


def build_resume_toon(
    raw_resume_text: str,
    llm_output: dict[str, Any],
    enrichment_context: ResumeEnrichmentContext | None = None,
) -> dict[str, Any]:
    """
    Run resume TOON repair, normalization, enrichment, and text inference.
    Caller runs validate_toon_format.
    """
    raw_toon = copy.deepcopy(llm_output) if isinstance(llm_output, dict) else {}
    log_resume_toon_stage("raw_toon", payload=raw_toon)

    repaired, repair_actions = repair_resume_toon(raw_toon, raw_resume_text=raw_resume_text or "")
    log_resume_toon_stage("repaired_toon", payload=repaired, repair_actions=repair_actions)

    normalized = normalize_proposal(repaired, "resume")
    log_resume_toon_stage("normalized_toon", payload=normalized, repair_actions=repair_actions)

    enriched, enrich_actions = enrich_resume_toon(normalized, enrichment_context)
    log_resume_toon_stage(
        "enriched_toon",
        payload=enriched,
        repair_actions=repair_actions,
        enrich_actions=enrich_actions,
    )

    inferred, infer_actions = infer_resume_toon(enriched, raw_resume_text or "")
    log_resume_toon_stage(
        "inferred_toon",
        payload=inferred,
        repair_actions=repair_actions,
        enrich_actions=enrich_actions,
        infer_actions=infer_actions,
    )

    return inferred


def log_validated_resume_toon(
    toon: dict[str, Any],
    *,
    valid: bool,
    error_msg: str | None = None,
    validation_issues: list[str] | None = None,
) -> None:
    if validation_issues is None and error_msg:
        validation_issues = [part.strip() for part in error_msg.split(";") if part.strip()]
    if not valid:
        log_resume_toon_stage(
            "validation_issues",
            payload=toon,
            validation_issues=validation_issues or [],
            validation_error=error_msg or "unknown",
        )
    if valid:
        log_resume_toon_stage("validated_toon", payload=toon)
    else:
        log_resume_toon_stage(
            "validated_toon",
            payload=toon,
            validation_issues=validation_issues,
            validation_error=error_msg or "unknown",
        )
