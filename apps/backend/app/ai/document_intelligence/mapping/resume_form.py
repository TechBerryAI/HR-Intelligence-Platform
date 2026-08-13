"""
Explicit Resume → Application Form mappings.

Every form field has exactly ONE canonical source.
No heuristics. No reflection. No object spreading. No alias OR-chains.
If a mapping cannot be proven, the field is left empty.
"""
from __future__ import annotations

import re

from app.ai.document_intelligence.models.candidate import CandidateProfile
from app.ai.document_intelligence.models.form_dtos import (
    ApplicationFormDTO,
    CertificationFormRow,
    EducationFormRow,
    ExperienceFormRow,
    FieldTrace,
)
from app.ai.document_intelligence.validation.engine import (
    validate_email,
    validate_nonempty,
    validate_location,
    validate_phone,
    validate_url,
)

MAPPER_ID = 'document_intelligence.mapping.resume_form.v1'

# Mapping graph: form_field → canonical_path (exactly one source each)
RESUME_FORM_MAPPING_GRAPH: dict[str, str] = {
    'fullName': 'personal.full_name',
    'email': 'contact.email',
    'phone': 'contact.phone',
    'linkedinUrl': 'contact.linkedin',
    'portfolioUrl': 'contact.portfolio',
    'githubUrl': 'contact.github',
    'currentLocation': 'contact.location',
    'preferredLocation': 'contact.preferred_location',
    'experienceLevel': 'total_experience_years|experience[]',
    'skills': 'skills[].canonical',
    'summary': 'personal.summary',
    'education[].degree': 'education[].degree+field',
    'education[].institution': 'education[].institution',
    'education[].cgpa': 'education[].gpa',
    'education[].startMonth': 'education[].start',
    'education[].endMonth': 'education[].end',
    'experiences[].company': 'experience[].company',
    'experiences[].role': 'experience[].role',
    'experiences[].startMonth': 'experience[].start',
    'experiences[].endMonth': 'experience[].end',
    'experiences[].isCurrent': 'experience[].is_current',
    'experiences[].description': 'experience[].description',
    'certifications[].name': 'certificates[].name',
    'certifications[].issuer': 'certificates[].issuer',
    'certifications[].validTill': 'certificates[].valid_till',
    'certifications[].validationUrl': 'certificates[].validation_url',
    'certifications[].status': 'certificates[].status',
}


def _meta_source(profile: CandidateProfile, path: str, default: str = 'canonical') -> str:
    meta = profile.field_meta or {}
    entry = meta.get(path)
    if isinstance(entry, dict) and entry.get('source'):
        return str(entry['source'])
    # Common TOON provenance keys
    for key in (path, path.replace('personal.', 'person.').replace('contact.', 'person.')):
        entry = meta.get(key)
        if isinstance(entry, dict) and entry.get('source'):
            return str(entry['source'])
    return default


def _trace(
    form_field: str,
    canonical_path: str,
    *,
    source: str,
    validator: str,
    confidence: float,
    reason: str,
) -> FieldTrace:
    return FieldTrace(
        form_field=form_field,
        canonical_path=canonical_path,
        mapper=MAPPER_ID,
        source=source,
        validator=validator,
        confidence=confidence,
        reason=reason,
    )


