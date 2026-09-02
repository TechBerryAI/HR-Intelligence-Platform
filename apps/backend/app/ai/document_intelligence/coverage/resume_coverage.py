"""Resume completeness coverage — recover contact/location/education/experience from source only."""
from __future__ import annotations

import re
from typing import Any

from app.ai.document_intelligence.coverage.jd_coverage import CoverageReport, FieldCoverage
from app.ai.document_intelligence.deterministic import (
    extract_email,
    extract_phone,
    extract_simple_location,
)
from app.ai.document_intelligence.models.candidate import CandidateProfile, ExperienceEntry
from app.ai.document_intelligence.parsers.resume import (
    coalesce_education,
    parse_education,
    parse_experience,
)
from app.ai.document_intelligence.validation.engine import is_grounded_education_row, validate_phone

# VALIDATION_FIX_experience_section_evidence
_EXP_SECTION_RE = re.compile(
    r'(?im)^(?:\*\*)?(?:work\s*experience|professional\s*experience|experience|'
    r'employment|work\s+history|career\s+history|internships?|internship\s+experience|'
    r'industrial\s+trainings?|summer\s+internship|internship\s*/\s*training|'
    r'management\s+internship|research\s+internship|graduate\s+internship|'
    r'training\s+experience|'
    r'trainings?|apprenticeships?)\b'
)


def has_experience_section_evidence(text: str) -> bool:
    """True when a Work/Internship/Experience section header exists in source."""
    return bool(_EXP_SECTION_RE.search(text or ''))


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
    from app.ai.parser.enrichment.resume_text_inference import known_location_cities

    if re.search(
        r'(?i)(?:location|address|based\s+in|residing|current\s+location)',
        text or '',
    ):
        return True
    if re.search(r'(?i)\b(?:remote|hybrid|vellore\s+institute)\b', text or ''):
        return True
    for city in known_location_cities():
        if re.search(rf'(?i)\b{re.escape(city)}\b', text or ''):
            return True
    return False


def _has_education_evidence(text: str) -> bool:
    return bool(
        re.search(
            r'(?i)\b(?:education|academic|bachelor|master|b\.?\s*tech|m\.?\s*tech|'
            r'university|college|12th|10th|diploma)\b',
            text or '',
        )
    )


def _experience_section_text(text: str) -> str:
    """Slice Experience/Internship body from raw text for grounded re-parse."""
    m = re.search(
        r'(?ims)(?:^|\n)\s*(?:\*\*)?(?:work\s*experience|professional\s*experience|'
        r'experience|employment|work\s+history|internships?|internship\s+experience|'
        r'industrial\s+trainings?|summer\s+internship|internship\s*/\s*training[^\n]*|'
        r'trainings?|apprenticeships?)\b[^\n]*\n'
        r'(.*?)(?=\n\s*(?:\*\*)?(?:education|academic|skills|skill\s*sets?|'
        r'technical\s+skills?|technical\s+proficiency|technical\s+expertise|'
        r'technical\s+knowledge|projects?|certifications?|personal\s+details|'
        r'personal\s+information|biodata|declaration)(?:\*\*)?\s*:?\s*$|\Z)',
        text or '',
    )
    return (m.group(1) if m else '').strip()


def _is_plausible_location(value: str) -> bool:
    """Reject skill/summary pollution that slipped into contact.location."""
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_location_value

    return is_plausible_location_value(value)


