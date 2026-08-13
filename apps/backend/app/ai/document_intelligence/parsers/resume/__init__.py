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

# Only split on '|'. En/em dashes are date-range separators
# ("Infosenseglobal | Dec 2024 – Present" must not become Role|Company|Dates).
_PIPE_EXP = re.compile(
    r'^(.+?)\s*\|\s*(.+?)\s*\|\s*(.+)$'
)
_AT_EXP = re.compile(r'^(.+?)\s+(?:at|@)\s+(.+)$', re.I)
# Role - Company - (Mon YYYY - Mon YYYY|Now)   OR   Role - Company - Mon YYYY - Mon YYYY
_DASH_ROLE_COMPANY_DATES = re.compile(
    r'^(.+?)\s*[-–—]\s*(.+?)\s*[-–—]\s*\(?\s*'
    r'((?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2})'
    r'\s*(?:[-–—]|to)\s*'
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}|Present|Current|Now))\s*\)?\s*$',
    re.I,
)
_EXP_META_LINE = re.compile(
    r'(?i)^(?:responsibilities|duties|key\s+achievements|achievements|'
    r'client\s*name\s*/?\s*projects?|projects?\s*:|clients?\s*:)\b'
)
# VALIDATION_FIX_duty_verbs_align — keep in sync with sanitize_experience_row
_DUTY_VERB_START = re.compile(
    r'(?i)^(?:managed|executed|coordinated|collaborated|utilized|maintained|'
    r'facilitated|developed|designed|created|built|led|drove|implemented|'
    r'optimized|improved|increased|worked|assisted|supported|handled|'
    r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
    r'identifying|enabling|engineered|gained|helped|wrote|responsible\s+for|'
    r'administer(?:ed|ing)?|completed|pursued|strengthened|scheduled|'
    r'diagnosing|configuring|installing|creating|executing|participating|'
    r'using|implementing|monitoring|maintaining|query)\b'
)
# Narrow: bare "project" over-dropped real jobs that mention project delivery.
_PROJECT_LIKE_EXP = re.compile(
    r'(?i)\b(?:assignment|coursera|internship\s+project|academic\s+project|'
    r'fictional\s+brand|client\s*name\s*/?\s*projects?|key\s+projects?|'
    r'role:\s*primary\s+dba)\b'
)
_EXP_SECTION_STOP = re.compile(
    r'(?i)^(?:key\s+projects?|projects?|certifications?|certificates?|'
    r'education|academic|skills|awards|languages?|interests?)\b'
)
_TRAINING_ONLY_COMPANY = re.compile(
    r'(?i)^(?:professional\s+development|self[- ]directed(?:\s+learning)?|'
    r'training|career\s+break)$'
)
_JOB_TITLE_CUE = re.compile(
    r'(?i)\b(?:'
    r'intern|engineer|developer|analyst|trainee|manager|officer|associate|'
    r'consultant|lead|executive|specialist|administrator|admin|architect|'
    r'designer|scientist|director|head|dba|programmer|coordinator|supervisor|'
    r'recruiter|accountant|teacher|professor|nurse|technician'
    r')\b'
)
_PIPE_TWO = re.compile(r'^(.+?)\s*[|]\s*(.+)$')
_CITY_LIKE = re.compile(
    r'(?i)^(?:'
    r'remote|hybrid|wfh|work\s+from\s+home|'
    r'mumbai|delhi|new\s+delhi|pune|thane|hyderabad|chennai|bangalore|bengaluru|'
    r'noida|gurugram|gurgaon|kolkata|ahmedabad|navi\s+mumbai|kalwa|nashik|'
    r'surat|vadodara|ambernath|dombivli|dombivili|sindhudurg|sewree|solapur|'
    r'mulund|kandivali|andheri|powai|kalyan|vasai|virar|panvel|india|'
    r'(?:[A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)*)(?:,\s*(?:India|Maharashtra|Karnataka|'
    r'Tamil\s+Nadu|Telangana|Gujarat|KA|MH|TN|TS|UP|DL|USA|UK))'
    r')$'
)
_DATE_FIRST_LINE = re.compile(
    r'(?i)^\(?\s*('
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2})'
    r'\s*(?:[-–—]|to)\s*'
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}|Present|Current|Now)'
    r')\s*\)?(?:\s*[|•·]\s*(.+))?$'
)
_DEGREE_PAT = re.compile(
    r'(?i)\b('
    r'Masters?(?:\s+of)?(?:\s+Arts|\s+Science|\s+Commerce|\s+Business|\s+Technology)?'
    r'(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|Bachelors?(?:\s+of)?(?:\s+Arts|\s+Science|\s+Commerce|\s+Mass\s+Media|\s+Technology|\s+Engineering)?'
    r'(?:\s*[-–—]?\s*[A-Za-z &\-/]+)?'
    r'|Master(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?'
    r'|Bachelor(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?'
    r'|Associate(?:\'?s)?(?:\s+(?:of|in|degree)\s+[A-Za-z &\-/]+)?'
    r'|BACHELOR\s+OF\s+ENGINEERING(?:\s*[-–—]?\s*[A-Za-z &\-/]+)?'
    r'|B\.?\s?Tech(?:\s+[A-Za-z &\-/]+)?|B\.?\s?E\.?(?![a-z])|'
    r'B\.?\s?Com(?:m(?:erce)?)?|M\.?\s?Com(?:m(?:erce)?)?|'
    r'B\.?\s?Sc(?:ience)?|M\.?\s?Sc(?:ience)?|'
    r'M\.?\s?Tech|M\.?\s?S\.?(?![a-z])|M\.?\s?B\.?\s?A\.?(?![a-z])|'
    r'M\.?\s?C\.?\s?A\.?(?![a-z])|B\.?\s?C\.?\s?A\.?(?![a-z])|B\.?\s?B\.?\s?A\.?(?![a-z])|'
    r'M\.?\s?A\.?(?![a-z])|B\.?\s?A\.?(?![a-z])|'
    r'Ph\.?\s?D\.?(?![a-z])|Diploma(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|Pre[\s\-]?University|Higher\s+Secondary|Senior\s+Secondary|Secondary\s+School'
    r'|(?:1[0-2](?:th|st|nd|rd)?|10th|12th)\s+Passed(?:\s+in\s+[A-Za-z &\-/]+)?'
    r')\b'
)
_EDU_DUTY_LINE = re.compile(
    r'(?i)^(?:'
    r'configured|setup|performed|effectively|responsible|worked|managed|developed|'
    r'implemented|maintained|monitoring|backup|restore|project\s+name|role\s*:|'
    r'duration\s*:|organizational\s+experience|executed|coordinated|facilitated|'
    r'optimized|increased|engagement|responsibilities|client\s+name|technologies\s+used|'
    r'resulting\s+in|drove\s+a|leading\s+to'
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
            # institution-only + degree that also has institution text (prefer cur institution)
            if cur_inst and not cur_deg and n_deg and n_inst and n_inst.lower() in cur_inst.lower():
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
        # Degree|Institution on a single orphan row
        if cur_deg and not cur_inst and '|' in cur_deg:
            left, _, right = cur_deg.partition('|')
            if len(right.strip()) >= 3:
                merged.append(
                    EducationEntry(
                        degree=left.strip()[:200],
                        field=cur.field,
                        institution=right.strip()[:200],
                        gpa=cur.gpa,
                        start=cur.start,
                        end=cur.end,
                    )
                )
                i += 1
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
        # Compact labeled line: "Education: - B. Com" / "Education: B.Tech CSE"
        inline = re.search(
            r'(?im)^(?:\*\*)?education(?:al)?\s*(?:qualification|background|details)?s?'
            r'(?:\*\*)?\s*:\s*[-–—]?\s*(.+?)\s*$',
            full_text,
        )
        if inline:
            cand = re.sub(r'^[\s•·\-\*]+', '', inline.group(1).strip())
            # Stop if the "value" is actually the next biodata label
            if cand and not re.match(
                r'(?i)^(?:date\s+of\s+birth|dob|marital\s+status|location|address|gender|nationality)\b',
                cand,
            ):
                raw = cand
        if not raw:
            m = re.search(
                r'(?i)(?:^|\n)\s*(?:\*\*)?(?:education(?:al)?\s*(?:qualification|background|details)?s?'
                r'|academic\s+(?:details|background|qualifications?)|academics|'
                r'educational\s+(?:qualifications|background))(?:\*\*)?\s*:?\s*'
                r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|work\s+experience|professional\s+experience|'
                r'employment|work\s+history|internships?|industrial\s+training|'
                r'skills|skill\s*sets?|technical\s+skills?|projects?|certifications?|'
                r'software\s+skills|languages?|awards?|declaration|personal\s+details|'
                r'date\s+of\s+birth|dob|marital\s+status|location|address|summary|'
                r'objective|achievements?)\b|\Z)',
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
        # Experience bullets leak into education when section bounds are weak
        if _EDU_DUTY_LINE.match(stripped):
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

        # Prefer splitting "B.com – SV University" before institution-only classification
        if (
            not institution
            and not degree
            and re.search(r'[-–—]', line_wo_dates)
            and _DEGREE_PAT.search(line_wo_dates)
        ):
            parts = re.split(r'\s*[-–—]\s*', line_wo_dates, maxsplit=1)
            if len(parts) == 2 and _looks_like_degree_line(parts[0]) and (
                _INSTITUTION_CUE.search(parts[1])
                or is_institution_like(parts[1])
                or len(parts[1].strip()) >= 4
            ):
                degree, institution = parts[0].strip(), parts[1].strip()
                i += 1
                if 'Computer Science' in (degree + ' ' + institution):
                    field = 'Computer Science'
                education.append(
                    EducationEntry(
                        degree=degree[:200],
                        field=field,
                        institution=institution[:200],
                        start=start,
                        end=end,
                    )
                )
                continue

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

        # Compact "B.com – SV University, Tirupathi" one-liners (fallback)
        if degree and not institution and re.search(r'[-–—]', degree):
            parts = re.split(r'\s*[-–—]\s*', degree, maxsplit=1)
            if len(parts) == 2 and _looks_like_degree_line(parts[0]) and (
                _INSTITUTION_CUE.search(parts[1])
                or is_institution_like(parts[1])
                or len(parts[1].strip()) >= 4
            ):
                degree, institution = parts[0].strip(), parts[1].strip()
        if degree or institution:
            # Drop duty / project lines that slipped through
            blob = f'{degree} {institution}'.strip()
            if _EDU_DUTY_LINE.match(blob) or (
                len(blob) > 80
                and not _DEGREE_PAT.search(blob)
                and not _INSTITUTION_CUE.search(blob)
            ):
                continue
            # Pipe-separated: "Mumbai University | BHARAT COLLEGE OF ENGINEERING"
            if institution and '|' in institution and not degree:
                left, _, right = institution.partition('|')
                if _looks_like_degree_line(left.strip()):
                    degree = left.strip()
                    institution = right.strip()
                elif _looks_like_institution_line(left.strip()) and _looks_like_institution_line(right.strip()):
                    institution = f'{left.strip()}, {right.strip()}'
            if degree and '|' in degree and not institution:
                left, _, right = degree.partition('|')
                if _INSTITUTION_CUE.search(right) or is_institution_like(right.strip()):
                    degree = left.strip()
                    institution = right.strip()
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
        r'(?i)^(?:technical\s+)?skills?(?:\s*,?\s*(?:tools?|platforms?|abilities|technologies?))*(?:\s+and\s+(?:tools?|platforms?|abilities|technologies?))*\s*:?\s*',
        '',
        raw,
    ).strip()
    # Drop leftover header crumbs from "SKILLS, TOOLS AND PLATFORMS"
    raw = re.sub(
        r'(?i)^(?:tools?|platforms?|abilities|technologies?)(?:\s+and\s+(?:tools?|platforms?|abilities))?\s*:?\s*',
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


def parse_personal(text: str, preamble: str, *, source_filename: str = '') -> PersonalInfo:
    # VALIDATION_FIX_personal_name_fulltext
    from app.ai.parser.enrichment.resume_text_inference import name_from_resume_filename

    src = preamble or text
    name = extract_name_from_text(src)
    if name and not is_plausible_person_name(name):
        name = ''
    if not name and text and text != src:
        name = extract_name_from_text(text)
        if name and not is_plausible_person_name(name):
            name = ''
    # Last resort: first non-contact early line that becomes plausible after honorific strip
    if not name:
        for line in (src or text or '').splitlines()[:12]:
            cand = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', line.strip())
            cand = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff]', '', cand).strip()
            cand = cand.rstrip('-:–—|').strip()
            if not cand or '@' in cand or re.search(r'\d{6,}', cand):
                continue
            if is_plausible_person_name(cand):
                name = cand.title() if cand.isupper() else cand
                break
    file_name = name_from_resume_filename(source_filename) if source_filename else ''
    # Prefer a multi-word filename name over a weak single-token body guess
    if file_name:
        if not name:
            name = file_name
        elif len(name.split()) == 1 and len(file_name.split()) >= 2:
            name = file_name
    if name:
        name = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', name).strip()
        if name.isupper() and len(name.split()) >= 2:
            name = name.title()
    ok, _ = validate_person_name(name) if name else (False, '')
    # If DI validator is stricter than plausible-name check, still keep plausible names
    if name and not ok and is_plausible_person_name(name):
        ok = True
    summary = extract_summary_from_text(text)
    return PersonalInfo(full_name=name if ok else '', summary=summary)


def parse_contact(text: str, preamble: str) -> ContactInfo:
    """Prefer preamble+text; fill gaps from full text when header miss."""
    src = f'{preamble}\n{text}' if preamble else text
    email = extract_email(src)
    phone = extract_phone(src)
    location = extract_simple_location(src)
    linkedin = extract_linkedin(src)
    github = extract_github(src)
    portfolio = extract_portfolio(src)
    # Header-only miss: retry missing fields on full document
    if text and text.strip() and (not email or not phone or not location):
        if not email:
            email = extract_email(text) or email
        if not phone:
            phone = extract_phone(text) or phone
        if not location:
            location = extract_simple_location(text) or location
        if not linkedin:
            linkedin = extract_linkedin(text) or linkedin
        if not github:
            github = extract_github(text) or github
        if not portfolio:
            portfolio = extract_portfolio(text) or portfolio
    return ContactInfo(
        email=email,
        phone=phone,
        location=location,
        preferred_location=location if location else '',
        linkedin=linkedin,
        github=github,
        portfolio=portfolio,
    )


def _is_project_like_experience(role: str, company: str = '', description: str = '') -> bool:
    blob = f'{role} {company} {description}'.strip()
    return bool(blob and _PROJECT_LIKE_EXP.search(blob))


def _has_job_title_cue(text: str) -> bool:
    return bool(_JOB_TITLE_CUE.search((text or '').strip()))


def _looks_like_company_line(text: str) -> bool:
    """Company/org line without a job-title cue (e.g. Infosenseglobal)."""
    s = (text or '').strip().rstrip('.')
    raw = (text or '').strip()
    if not s or len(s) > 80 or len(s.split()) > 6:
        return False
    if raw.endswith('.') and len(s.split()) >= 4:
        return False
    if _has_job_title_cue(s) or _DUTY_VERB_START.match(s) or _CITY_LIKE.match(s):
        return False
    if extract_date_range(s)[0]:
        return False
    if _is_bullet_or_duty_line(s) or is_section_header_line(s):
        return False
    # Duty wrap / prose — companies are capitalized
    if s[0].islower():
        return False
    if re.match(
        r'(?i)^(designing|managing|administering|installing|configuring|creating|'
        r'monitoring|scheduling|implementing|maintaining|executing|performing|'
        r'supporting|optimizing|improving|developing|building|leading|working|'
        r'diagnosing|participating|using|query|security|experience\s+in)\b',
        s,
    ):
        return False
    if re.search(r'(?i)\b(?:and|with|for|from|the|across|during)\b', s) and len(s.split()) >= 4:
        if not re.search(r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies|solutions|labs|systems)\b', s):
            return False
    return True


_DATE_RANGE_STRIP = re.compile(
    r'(?i)\(?\s*(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'\s*[-–—to]+\s*(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|Present|Current|Now)\s*\)?'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}\s*[-–—to]+\s*'
    r'(?:(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}|Present|Current|Now)'
)


