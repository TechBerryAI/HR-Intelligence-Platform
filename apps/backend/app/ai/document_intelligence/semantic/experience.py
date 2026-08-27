"""AI experience merge for apply-form autofill.

Merges experience rows from a full resume_parsing JSON payload with
deterministic rows only when the AI set is more complete and grounded.
Ollama is invoked once by enrich_resume_semantic, not here.
"""
from __future__ import annotations

import logging
from typing import Any

from app.ai.document_intelligence.canonical.from_toon import candidate_profile_from_toon
from app.ai.document_intelligence.experience_quality import (
    experience_is_incomplete,
    ground_experience_rows,
    merge_experience_rows,
)
from app.ai.document_intelligence.models.candidate import CandidateProfile, ExperienceEntry
from app.ai.document_intelligence.validation.engine import sanitize_experience_row
from app.core.timing import timing

logger = logging.getLogger(__name__)

_PRESENT = frozenset({'present', 'current', 'now'})


def _entries_from_ai_payload(raw: dict[str, Any]) -> list[ExperienceEntry]:
    items = raw.get('experience')
    if not isinstance(items, list):
        return []
    out: list[ExperienceEntry] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        role = str(item.get('role') or item.get('title') or '').strip()[:200]
        company = str(item.get('company') or '').strip()[:200]
        start = str(item.get('start') or item.get('from') or '').strip()
        end = str(item.get('end') or item.get('to') or '').strip()
        desc = str(item.get('description') or '').strip()[:2000]
        is_current = end.lower() in _PRESENT
        if is_current:
            end = ''
        if not (role or company):
            continue
        cleaned = sanitize_experience_row(
            ExperienceEntry(
                role=role,
                company=company,
                start=start,
                end=end,
                is_current=is_current,
                description=desc,
            )
        )
        if cleaned.role or cleaned.company:
            out.append(cleaned)
    return out


def merge_experience_from_ai(
    profile: CandidateProfile,
    raw: dict[str, Any],
    source_text: str,
) -> CandidateProfile:
    """Keep the better grounded experience set from an existing resume_parsing payload.

    Does not invoke Ollama. Callers must obtain ``raw`` from the single
    full-resume semantic call in ``enrich_resume_semantic``.
    """
    text = (source_text or '').strip()
    if not isinstance(raw, dict):
        return profile
    try:
        ai_rows = _entries_from_ai_payload(raw)
        if not ai_rows:
            adapted = candidate_profile_from_toon(
                raw if raw.get('type') else {**raw, 'type': 'resume'}
            )
            ai_rows = list(adapted.experience or [])
        ai_rows = ground_experience_rows(ai_rows, text)
        merged = merge_experience_rows(list(profile.experience or []), ai_rows)
        if merged is profile.experience:
            return profile
        return profile.model_copy(update={'experience': merged})
    except Exception as exc:
        logger.debug('experience AI merge failed: %s', exc)
        return profile


@timing
def extract_and_merge_experience(
    profile: CandidateProfile,
    source_text: str,
    *,
    raw: dict[str, Any] | None = None,
) -> CandidateProfile:
    """Merge experience from a resume_parsing JSON payload.

    Ollama is owned by ``enrich_resume_semantic`` (at most one full resume call
    per parse). Pass ``raw`` from that response. A missing payload is a no-op
    so this helper cannot issue a second inference.
    """
    if not isinstance(raw, dict):
        return profile
    return merge_experience_from_ai(profile, raw, source_text)


__all__ = [
    'experience_is_incomplete',
    'extract_and_merge_experience',
    'merge_experience_from_ai',
]
