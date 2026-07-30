"""
Resume TOON enrichment helpers.
Candidate account enrichment removed — public apply uses form + parse TOON only.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ResumeEnrichmentContext:
    email: str
    name: str


def get_candidate_enrichment_context(user: dict[str, Any] | None) -> ResumeEnrichmentContext | None:
    """No longer used for candidate JWT; kept as no-op for call sites."""
    return None