def _strip_date_range(text: str) -> str:
    return _DATE_RANGE_STRIP.sub('', text or '').strip(' |-–—,()')


def _looks_like_role_only_line(text: str) -> bool:
    s = (text or '').strip()
    if not s or len(s.split()) > 8 or extract_date_range(s)[0]:
        return False
    if _DUTY_VERB_START.match(s) or _is_bullet_or_duty_line(s) or is_section_header_line(s):
        return False
    if _CITY_LIKE.match(s):
        return False
    return _has_job_title_cue(s) or (
        is_plausible_job_title(s) and bool(re.search(r'(?i)\bintern\b', s))
    )


def _is_role_comma_company_header(text: str) -> bool:
    """True for 'Role, Company' / 'Role,Company' job headers (not duty prose)."""
    stripped = re.sub(r'^[\s•·\-\*●▪▸►]+', '', (text or '').strip())
    comma_parts = re.split(r',\s*', stripped, maxsplit=1)
    if len(comma_parts) != 2:
        return False
    left, right = comma_parts[0].strip(), comma_parts[1].strip()
    if not left or not right:
        return False
    if not (_has_job_title_cue(left) or re.search(r'(?i)\bintern\b', left)):
        return False
    if _DUTY_VERB_START.match(left) or _DUTY_VERB_START.match(right):
        return False
    if len(left.split()) > 6 or not (1 <= len(right.split()) <= 8):
        return False
    # Duty sentences have many clauses / conjunctions on the right
    if re.search(r'(?i)\b(?:resulting|ensuring|improving|including|across|and|wrote|reported)\b', right):
        return False
    return True


