"""Resume completeness coverage — recover contact/location/education from source only."""
from __future__ import annotations

import re
from typing import Any

from app.ai.document_intelligence.coverage.jd_coverage import CoverageReport, FieldCoverage
from app.ai.document_intelligence.deterministic import (
    extract_email,
    extract_phone,
    extract_simple_location,
)
from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.parsers.resume import coalesce_education, parse_education


def _has_email_evidence(text: str) -> bool:
    return bool(re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text or ''))


def _has_phone_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)(?:phone|mobile|mob|cell|tel)\s*[:.\-–—]?|'
            r'\+?\d[\d\s().\-]{8,}\d|'
            r'\b[6-9]\d{9}\b',
            text or '',
        )
    )


def _has_location_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)(?:location|address|based\s+in|residing)|'
            r'\b(?:mumbai|delhi|bangalore|bengaluru|hyderabad|chennai|pune|thane|'
            r'noida|gurugram|kolkata|remote|hybrid)\b',
            text or '',
        )
    )


def _has_education_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)\b(?:education|academic|bachelor|master|b\.?\s*tech|m\.?\s*tech|'
            r'university|college|12th|10th|diploma)\b',
            text or '',
        )
    )


def recover_resume_profile_gaps(
    profile: CandidateProfile,
    raw_text: str,
) -> tuple[CandidateProfile, CoverageReport]:
    """
    Fill empty contact/location/education fields only when evidence exists in source.
    Never invents experience or names.
    """
    text = raw_text or ''
    data = profile.model_dump()
    contact = data.get('contact') or {}
    recovered: list[str] = []
    fields: list[FieldCoverage] = []

    # Email
    email = str(contact.get('email') or '').strip()
    email_ev = _has_email_evidence(text)
    if email:
        fields.append(FieldCoverage('email', 'filled', True))
    elif email_ev:
        found = extract_email(text)
        if found:
            contact['email'] = found
            recovered.append('email')
            fields.append(FieldCoverage('email', 'recovered', True, found[:80]))
        else:
            fields.append(FieldCoverage('email', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('email', 'missing_no_evidence', False))

    # Phone
    phone = str(contact.get('phone') or '').strip()
    phone_ev = _has_phone_evidence(text)
    if phone:
        fields.append(FieldCoverage('phone', 'filled', True))
    elif phone_ev:
        found = extract_phone(text)
        if found:
            contact['phone'] = found
            recovered.append('phone')
            fields.append(FieldCoverage('phone', 'recovered', True, found[:40]))
        else:
            fields.append(FieldCoverage('phone', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('phone', 'missing_no_evidence', False))

    # Location
    loc = str(contact.get('location') or '').strip()
    loc_ev = _has_location_evidence(text)
    if loc:
        fields.append(FieldCoverage('location', 'filled', True))
    elif loc_ev:
        found = extract_simple_location(text)
        if found:
            contact['location'] = found
            if not str(contact.get('preferred_location') or '').strip():
                contact['preferred_location'] = found
            recovered.append('location')
            fields.append(FieldCoverage('location', 'recovered', True, found[:80]))
        else:
            fields.append(FieldCoverage('location', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('location', 'missing_no_evidence', False))

    # Preferred location: mirror current when empty (grounded copy only)
    if (
        str(contact.get('location') or '').strip()
        and not str(contact.get('preferred_location') or '').strip()
    ):
        contact['preferred_location'] = contact['location']
        recovered.append('preferred_location')

    data['contact'] = contact

    # Education halves: re-parse from source when empty or incomplete
    edu_list = list(data.get('education') or [])
    edu_complete = any(
        str(e.get('degree') or '').strip() and str(e.get('institution') or '').strip()
        for e in edu_list
        if isinstance(e, dict)
    )
    edu_ev = _has_education_evidence(text)
    if edu_complete:
        fields.append(FieldCoverage('education', 'filled', True))
    elif edu_ev:
        parsed = coalesce_education(parse_education('', text))
        grounded = [
            e
            for e in parsed
            if (e.degree or '').strip() and (e.institution or '').strip()
        ]
        if grounded and (not edu_list or len(grounded) > len(edu_list)):
            data['education'] = [e.model_dump() for e in grounded]
            recovered.append('education')
            fields.append(
                FieldCoverage('education', 'recovered', True, f'{len(grounded)} rows')
            )
        elif grounded and not edu_complete:
            # Merge: fill empty halves only
            if not edu_list:
                data['education'] = [e.model_dump() for e in grounded]
                recovered.append('education')
                fields.append(
                    FieldCoverage('education', 'recovered', True, f'{len(grounded)} rows')
                )
            else:
                fields.append(FieldCoverage('education', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('education', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('education', 'missing_no_evidence', False))

    report = CoverageReport(fields=fields)
    try:
        updated = CandidateProfile.model_validate(data)
    except Exception:
        return profile, report
    return updated, report


def resume_has_recoverable_gaps(profile: CandidateProfile, raw_text: str) -> bool:
    """True when contact/location/education incomplete but source has evidence."""
    contact = profile.contact
    text = raw_text or ''
    if not (contact.email or '').strip() and _has_email_evidence(text):
        return True
    if not (contact.phone or '').strip() and _has_phone_evidence(text):
        return True
    if not (contact.location or '').strip() and _has_location_evidence(text):
        return True
    edu_ok = any(
        (e.degree or '').strip() and (e.institution or '').strip() for e in profile.education
    )
    if not edu_ok and _has_education_evidence(text):
        return True
    return False
