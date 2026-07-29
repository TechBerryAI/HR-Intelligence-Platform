"""
Resume TOON enrichment — trusted account fallbacks for authenticated candidate uploads.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domains.identity.authorization.rbac import ROLE_CANDIDATE, get_role, get_user_id


@dataclass
class ResumeEnrichmentContext:
    email: str
    name: str


def get_candidate_enrichment_context(user: dict[str, Any] | None) -> ResumeEnrichmentContext | None:
    """Load trusted email/name for CANDIDATE uploads only."""
    if not user or get_role(user) != ROLE_CANDIDATE:
        return None

    from app.database.connection.db import db_get

    candidate_id = get_user_id(user)
    email = (user.get('email') or '').strip()
    name = ''

    if candidate_id:
        profile = db_get(
            'SELECT full_name, email FROM candidate_profiles WHERE candidate_id = ?',
            (candidate_id,),
        )
        if profile:
            name = (profile.get('full_name') or '').strip()
            if not email:
                email = (profile.get('email') or '').strip()

        if not name or not email:
            signup = db_get(
                'SELECT name, email FROM candidate_signup WHERE cid = ?',
                (candidate_id,),
            )
            if signup:
                if not name:
                    name = (signup.get('name') or '').strip()
                if not email:
                    email = (signup.get('email') or '').strip()

    if not email and not name:
        return None

    return ResumeEnrichmentContext(email=email, name=name)


def enrich_resume_toon(
    toon: dict[str, Any],
    ctx: ResumeEnrichmentContext | None,
) -> tuple[dict[str, Any], list[str]]:
    """Fill missing person.email/name from account; never overwrite extracted values."""
    actions: list[str] = []
    if not ctx or not isinstance(toon, dict):
        return toon, actions

    person = toon.get('person')
    if not isinstance(person, dict):
        person = {}
        toon['person'] = person

    if not (person.get('email') or '').strip() and ctx.email:
        person['email'] = ctx.email.strip()
        actions.append('enriched_email_from_account')

    if not (person.get('name') or '').strip() and ctx.name:
        person['name'] = ctx.name.strip()
        actions.append('enriched_name_from_account')

    return toon, actions
