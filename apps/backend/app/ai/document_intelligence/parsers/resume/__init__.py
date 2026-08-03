"""Resume section parsers — each emits canonical fragments only."""
from __future__ import annotations

import re
from typing import Any

from app.ai.document_intelligence.deterministic import (
    extract_date_range,
    extract_email,
    extract_github,
    extract_linkedin,
    extract_phone,
    extract_portfolio,
    extract_simple_location,
    normalize_month_token,
)
from app.ai.document_intelligence.models.candidate import (
    CandidateProfile,
    CertificateEntry,
    ContactInfo,
    EducationEntry,
    ExperienceEntry,
    LanguageEntry,
    PersonalInfo,
    ProjectEntry,
    SkillEntry,
)
from app.ai.document_intelligence.sections import SectionSpan, pick_section
from app.ai.document_intelligence.validation.engine import (
    sanitize_candidate_profile,
    validate_person_name,
    validate_skill_item,
)
from app.ai.parser.enrichment.resume_text_inference import (
    compute_total_experience_years,
    extract_name_from_text,
    extract_summary_from_text,
    filter_skill_items,
    is_institution_like,
    is_plausible_job_title,
    is_plausible_person_name,
    is_section_header_line,
    split_list_items,
)

_PIPE_EXP = re.compile(
    r'^(.+?)\s*[|–—]\s*(.+?)\s*[|–—]\s*(.+)$'
)
_AT_EXP = re.compile(r'^(.+?)\s+(?:at|@)\s+(.+)$', re.I)
_DEGREE_PAT = re.compile(
    r'(?i)\b('
    r'Masters?(?:\s+of)?(?:\s+Arts|\s+Science|\s+Commerce|\s+Business|\s+Technology)?'
    r'(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|Bachelors?(?:\s+of)?(?:\s+Arts|\s+Science|\s+Commerce|\s+Mass\s+Media|\s+Technology|\s+Engineering)?'
    r'(?:\s*[-–—]?\s*[A-Za-z &\-/]+)?'
    r'|Master(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?'
    r'|Bachelor(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?'
    r'|Associate(?:\'?s)?(?:\s+(?:of|in|degree)\s+[A-Za-z &\-/]+)?'
    r'|B\.?\s?Tech(?:\s+[A-Za-z &\-/]+)?|B\.?\s?E\.?(?![a-z])|'
    r'M\.?\s?Tech|M\.?\s?S\.?(?![a-z])|M\.?\s?B\.?\s?A\.?(?![a-z])|'
    r'M\.?\s?A\.?(?![a-z])|B\.?\s?A\.?(?![a-z])|'
    r'Ph\.?\s?D\.?(?![a-z])|Diploma(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|(?:1[0-2](?:th|st|nd|rd)?|10th|12th)\s+Passed(?:\s+in\s+[A-Za-z &\-/]+)?'
    r')\b'
)
_INSTITUTION_CUE = re.compile(
    r'(?i)\b(?:university|college|school|institute|academy|vidyalaya|'
    r'polytechnic|iit|nit|iiit|somaiya|association)\b'
)
_DATE_RANGE_STRIP = re.compile(
    r'(?i)\b(?:'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}'
    r')\s*(?:[-–—]|to)\s*'
    r'(?:'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}|Present|Current|Now'
    r')\b'
)
_PROJECT_LIKE_EXP = re.compile(
    r'(?i)\b(?:assignment|coursera|project|internship\s+project|fictional\s+brand)\b'
)


def _looks_like_degree_line(line: str) -> bool:
    s = (line or '').strip()
    if not s or len(s) > 200:
        return False
    if _DEGREE_PAT.search(s):
        return True
    if re.match(r'(?i)^(masters?|bachelors?|diploma|phd|m\.?a\.?|b\.?a\.?|b\.?tech)\b', s):
        return True
    if re.match(r'(?i)^(1[0-2](?:th)?|10th|12th)\s+passed\b', s):
        return True
    return False