def _is_bullet_or_duty_line(line: str) -> bool:
    """True for responsibility bullets / duty sentences — never job headers."""
    raw = (line or '').strip()
    if not raw:
        return False
    if raw[:1] in '•·*-●▪▸►' or raw.startswith(('●', '•')):
        return True
    stripped = re.sub(r'^[\s•·\-\*●▪▸►]+', '', raw).strip()
    if _EXP_META_LINE.match(stripped):
        return True
    if _DUTY_VERB_START.match(stripped):
        return True
    # "AI Trainee, Heavy Engineering Corporation" is a header (often 40–70 chars)
    if _is_role_comma_company_header(stripped):
        return False
    # Mid/long prose with comma clauses is a duty sentence, not a title
    # (Saloni-style: "Trends, and Revenue KPIs, enabling data…")
    if ',' in stripped and len(stripped) > 40:
        return True
    if len(stripped) > 90 and ',' in stripped:
        return True
    return False


def _looks_like_job_header_line(line: str) -> bool:
    """Heuristic: line is a role/company/dates header, not a duty."""
    stripped = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not stripped or _EXP_META_LINE.match(stripped):
        return False
    if _is_role_comma_company_header(stripped):
        return True
    if _is_bullet_or_duty_line(stripped):
        return False
    if _DASH_ROLE_COMPANY_DATES.match(stripped) or _PIPE_EXP.match(stripped):
        return True
    start, _end = extract_date_range(stripped)
    if start and (
        ' - ' in stripped or ' – ' in stripped or '|' in stripped or ' at ' in stripped.lower()
    ):
        return True
    return False


