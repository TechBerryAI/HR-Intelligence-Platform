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
from app.ai.document_intelligence.validation.engine import (
    is_keepable_education_form_row,
    validate_phone,
)

# VALIDATION_FIX_experience_section_evidence
_EXP_SECTION_RE = re.compile(
    r'(?im)^(?:\*\*)?(?:work\s*experience|professional\s*experience|technical\s+experience|'
    r'experience|'
    r'employment|work\s+history|career\s+history|internships?|internship\s+experience|'
    r'industrial\s+trainings?|summer\s+internship|internship\s*/\s*training|'
    r'management\s+internship|research\s+internship|graduate\s+internship|'
    r'training\s+experience|'
    r'trainings?|apprenticeships?)\b'
)


def has_experience_section_evidence(text: str) -> bool:
    """True when a Work/Internship/Experience section header exists in source.

    'Work experience = fresher' and 'Total Experience: 4.7 Years' are not job sections.
    """
    from app.ai.parser.enrichment.resume_text_inference import (
        is_fresher_or_years_only_experience_line,
    )

    for m in _EXP_SECTION_RE.finditer(text or ''):
        line_start = (text or '').rfind('\n', 0, m.start()) + 1
        line_end = (text or '').find('\n', m.start())
        line = (text or '')[line_start: line_end if line_end != -1 else None]
        if is_fresher_or_years_only_experience_line(line):
            continue
        return True
    return False


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
        r'technical\s+experience|experience|employment|work\s+history|internships?|'
        r'internship\s+experience|'
        r'industrial\s+trainings?|summer\s+internship|internship\s*/\s*training[^\n]*|'
        r'trainings?|apprenticeships?)\b[^\n]*\n'
        r'(.*?)(?=\n\s*(?:\*\*)?(?:education|academic|skills|skill\s*sets?|'
        r'technical\s+skills?|technical\s+proficiency|technical\s+expertise|'
        r'technical\s+knowledge|projects?|certifications?|personal\s+details|'
        r'personal\s+information|personalinformation|biodata|declaration|'
        r'hobbies|areas?\s+of\s+strength)(?:\*\*)?\s*:?\s*$|\Z)',
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
    name_ev = bool(extract_name_from_text(text) if text else '')
    if full_name and is_plausible_person_name(full_name):
        fields.append(FieldCoverage('fullName', 'filled', True))
    elif name_ev:
        found = extract_name_from_text(text)
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
            if is_keepable_education_form_row(e.degree, e.institution)
        ]
        if grounded and not edu_list:
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

    # Experience: same parser only; fill empty fields — never replace anchored rows
    exp_list = list(data.get('experience') or [])
    exp_ev = has_experience_section_evidence(text)
    from app.ai.document_intelligence.experience_quality import (
        experience_is_incomplete,
        merge_experience_field_level,
        row_is_anchored,
    )

    if exp_ev:
        section_body = _experience_section_text(text)
        parsed_exp = parse_experience(section_body, text) if section_body else []
        if not parsed_exp:
            from app.ai.document_intelligence.parsers.resume import (
                _structural_employment_window,
            )

            window = _structural_employment_window(text)
            if window:
                parsed_exp = parse_experience('Experience\n' + window, text)
        if parsed_exp:
            from app.ai.parser.enrichment.resume_text_inference import (
                has_credible_employment_evidence,
                is_non_job_experience_record,
            )

            parsed_exp = [
                e
                for e in parsed_exp
                if not is_non_job_experience_record(e) and has_credible_employment_evidence(e)
            ]
        existing_rows = [
            ExperienceEntry.model_validate(e) if isinstance(e, dict) else e
            for e in exp_list
        ]
        if existing_rows and any(row_is_anchored(e) for e in existing_rows):
            merged = merge_experience_field_level(existing_rows, parsed_exp)
            if merged != existing_rows:
                data['experience'] = [e.model_dump() for e in merged]
                recovered.append('experience')
            fields.append(
                FieldCoverage(
                    'experience',
                    'missing_with_evidence' if experience_is_incomplete(merged, text) else 'filled',
                    True,
                )
            )
        elif not existing_rows and parsed_exp:
            data['experience'] = [e.model_dump() for e in parsed_exp]
            recovered.append('experience')
            fields.append(
                FieldCoverage(
                    'experience',
                    'missing_with_evidence'
                    if experience_is_incomplete(parsed_exp, text)
                    else 'recovered',
                    True,
                    f'{len(parsed_exp)} rows',
                )
            )
        elif existing_rows:
            fields.append(
                FieldCoverage(
                    'experience',
                    'missing_with_evidence' if experience_is_incomplete(existing_rows, text) else 'filled',
                    True,
                )
            )
        else:
            fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
    elif exp_list:
        if experience_is_incomplete(exp_list, text):
            fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
        else:
            fields.append(FieldCoverage('experience', 'filled', True))
    else:
        fields.append(FieldCoverage('experience', 'missing_no_evidence', False))

    # Skills: never harvest the full document when a Skills section already produced items
    skills = list(data.get('skills') or [])
    has_skills_heading = bool(
        re.search(
            r'(?im)^(?:\*\*)?(?:(?:technical|key|core|soft)\s+)?skills?\b|'
            r'^technical\s+(?:proficiency|expertise|knowledge)\b',
            text or '',
        )
    )
    if not skills and not has_skills_heading:
        from app.ai.document_intelligence.validation.engine import validate_skill_item
        from app.ai.parser.enrichment.resume_text_inference import extract_skills_from_text

        added = []
        for item in extract_skills_from_text(text, allow_unlabeled_lists=False):
            if not validate_skill_item(item)[0]:
                continue
            added.append({'name': item, 'canonical': item, 'category': ''})
            if len(added) >= 40:
                break
        if added:
            data['skills'] = added
            recovered.append('skills')
            fields.append(FieldCoverage('skills', 'recovered', True, f'{len(added)} items'))

    meta = dict(data.get('field_meta') or {})
    prov = dict(meta.get('_field_provenance') or {})
    try:
        from app.ai.parser.engine.confidence import provenance_outranks
    except Exception:
        provenance_outranks = None  # type: ignore[assignment]
    _RECOVER_PATH = {
        'fullName': 'personal.full_name',
        'education': 'education',
        'experience': 'experience',
        'skills': 'skills',
    }
    for key in recovered:
        path = _RECOVER_PATH.get(key)
        if not path:
            continue
        src = 'document_wide_recovery'
        existing = prov.get(path, '')
        if provenance_outranks is None or provenance_outranks(src, existing):
            prov[path] = src
    meta['_field_provenance'] = prov
    data['field_meta'] = meta

    report = CoverageReport(fields=fields)
    try:
        updated = CandidateProfile.model_validate(data)
    except Exception:
        return profile, report
    from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile

    return sanitize_candidate_profile(updated, source_text=text or ''), report


