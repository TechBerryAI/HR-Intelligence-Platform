"""Knowledge normalization on canonical models."""
from __future__ import annotations

from app.ai.document_intelligence.models.candidate import CandidateProfile, SkillEntry
from app.ai.document_intelligence.models.job import JobProfile
from app.ai.parser.engine.knowledge import normalize_job_title, normalize_skill


def apply_knowledge_to_candidate(profile: CandidateProfile) -> CandidateProfile:
    skills = []
    for s in profile.skills:
        name = s.name or s.canonical
        canon, _ = normalize_skill(name) if name else ('', None)
        skills.append(SkillEntry(name=name, canonical=canon or name, category=s.category))
    experience = []
    for e in profile.experience:
        role, _ = normalize_job_title(e.role) if e.role else (e.role, None)
        experience.append(e.model_copy(update={'role': role or e.role}))
    return profile.model_copy(update={'skills': skills, 'experience': experience})


def apply_knowledge_to_job(profile: JobProfile) -> JobProfile:
    def _dedupe_keep_jd_wording(items: list[str]) -> list[str]:
        """Keep JD skill wording as written — do not expand aliases (aws→Amazon Web Services)."""
        out = []
        seen = set()
        for i in items:
            val = (i or '').strip()
            if not val:
                continue
            key = val.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(val)
        return out

    skills = profile.skills.model_copy(
        update={
            'mandatory': _dedupe_keep_jd_wording(profile.skills.mandatory),
            'preferred': _dedupe_keep_jd_wording(profile.skills.preferred),
            'general': _dedupe_keep_jd_wording(profile.skills.general),
        }
    )
    title, _ = normalize_job_title(profile.basic.title) if profile.basic.title else ('', None)
    basic = profile.basic.model_copy(update={'title': title or profile.basic.title})
    return profile.model_copy(update={'skills': skills, 'basic': basic})