_DATE_ATOM = re.compile(
    r'(?i)^(?:'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
    r'|(?:19|20)\d{2}'
    r'|[-–—]|to'
    r')$'
)


def _join_wrapped_date_lines(lines: list[str]) -> list[str]:
    """Reassemble PDF-split date ranges: May / 2024 / – / July / 2024."""
    out: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if not buf:
            return
        out.append(' '.join(buf))
        buf.clear()

    for raw in lines:
        s = (raw or '').strip()
        if not s:
            continue
        if _DATE_ATOM.match(s):
            buf.append(s)
            continue
        flush()
        out.append(s)
    flush()
    return out


def _join_wrapped_experience_lines(lines: list[str]) -> list[str]:
    """Join PDF-wrapped duty lines onto the previous bullet/header."""
    if not lines:
        return []
    out: list[str] = [lines[0]]
    for nxt in lines[1:]:
        prev = out[-1]
        n = nxt.strip()
        p = prev.strip()
        if not n:
            continue
        if (
            _looks_like_job_header_line(n)
            or _is_role_comma_company_header(n)
            or n[:1] in '•·*●▪▸►'
            or n.startswith('●')
        ):
            out.append(n)
            continue
        if _EXP_META_LINE.match(re.sub(r'^[\s•·\-\*●]+', '', n)):
            out.append(n)
            continue
        # Do not glue a following job title / Role, Company onto the previous line
        if (
            _looks_like_job_header_line(n)
            or _is_role_comma_company_header(n)
            or _looks_like_role_only_line(n)
            or _has_job_title_cue(n)
            or re.search(r'(?i)\bintern\b', n)
        ) and len(n.split()) <= 10 and not _DUTY_VERB_START.match(n):
            out.append(n)
            continue
        # Never glue duties/company onto a prior job header or date line
        if _looks_like_job_header_line(p) or _looks_like_role_only_line(p) or _looks_like_company_line(p):
            out.append(n)
            continue
        # Continuation of previous bullet / soft-wrapped sentence
        if (
            p[:1] in '•·*●▪▸►'
            or _DUTY_VERB_START.match(re.sub(r'^[\s•·\-\*●]+', '', p))
            or (n and n[0].islower())
            or (len(n) < 60 and not extract_date_range(n)[0])
        ) and not _looks_like_job_header_line(n):
            out[-1] = f'{p.rstrip()} {n.lstrip()}'.strip()
        else:
            out.append(n)
    return out


