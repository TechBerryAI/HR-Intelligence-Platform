"""Semantic association + field-accuracy layer.

Runs after deterministic section parsers (and coverage recovery). It does not
replace SECTION_DETECTION, OCR, or the existing extractors. It rebinds
already-extracted values to the correct record using section/record evidence.
"""
from __future__ import annotations

from app.ai.document_intelligence.association.classification import (
    associate_certificates_and_skills,
)
from app.ai.document_intelligence.association.education import associate_education
from app.ai.document_intelligence.association.experience import associate_experience
from app.ai.document_intelligence.association.summary import associate_summary
from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.sections import pick_section
from app.ai.parser.engine.types import SectionSpan


def apply_semantic_association(
    profile: CandidateProfile,
    sections: list[SectionSpan],
    source_text: str,
) -> CandidateProfile:
    """Return a copy of ``profile`` with association repairs applied."""
    if profile is None:
        return profile
    report: dict = {
        'experience': [],
        'education': [],
        'classification': [],
        'summary': [],
    }
    exp_text = pick_section(
        sections,
        'Experience',
        'Work Experience',
        'Professional Experience',
        'Employment',
        'Employment History',
        'Work History',
        'Career History',
        'Internship',
        'Internships',
        'Internship Experience',
        'Industrial Training',
    )
    # Do not scrape the whole resume when the Experience span is empty
    # (two-column / sidebar layouts). That path invented "Summary" as a company.
    if len((exp_text or '').strip()) >= 80:
        experience = associate_experience(
            list(profile.experience or []),
            exp_text,
            report=report['experience'],
        )
    else:
        experience = list(profile.experience or [])
        if report['experience'] is not None:
            report['experience'].append({'action': 'skip', 'reason': 'thin_experience_section'})
    edu_text = pick_section(
        sections,
        'Education',
        'Academic Background',
        'Academic Qualifications',
        'Academic Qualification',
        'Academics',
        'Educational Qualifications',
        'Educational Background',
        'Qualifications',
    ) or _fallback_section(source_text, 'education')

    education = associate_education(
        list(profile.education or []),
        edu_text,
        report=report['education'],
    )
    certificates, skills = associate_certificates_and_skills(
        list(profile.certificates or []),
        list(profile.skills or []),
        report=report['classification'],
    )
    personal = profile.personal
    contact = profile.contact
    summary = associate_summary(
        personal.summary if personal else '',
        contact_email=contact.email if contact else '',
        contact_phone=contact.phone if contact else '',
        contact_linkedin=contact.linkedin if contact else '',
        location=contact.location if contact else '',
        full_name=personal.full_name if personal else '',
        report=report['summary'],
    )
    if personal and summary != (personal.summary or ''):
        personal = personal.model_copy(update={'summary': summary})

    meta = dict(profile.field_meta or {})
    meta['association_report'] = report
    return profile.model_copy(
        update={
            'personal': personal or profile.personal,
            'experience': experience,
            'education': education,
            'certificates': certificates,
            'skills': skills,
            'field_meta': meta,
        }
    )


def _fallback_section(source_text: str, kind: str) -> str:
    """When section spans are empty, use the labeled body from full text."""
    text = source_text or ''
    if kind == 'experience':
        labels = r'experience|employment|work\s+history|internships?'
        stop = r'education|skills?|certifications?|projects?|summary|objective'
    else:
        labels = r'education|academic(?:s| background| qualifications?)?'
        stop = r'experience|employment|skills?|certifications?|projects?|summary'
    import re

    m = re.search(
        rf'(?is)(?:^|\n)\s*(?:{labels})\s*:?\s*\n(.*?)(?=\n\s*(?:{stop})\b|\Z)',
        text,
    )
    return (m.group(1) if m else '').strip()