def _looks_like_institution_line(line: str) -> bool:
    s = (line or '').strip()
    if not s or len(s) < 4:
        return False
    if _looks_like_degree_line(s) and not _INSTITUTION_CUE.search(s):
        return False
    if _INSTITUTION_CUE.search(s) or is_institution_like(s):
        return True
    if re.search(r'[-–—]\s*[A-Za-z].{2,40}$', s) and extract_date_range(s)[0]:
        return True
    return False


def _is_education_continuation(prev: str, nxt: str) -> bool:
    """True when nxt is a PDF wrap continuation of the previous institution line."""
    n = (nxt or '').strip()
    p = (prev or '').strip()
    if not n or not p:
        return False
    if _looks_like_degree_line(n) or _looks_like_degree_line(p):
        return False
    # Strong new-institution cue: full line with college/university and no wrap feel
    if (
        _INSTITUTION_CUE.search(n)
        and n[0].isupper()
        and len(n) > 25
        and not extract_date_range(n)[0]
        and not p.rstrip().endswith(('Higher', 'of', 'and', 'the', 'College', 'School'))
    ):
        return False
    # Lowercase start / mid-word wrap
    if n[0].islower():
        return True
    # Previous line looks truncated / incomplete institution
    p_wo = _DATE_RANGE_STRIP.sub('', p).strip(' \t|-–—,')
    if (
        p_wo
        and not extract_date_range(p)[0]
        and (
            p_wo.endswith(('Higher', 'of', 'and', 'the', '-', '–', '—'))
            or (len(p_wo) < 40 and _looks_like_institution_line(p_wo))
            or (len(p_wo) >= 8 and p_wo[-1:].islower() and _looks_like_institution_line(p_wo))
        )
        and not _looks_like_degree_line(n)
    ):
        # Next is leftover city/dates or remainder of institution name
        if extract_date_range(n)[0] or _INSTITUTION_CUE.search(n) or len(n) <= 50:
            return True
    # Short city+dates fragment alone
    if len(n) <= 40 and extract_date_range(n)[0] and not _looks_like_degree_line(n):
        # Only join onto institution-like previous, not onto degrees (already excluded)
        if _looks_like_institution_line(p_wo) or (p_wo and not _looks_like_degree_line(p)):
            return True
    if len(n) <= 20 and not _looks_like_degree_line(n) and _looks_like_institution_line(p_wo or p):
        return True
    return False


def _join_wrapped_education_lines(lines: list[str]) -> list[str]:
    if not lines:
        return []
    out: list[str] = [lines[0]]
    for nxt in lines[1:]:
        prev = out[-1]
        if _is_education_continuation(prev, nxt):
            # Join wrap without introducing double spaces awkwardly
            if prev.endswith('-') or nxt.startswith('-'):
                out[-1] = f'{prev.rstrip()} {nxt.lstrip()}'.strip()
            else:
                out[-1] = f'{prev.rstrip()} {nxt.lstrip()}'.strip()
        else:
            out.append(nxt)
    return out


