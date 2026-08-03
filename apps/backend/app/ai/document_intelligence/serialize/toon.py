"""Canonical → TOON serialization for ATS persistence only."""
from __future__ import annotations

from typing import Any

from app.ai.document_intelligence.canonical.from_toon import (
    toon_from_candidate_profile,
    toon_from_job_profile,
)
from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.models.job import JobProfile


def candidate_to_toon(profile: CandidateProfile) -> dict[str, Any]:
    return toon_from_candidate_profile(profile)


def job_to_toon(profile: JobProfile) -> dict[str, Any]:
    return toon_from_job_profile(profile)
