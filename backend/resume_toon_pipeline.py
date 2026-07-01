"""
Resume TOON pipeline: Repair → Canonicalize → Enrich → (caller validates) → Persist.

Structured debug logging at each stage when RESUME_PARSE_DEBUG=1 or logger DEBUG enabled.
"""
from __future__ import annotations

import copy
import json
import logging
import os
from typing import Any

from ai_runtime_adapter import canonicalize_resume_toon, repair_resume_toon
from parsing_utils import collect_toon_validation_issues
from resume_enrichment import ResumeEnrichmentContext, enrich_resume_toon

logger = logging.getLogger(__name__)

_LOG_TRUNCATE = 2000

_STAGE_LABELS = {
    "raw_extracted_text": "RAW EXTRACTED TEXT",
    "raw_toon": "RAW TOON FROM LLM",
    "repaired_toon": "REPAIRED TOON",
    "canonical_toon": "CANONICAL TOON",
    "enriched_toon": "ENRICHED TOON",
    "validation_result": "VALIDATION RESULT",
}


def _debug_enabled() -> bool:
    return os.getenv("RESUME_PARSE_DEBUG", "").lower() in ("1", "true", "yes")


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
    if len(raw) <= limit:
        return raw
    return raw[:limit] + f"... [{len(raw)} chars total]"


def _field_counts(toon: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(toon, dict):
        return {}
    counts: dict[str, Any] = {}
    for key in ("skills", "experience", "education", "projects", "certifications", "languages"):
        val = toon.get(key)
        counts[key] = len(val) if isinstance(val, list) else 0
    person = toon.get("person")
    if isinstance(person, dict):
        counts["person_fields"] = sum(
            1 for k in ("name", "email", "phone") if (person.get(k) or "").strip()
        )
    return counts


def _missing_required_fields(toon: dict[str, Any]) -> list[str]:
    issues = collect_toon_validation_issues(toon, "resume")
    missing: list[str] = []
    for issue in issues:
        if issue.startswith("Missing required field:"):
            missing.append(issue.replace("Missing required field: ", ""))
        elif issue.startswith("Missing person field:"):
            missing.append(issue.replace("Missing person field: ", ""))
        elif "must not be empty" in issue or "must be a non-empty array" in issue:
            missing.append(issue)
    return missing


def log_resume_toon_stage(
    stage: str,
    *,
    payload: Any = None,
    raw_resume_text: str | None = None,
    object_id: int | None = None,
    repair_actions: list[str] | None = None,
    canon_actions: list[str] | None = None,
    enrich_actions: list[str] | None = None,
    validation_issues: list[str] | None = None,
    validation_error: str | None = None,
) -> None:
    if not _debug_enabled() and not logger.isEnabledFor(logging.DEBUG):
        return

    label = _STAGE_LABELS.get(stage, stage.upper())
    extra: dict[str, Any] = {"stage": stage, "block": label}

    if object_id is not None:
        extra["object_id"] = object_id
    if repair_actions:
        extra["repair_actions"] = repair_actions
    if canon_actions:
        extra["canon_actions"] = canon_actions
    if enrich_actions:
        extra["enrich_actions"] = enrich_actions
    if validation_issues is not None:
        extra["validation_issues"] = validation_issues
    if validation_error:
        extra["validation_error"] = validation_error

    if stage == "raw_extracted_text" and raw_resume_text is not None:
        extra["text_length"] = len(raw_resume_text)
        extra["text_preview"] = _truncate_text(raw_resume_text)
    elif isinstance(payload, dict):
        extra["field_counts"] = _field_counts(payload)
        extra["missing_required_fields"] = _missing_required_fields(payload)
        extra["payload"] = _safe_json(payload)

    logger.debug("resume_toon_pipeline %s", label, extra=extra)


def build_resume_toon(
    raw_resume_text: str,
    llm_output: dict[str, Any],
    enrichment_context: ResumeEnrichmentContext | None = None,
) -> dict[str, Any]:
    """
    Run resume TOON repair, canonicalization, and enrichment on a single mutable object.
    Caller runs validate_toon_format.
    """
    toon = copy.deepcopy(llm_output) if isinstance(llm_output, dict) else {}
    toon_id = id(toon)

    log_resume_toon_stage("raw_extracted_text", raw_resume_text=raw_resume_text or "")
    log_resume_toon_stage("raw_toon", payload=toon, object_id=toon_id)

    toon, repair_actions = repair_resume_toon(toon, raw_resume_text=raw_resume_text or "")
    log_resume_toon_stage(
        "repaired_toon",
        payload=toon,
        object_id=toon_id,
        repair_actions=repair_actions,
    )

    toon, canon_actions = canonicalize_resume_toon(toon)
    log_resume_toon_stage(
        "canonical_toon",
        payload=toon,
        object_id=toon_id,
        repair_actions=repair_actions,
        canon_actions=canon_actions,
    )

    toon, enrich_actions = enrich_resume_toon(toon, enrichment_context)
    log_resume_toon_stage(
        "enriched_toon",
        payload=toon,
        object_id=toon_id,
        repair_actions=repair_actions,
        canon_actions=canon_actions,
        enrich_actions=enrich_actions,
    )

    return toon


def log_validated_resume_toon(
    toon: dict[str, Any],
    *,
    valid: bool,
    error_msg: str | None = None,
    validation_issues: list[str] | None = None,
) -> None:
    if validation_issues is None and error_msg:
        validation_issues = [part.strip() for part in error_msg.split(";") if part.strip()]

    log_resume_toon_stage(
        "validation_result",
        payload=toon,
        object_id=id(toon),
        validation_issues=validation_issues or [],
        validation_error=None if valid else (error_msg or "unknown"),
    )