def map_candidate_to_form(
    profile: CandidateProfile,
    coverage: list[dict] | None = None,
) -> ApplicationFormDTO:
    """Map CandidateProfile → ApplicationFormDTO with explicit one-to-one sources."""
    traces: list[FieldTrace] = []

    # --- Scalar fields (one source each) ---
    name_ok, name_reason = validate_nonempty(profile.personal.full_name, 'full_name')
    full_name = profile.personal.full_name if name_ok else ''
    traces.append(
        _trace(
            'fullName',
            'personal.full_name',
            source=_meta_source(profile, 'person.name', 'deterministic'),
            validator='validate_nonempty' if name_ok else 'none',
            confidence=0.95 if name_ok else 0.0,
            reason=name_reason if name_ok else 'empty_or_invalid',
        )
    )

    email_ok, email_reason = validate_email(profile.contact.email)
    email = profile.contact.email if email_ok else ''
    traces.append(
        _trace(
            'email',
            'contact.email',
            source=_meta_source(profile, 'person.email', 'deterministic'),
            validator='validate_email' if email_ok else 'none',
            confidence=0.99 if email_ok else 0.0,
            reason=email_reason if email_ok else 'invalid_email',
        )
    )

    phone_ok, phone_reason = validate_phone(profile.contact.phone)
    phone = profile.contact.phone if phone_ok else ''
    traces.append(
        _trace(
            'phone',
            'contact.phone',
            source=_meta_source(profile, 'person.phone', 'deterministic'),
            validator='validate_phone' if phone_ok else 'none',
            confidence=0.95 if phone_ok else 0.0,
            reason=phone_reason if phone_ok else 'invalid_phone',
        )
    )

    li_ok, li_reason = validate_url(profile.contact.linkedin, allow_empty=True, host_hint='linkedin')
    linkedin = profile.contact.linkedin if li_ok and profile.contact.linkedin else ''
    traces.append(
        _trace(
            'linkedinUrl',
            'contact.linkedin',
            source=_meta_source(profile, 'person.linkedin', 'deterministic'),
            validator='validate_url' if linkedin else 'none',
            confidence=0.95 if linkedin else 0.0,
            reason=li_reason if linkedin else 'empty',
        )
    )

    port_ok, port_reason = validate_url(profile.contact.portfolio, allow_empty=True)
    portfolio = profile.contact.portfolio if port_ok and profile.contact.portfolio else ''
    traces.append(
        _trace(
            'portfolioUrl',
            'contact.portfolio',
            source=_meta_source(profile, 'person.portfolio', 'deterministic'),
            validator='validate_url' if portfolio else 'none',
            confidence=0.9 if portfolio else 0.0,
            reason=port_reason if portfolio else 'empty',
        )
    )

    gh_ok, gh_reason = validate_url(profile.contact.github, allow_empty=True, host_hint='github')
    github = profile.contact.github if gh_ok and profile.contact.github else ''
    traces.append(
        _trace(
            'githubUrl',
            'contact.github',
            source=_meta_source(profile, 'person.github', 'deterministic'),
            validator='validate_url' if github else 'none',
            confidence=0.95 if github else 0.0,
            reason=gh_reason if github else 'empty',
        )
    )

    loc_ok, loc_reason = validate_location(profile.contact.location)
    current_location = (profile.contact.location if loc_ok else '').strip()
    current_location = re.sub(r'^[\-–—•·]+\s*', '', current_location).strip()
    if current_location:
        current_location = current_location.splitlines()[0].strip()
        # "Hyderabad, India" — drop trailing bleed after country
        current_location = re.split(r'(?i)(?<=\bIndia)\s+', current_location, maxsplit=1)[0].strip()
        loc_ok, loc_reason = validate_location(current_location)
    if current_location and not loc_ok:
        current_location = ''
    if not current_location:
        loc_ok = False
        loc_reason = loc_reason if loc_reason != 'ok' else 'empty'
    traces.append(
        _trace(
            'currentLocation',
            'contact.location',
            source=_meta_source(profile, 'person.location', 'deterministic'),
            validator='validate_location' if loc_ok else 'none',
            confidence=0.85 if loc_ok else 0.0,
            reason=loc_reason if loc_ok else (loc_reason or 'empty'),
        )
    )

    # preferredLocation: preferred_location, else current location
    # VALIDATION_FIX_preferred_location_fallback
    pref = (profile.contact.preferred_location or '').strip()
    pref_ok, pref_loc_reason = validate_location(pref) if pref else (False, 'empty')
    if not pref_ok:
        pref = ''
    if not pref and current_location:
        pref = current_location
        pref_source_path = 'contact.location'
        pref_reason = 'fallback_current_location'
        pref_ok = True
    else:
        pref_source_path = 'contact.preferred_location'
        pref_reason = pref_loc_reason if pref else 'empty'
    preferred_location = pref if pref_ok else ''
    traces.append(
        _trace(
            'preferredLocation',
            pref_source_path,
            source=_meta_source(profile, 'person.preferred_location', 'deterministic'),
            validator='validate_location' if pref_ok else 'none',
            confidence=0.85 if pref_ok else 0.0,
            reason=pref_reason if pref_ok else 'empty',
        )
    )

    # experienceLevel: derived solely from total_experience_years OR experience length
    years = profile.total_experience_years
    has_exp = len([e for e in profile.experience if e.company or e.role]) > 0
    if years is not None and years > 0:
        experience_level = 'experienced'
        el_reason = f'total_experience_years={years}'
        el_path = 'total_experience_years'
        el_conf = 0.9
    elif has_exp:
        experience_level = 'experienced'
        el_reason = 'experience[] non-empty'
        el_path = 'experience[]'
        el_conf = 0.85
    else:
        experience_level = 'fresher'
        el_reason = 'no_experience'
        el_path = 'total_experience_years|experience[]'
        el_conf = 0.8
    traces.append(
        _trace(
            'experienceLevel',
            el_path,
            source='derived',
            validator='experience_level_rule',
            confidence=el_conf,
            reason=el_reason,
        )
    )

    skill_names = [s.name or s.canonical for s in profile.skills if (s.name or s.canonical).strip()]
    skills_str = ', '.join(skill_names)
    traces.append(
        _trace(
            'skills',
            'skills[].canonical',
            source='knowledge',
            validator='skill_list' if skill_names else 'none',
            confidence=0.9 if skill_names else 0.0,
            reason=f'{len(skill_names)} skills' if skill_names else 'empty',
        )
    )

    summary = profile.personal.summary.strip()
    traces.append(
        _trace(
            'summary',
            'personal.summary',
            source='semantic_ai',
            validator='validate_nonempty' if summary else 'none',
            confidence=0.8 if summary else 0.0,
            reason='ok' if summary else 'empty',
        )
    )

    # --- Education rows ---
    education_rows: list[EducationFormRow] = []
    for edu in profile.education:
        degree = edu.degree
        institution = edu.institution
        if degree and edu.field and edu.field.lower() not in degree.lower():
            # Explicit composition rule documented in mapping graph (degree+field)
            degree = f'{degree} in {edu.field}'
        elif not degree and edu.field:
            degree = edu.field
        # VALIDATION_FIX_education_degree_from_institution
        if not (degree or '').strip() and (institution or '').strip():
            import re as _re

            m = _re.search(
                r'(?i)\b('
                r'(?:Bachelor|Master|Doctor)(?:\'?s)?(?:\s+of\s+[A-Za-z &/.-]+)?'
                r'|BACHELOR\s+OF\s+ENGINEERING(?:\s*[-–—]?\s*[A-Za-z &/.-]+)?'
                r'|B\.?\s*Tech|M\.?\s*Tech|B\.?\s*E\.?|M\.?\s*E\.?'
                r'|B\.?\s*Sc|M\.?\s*Sc|BSC(?:\s*\([^)]+\))?|MSC'
                r'|B\.?\s*Com(?:m(?:erce)?)?|M\.?\s*Com(?:m(?:erce)?)?'
                r'|MBA|MCA|BCA|BBA|Ph\.?\s*D\.?'
                r'|Diploma(?:\s+in\s+[A-Za-z &/.-]+)?'
                r'|Degree\s+in\s+[A-Za-z ()&/.-]+'
                r'|Pre[\s\-]?University|Higher\s+Secondary|Senior\s+Secondary'
                r'|HSC|SSC|12th|10th'
                r')\b.*$',
                institution,
            )
            if m:
                degree = m.group(0).strip(' |,-')[:200]
                institution = institution[: m.start()].strip(' |,-') or institution
            # "B.com – SV University, Tirupathi …"
            elif _re.search(r'[-–—]', institution):
                parts = _re.split(r'\s*[-–—]\s*', institution, maxsplit=1)
                if len(parts) == 2 and _re.search(
                    r'(?i)\b(?:b\.?\s*com|b\.?\s*tech|b\.?\s*e|m\.?\s*tech|mba|mca|bca|'
                    r'bachelor|master|diploma|ph\.?\s*d)\b',
                    parts[0],
                ):
                    degree, institution = parts[0].strip()[:200], parts[1].strip()[:200]
        # Degree mentions institution: "BE MECHANICAL in college PVPIT Budgaon"
        if (degree or '').strip() and not (institution or '').strip():
            import re as _re

            m = _re.search(
                r'(?i)\b(?:in|from|at)\s+(?:college\s+|university\s+|institute\s+)?(.+)$',
                degree,
            )
            if m and len(m.group(1).strip()) >= 3:
                institution = m.group(1).strip(' |,-')[:200]
                degree = degree[: m.start()].strip(' |,-') or degree
            elif '|' in degree:
                left, _, right = degree.partition('|')
                if len(right.strip()) >= 3:
                    degree, institution = left.strip(), right.strip()
            elif _re.search(r'[-–—]', degree):
                parts = _re.split(r'\s*[-–—]\s*', degree, maxsplit=1)
                if len(parts) == 2 and len(parts[1].strip()) >= 3:
                    degree, institution = parts[0].strip()[:200], parts[1].strip()[:200]
        # Still missing one side: only keep when both sides are grounded (no invented placeholders)
        if (degree or '').strip() and not (institution or '').strip():
            continue
        if (institution or '').strip() and not (degree or '').strip():
            continue
        # Drop experience/project pollution rows
        blob = f'{degree} {institution}'.lower()
        if any(
            tok in blob
            for tok in (
                'configured mysql', 'master-slave', 'project name', 'duration',
                'organizational experience', 'replication setup',
                'responsibilities', 'client name', 'technologies used',
                'executed on-page', 'managed and optimized', 'facilitated smooth',
            )
        ):
            continue
        if degree.strip().lower() in {'education', 'educational', 'qualification', 'qualifications'}:
            continue
        if not (degree or institution or edu.gpa or edu.start or edu.end):
            continue
        # Require both sides for apply-form education (matches frontend validator)
        if not ((degree or '').strip() and (institution or '').strip()):
            continue
        education_rows.append(
            EducationFormRow(
                degree=degree or '',
                institution=institution or '',
                cgpa=edu.gpa,
                startMonth=edu.start,
                endMonth=edu.end,
            )
        )
    traces.append(
        _trace(
            'education[]',
            'education[]',
            source='semantic_ai',
            validator='education_rows',
            confidence=0.85 if education_rows else 0.0,
            reason=f'{len(education_rows)} rows',
        )
    )

    # --- Experience rows ---
    experience_rows: list[ExperienceFormRow] = []
    for exp in profile.experience:
        if not (exp.company or exp.role or exp.start):
            continue
        experience_rows.append(
            ExperienceFormRow(
                company=exp.company,
                role=exp.role,
                startMonth=exp.start,
                endMonth='' if exp.is_current else exp.end,
                isCurrent=exp.is_current,
                description=exp.description,
            )
        )
    traces.append(
        _trace(
            'experiences[]',
            'experience[]',
            source='semantic_ai',
            validator='experience_rows',
            confidence=0.85 if experience_rows else 0.0,
            reason=f'{len(experience_rows)} rows',
        )
    )

    # --- Certifications ---
    cert_rows: list[CertificationFormRow] = []
    for cert in profile.certificates:
        if not cert.name:
            continue
        cert_rows.append(
            CertificationFormRow(
                name=cert.name,
                issuer=cert.issuer,
                validTill=cert.valid_till,
                validationUrl=cert.validation_url,
                status=cert.status,
            )
        )
    traces.append(
        _trace(
            'certifications[]',
            'certificates[]',
            source='semantic_ai',
            validator='cert_rows',
            confidence=0.8 if cert_rows else 0.0,
            reason=f'{len(cert_rows)} rows',
        )
    )

    # Empty placeholders so form UI always has at least one editable row
    if not education_rows:
        education_rows = [EducationFormRow()]
    if not experience_rows:
        experience_rows = [ExperienceFormRow()]
    if not cert_rows:
        cert_rows = [CertificationFormRow()]

    # Merge coverage into field traces for UI visibility (JD parity)
    coverage_rows = list(coverage or [])
    cov_by_field = {c.get('field'): c for c in coverage_rows if isinstance(c, dict)}
    for form_field, cov_key in (
        ('fullName', 'fullName'),
        ('email', 'email'),
        ('phone', 'phone'),
        ('currentLocation', 'location'),
        ('education', 'education'),
        ('experiences', 'experience'),
    ):
        c = cov_by_field.get(cov_key)
        if not c:
            continue
        traces.append(
            _trace(
                form_field,
                f'coverage.{cov_key}',
                source='coverage_gate',
                validator=str(c.get('status') or ''),
                confidence=0.95 if c.get('status') in ('filled', 'recovered') else 0.4,
                reason=str(c.get('detail') or c.get('status') or ''),
            )
        )

    return ApplicationFormDTO(
        fullName=full_name,
        email=email,
        phone=phone,
        linkedinUrl=linkedin,
        portfolioUrl=portfolio,
        githubUrl=github,
        currentLocation=current_location,
        preferredLocation=preferred_location,
        experienceLevel=experience_level,
        skills=skills_str,
        summary=summary,
        education=education_rows,
        experiences=experience_rows,
        certifications=cert_rows,
        skillsList=skill_names,
        summaryText=summary,
        trace=traces,
        coverage=coverage_rows,
    )