def recover_resume_profile_gaps(
    profile: CandidateProfile,
    raw_text: str,
) -> tuple[CandidateProfile, CoverageReport]:
    """
    Fill empty contact/location/education/experience fields only when evidence exists.
    Never invents names.
    """
    text = raw_text or ''
    data = profile.model_dump()
    contact = data.get('contact') or {}
    personal = data.get('personal') or {}
    recovered: list[str] = []
    fields: list[FieldCoverage] = []

    # Full name — report only (never invent); recover via existing parsers elsewhere
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_name_from_text,
        is_plausible_person_name,
    )

    full_name = str(personal.get('full_name') or '').strip()
    name_ev = bool(extract_name_from_text(text[:2500]) if text else '')
    if full_name and is_plausible_person_name(full_name):
        fields.append(FieldCoverage('fullName', 'filled', True))
    elif name_ev:
        found = extract_name_from_text(text[:2500])
        if found and is_plausible_person_name(found):
            # Replace missing OR implausible body/LLM names (e.g. "Lead Generation")
            if not full_name or not is_plausible_person_name(full_name):
                personal['full_name'] = found
                data['personal'] = personal
                recovered.append('fullName')
                fields.append(FieldCoverage('fullName', 'recovered', True, found[:80]))
            else:
                fields.append(FieldCoverage('fullName', 'filled', True))
        elif not full_name:
            fields.append(FieldCoverage('fullName', 'missing_with_evidence', True))
        elif not is_plausible_person_name(full_name):
            personal['full_name'] = ''
            data['personal'] = personal
            recovered.append('fullName_cleared_implausible')
            fields.append(FieldCoverage('fullName', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('fullName', 'filled', True, 'unvalidated'))
    else:
        if full_name and not is_plausible_person_name(full_name):
            personal['full_name'] = ''
            data['personal'] = personal
            recovered.append('fullName_cleared_implausible')
            full_name = ''
        fields.append(
            FieldCoverage(
                'fullName',
                'filled' if full_name else 'missing_no_evidence',
                bool(full_name),
            )
        )

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

    # Phone — drop year-soup / invalid phones then re-extract
    phone = str(contact.get('phone') or '').strip()
    phone_ok = validate_phone(phone)[0] if phone else False
    phone_ev = _has_phone_evidence(text)
    if phone and phone_ok:
        fields.append(FieldCoverage('phone', 'filled', True))
    elif phone_ev:
        found = extract_phone(text)
        if found and validate_phone(found)[0]:
            contact['phone'] = found
            recovered.append('phone')
            fields.append(FieldCoverage('phone', 'recovered', True, found[:40]))
        elif phone and not phone_ok:
            contact['phone'] = ''
            fields.append(FieldCoverage('phone', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('phone', 'missing_with_evidence', True))
    else:
        if phone and not phone_ok:
            contact['phone'] = ''
        fields.append(FieldCoverage('phone', 'missing_no_evidence', False))

    # Location — clear polluted values then re-extract / peel from edu+job
    from app.ai.parser.enrichment.resume_text_inference import (
        peel_location_from_structured,
    )

    loc = str(contact.get('location') or '').strip()
    loc_ok = _is_plausible_location(loc) if loc else False
    loc_ev = _has_location_evidence(text)
    if loc and loc_ok:
        fields.append(FieldCoverage('location', 'filled', True))
    else:
        if loc and not loc_ok:
            contact['location'] = ''
            if str(contact.get('preferred_location') or '').strip() == loc:
                contact['preferred_location'] = ''
            loc = ''
        found = extract_simple_location(text) if (loc_ev or text) else ''
        if not (found and _is_plausible_location(found)):
            found = peel_location_from_structured(
                experience=list(data.get('experience') or []),
                education=list(data.get('education') or []),
                raw_text=text,
            )
        if found and _is_plausible_location(found):
            contact['location'] = found
            if not str(contact.get('preferred_location') or '').strip() or not _is_plausible_location(
                str(contact.get('preferred_location') or '')
            ):
                contact['preferred_location'] = found
            recovered.append('location')
            fields.append(FieldCoverage('location', 'recovered', True, found[:80]))
        elif loc_ev:
            fields.append(FieldCoverage('location', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('location', 'missing_no_evidence', False))

    # Preferred location: mirror current when empty (grounded copy only)
    pref = str(contact.get('preferred_location') or '').strip()
    if pref and not _is_plausible_location(pref):
        contact['preferred_location'] = ''
        pref = ''
    if (
        str(contact.get('location') or '').strip()
        and _is_plausible_location(str(contact.get('location') or ''))
        and not pref
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
            if is_grounded_education_row(e.degree, e.institution)
        ]
        if grounded and (not edu_list or len(grounded) > len(edu_list)):
            data['education'] = [e.model_dump() for e in grounded]
            recovered.append('education')
            fields.append(
                FieldCoverage('education', 'recovered', True, f'{len(grounded)} rows')
            )
        elif grounded and not edu_complete:
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

    # Experience: recover when empty, or replace incomplete rows with a better section parse
    exp_list = list(data.get('experience') or [])
    exp_ev = has_experience_section_evidence(text)

    def _complete_exp_count(rows: list) -> int:
        n = 0
        for e in rows:
            if isinstance(e, dict):
                role, company = str(e.get('role') or '').strip(), str(e.get('company') or '').strip()
            else:
                role, company = (getattr(e, 'role', '') or '').strip(), (getattr(e, 'company', '') or '').strip()
            if role and company:
                n += 1
        return n

    if exp_ev:
        section_body = _experience_section_text(text)
        parsed_exp = parse_experience(section_body, text) if section_body else []
        if parsed_exp:
            from app.ai.parser.enrichment.resume_text_inference import is_non_job_experience_record

            parsed_exp = [e for e in parsed_exp if not is_non_job_experience_record(e)]
        if not parsed_exp:
            from app.ai.parser.enrichment.resume_text_inference import (
                extract_experience_from_text,
                is_non_job_experience_record,
            )

            loose = extract_experience_from_text(text)
            parsed_exp = [
                ExperienceEntry(
                    company=str(e.get('company') or '')[:200],
                    role=str(e.get('title') or e.get('role') or '')[:200],
                    start=str(e.get('from') or e.get('start') or ''),
                    end=str(e.get('to') or e.get('end') or ''),
                    description=str(e.get('description') or '')[:2000],
                )
                for e in loose
                if isinstance(e, dict)
                and (
                    str(e.get('title') or e.get('role') or '').strip()
                    or str(e.get('company') or '').strip()
                )
                and not is_non_job_experience_record(e)
            ]
        parsed_complete = _complete_exp_count(parsed_exp)
        existing_complete = _complete_exp_count(exp_list)
        better = parsed_exp and (
            not exp_list
            or parsed_complete > existing_complete
            or (parsed_complete >= existing_complete and len(parsed_exp) > len(exp_list))
        )
        if better:
            data['experience'] = [e.model_dump() for e in parsed_exp]
            recovered.append('experience')
            from app.ai.document_intelligence.experience_quality import experience_is_incomplete

            if experience_is_incomplete(parsed_exp, text):
                fields.append(
                    FieldCoverage(
                        'experience', 'missing_with_evidence', True, f'{len(parsed_exp)} rows'
                    )
                )
            else:
                fields.append(
                    FieldCoverage('experience', 'recovered', True, f'{len(parsed_exp)} rows')
                )
        elif exp_list:
            from app.ai.document_intelligence.experience_quality import experience_is_incomplete

            if experience_is_incomplete(exp_list, text):
                fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
            else:
                fields.append(FieldCoverage('experience', 'filled', True))
        else:
            fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
    elif exp_list:
        from app.ai.document_intelligence.experience_quality import experience_is_incomplete

        if experience_is_incomplete(exp_list, text):
            fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('experience', 'filled', True))
    else:
        fields.append(FieldCoverage('experience', 'missing_no_evidence', False))

    report = CoverageReport(fields=fields)
    try:
        updated = CandidateProfile.model_validate(data)
    except Exception:
        return profile, report
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile

    return sanitize_candidate_profile(updated, source_text=text or ''), report


def resume_has_recoverable_gaps(profile: CandidateProfile, raw_text: str) -> bool:
    """True when contact/location/education/experience incomplete but source has evidence."""
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_name_from_text,
        is_plausible_person_name,
    )

    contact = profile.contact
    text = raw_text or ''
    name = (profile.personal.full_name or '').strip()
    if (not name or not is_plausible_person_name(name)) and extract_name_from_text(text[:2500]):
        return True
    if not (contact.email or '').strip() and _has_email_evidence(text):
        return True
    phone = (contact.phone or '').strip()
    if (not phone or not validate_phone(phone)[0]) and _has_phone_evidence(text):
        return True
    loc = (contact.location or '').strip()
    if (not loc or not _is_plausible_location(loc)) and _has_location_evidence(text):
        return True
    edu_ok = any(
        (e.degree or '').strip() and (e.institution or '').strip() for e in profile.education
    )
    if not edu_ok and _has_education_evidence(text):
        return True
    from app.ai.document_intelligence.experience_quality import experience_is_incomplete

    if experience_is_incomplete(profile.experience, text):
        return True
    return False
