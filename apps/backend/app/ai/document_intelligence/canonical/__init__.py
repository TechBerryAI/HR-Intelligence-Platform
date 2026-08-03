"""Canonical package."""
from app.ai.document_intelligence.canonical.from_toon import (
    candidate_profile_from_toon,
    job_profile_from_toon,
    toon_from_candidate_profile,
    toon_from_job_profile,
)

__all__ = [
    'candidate_profile_from_toon',
    'job_profile_from_toon',
    'toon_from_candidate_profile',
    'toon_from_job_profile',
]
