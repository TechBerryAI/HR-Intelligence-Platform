"""
Resume TOON inference — fill remaining gaps from raw resume text after enrichment.
"""
from __future__ import annotations

from typing import Any

from resume_text_inference import infer_resume_fields_from_text


def infer_resume_toon(toon: dict[str, Any], raw_resume_text: str) -> tuple[dict[str, Any], list[str]]:
    """
    Fill empty/missing fields from raw text. Never overwrite non-empty values.
    Runs after enrichment so account email/name are already applied.
    """
    actions: list[str] = []
    if not isinstance(toon, dict):
        return toon, actions

    inferred = infer_resume_fields_from_text(raw_resume_text or "")

    skills = toon.get("skills")
    if not isinstance(skills, list) or len(skills) == 0:
        new_skills = inferred.get("skills") or []
        if new_skills:
            toon["skills"] = new_skills
            actions.append("inferred_skills_from_text")

    if not (toon.get("summary") or "").strip():
        summary = inferred.get("summary") or ""
        if summary:
            toon["summary"] = summary
            actions.append("inferred_summary_from_text")

    person = toon.get("person")
    if not isinstance(person, dict):
        person = {}
        toon["person"] = person

    if not (person.get("phone") or "").strip():
        phone = (inferred.get("person") or {}).get("phone") or ""
        if phone:
            person["phone"] = phone
            actions.append("inferred_phone_from_text")

    experience = toon.get("experience")
    if not isinstance(experience, list) or len(experience) == 0:
        new_exp = inferred.get("experience") or []
        if new_exp:
            toon["experience"] = new_exp
            actions.append("inferred_experience_from_text")

    return toon, actions