def assess_resume_coverage(profile: CandidateProfile, raw_text: str) -> CoverageReport:
    """Report completeness from the current profile. Does not mutate fields."""
    text = raw_text or ''
    fields: list[FieldCoverage] = []
    from app.ai.document_intelligence.experience_quality import experience_is_incomplete
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_person_name

    from app.ai.parser.enrichment.resume_text_inference import extract_name_from_text

    name = (profile.personal.full_name or '').strip()
    if name and is_plausible_person_name(name):
        fields.append(FieldCoverage('fullName', 'filled', True))
    elif extract_name_from_text(text):
        fields.append(FieldCoverage('fullName', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('fullName', 'missing_no_evidence', bool(name)))

    email = (profile.contact.email or '').strip()
    if email:
        fields.append(FieldCoverage('email', 'filled', True))
    elif _has_email_evidence(text):
        fields.append(FieldCoverage('email', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('email', 'missing_no_evidence', False))

    phone = (profile.contact.phone or '').strip()
    if phone:
        fields.append(FieldCoverage('phone', 'filled', True))
    elif _has_phone_evidence(text):
        fields.append(FieldCoverage('phone', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('phone', 'missing_no_evidence', False))

    loc = (profile.contact.location or '').strip()
    if loc and _is_plausible_location(loc):
        fields.append(FieldCoverage('location', 'filled', True))
    elif _has_location_evidence(text):
        fields.append(FieldCoverage('location', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('location', 'missing_no_evidence', False))

    edu_ok = any((e.degree or '').strip() and (e.institution or '').strip() for e in profile.education)
    if edu_ok:
        fields.append(FieldCoverage('education', 'filled', True))
    elif _has_education_evidence(text):
        fields.append(FieldCoverage('education', 'missing_with_evidence', True))
    else:
        fields.append(FieldCoverage('education', 'missing_no_evidence', False))

    if profile.experience and not experience_is_incomplete(profile.experience, text):
        fields.append(FieldCoverage('experience', 'filled', True))
    elif has_experience_section_evidence(text):
        fields.append(FieldCoverage('experience', 'missing_with_evidence', True))
    elif profile.experience:
        fields.append(FieldCoverage('experience', 'filled', True))
    else:
        fields.append(FieldCoverage('experience', 'missing_no_evidence', False))

    return CoverageReport(fields=fields)


def resume_has_recoverable_gaps(profile: CandidateProfile, raw_text: str) -> bool:
    """True when contact/location/education/experience incomplete but source has evidence."""
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_name_from_text,
        is_plausible_person_name,
    )

    contact = profile.contact
    text = raw_text or ''
    name = (profile.personal.full_name or '').strip()
    if (not name or not is_plausible_person_name(name)) and extract_name_from_text(text):
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