def _parse_experience_line(line: str) -> ExperienceEntry | None:
    raw_line = (line or '').strip()
    if not raw_line or is_section_header_line(raw_line) or len(raw_line) < 3:
        return None
    # Never promote bullets / duty sentences / meta labels to experience rows
    if _is_bullet_or_duty_line(raw_line) or _EXP_META_LINE.match(
        re.sub(r'^[\s•·\-\*●]+', '', raw_line)
    ):
        return None

    stripped = re.sub(r'^[\s•·\-\*●]+', '', raw_line).strip()
    if _is_project_like_experience(stripped):
        return None
    if re.match(r'(?i)^client\s*name', stripped):
        return None

    start, end = extract_date_range(stripped)
    is_current = bool(end and re.match(r'(?i)^(present|current|now)$', end))
    if is_current:
        end = ''

    # Pure geo / City, Region lines are job locations — not roles/companies
    if _CITY_LIKE.match(stripped):
        if start:
            return ExperienceEntry(
                start=start,
                end=end,
                is_current=is_current,
                location=stripped[:120],
            )
        return None

    # Preferred: Role - Company - (dates)  OR  Role — Company
    dash = _DASH_ROLE_COMPANY_DATES.match(stripped)
    if dash:
        role = dash.group(1).strip(' -–—|')
        company = dash.group(2).strip(' -–—|')
        d_start, d_end = extract_date_range(dash.group(3))
        if d_start:
            start, end = d_start, d_end
            is_current = bool(end and re.match(r'(?i)^(present|current|now)$', end))
            if is_current:
                end = ''
        if role and not _DUTY_VERB_START.match(role) and not _EXP_META_LINE.match(role):
            return ExperienceEntry(
                company=company[:200],
                role=role[:200],
                start=start,
                end=end,
                is_current=is_current,
            )

    # Em/en/hyphen without dates: SDE Intern — Edviron / Role - Company
    # Require whitespace around the dash so "self-directed" / "Point-in-Time" stay intact.
    em = re.match(r'^(.+?)\s+(?:[—–]|-)\s+(.+)$', stripped)
    if em and not start and '|' not in stripped:
        left, right = em.group(1).strip(), em.group(2).strip()
        # Avoid splitting long duty sentences on hyphens
        if (
            (_has_job_title_cue(left) or re.search(r'(?i)\bintern\b', left))
            and not _DUTY_VERB_START.match(left)
            and not _DUTY_VERB_START.match(right)
            and len(left.split()) <= 8
            and len(right.split()) <= 8
            and not re.search(r'[.]$', stripped)
        ):
            return ExperienceEntry(company=right[:200], role=left[:200])

    # Date-first BEFORE Role|Company|Dates — en-dash date ranges also match pipe separators
    date_first = _DATE_FIRST_LINE.match(stripped)
    if date_first:
        d_start, d_end = extract_date_range(date_first.group(1) or stripped)
        if d_start:
            start, end = d_start, d_end
            is_current = bool(end and re.match(r'(?i)^(present|current|now)$', end))
            if is_current:
                end = ''
            loc_or_co = (date_first.group(2) or '').strip()
            if loc_or_co and _CITY_LIKE.match(loc_or_co):
                return ExperienceEntry(
                    company='',
                    role='',
                    start=start,
                    end=end,
                    is_current=is_current,
                    location=loc_or_co[:120],
                )
            return ExperienceEntry(
                company=loc_or_co[:200] if loc_or_co else '',
                role='',
                start=start,
                end=end,
                is_current=is_current,
            )

    # Gold / common: Role | Company | Dates
    pipe = _PIPE_EXP.match(stripped)
    if pipe:
        role = pipe.group(1).strip()
        company = pipe.group(2).strip()
        # Reject date tokens mistaken for Role | Company (e.g. 07/2025 – 10/2025 | Remote)
        if extract_date_range(role)[0] or extract_date_range(company)[0]:
            role = ''
        if not start:
            start, end2 = extract_date_range(pipe.group(3))
            if end2:
                is_current = bool(re.match(r'(?i)^(present|current|now)$', end2))
                end = '' if is_current else end2
        if role and not _DUTY_VERB_START.match(role) and (
            is_plausible_job_title(role) or len(role.split()) <= 8
        ):
            loc = ''
            if _CITY_LIKE.match(company):
                loc, company = company, ''
            return ExperienceEntry(
                company=company,
                role=role,
                start=start,
                end=end,
                is_current=is_current,
                location=loc[:120],
            )

    # Two-part pipe: Role | Company, Company | City, or Company | Dates
    pipe2 = _PIPE_TWO.match(stripped)
    if pipe2:
        left, right = pipe2.group(1).strip(), pipe2.group(2).strip()
        r_start, r_end = extract_date_range(right)
        l_start, _ = extract_date_range(left)
        if r_start and not l_start:
            is_current = bool(r_end and re.match(r'(?i)^(present|current|now)$', r_end))
            end = '' if is_current else r_end
            leftover = _strip_date_range(right)
            loc = ''
            if leftover and _CITY_LIKE.match(leftover):
                loc, leftover = leftover, ''
            if leftover:
                role_left = (
                    _looks_like_role_only_line(left)
                    or _has_job_title_cue(left)
                    or bool(re.search(r'(?i)\bintern\b', left))
                )
                return ExperienceEntry(
                    company=(leftover if role_left else left)[:200],
                    role=(left if role_left else leftover)[:200],
                    start=r_start,
                    end=end,
                    is_current=is_current,
                    location=loc[:120],
                )
            if _looks_like_role_only_line(left) or _has_job_title_cue(left):
                return ExperienceEntry(
                    role=left[:200],
                    start=r_start,
                    end=end,
                    is_current=is_current,
                    location=loc[:120],
                )
            if _CITY_LIKE.match(left):
                return ExperienceEntry(
                    start=r_start,
                    end=end,
                    is_current=is_current,
                    location=left[:120],
                )
            return ExperienceEntry(
                company=left[:200],
                start=r_start,
                end=end,
                is_current=is_current,
                location=loc[:120],
            )
        if not start:
            if _CITY_LIKE.match(right):
                # Company | City — store city on location; role often on next line
                return ExperienceEntry(
                    company=left[:200],
                    role='',
                    start='',
                    end='',
                    location=right[:120],
                )
            if (
                (is_plausible_job_title(left) or re.search(r'(?i)\bintern\b', left))
                and not _DUTY_VERB_START.match(left)
                and len(left.split()) <= 8
            ):
                return ExperienceEntry(
                    company=right[:200],
                    role=left[:200],
                    start=start,
                    end=end,
                    is_current=is_current,
                )

    # Role at Company
    line_wo = _strip_date_range(stripped) if start else stripped
    at_m = _AT_EXP.match(line_wo)
    if at_m:
        role, company = at_m.group(1).strip(), at_m.group(2).strip()
        if is_plausible_job_title(role) and not _DUTY_VERB_START.match(role):
            return ExperienceEntry(
                company=company, role=role, start=start, end=end, is_current=is_current,
            )

    # Comma: Role, Company — only when left is a short title AND right looks like an org
    # (never split duty sentences on commas; never treat City, Country as a job)
    parts = re.split(r',\s*', line_wo, maxsplit=1)
    if (
        len(parts) == 2
        and (
            is_plausible_job_title(parts[0])
            or _has_job_title_cue(parts[0])
            or re.search(r'(?i)\bintern\b', parts[0])
        )
        and not _DUTY_VERB_START.match(parts[0])
        and not _CITY_LIKE.match(parts[0])
        and not _CITY_LIKE.match(parts[1])
        and not _CITY_LIKE.match(line_wo)
        and len(parts[0].split()) <= 6
        and len(parts[1].split()) <= 8
        and not _DUTY_VERB_START.match(parts[1])
        and not re.search(r'(?i)\b(?:resulting|ensuring|improving|including|across|and|wrote|reported)\b', parts[1])
    ):
        return ExperienceEntry(
            company=parts[1].strip(),
            role=parts[0].strip(),
            start=start,
            end=end,
            is_current=is_current,
        )

    if (
        is_plausible_job_title(line_wo)
        and start
        and not _DUTY_VERB_START.match(line_wo)
        and len(line_wo.split()) <= 8
    ):
        # Prefer company when the leftover text has no title cue (e.g. "Infosenseglobal Dec 2024 – Present")
        if _has_job_title_cue(line_wo) or re.search(r'(?i)\bintern\b', line_wo):
            return ExperienceEntry(role=line_wo.strip(), start=start, end=end, is_current=is_current)
        if _looks_like_company_line(line_wo):
            return ExperienceEntry(company=line_wo.strip(), start=start, end=end, is_current=is_current)
        return ExperienceEntry(role=line_wo.strip(), start=start, end=end, is_current=is_current)

    # Stacked resume layouts: Role and Company on their own lines (dates follow)
    if not start and _looks_like_role_only_line(line_wo):
        return ExperienceEntry(role=line_wo.strip()[:200])
    if not start and _looks_like_company_line(line_wo):
        return ExperienceEntry(company=line_wo.strip()[:200])

    return None