def coalesce_education(rows: list[EducationEntry]) -> list[EducationEntry]:
    """
    Merge orphan institution-only + degree-only pairs (and reverse).
    Prefer dates from whichever side has them.
    """
    if not rows:
        return []
    merged: list[EducationEntry] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        cur_inst = (cur.institution or '').strip()
        cur_deg = (cur.degree or '').strip()
        if nxt:
            n_inst = (nxt.institution or '').strip()
            n_deg = (nxt.degree or '').strip()
            # institution-only + degree-only
            if cur_inst and not cur_deg and n_deg and not n_inst:
                merged.append(
                    EducationEntry(
                        degree=n_deg[:200],
                        field=cur.field or nxt.field,
                        institution=cur_inst[:200],
                        gpa=cur.gpa or nxt.gpa,
                        start=cur.start or nxt.start,
                        end=cur.end or nxt.end,
                    )
                )
                i += 2
                continue
            # degree-only + institution-only
            if cur_deg and not cur_inst and n_inst and not n_deg:
                merged.append(
                    EducationEntry(
                        degree=cur_deg[:200],
                        field=cur.field or nxt.field,
                        institution=n_inst[:200],
                        gpa=cur.gpa or nxt.gpa,
                        start=cur.start or nxt.start,
                        end=cur.end or nxt.end,
                    )
                )
                i += 2
                continue
            # truncated institution + continuation institution with dates, then degree handled next loop
            if (
                cur_inst
                and not cur_deg
                and n_inst
                and not n_deg
                and (n_inst[0].islower() or len(n_inst) < 30)
            ):
                combined = f'{cur_inst} {n_inst}'.strip()
                start = cur.start or nxt.start
                end = cur.end or nxt.end
                # Peek third for degree
                if i + 2 < len(rows):
                    third = rows[i + 2]
                    t_deg = (third.degree or '').strip()
                    t_inst = (third.institution or '').strip()
                    if t_deg and not t_inst:
                        merged.append(
                            EducationEntry(
                                degree=t_deg[:200],
                                field=third.field or cur.field,
                                institution=combined[:200],
                                start=start or third.start,
                                end=end or third.end,
                            )
                        )
                        i += 3
                        continue
                merged.append(
                    EducationEntry(
                        degree='',
                        institution=combined[:200],
                        start=start,
                        end=end,
                    )
                )
                i += 2
                continue
        if cur_inst or cur_deg:
            merged.append(cur)
        i += 1
    return merged


def parse_education(section_text: str, full_text: str = '') -> list[EducationEntry]:
    """
    Parse education as multi-line blocks (institution + degree).
    Never split a single institution name on internal commas.
    Coalesces PDF-wrap orphans into complete rows.
    """
    raw = section_text.strip()
    if not raw and full_text:
        m = re.search(
            r'(?i)(?:^|\n)\s*(?:\*\*)?education(?:\*\*)?\s*:?\s*'
            r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|skills|projects?|certifications?|'
            r'languages?|awards?|declaration)\b|\Z)',
            full_text,
        )
        raw = (m.group(1) if m else '').strip()
        if not raw:
            from app.ai.parser.enrichment.resume_text_inference import extract_education_from_text

            out = []
            for e in extract_education_from_text(full_text):
                year = str(e.get('year') or e.get('to') or '')
                out.append(
                    EducationEntry(
                        degree=str(e.get('degree') or ''),
                        field=str(e.get('field') or ''),
                        institution=str(e.get('institution') or ''),
                        gpa=str(e.get('gpa') or ''),
                        start=normalize_month_token(str(e.get('from') or '')),
                        end=normalize_month_token(year),
                    )
                )
            return coalesce_education(out)

    lines = []
    for line in raw.splitlines():
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not stripped or is_section_header_line(stripped):
            continue
        lines.append(stripped)
    lines = _join_wrapped_education_lines(lines)

    education: list[EducationEntry] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        start, end = extract_date_range(line)
        line_wo_dates = _DATE_RANGE_STRIP.sub('', line).strip(' \t|-–—,') if start else line

        institution = ''
        degree = ''
        field = ''

        if _looks_like_institution_line(line_wo_dates) or (
            start and not _looks_like_degree_line(line_wo_dates)
        ):
            institution = line_wo_dates.strip()
            # Consume wrap continuations already joined; still peek for degree
            if i + 1 < len(lines) and _looks_like_degree_line(lines[i + 1]):
                degree = lines[i + 1].strip()
                d_start, d_end = extract_date_range(lines[i + 1])
                if not start and d_start:
                    start, end = d_start, d_end
                i += 2
            else:
                i += 1
        elif _looks_like_degree_line(line_wo_dates):
            degree = line_wo_dates.strip()
            i += 1
        else:
            if _DEGREE_PAT.search(line_wo_dates):
                degree = line_wo_dates
            elif _INSTITUTION_CUE.search(line_wo_dates):
                institution = line_wo_dates
            i += 1
            if not degree and not institution:
                continue

        if 'Computer Science' in (degree + ' ' + institution):
            field = 'Computer Science'

        # Gold one-liner: "B.Tech Computer Science, State University, 2015"
        if degree and not institution and ',' in degree:
            parts = [p.strip() for p in degree.split(',') if p.strip()]
            non_year = [p for p in parts if not re.fullmatch(r'(?:19|20)\d{2}', p)]
            if len(non_year) >= 2 and (
                is_institution_like(non_year[-1])
                or 'university' in non_year[-1].lower()
                or 'college' in non_year[-1].lower()
                or 'state' in non_year[-1].lower()
            ):
                institution = non_year[-1]
                degree = ', '.join(non_year[:-1])
                if not end:
                    ym = re.search(r'\b((?:19|20)\d{2})\b', ','.join(parts))
                    if ym:
                        end = ym.group(1)

        if degree or institution:
            education.append(
                EducationEntry(
                    degree=degree[:200],
                    field=field,
                    institution=institution[:200],
                    start=start,
                    end=end,
                )
            )
    return coalesce_education(education)


