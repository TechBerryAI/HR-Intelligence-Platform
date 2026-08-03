"""Composable field parsers — re-export existing extractors (no duplication)."""
from __future__ import annotations

from typing import Any

from app.ai.parser.enrichment import resume_text_inference as rti
from app.ai.parser.enrichment import jd_text_inference as jti


def parse_resume_contact(text: str) -> dict[str, Any]:
    """Deterministic person contact fields from full text."""
    fields = rti.infer_resume_fields_from_text(text or '')
    person = fields.get('person') if isinstance(fields.get('person'), dict) else {}
    return {
        'name': person.get('name') or fields.get('name') or '',
        'email': person.get('email') or fields.get('email') or '',
        'phone': person.get('phone') or fields.get('phone') or '',
        'location': person.get('location') or fields.get('location') or '',
        'linkedin': person.get('linkedin') or fields.get('linkedin') or '',
        'github': person.get('github') or fields.get('github') or '',
        'portfolio': person.get('portfolio') or fields.get('portfolio') or '',
        'website': person.get('website') or fields.get('website') or '',
        'twitter': person.get('twitter') or fields.get('twitter') or '',
    }


def parse_resume_from_text(text: str) -> dict[str, Any]:
    """Full deterministic resume field inference (existing module)."""
    return rti.infer_resume_fields_from_text(text or '')


def parse_jd_from_text(text: str) -> dict[str, Any]:
    """Full deterministic JD field inference (existing module)."""
    return jti.infer_jd_fields_from_text(text or '')


def parse_jd_skills(text: str) -> tuple[list[str], list[str], list[str]]:
    return jti.extract_skills_from_text(text or '')


def parse_jd_salary(text: str) -> str:
    return jti.extract_salary_from_text(text or '')


def parse_jd_dates_experience(text: str) -> tuple[Any, Any]:
    return jti.extract_experience_years(text or '')


# Plausibility — single source of truth for backend (and FE should trust TOON)
is_plausible_job_title = rti.is_plausible_job_title
is_plausible_person_name = rti.is_plausible_person_name
filter_skill_items = rti.filter_skill_items