def _coalesce_stacked_experience_entries(rows: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Merge adjacent Role-only + Company|Dates (or reverse) into one job."""
    out: list[ExperienceEntry] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt:
            cur_role, cur_co = (cur.role or '').strip(), (cur.company or '').strip()
            nxt_role, nxt_co = (nxt.role or '').strip(), (nxt.company or '').strip()
            dates_conflict = bool(cur.start and nxt.start and cur.start != nxt.start)
            if not dates_conflict and cur_role and not cur_co and nxt_co and not nxt_role:
                out.append(
                    cur.model_copy(
                        update={
                            'company': nxt_co[:200],
                            'start': cur.start or nxt.start,
                            'end': cur.end or nxt.end,
                            'is_current': cur.is_current or nxt.is_current,
                            'location': (cur.location or nxt.location or '')[:120],
                            'description': (cur.description or nxt.description or '').strip(),
                        }
                    )
                )
                i += 2
                continue
            if not dates_conflict and cur_co and not cur_role and nxt_role and not nxt_co:
                out.append(
                    cur.model_copy(
                        update={
                            'role': nxt_role[:200],
                            'start': cur.start or nxt.start,
                            'end': cur.end or nxt.end,
                            'is_current': cur.is_current or nxt.is_current,
                            'location': (cur.location or nxt.location or '')[:120],
                            'description': (cur.description or nxt.description or '').strip(),
                        }
                    )
                )
                i += 2
                continue
        out.append(cur)
        i += 1
    return out


def parse_experience(section_text: str, full_text: str = '') -> list[ExperienceEntry]:
    """
    Parse experience ONLY from the Experience section span.
    Empty section → [] (fresher / projects-only resumes). Never scrape Projects via full-text fallback.
    Supports 'Role - Company - (dates)' headers. Consecutive headers before a shared
    Responsibilities block each become their own row and share that description.
    """
    _ = full_text  # retained for API compat; intentionally unused
    raw = (section_text or '').strip()
    if not raw:
        return []

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    lines = _join_wrapped_date_lines(lines)
    lines = _join_wrapped_experience_lines(lines)

    entries: list[ExperienceEntry] = []
    pending_jobs: list[ExperienceEntry] = []
    pending_desc: list[str] = []

    def _flush_pending() -> None:
        nonlocal pending_jobs, pending_desc
        desc = ' '.join(pending_desc).strip()
        pending_desc = []
        if not pending_jobs:
            return
        for job in pending_jobs:
            if _is_project_like_experience(job.role, job.company, desc):
                continue
            if desc:
                job = job.model_copy(update={'description': desc})
            entries.append(job)
        pending_jobs = []

    for line in lines:
        header_probe = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
        if _EXP_SECTION_STOP.match(header_probe):
            _flush_pending()
            break
        entry = _parse_experience_line(line)
        if entry and (entry.role or entry.company or entry.start or entry.location):
            if _is_project_like_experience(entry.role, entry.company):
                continue
            # Date/location-only line → attach to previous job header
            if (
                pending_jobs
                and not pending_desc
                and not (entry.role or '').strip()
                and not (entry.company or '').strip()
                and (entry.start or entry.location)
            ):
                prev = pending_jobs[-1]
                pending_jobs[-1] = prev.model_copy(
                    update={
                        'start': prev.start or entry.start,
                        'end': prev.end or entry.end,
                        'is_current': prev.is_current or entry.is_current,
                        'location': (prev.location or entry.location or '')[:120],
                    }
                )
                continue
            # Role header then company / Company|Dates on next line
            if (
                pending_jobs
                and not pending_desc
                and (pending_jobs[-1].role or '').strip()
                and not (pending_jobs[-1].company or '').strip()
                and (entry.company or '').strip()
                and not (entry.role or '').strip()
            ):
                prev = pending_jobs[-1]
                pending_jobs[-1] = prev.model_copy(
                    update={
                        'company': entry.company.strip()[:200],
                        'start': prev.start or entry.start,
                        'end': prev.end or entry.end,
                        'is_current': prev.is_current or entry.is_current,
                        'location': (prev.location or entry.location or '')[:120],
                    }
                )
                continue
            # Company / Company|Dates stub then role title on next line
            if (
                pending_jobs
                and not pending_desc
                and not (pending_jobs[-1].role or '').strip()
                and (pending_jobs[-1].company or '').strip()
                and (entry.role or '').strip()
                and not (entry.company or '').strip()
            ):
                prev = pending_jobs[-1]
                pending_jobs[-1] = prev.model_copy(
                    update={
                        'role': entry.role.strip()[:200],
                        'start': prev.start or entry.start,
                        'end': prev.end or entry.end,
                        'is_current': prev.is_current or entry.is_current,
                        'location': (prev.location or entry.location or '')[:120],
                    }
                )
                continue
            if (
                pending_jobs
                and not pending_desc
                and not (pending_jobs[-1].role or '').strip()
                and (entry.role or entry.company)
                and (
                    _has_job_title_cue(entry.role or '')
                    or is_plausible_job_title(entry.role)
                    or re.search(r'(?i)\bintern\b', entry.role or '')
                )
                and not _is_bullet_or_duty_line(entry.role or '')
            ):
                prev = pending_jobs[-1]
                pending_jobs[-1] = prev.model_copy(
                    update={
                        'role': (entry.role or entry.company)[:200],
                        'company': (entry.company or prev.company)[:200],
                        'start': prev.start or entry.start,
                        'end': prev.end or entry.end,
                        'is_current': prev.is_current or entry.is_current,
                        'location': (prev.location or entry.location or '')[:120],
                    }
                )
                continue
            # New header after duties → close previous block(s)
            if pending_jobs and pending_desc:
                _flush_pending()
            pending_jobs.append(entry)
            continue
        stripped = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
        if not stripped or stripped in '-–—' or is_section_header_line(stripped) or _EXP_META_LINE.match(stripped):
            continue
        # Role-only line after Company | City stub
        if (
            pending_jobs
            and not pending_desc
            and not (pending_jobs[-1].role or '').strip()
            and _looks_like_role_only_line(stripped)
        ):
            prev = pending_jobs[-1]
            pending_jobs[-1] = prev.model_copy(update={'role': stripped[:200]})
            continue
        # Company-only line after role header
        if (
            pending_jobs
            and not pending_desc
            and (pending_jobs[-1].role or '').strip()
            and not (pending_jobs[-1].company or '').strip()
            and _looks_like_company_line(stripped)
        ):
            prev = pending_jobs[-1]
            pending_jobs[-1] = prev.model_copy(update={'company': stripped[:200]})
            continue
        if pending_jobs:
            pending_desc.append(stripped)

    _flush_pending()

    cleaned: list[ExperienceEntry] = []
    for e in entries:
        role = (e.role or '').strip()
        company = (e.company or '').strip()
        if _DUTY_VERB_START.match(role) or _DUTY_VERB_START.match(company):
            continue
        if (role and role[:1] in '•·*●') or (company and company[:1] in '•·*●'):
            continue
        if not (role or company or e.start):
            continue
        if _TRAINING_ONLY_COMPANY.match(company) and not _has_job_title_cue(role):
            continue
        if e.start or (role and company and not _is_bullet_or_duty_line(role)):
            cleaned.append(e)
        elif role and (
            _has_job_title_cue(role)
            or is_plausible_job_title(role)
            or re.search(r'(?i)\bintern\b', role)
        ) and not _is_bullet_or_duty_line(role):
            cleaned.append(e)
        elif company and not role and e.start:
            cleaned.append(e)
        elif company and e.location:
            cleaned.append(e)
        elif company and role:
            cleaned.append(e)
    return _coalesce_stacked_experience_entries(cleaned)


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
    source_text: str = '',
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
    # Seed prose years when dated ranges are empty (sanitize may refine)
    if years is None and source_text:
        from app.ai.parser.enrichment.resume_text_inference import (
            extract_total_experience_years_from_text,
        )

        years = extract_total_experience_years_from_text(source_text)
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
    return sanitize_candidate_profile(profile, source_text=source_text or '')


def parse_resume_from_sections(
    sections: list[SectionSpan],
    full_text: str,
    *,
    max_workers: int = 4,
    source_filename: str = '',
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
        sections,
        'Experience',
        'Work Experience',
        'Professional Experience',
        'Employment',
        'Work History',
        'Internship',
        'Internships',
        'Industrial Training',
        'Summer Internship',
    )
    edu_text = pick_section(
        sections,
        'Education',
        'Academic Background',
        'Academics',
        'Academic Details',
        'Educational Qualifications',
        'Educational Background',
        'Educational Qualification',
        'Qualifications',
    )
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
    results['personal'] = parse_personal(full_text, preamble, source_filename=source_filename)
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
        source_text=full_text or '',
    )