def parse_skills(section_text: str, full_text: str = '') -> list[SkillEntry]:
    raw = section_text.strip()
    raw = re.sub(
        r'(?i)^(?:technical\s+)?skills?(?:\s+and\s+abilities)?\s*:?\s*',
        '',
        raw,
    ).strip()
    if not raw and full_text:
        from app.ai.parser.enrichment.resume_text_inference import extract_skills_from_text

        return [SkillEntry(name=s, canonical=s) for s in extract_skills_from_text(full_text)]
    items = filter_skill_items(split_list_items(raw), max_items=40)
    out: list[SkillEntry] = []
    for s in items:
        ok, _ = validate_skill_item(s)
        if ok:
            out.append(SkillEntry(name=s, canonical=s))
    return out


def parse_personal(text: str, preamble: str) -> PersonalInfo:
    src = preamble or text
    name = extract_name_from_text(src)
    if name and not is_plausible_person_name(name):
        name = ''
    ok, _ = validate_person_name(name) if name else (False, '')
    summary = extract_summary_from_text(text)
    return PersonalInfo(full_name=name if ok else '', summary=summary)


def parse_contact(text: str, preamble: str) -> ContactInfo:
    src = f'{preamble}\n{text}' if preamble else text
    return ContactInfo(
        email=extract_email(src),
        phone=extract_phone(src),
        location=extract_simple_location(src),
        preferred_location='',
        linkedin=extract_linkedin(src),
        github=extract_github(src),
        portfolio=extract_portfolio(src),
    )


def _is_project_like_experience(role: str, company: str = '', description: str = '') -> bool:
    blob = f'{role} {company} {description}'.strip()
    return bool(blob and _PROJECT_LIKE_EXP.search(blob))


