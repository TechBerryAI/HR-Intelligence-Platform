"""AI experience extraction for apply-form autofill.

Uses the resume_parsing capability on the Experience section, then merges
with deterministic rows only when the AI set is more complete and grounded.
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


@timing
def extract_and_merge_experience(
    profile: CandidateProfile,
    source_text: str,
) -> CandidateProfile:
    """Run resume AI on the experience span and keep the better grounded set."""
    from app.ai.document_intelligence.coverage.resume_coverage import _experience_section_text
    from app.ai.document_intelligence.semantic import _call_section_llm

    text = (source_text or '').strip()
    if len(text) < 40:
        return profile
    section = _experience_section_text(text) or text
    payload = (
        'Parse this resume. Put every WORK job in experience[]. '
        'title = job title only. company = employer only. Never swap them. '
        'Stacked layout example: "Database Administrator" then '
        '"Infosenseglobal | Dec 2024 – Present". Skip projects and training.\n\n'
        f'{section[:7000]}'
    )
    raw = _call_section_llm(payload, 'resume')
    if not isinstance(raw, dict):
        return profile
    try:
        ai_rows = _entries_from_ai_payload(raw)
        if not ai_rows:
            # Standard resume_parsing output may need the TOON adapter
            adapted = candidate_profile_from_toon(raw if raw.get('type') else {**raw, 'type': 'resume'})
            ai_rows = list(adapted.experience or [])
        ai_rows = ground_experience_rows(ai_rows, text)
        merged = merge_experience_rows(list(profile.experience or []), ai_rows)
        if merged is profile.experience:
            return profile
        return profile.model_copy(update={'experience': merged})
    except Exception as exc:
        logger.debug('experience AI merge failed: %s', exc)
        return profile


__all__ = [
    'experience_is_incomplete',
    'extract_and_merge_experience',
]
