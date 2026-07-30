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


def enrich_resume_toon(
    toon: dict[str, Any],
    context: ResumeEnrichmentContext | None,
) -> tuple[dict[str, Any], list[str]]:
    """
    Fill missing person.email / person.name from account context.
    Never overwrites non-empty resume values. No-op when context is None.
    """
    actions: list[str] = []
    if not isinstance(toon, dict):
        return toon, actions
    if context is None:
        return toon, actions

    person = toon.get("person")
    if not isinstance(person, dict):
        person = {}
        toon["person"] = person

    if not (person.get("email") or "").strip() and (context.email or "").strip():
        person["email"] = context.email.strip()
        actions.append("enriched_email_from_account")

    if not (person.get("name") or "").strip() and (context.name or "").strip():
        person["name"] = context.name.strip()
        actions.append("enriched_name_from_account")

    return toon, actions