def _parse_experience_line(line: str) -> ExperienceEntry | None:
    stripped = re.sub(r'^[\s•·\-\*]+', '', (line or '').strip())
    if not stripped or is_section_header_line(stripped) or len(stripped) < 3:
        return None
    if _is_project_like_experience(stripped):
        return None
    start, end = extract_date_range(stripped)
    is_current = bool(end and re.match(r'(?i)^(present|current|now)$', end))
    if is_current:
        end = ''

    # Gold / common: Role | Company | Dates
    pipe = _PIPE_EXP.match(stripped)
    if pipe:
        role = pipe.group(1).strip()
        company = pipe.group(2).strip()
        # group3 may be dates already extracted
        if not start:
            start, end2 = extract_date_range(pipe.group(3))
            if end2:
                is_current = bool(re.match(r'(?i)^(present|current|now)$', end2))
                end = '' if is_current else end2
        if role and (is_plausible_job_title(role) or len(role.split()) <= 8):
            return ExperienceEntry(
                company=company,
                role=role,
                start=start,
                end=end,
                is_current=is_current,
            )

    # Role at Company
    line_wo = stripped
    if start:
        line_wo = re.sub(
            r'(?i)\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
            r'\s*[-–—to]+\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}|Present|Current|Now)\b',
            '',
            stripped,
        ).strip(' |-–—,')
    at_m = _AT_EXP.match(line_wo)
    if at_m:
        role, company = at_m.group(1).strip(), at_m.group(2).strip()
        if is_plausible_job_title(role):
            return ExperienceEntry(
                company=company, role=role, start=start, end=end, is_current=is_current,
            )

    # Comma: Role, Company
    parts = re.split(r',\s+', line_wo, maxsplit=1)
    if len(parts) == 2 and is_plausible_job_title(parts[0]):
        return ExperienceEntry(
            company=parts[1].strip(),
            role=parts[0].strip(),
            start=start,
            end=end,
            is_current=is_current,
        )

    if is_plausible_job_title(line_wo) and start:
        return ExperienceEntry(role=line_wo.strip(), start=start, end=end, is_current=is_current)
    return None


def parse_experience(section_text: str, full_text: str = '') -> list[ExperienceEntry]:
    """
    Parse experience ONLY from the Experience section span.
    Empty section → [] (fresher / projects-only resumes). Never scrape Projects via full-text fallback.
    """
    _ = full_text  # retained for API compat; intentionally unused
    raw = (section_text or '').strip()
    if not raw:
        return []

    entries: list[ExperienceEntry] = []
    pending_desc: list[str] = []
    current: ExperienceEntry | None = None
    for line in raw.splitlines():
        entry = _parse_experience_line(line)
        if entry and (entry.role or entry.company):
            if _is_project_like_experience(entry.role, entry.company):
                continue
            if current:
                if pending_desc:
                    current = current.model_copy(
                        update={'description': ' '.join(pending_desc).strip()}
                    )
                    pending_desc = []
                if not _is_project_like_experience(current.role, current.company, current.description):
                    entries.append(current)
            current = entry
            continue
        # Description bullet under current role
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if current and stripped and not is_section_header_line(stripped):
            pending_desc.append(stripped)
    if current:
        if pending_desc:
            current = current.model_copy(update={'description': ' '.join(pending_desc).strip()})
        if not _is_project_like_experience(current.role, current.company, current.description):
            entries.append(current)
    return entries


def parse_summary(section_text: str, full_text: str = '') -> str:
    if section_text.strip():
        return ' '.join(section_text.split())[:2000]
    return extract_summary_from_text(full_text)


def parse_certifications(section_text: str, full_text: str = '') -> list[CertificateEntry]:
    raw = section_text.strip()
    if not raw and full_text:
        from app.ai.parser.enrichment.resume_text_inference import extract_certifications_from_text

        certs = []
        for c in extract_certifications_from_text(full_text):
            if isinstance(c, str):
                certs.append(CertificateEntry(name=c))
            elif isinstance(c, dict):
                certs.append(
                    CertificateEntry(
                        name=str(c.get('name') or ''),
                        issuer=str(c.get('issuer') or ''),
                    )
                )
        return certs
    out: list[CertificateEntry] = []
    for line in raw.splitlines():
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if stripped and not is_section_header_line(stripped):
            parts = re.split(r'\s+[-–—|]\s+|\s+from\s+|\s+by\s+', stripped, maxsplit=1, flags=re.I)
            out.append(
                CertificateEntry(
                    name=parts[0].strip()[:200],
                    issuer=parts[1].strip()[:200] if len(parts) > 1 else '',
                )
            )
    return out


def parse_projects(section_text: str) -> list[ProjectEntry]:
    out: list[ProjectEntry] = []
    for line in (section_text or '').splitlines():
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if stripped and not is_section_header_line(stripped):
            out.append(ProjectEntry(name=stripped[:200]))
    return out


def parse_languages(section_text: str) -> list[LanguageEntry]:
    items = split_list_items(section_text or '')
    return [LanguageEntry(name=i) for i in items if i]


def parse_links(text: str) -> list[str]:
    links = []
    for u in (extract_linkedin(text), extract_github(text), extract_portfolio(text)):
        if u:
            links.append(u)
    return links


def merge_resume_sections(
    *,
    personal: PersonalInfo,
    contact: ContactInfo,
    experience: list[ExperienceEntry],
    education: list[EducationEntry],
    skills: list[SkillEntry],
    certificates: list[CertificateEntry],
    projects: list[ProjectEntry],
    languages: list[LanguageEntry],
) -> CandidateProfile:
    years = compute_total_experience_years(
        [
            {
                'from': e.start,
                'to': 'Present' if e.is_current else e.end,
            }
            for e in experience
        ]
    )
    profile = CandidateProfile(
        personal=personal,
        contact=contact,
        experience=experience,
        education=education,
        skills=skills,
        certificates=certificates,
        projects=projects,
        languages=languages,
        total_experience_years=years,
    )
    return sanitize_candidate_profile(profile)


def parse_resume_from_sections(
    sections: list[SectionSpan],
    full_text: str,
    *,
    max_workers: int = 4,
) -> CandidateProfile:
    preamble = pick_section(sections, 'Preamble') or ''
    if not preamble and sections:
        # Leading unlabeled content
        for s in sections:
            if s.label.lower() == 'preamble':
                preamble = s.text
                break
        if not preamble:
            # Use first ~800 chars as contact zone
            preamble = full_text[:800]

    exp_text = pick_section(
        sections, 'Experience', 'Work Experience', 'Professional Experience', 'Employment', 'Work History',
    )
    edu_text = pick_section(sections, 'Education', 'Academic Background', 'Academics', 'Qualifications')
    skills_text = pick_section(
        sections, 'Skills', 'Technical Skills', 'Core Skills', 'Key Skills', 'Technologies', 'Tools',
    )
    summary_text = pick_section(
        sections, 'Summary', 'Professional Summary', 'Objective', 'Profile', 'About Me',
    )
    cert_text = pick_section(sections, 'Certifications', 'Certificates', 'Licenses')
    proj_text = pick_section(sections, 'Projects', 'Project')
    lang_text = pick_section(sections, 'Languages')

    results: dict[str, Any] = {}
    # Sequential section parsing — avoids import/thread deadlocks under Flask workers
    results['personal'] = parse_personal(full_text, preamble)
    results['contact'] = parse_contact(full_text, preamble)
    results['experience'] = parse_experience(exp_text, full_text)
    results['education'] = parse_education(edu_text, full_text)
    results['skills'] = parse_skills(skills_text, full_text)
    results['summary'] = parse_summary(summary_text, full_text)
    results['certs'] = parse_certifications(cert_text, full_text)
    results['projects'] = parse_projects(proj_text)
    results['languages'] = parse_languages(lang_text)
    _ = max_workers  # retained for API compat / future parallel profiles

    personal: PersonalInfo = results['personal']
    summary = results['summary'] or ''
    if not summary and preamble:
        # Unlabeled intro paragraph after contact (common in Indian resumes)
        paras = [p.strip() for p in re.split(r'\n\s*\n', preamble) if p.strip()]
        for p in paras:
            if len(p) > 80 and not re.search(r'@|linkedin|github|\+\d', p, re.I):
                summary = ' '.join(p.split())[:2000]
                break
    if summary:
        personal = personal.model_copy(update={'summary': summary or personal.summary})

    return merge_resume_sections(
        personal=personal,
        contact=results['contact'],
        experience=results['experience'],
        education=results['education'],
        skills=results['skills'],
        certificates=results['certs'],
        projects=results['projects'],
        languages=results['languages'],
    )
