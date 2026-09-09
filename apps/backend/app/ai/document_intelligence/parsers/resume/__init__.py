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
    peel_education_date_phrase,
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
    extract_summary_details,
    extract_summary_from_text,
    filter_skill_items,
    document_identity_names,
    identity_is_employer_value,
    identity_matches_person,
    is_contact_or_reference_line,
    is_contact_section_label,
    is_document_title_line,
    is_institution_like,
    is_biodata_or_address_line,
    is_labeled_contact_metadata,
    is_non_job_experience_record,
    has_credible_employment_evidence,
    is_fresher_or_years_only_experience_line,
    is_plausible_job_title,
    is_plausible_person_name,
    is_project_or_employment_meta_label,
    is_section_header_line,
    peel_inline_contact,
    is_valid_summary,
    looks_like_contact_person_line,
    looks_like_email_or_url,
    looks_like_phone_token,
    looks_like_education_as_experience_row,
    looks_like_skill_or_duration_company,
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
    r'|(?:19|20)\d{2}|Present|Current|Now|Till\s*Date|Ongoing|Pursuing))\s*\)?\s*$',
    re.I,
)
_EXP_META_LINE = re.compile(
    r'(?i)^(?:'
    r'(?:key\s+)?responsibilities|duties(?:\s+and\s+responsibilities)?|'
    r'job\s+description|work\s+description|role\s+(?:description|summary)|'
    r'key\s+achievements|achievements|'
    r'client\s*name\s*/?\s*projects?|projects?|'
    r'environment|technologies?\s+used|'
    r'project\s+title|project\s+name|learnings?|key\s+learnings?|'
    r'conclusion|takeaways?'
    r')\s*[:\-–—]'
)
# Whole-line labels that must never become a company/role.
_BARE_DUTY_HEADER = re.compile(
    r'(?i)^(?:(?:key\s+)?responsibilities|duties(?:\s+and\s+responsibilities)?|'
    r'job\s+description|work\s+description|role\s+(?:description|summary)|'
    r'key\s+achievements|achievements(?:\s*/\s*tasks)?|'
    r'learnings?|key\s+learnings?|conclusion|takeaways?|'
    r'project\s+title|project\s+name|'
    r'clients?|duration|environment|projects?\s*(?:#|no\.?\s*)?\d*'
    r')\s*:?\s*$'
)
# VALIDATION_FIX_duty_verbs_align — keep in sync with sanitize_experience_row
_DUTY_VERB_START = re.compile(
    r'(?i)^(?:managed|executed|coordinated|collaborated|utilized|maintained|'
    r'facilitated|developed|designed|created|built|led|drove|implemented|'
    r'implement|develop|build|create|manage|monitor|configure|install|'
    r'optimized|improved|increased|worked|assisted|supported|handled|'
    r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
    r'researched|prepared|observed|catalogued|coordinated|reviewed|'
    r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
    r'identifying|enabling|engineered|gained|helped|wrote|responsible\s+for|'
    r'administer(?:ed|ing)?|completed|pursued|strengthened|scheduled|'
    r'diagnosing|configuring|installing|creating|executing|participating|'
    r'using|implementing|monitoring|maintaining|query)\b'
)
# Narrow: bare "project" over-dropped real jobs that mention project delivery.
_PROJECT_LIKE_EXP = re.compile(
    r'(?i)(?:'
    r'\b(?:assignment|coursera|internship\s+project|academic\s+project|'
    r'fictional\s+brand|client\s*name\s*/?\s*projects?|key\s+projects?|'
    r'role:\s*primary\s+dba)\b'
    r'|^(?:projects?\s*(?:#|no\.?\s*|number\s+)?\s*\d+)\b'
    r')'
)
# Whole-line headers only. "Project Development & Execution …" is a duty, not Projects.
_EXP_SECTION_STOP = re.compile(
    r'(?i)^(?:key\s+projects?|projects?|certifications?|certificates?|'
    r'education|academic|skills|technical\s+proficiency|technical\s+expertise|'
    r'technical\s+knowledge|awards|languages?|interests?'
    r')\s*:?\s*$'
)
# Numbered project blocks nested inside Experience text (not "Project Title:" duties).
_PROJECT_BLOCK_HEADING = re.compile(
    r'(?i)^(?:key\s+)?projects?\s*(?:#|no\.?\s*|number\s+)?\s*\d+\b'
)
_EMPLOYMENT_DURATION_LABEL = re.compile(
    r'(?i)^(?:duration|period|tenure|timeline|dates?|period\s*/\s*duration)\s*[:\-–—]\s*(.+)$'
)
_LABELED_EMPLOYER_LINE = re.compile(
    r'(?i)^(?:(?:current|previous|former|past|last)\s+)?'
    r'(?:payroll\s+|consulting\s+|vendor\s+)?'
    r'(?:name\s+of\s+(?:the\s+)?)?'
    r'(?:company(?:\s+name)?|employer|organization|organisation)'
    r'(?:[\'’]s)?(?:\s+name)?\s*[:\-–—]\s*(.+)$'
)
_LABELED_CLIENT_LINE = re.compile(
    r'(?i)^(?:(?:end\s+)?clients?(?:\s+name)?|client\s+company|'
    r'client\s+side|client\s+organization|client\s+organisation)\s*[:\-–—]\s*(.+)$'
)
_PAREN_CLIENT = re.compile(
    r'(?i)^(.+?)\s*\(\s*(?:end\s+)?clients?\s*[:\-–—]\s*(.+?)\s*\)\s*$'
)
_INLINE_SLASH_CLIENT = re.compile(
    r'(?i)^(.+?)\s*/\s*(?:end\s+)?clients?\s*[:\-–—]\s*(.+)$'
)
_DESC_EMPLOYER_LABEL = re.compile(
    r'(?i)(?:^|[•\n])\s*(?:payroll\s+company|(?:current|past|previous|former)\s+employer|'
    r'(?:name\s+of\s+(?:the\s+)?)?(?:company(?:\s+name)?|employer))\s*[:\-–—]\s*'
    r'([^\n•]+)'
)
_EXPERIENCE_PREFIX_COMPANY = re.compile(
    r'(?i)^(?:work\s+)?experience\s*[:\-–—]\s*(.+)$'
)
_ROLE_YEARS_TENURE = re.compile(
    r'(?i)^(.+?)\s*[:\-–—]\s*(\d+(?:\.\d+)?\+?\s*(?:years?|yrs?|year)\b.*)$'
)
_DATE_CARRIER_PREFIX = re.compile(
    r'(?i)^(?:(?:current|previous|former|past|last)\s+)?'
    r'(?:clients?|duration|period|tenure|timeline|dates?|location)\s*[:\-–—]\s*'
)
_LABELED_DUTY_LINE = re.compile(
    r'(?i)^(?:professional\s+development|leadership(?:\s+and\s+teamwork)?|'
    r'project\s+development(?:\s*(?:and|&)\s*execution)?|'
    r'achievements?(?:\s*/\s*tasks)?|(?:key\s+)?responsibilities|duties|'
    r'job\s+description|work\s+description|'
    r'teamwork|project\s+title|project\s+name|learnings?|conclusion)\s*:\s+\S'
)
_TRAINING_ONLY_COMPANY = re.compile(
    r'(?i)^(?:professional\s+development|self[- ]directed(?:\s+learning)?|'
    r'training|career\s+break)$'
)
_JOB_TITLE_CUE = re.compile(
    r'(?i)\b(?:'
    r'intern|engineer|enginner|enginneer|developer|developper|analyst|trainee|'
    r'manager|maneger|officer|associate|consultant|lead|executive|specialist|'
    r'administrator|adminstrator|admin|architect|'
    r'designer|scientist|director|head|dba|programmer|coordinator|supervisor|'
    r'recruiter|accountant|teacher|professor|nurse|technician|trainer|'
    r'instructor|apprentice|assitant|assistant'
    r')\b'
)
_INLINE_ROLE_LABEL = re.compile(
    r'(?i)(?:^|[\s|,;])(?:role|title|designation|position|job\s+title)\s*[:\-–—]\s*'
    r'(.{2,60}?)(?=\s+(?:responsibilit\w*|duties|location|duration|company|employer)\b|$)'
)
_FROM_COLON_ORG_AS = re.compile(
    r'(?i)^(?:from\s+)?.{0,90}?:\s*(.+?)\s+as\s+(?:an?\s+)?(.+)$'
)
_NON_ORG_IN_TAIL = re.compile(
    r'(?i)\b(?:production|environment|support|team|department|office|field|'
    r'domain|industry)\s*$'
)
_CITY_PIN_LINE = re.compile(
    r'(?i)^(?:'
    r'remote|hybrid|wfh|mumbai|delhi|new\s+delhi|pune|thane|hyderabad|chennai|'
    r'bangalore|bengaluru|noida|gurugram|gurgaon|kolkata|ahmedabad|'
    r'navi\s+mumbai|kalwa|nashik|surat|vadodara|andheri|powai|kalyan|vasai|'
    r'virar|panvel|india'
    r')\s+[1-9]\d{5}$'
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
_DATE_ATOM_LINE = (
    r'(?:(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
    r'(?:\s+(?:19|20)\d{2}|\s*[\'’]\s*\d{2})'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2})'
)
_DATE_PRESENT_LINE = (
    r'(?:Present|Current|Now|Till\s*Date|Tilldate|Ongoing|Pursuing)'
)
_DATE_FIRST_LINE = re.compile(
    rf'(?i)^\(?\s*('
    rf'(?:from\s+|since\s+)?{_DATE_ATOM_LINE}'
    rf'(?:'
    rf'\s*(?:[-–—]|to|until|till(?!\s*date))\s*(?:{_DATE_ATOM_LINE}|{_DATE_PRESENT_LINE})'
    rf'|\s+till\s*date'
    rf')?'
    rf')\s*\)?(?:\s*[|•·]\s*(.+))?$'
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
    r'MMS|PGDM|PGP|'
    r'Ph\.?\s?D\.?(?![a-z])|Diploma(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|Pre[\s\-]?University|Higher\s+Secondary|Senior\s+Secondary|Secondary\s+School'
    r'|(?:10th|12th)(?!\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))'
    r'(?:\s+(?:std|standard|grade|class|passed))?(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|(?:1[0-2](?:th|st|nd|rd)?|10th|12th)\s+Passed(?:\s+in\s+[A-Za-z &\-/]+)?'
    r'|HSC|SSC|CBSE|ICSE|PUC'
    r')\b'
)
_EDU_DUTY_LINE = re.compile(
    r'(?i)^(?:'
    r'configured|setup|performed|effectively|responsible|worked|managed|developed|'
    r'implemented|maintained|monitoring|backup|restore|project\s+name|role\s*:|'
    r'duration\s*:|organizational\s+experience|executed|coordinated|facilitated|'
    r'optimized|increased|engagement|responsibilities|client\s+name|technologies\s+used|'
    r'resulting\s+in|drove\s+a|leading\s+to|helped|trained|taught|applied|'
    r'identifying|enabling|assisted|supported|collaborated|created|built'
    r')\b'
)
_INSTITUTION_CUE = re.compile(
    r'(?i)\b(?:university|college|school|institute|academy|vidyalaya|'
    r'polytechnic|iit|nit|iiit|somaiya|association)\b'
)
_DATE_RANGE_STRIP = re.compile(
    r'(?i)\(?\s*(?:'
    r'(?:(?:from|since)\s+)?'
    r'(?:(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+)?'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
    r'(?:\s+(?:19|20)\d{2}|\s*[\'’]\s*\d{2}|\s+\d{2}(?!\d))'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}'
    r')(?:'
    r'\s*(?:[-–—]|to|until|till(?!\s*date))\s*'
    r'(?:'
    r'(?:(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+)?'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
    r'(?:\s+(?:19|20)\d{2}|\s*[\'’]\s*\d{2}|\s+\d{2}(?!\d))'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}|Present|Current|Now|Till\s*Date|Tilldate|'
    r'T[il]l\s+now|Ongoing|Pursuing'
    r')'
    r'|\s+till\s*date'
    r')\s*\)?'
)


_SCHOOL_LEVEL_HEADING = re.compile(
    r'(?i)^[:\-–—\s]*(?:10th|12th|ssc|hsc|cbse|icse|puc)\b'
    r'(?!\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))'
)
_NUMBERED_DUTY_LINE = re.compile(r'^\d{1,2}\.\s+\S')
_DEGREE_FROM_INST = re.compile(r'(?i)^(.+?)(?<![A-Za-z])from\s+(.+)$')
_EDU_TRAILING_MONTH_YEAR = re.compile(
    r'(?i)(?:[,;|\s]+|(?<=\s))(?:in\s+)?'
    r'('
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r')\b\.?\s*([A-Za-z][A-Za-z .]{0,40})?\s*$'
)


def _looks_like_degree_line(line: str) -> bool:
    s = (line or '').strip().lstrip(':').strip()
    if not s or len(s) > 200:
        return False
    if _NUMBERED_DUTY_LINE.match(s) and not re.match(r'(?i)^\d{1,2}th\b', s):
        return False
    if _DEGREE_PAT.search(s):
        return True
    if re.match(r'(?i)^(masters?|bachelors?|diploma|phd|m\.?a\.?|b\.?a\.?|b\.?tech|mms|mba|pgdm)\b', s):
        return True
    if _SCHOOL_LEVEL_HEADING.match(s):
        return True
    if re.match(r'(?i)^(1[0-2](?:th)?|10th|12th)\s+passed\b', s):
        return True
    if re.match(r'(?i)^(hsc|ssc|cbse|icse|puc|s\.?\s*s\.?\s*c\.?|h\.?\s*s\.?\s*c\.?)\b', s):
        return True
    return False


_EDU_TRAILING_YEAR = re.compile(r'(?i)\s*[|/\-–—,]*\s*((?:19|20)\d{2})\s*\.?\s*$')
_EDU_GPA_TOKEN = re.compile(
    r'(?i)(?:\b(?:cgpa|gpa|aggregate)\s*[:\-–—]?\s*([\d]{1,2}(?:\.\d+)?)(?:\s*\(\s*cgpa\s*\))?'
    r'|(\d{1,3}(?:\.\d{1,2})?\s*%))'
)
_GPA_ONLY_LINE = re.compile(
    r'(?i)^(?:grade|cgpa|gpa|percentage|score|aggregate)\s*[:\-–—]?\s*'
    r'([\d]{1,2}(?:\.\d+)?|\d{1,3}(?:\.\d{1,2})?\s*%)(?:\s*\(\s*cgpa\s*\))?\s*$'
)
_FIELD_ONLY_LINE = re.compile(
    r'^\(\s*([A-Za-z][A-Za-z0-9 &/\-]{2,60})\s*\)\s*$'
)
_BRACKET_FIELD = re.compile(r'\[([^\]]{2,60})\]')
_PURSUING_LINE = re.compile(
    r'(?i)^(pursuing|ongoing|in\s+progress|currently\s+pursuing|till\s*date)\s*\.?$'
)
_DATE_ONLY_LINE = re.compile(
    r'(?i)^(?:'
    r'(?:(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+)?'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+'
    r')?'
    r'(?:19|20)\d{2}'
    r'(?:\s*[-–—]\s*(?:(?:19|20)\d{2}|Present|Current|Now|Till\s*Date|Ongoing|Pursuing))?'
    r'\s*$'
)
_EDU_COL_DEGREE = re.compile(r'(?i)\b(?:degree|qualification|course|program|programme)\b')
_EDU_COL_INST = re.compile(r'(?i)\b(?:institution|university|college|school|board)\b')
_EDU_COL_YEAR = re.compile(r'(?i)\b(?:year|duration|period|passing)\b')
_EDU_COL_GPA = re.compile(r'(?i)\b(?:percent|cgpa|gpa|marks|score|grade)\b')
_EXP_COL_COMPANY = re.compile(
    r'(?i)\b(?:company|employer|organization|organisation|firm|client)\b'
)
_EXP_COL_ROLE = re.compile(r'(?i)\b(?:role|title|designation|position)\b')
_EXP_COL_DATES = re.compile(r'(?i)\b(?:duration|period|dates?|tenure)\b')
_EXP_COL_START = re.compile(r'(?i)^(?:from|start(?:\s*date)?)\b')
_EXP_COL_END = re.compile(r'(?i)^(?:to|end(?:\s*date)?|till)\b')


def _degree_bracket_field(text: str) -> tuple[str, str]:
    """Split 'MMS [Marketing]' into degree + field. Empty field if none."""
    s = (text or '').strip()
    m = _BRACKET_FIELD.search(s)
    if not m:
        return s, ''
    field = m.group(1).strip()
    degree = (s[: m.start()] + s[m.end() :]).strip()
    return degree or s, field


def _edu_header_roles(parts: list[str]) -> list[str] | None:
    roles: list[str] = []
    for p in parts:
        low = (p or '').lower().rstrip(':')
        if _EDU_COL_DEGREE.search(low):
            roles.append('degree')
        elif _EDU_COL_INST.search(low):
            roles.append('institution')
        elif _EDU_COL_YEAR.search(low):
            roles.append('year')
        elif _EDU_COL_GPA.search(low):
            roles.append('gpa')
        else:
            roles.append('other')
    mapped = {r for r in roles if r != 'other'}
    if 'degree' in mapped and ('institution' in mapped or 'year' in mapped):
        return roles
    return None


def _classify_edu_cell(cell: str) -> str:
    s = (cell or '').strip()
    if not s:
        return 'other'
    if re.fullmatch(
        r'(?i)(?:19|20)\d{2}(?:\s*[-–—]\s*(?:(?:19|20)\d{2}|Present|Current|Now|Till\s*Date|Ongoing|Pursuing))?',
        s,
    ):
        return 'year'
    if re.search(r'(?i)\d+(?:\.\d+)?\s*%|\bcgpa\b|\bgpa\b', s) or re.fullmatch(
        r'\d{1,2}(?:\.\d{1,2})?', s
    ):
        return 'gpa'
    if _looks_like_degree_line(s) or _DEGREE_PAT.search(s):
        return 'degree'
    if _INSTITUTION_CUE.search(s) or is_institution_like(s):
        return 'institution'
    return 'other'


def _education_from_table_row(parts: list[str], roles: list[str] | None) -> EducationEntry | None:
    cells = [(p or '').strip() for p in parts]
    if not any(cells):
        return None
    degree = institution = gpa = start = end = field = ''
    if roles and len(roles) == len(cells):
        for cell, role in zip(cells, roles):
            if not cell:
                continue
            if role == 'degree':
                degree, extra = _degree_bracket_field(cell)
                field = field or extra
            elif role == 'institution':
                institution = cell
            elif role == 'year':
                a, b = extract_date_range(cell)
                if a and b:
                    start, end = a, b
                elif a:
                    end = a
                else:
                    end = normalize_month_token(cell)
            elif role == 'gpa':
                gpa = cell
            elif role == 'other':
                kind = _classify_edu_cell(cell)
                if kind == 'degree' and not degree:
                    degree, extra = _degree_bracket_field(cell)
                    field = field or extra
                elif kind == 'institution' and not institution:
                    institution = cell
                elif kind == 'year' and not (start or end):
                    a, b = extract_date_range(cell)
                    if a and b:
                        start, end = a, b
                    else:
                        end = a or normalize_month_token(cell)
                elif kind == 'gpa' and not gpa:
                    gpa = cell
    else:
        unused = set(range(len(cells)))
        for i, cell in enumerate(cells):
            kind = _classify_edu_cell(cell)
            if kind == 'degree' and not degree:
                degree, extra = _degree_bracket_field(cell)
                field = field or extra
                unused.discard(i)
            elif kind == 'institution' and not institution:
                institution = cell
                unused.discard(i)
            elif kind == 'year' and not (start or end):
                    a, b = extract_date_range(cell)
                    if a and b:
                        start, end = a, b
                    else:
                        end = a or normalize_month_token(cell)
                    unused.discard(i)
            elif kind == 'gpa' and not gpa:
                gpa = cell
                unused.discard(i)
        # leftover cells: prefer unused as institution then degree
        for i in sorted(unused):
            cell = cells[i]
            if not cell:
                continue
            if not degree:
                degree, extra = _degree_bracket_field(cell)
                field = field or extra
            elif not institution:
                institution = cell
    if institution:
        inst_core, inst_year = peel_education_date_phrase(institution)
        if inst_year:
            institution = inst_core
            if not end:
                end = inst_year
            if start and not extract_date_range(institution)[0] and start == end:
                start = ''
    if degree:
        deg_core, deg_year = peel_education_date_phrase(degree)
        if deg_year:
            degree = deg_core
            if not end:
                end = deg_year
            if start and start == end:
                start = ''
    if not degree and not institution:
        return None
    return EducationEntry(
        degree=degree[:200],
        field=field[:120],
        institution=institution[:200],
        gpa=gpa[:40],
        start=start,
        end=end,
    )


def _parse_pipe_education_table(lines: list[str]) -> list[EducationEntry] | None:
    """Map headered pipe/tab education tables without mixing row cells."""
    if len(lines) < 2:
        return None
    first = [p.strip() for p in re.split(r'[|\t]', lines[0]) if p.strip()]
    roles = _edu_header_roles(first) if len(first) >= 2 else None
    if not roles:
        # Require at least two data rows that look like aligned cells
        scored = 0
        for ln in lines[:6]:
            parts = [p.strip() for p in re.split(r'[|\t]', ln) if p.strip()]
            if len(parts) >= 3:
                kinds = [_classify_edu_cell(p) for p in parts]
                if kinds.count('other') <= 1:
                    scored += 1
        if scored < 2:
            return None
    out: list[EducationEntry] = []
    start_i = 1 if roles else 0
    for ln in lines[start_i:]:
        parts = [p.strip() for p in re.split(r'[|\t]', ln)]
        nonempty = [p for p in parts if p]
        if len(nonempty) < 2:
            continue
        headerish = {p.lower().rstrip(':') for p in nonempty}
        if headerish & {'degree', 'institution', 'university', 'college', 'year', 'board', 'percentage', 'cgpa'}:
            continue
        row = _education_from_table_row(nonempty if not roles else parts[: len(roles)] or nonempty, roles)
        if row:
            out.append(row)
    return out if len(out) >= 1 else None


def _experience_header_roles(parts: list[str]) -> list[str] | None:
    roles: list[str] = []
    for p in parts:
        low = (p or '').lower().rstrip(':')
        if _EXP_COL_COMPANY.search(low):
            roles.append('company')
        elif _EXP_COL_ROLE.search(low):
            roles.append('role')
        elif _EXP_COL_START.search(low):
            roles.append('start')
        elif _EXP_COL_END.search(low):
            roles.append('end')
        elif _EXP_COL_DATES.search(low):
            roles.append('dates')
        else:
            roles.append('other')
    if 'company' in roles and ('role' in roles or 'start' in roles or 'dates' in roles):
        return roles
    if 'role' in roles and ('start' in roles or 'dates' in roles):
        return roles
    return None


def _peel_education_meta(line: str) -> tuple[str, str, str]:
    """Strip trailing year / CGPA / percentage from an education one-liner."""
    s = (line or '').strip()
    gpa = ''
    year = ''
    my = _EDU_TRAILING_MONTH_YEAR.search(s)
    if my:
        year = normalize_month_token(my.group(1))
        place = (my.group(2) or '').strip(' ,')
        s = s[: my.start()].strip(' \t|-–—,')
        if place and (_INSTITUTION_CUE.search(place) or is_institution_like(place)):
            s = f'{s} {place}'.strip() if s else place
    if not year:
        s, year = peel_education_date_phrase(s)
    gm = _EDU_GPA_TOKEN.search(s)
    if gm:
        gpa = (gm.group(1) or gm.group(2) or '').strip()
        s = (s[: gm.start()] + s[gm.end() :]).strip(' \t|-–—,')
        s = re.sub(r'\s*[-–—]\s*$', '', s).strip()
    s = re.sub(r'(?i)[, ]*\baggregate\b\s*$', '', s).strip(' \t|-–—,')
    return s, gpa, year


def _conservative_from_institution(right: str) -> bool:
    """Keep a FROM-clause token as written; never invent a full institution."""
    r = (right or '').strip()
    if not r:
        return False
    if _INSTITUTION_CUE.search(r) or is_institution_like(r):
        return True
    words = r.split()
    if not (1 <= len(words) <= 4):
        return False
    if r.endswith('.') and len(words) >= 3:
        return False
    if re.search(r'(?i)\b(?:developed|responsible|implemented|worked|managed)\b', r):
        return False
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 .'\-]{1,60}", r))


_DEGREE_SCHOOL_PHRASE = re.compile(
    r'(?i)\b(?:'
    r'(?:secondary|high|higher\s+secondary|senior\s+secondary)\s+school\s+certificate'
    r'|school\s+certificate|school\s+leaving|ssc|hsc'
    r')\b'
)


def _comma_part_is_institution(part: str) -> bool:
    p = (part or '').strip()
    if not p:
        return False
    if _DEGREE_SCHOOL_PHRASE.search(p) and not re.search(
        r'(?i)\b(?:college|university|institute|academy|vidyalaya)\b', p
    ):
        # "Secondary School Certificate (SSC)" is the degree, not the school
        if _looks_like_degree_line(p) or re.search(r'(?i)\bcertificate\b', p):
            return False
    if _INSTITUTION_CUE.search(p) or is_institution_like(p):
        return True
    return False


def split_education_oneliner(line: str) -> tuple[str, str, str, str]:
    """Split compact education lines used on many CVs.

    Examples:
    - B.Sc. in Information Technology (BSc.IT), Gurunanak Khalsa College, Mumbai - CGPA: 9.3 | 2025
    - Higher Secondary Certificate (HSC) - Science, Jai Hind College, Mumbai - 91.00% | 2021
    - Bachelor of Science, State University, 2020
    """
    core, gpa, year = _peel_education_meta(line)
    if not core:
        return '', '', gpa, year
    from_m = _DEGREE_FROM_INST.match(core)
    if from_m:
        left, right = from_m.group(1).strip(), from_m.group(2).strip()
        if _looks_like_degree_line(left) and _conservative_from_institution(right):
            return left, right, gpa, year
        if _looks_like_degree_line(left):
            return left, '', gpa, year
    if ':' in core:
        left, _, right = core.partition(':')
        left, right = left.strip(), right.strip()
        if left and right and _looks_like_degree_line(left) and (
            _INSTITUTION_CUE.search(right) or is_institution_like(right)
        ):
            return left, right, gpa, year
    if ',' in core:
        parts = [p.strip() for p in core.split(',') if p.strip()]
        inst_idx = next(
            (i for i, p in enumerate(parts) if _comma_part_is_institution(p)),
            None,
        )
        if inst_idx is not None and inst_idx > 0:
            degree = ', '.join(parts[:inst_idx]).strip()
            institution = ', '.join(parts[inst_idx:]).strip()
            return degree, institution, gpa, year
        if inst_idx == 0 and len(parts) >= 2 and (
            _looks_like_degree_line(parts[1]) or _DEGREE_PAT.search(parts[1])
        ) and not _comma_part_is_institution(parts[1]):
            return parts[1].strip(), parts[0].strip(), gpa, year
    if (
        re.search(r'[-–—]', core)
        and _DEGREE_PAT.search(core)
        and not _hyphen_is_inside_parens(core)
    ):
        parts = re.split(r'\s*[-–—]\s*', core, maxsplit=1)
        if len(parts) == 2 and _looks_like_degree_line(parts[0]) and (
            _INSTITUTION_CUE.search(parts[1]) or is_institution_like(parts[1])
        ):
            return parts[0].strip(), parts[1].strip(), gpa, year
    adj_deg, adj_inst = _split_adjacent_degree_institution(core)
    if adj_deg and adj_inst:
        return adj_deg, adj_inst, gpa, year
    return core, '', gpa, year


_DEGREE_LEAD_SPLIT = re.compile(
    r'(?i)^('
    r'(?:Bachelor(?:\'?s)?|Master(?:\'?s)?|Associate(?:\'?s)?)'
    r'(?:\s+of(?:\s+(?:Arts|Science|Commerce|Engineering|Technology|Business|Education))?)?'
    r'(?:\s+in\s+[A-Za-z &\-/]{2,40})?'
    r'|B\.?\s?E\.?(?:\s+in\s+[A-Za-z &\-/]{2,40})?'
    r'|B\.?\s?Tech(?:\s+in\s+[A-Za-z &\-/]{2,40})?'
    r'|M\.?\s?Tech(?:\s+in\s+[A-Za-z &\-/]{2,40})?'
    r'|B\.?\s?Sc(?:\s+in\s+[A-Za-z &\-/]{2,40})?'
    r')\s+(.+)$'
)


def _split_adjacent_degree_institution(line: str) -> tuple[str, str]:
    """Split unlabeled 'Degree Institution' when the tail has institution evidence."""
    s = (line or '').strip()
    if not s:
        return '', ''
    m = _DEGREE_LEAD_SPLIT.match(s)
    if not m:
        return '', ''
    degree, rest = m.group(1).strip(), m.group(2).strip()
    rest = re.sub(r'(?i)\b(?:in\s+the\s+year\s+)?(?:19|20)\d{2}\b', '', rest).strip(' ,.-')
    if not rest or len(rest.split()) < 1:
        return '', ''
    if _INSTITUTION_CUE.search(rest) or is_institution_like(rest):
        return degree, rest
    return '', ''


_EDUCATION_KEEP_LABELS = frozenset({
    'education',
    'academic background',
    'academic qualifications',
    'academic qualification',
    'academic details',
    'academics',
    'qualifications',
    'qualification',
    'educational qualifications',
    'educational qualification',
    'educational background',
})
# Stop Education only when the next span is a real sibling section that
# historically leaked into Institution (Experience / Skills / Projects / …).
# Personal Details often carries leftover degree lines — do not cut those.
_EDUCATION_STOP_LABELS = frozenset({
    'experience',
    'work experience',
    'professional experience',
    'technical experience',
    'employment',
    'work history',
    'skills',
    'technical skills',
    'key skills',
    'projects',
    'project experience',
    'certifications',
    'certificates',
    'summary',
    'professional summary',
    'objective',
    'professional objective',
    'career objective',
    'declaration',
})


def _is_foreign_education_heading(line: str) -> bool:
    """True when a sibling section starts inside an Education span."""
    try:
        from app.ai.parser.layout.heuristic import (
            normalize_section_header,
            split_glued_heading_line,
        )
    except Exception:
        normalize_section_header = None  # type: ignore[assignment]
        split_glued_heading_line = None  # type: ignore[assignment]
    label = ''
    if split_glued_heading_line:
        glued, _rest = split_glued_heading_line(line)
        if glued:
            label = glued.strip().lower()
    if not label and normalize_section_header:
        label = (normalize_section_header(line) or '').strip().lower()
    if not label and is_section_header_line(line):
        label = re.sub(r'^[\s#*•\-]+|[\s#:]+$', '', line.strip()).strip().lower()
    if not label:
        return False
    if label in _EDUCATION_KEEP_LABELS:
        return False
    return label in _EDUCATION_STOP_LABELS


def _looks_like_institution_line(line: str) -> bool:
    s = (line or '').strip()
    if not s or len(s) < 4:
        return False
    if is_labeled_contact_metadata(s):
        return False
    # Combined "Degree: University" / "Degree from University" is not institution-only.
    if _looks_like_degree_line(s):
        return False
    if _INSTITUTION_CUE.search(s) or is_institution_like(s):
        return True
    if re.search(r'[-–—]\s*[A-Za-z].{2,40}$', s) and extract_date_range(s)[0]:
        return True
    return False


def _education_field_is_junk(value: str) -> bool:
    s = (value or '').strip().lstrip(':').strip()
    if not s:
        return True
    if re.match(r'(?i)^(?:the\s+)?(?:university|institute|college|school)(?:\s+of)?$', s):
        return True
    if re.match(r'(?i)^(?:university|institute|college|school)\s*,\s*[A-Za-z]', s):
        return True
    if is_biodata_or_address_line(value) or is_biodata_or_address_line(s):
        return True
    if looks_like_email_or_url(s) or looks_like_phone_token(s):
        return True
    if '@' in s:
        return True
    return False


def _sanitize_education_row(row: EducationEntry) -> EducationEntry | None:
    """Drop biodata/contact crumbs; keep rows with a degree or institution cue."""
    deg = (row.degree or '').strip().lstrip(':').strip()
    inst = (row.institution or '').strip().lstrip(':').strip()
    if _education_field_is_junk(deg):
        deg = ''
    if _education_field_is_junk(inst):
        inst = ''
    if not deg and not inst:
        return None
    if deg and not _looks_like_degree_line(deg) and not (
        inst and (_looks_like_institution_line(inst) or _INSTITUTION_CUE.search(inst))
    ):
        return None
    if inst and not deg and not (
        _looks_like_institution_line(inst) or _INSTITUTION_CUE.search(inst)
    ):
        return None
    if deg == (row.degree or '').strip() and inst == (row.institution or '').strip():
        return row
    return row.model_copy(update={'degree': deg[:200], 'institution': inst[:200]})


def _filter_education_rows(rows: list[EducationEntry]) -> list[EducationEntry]:
    out: list[EducationEntry] = []
    for row in rows:
        cleaned = _sanitize_education_row(row)
        if cleaned is not None:
            out.append(cleaned)
    return out


def _unbalanced_open_paren(text: str) -> bool:
    s = text or ''
    return s.count('(') > s.count(')')


def _hyphen_is_inside_parens(text: str) -> bool:
    """True when every hyphen sits inside a parenthetical (not a degree–school sep)."""
    depth = 0
    outside = False
    for ch in text or '':
        if ch == '(':
            depth += 1
        elif ch == ')':
            depth = max(0, depth - 1)
        elif ch in '-–—' and depth == 0:
            outside = True
    return (not outside) and ('-' in (text or '') or '–' in (text or '') or '—' in (text or ''))


def _is_education_continuation(prev: str, nxt: str) -> bool:
    """True when nxt is a PDF wrap continuation of the previous institution line."""
    n = (nxt or '').strip()
    p = (prev or '').strip()
    if not n or not p:
        return False
    if _SCHOOL_LEVEL_HEADING.match(n.lstrip(':').strip()):
        return False
    if re.match(r'(?i)^(grade|cgpa|gpa|percentage|score)\s*:', n):
        return False
    if _GPA_ONLY_LINE.match(n) or _FIELD_ONLY_LINE.match(n):
        return False
    if _PURSUING_LINE.match(n) or _DATE_ONLY_LINE.match(n):
        return False
    if _EDU_DUTY_LINE.match(n) or _DUTY_VERB_START.match(n):
        return False
    if _has_job_title_cue(n) and not _looks_like_degree_line(n):
        return False
    # Wrapped degree: "Ph.D. (Pursuing" + "I.T.)"
    if _unbalanced_open_paren(p) and n.count(')') >= n.count('('):
        return True
    # Degree + a line that is itself an institution cue word (wrapped "University")
    if _looks_like_degree_line(p) and not _looks_like_degree_line(n):
        if _is_foreign_education_heading(n) or is_section_header_line(n):
            return False
        if len(n.split()) == 1 and _INSTITUTION_CUE.search(n):
            return True
        if (
            p.rstrip().endswith(
                ('Higher', 'of', 'and', 'the', 'from', 'College', 'School',
                 'Technological')
            )
            and _INSTITUTION_CUE.search(n)
        ):
            return True
        return False
    if _looks_like_degree_line(n):
        return False
    # Institution fragment + University/College
    if (
        not _looks_like_degree_line(p)
        and n[0].isupper()
        and len(p.split()) <= 4
        and len(n.split()) <= 4
        and (_INSTITUTION_CUE.search(n) or _INSTITUTION_CUE.search(p))
        and not extract_date_range(n)[0]
        and not is_section_header_line(n)
    ):
        return True
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


def _degree_family(degree: str) -> str:
    """Collapse common Indian/US degree spellings so stacked rows can merge."""
    s = re.sub(r'[^a-z0-9]', '', (degree or '').lower())
    s = s.replace('degree', '')
    if not s:
        return ''
    if s in {'be', 'beng'} or s.startswith('bachelorofeng') or s.startswith('bachelorsofeng'):
        return 'be'
    if s in {'btech'} or s.startswith('bacheloroftech') or s.startswith('bachelorsoftech'):
        return 'btech'
    if s in {'hsc', 'xii', '12th', '12thpassed'} or 'highersecondary' in s:
        return 'hsc'
    if s in {'ssc', 'x', '10th', '10thpassed'} or s.startswith('secondaryschool'):
        return 'ssc'
    return s


def _prefer_expanded_degree(a: str, b: str) -> str:
    a, b = (a or '').strip(), (b or '').strip()
    if not a:
        return b
    if not b:
        return a
    # Prefer "Bachelor of Engineering" over "B.E DEGREE"
    a_exp = bool(re.search(r'(?i)\b(?:bachelor|master|diploma)\b', a))
    b_exp = bool(re.search(r'(?i)\b(?:bachelor|master|diploma)\b', b))
    if b_exp and not a_exp:
        return b
    if a_exp and not b_exp:
        return a
    return a if len(a) >= len(b) else b


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
                nxt_school = bool(_SCHOOL_LEVEL_HEADING.match(n_deg.lstrip(':')))
                cur_tertiary = bool(
                    re.search(r'(?i)\b(?:university|college|institute)\b', cur_inst)
                    and not re.search(r'(?i)\b(?:school|vidyalaya|board)\b', cur_inst)
                )
                if nxt_school and cur_tertiary:
                    merged.append(cur)
                    i += 1
                    continue
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
                # Wrapped parenthetical field, not a school: "Ph.D. (Pursuing" + "I.T.)"
                if _unbalanced_open_paren(cur_deg) and (
                    ')' in n_inst or n_inst[:1].islower()
                ):
                    combined = f'{cur_deg} {n_inst}'.strip()
                    merged.append(
                        EducationEntry(
                            degree=combined[:200],
                            field=cur.field or nxt.field,
                            institution='',
                            gpa=cur.gpa or nxt.gpa,
                            start=cur.start or nxt.start,
                            end=cur.end or nxt.end,
                        )
                    )
                    i += 2
                    continue
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
            # Stacked "B.E DEGREE" + institution then "Bachelor of Engineering" + field
            if (
                cur_deg
                and n_deg
                and _degree_family(cur_deg)
                and _degree_family(cur_deg) == _degree_family(n_deg)
            ):
                inst = cur_inst or n_inst
                merged.append(
                    EducationEntry(
                        degree=_prefer_expanded_degree(cur_deg, n_deg)[:200],
                        field=cur.field or nxt.field,
                        institution=inst[:200],
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
    return _filter_education_rows(_merge_equivalent_degree_rows(merged))


def _merge_equivalent_degree_rows(rows: list[EducationEntry]) -> list[EducationEntry]:
    """Join 'B.E DEGREE' + college with a following 'Bachelor of Engineering' row."""
    if len(rows) < 2:
        return rows
    out: list[EducationEntry] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt:
            fam = _degree_family(cur.degree)
            if fam and fam == _degree_family(nxt.degree):
                cur_inst = (cur.institution or '').strip()
                n_inst = (nxt.institution or '').strip()
                different_schools = bool(
                    cur_inst
                    and n_inst
                    and cur_inst.lower() not in n_inst.lower()
                    and n_inst.lower() not in cur_inst.lower()
                )
                if not different_schools:
                    out.append(
                        EducationEntry(
                            degree=_prefer_expanded_degree(cur.degree, nxt.degree)[:200],
                            field=cur.field or nxt.field,
                            institution=(cur_inst or n_inst)[:200],
                            gpa=cur.gpa or nxt.gpa,
                            start=cur.start or nxt.start,
                            end=cur.end or nxt.end,
                        )
                    )
                    i += 2
                    continue
        out.append(cur)
        i += 1
    return out


_EDU_LINE_PREFIX = re.compile(
    r'^[\s•·\-\*●▪▸►✓✔▶►◆◇○●]+'
)


def _clean_edu_line(line: str) -> str:
    s = _EDU_LINE_PREFIX.sub('', (line or '').strip())
    return s.lstrip(':').strip()


def _unlabeled_education_window(full_text: str) -> str:
    """Collect degree + institution blocks when Education is a footer-only header."""
    if not full_text:
        return ''
    lines = [_clean_edu_line(ln) for ln in full_text.splitlines()]
    chunks: list[str] = []
    i = 0
    while i < len(lines):
        s = lines[i]
        if (
            s
            and _looks_like_degree_line(s)
            and not is_section_header_line(s)
            and not is_biodata_or_address_line(s)
            and s.count('|') < 2
            and '@' not in s
            and 'http' not in s.lower()
            and len(s) <= 120
        ):
            block = [s]
            j = i + 1
            while j < len(lines) and j <= i + 4:
                n = lines[j]
                if not n or is_section_header_line(n):
                    break
                if _looks_like_degree_line(n) and j > i:
                    break
                if (
                    _looks_like_institution_line(n)
                    or extract_date_range(n)[0]
                    or re.search(r'(?i)\b(?:grade|cgpa|gpa|university|board|college|session)\b', n)
                    or '|' in n
                ):
                    block.append(n)
                    j += 1
                    continue
                break
            if len(block) >= 2:
                chunks.extend(block)
            elif (
                _INSTITUTION_CUE.search(s)
                or is_institution_like(s)
                or (',' in s and _looks_like_degree_line(s))
            ):
                chunks.append(s)
            i = max(j, i + 1)
            continue
        # Institution then degree (two-column / header-above-name CVs)
        if (
            s
            and _looks_like_institution_line(s)
            and not _looks_like_degree_line(s)
            and not is_section_header_line(s)
            and i + 1 < len(lines)
            and _looks_like_degree_line(lines[i + 1])
        ):
            block = [s, lines[i + 1]]
            j = i + 2
            if j < len(lines) and (
                extract_date_range(lines[j])[0]
                or re.search(r'(?i)\b(?:grade|cgpa|session|graduated)\b', lines[j] or '')
            ):
                block.append(lines[j])
                j += 1
            chunks.extend(block)
            i = j
            continue
        i += 1
    return '\n'.join(chunks)


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
            extracted = coalesce_education(out)
            if any((e.degree or '').strip() and (e.institution or '').strip() for e in extracted):
                return extracted
            body = _unlabeled_education_window(full_text)
            if body:
                return parse_education(body, '')
            return extracted

    identity = (extract_name_from_text(full_text) or '').strip().lower() if full_text else ''

    lines = []
    for line in raw.splitlines():
        stripped = _clean_edu_line(line)
        if not stripped:
            continue
        if _is_foreign_education_heading(stripped):
            break
        if is_section_header_line(stripped):
            continue
        if is_biodata_or_address_line(stripped) or looks_like_email_or_url(stripped):
            continue
        if is_labeled_contact_metadata(stripped):
            continue
        if identity and stripped.lower() == identity:
            continue
        if looks_like_phone_token(stripped):
            continue
        # Experience bullets leak into education when section bounds are weak
        if _EDU_DUTY_LINE.match(stripped) or _DUTY_VERB_START.match(stripped):
            continue
        if _NUMBERED_DUTY_LINE.match(stripped) and not _SCHOOL_LEVEL_HEADING.match(stripped):
            continue
        if stripped[:1].islower() and not _INSTITUTION_CUE.search(stripped) and not _looks_like_degree_line(stripped):
            continue
        # Internships / job headers belong in Experience, not Education
        if _has_job_title_cue(stripped) and not _looks_like_degree_line(stripped):
            continue
        if re.match(r'(?i)^(grade|cgpa|gpa|percentage|score|aggregate)\s*[:\-–—]?', stripped):
            lines.append(stripped)
            continue
        lines.append(stripped)
    lines = _join_wrapped_education_lines(lines)

    table_rows = _parse_pipe_education_table(lines)
    if table_rows and len(table_rows) >= 1:
        return coalesce_education(table_rows)

    education: list[EducationEntry] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if _PURSUING_LINE.match(line):
            if education:
                prev = education[-1]
                education[-1] = prev.model_copy(update={'end': prev.end or 'Present'})
            i += 1
            continue
        gpa_only = _GPA_ONLY_LINE.match(line)
        if gpa_only:
            if education:
                prev = education[-1]
                education[-1] = prev.model_copy(update={'gpa': prev.gpa or gpa_only.group(1).strip()})
            i += 1
            continue
        field_only = _FIELD_ONLY_LINE.match(line)
        if field_only:
            if education:
                prev = education[-1]
                education[-1] = prev.model_copy(
                    update={'field': prev.field or field_only.group(1).strip()}
                )
            i += 1
            continue
        start, end = extract_date_range(line)
        if start and not end:
            # A lone education year is year-of-passing, not a start date.
            end, start = start, ''
        year_only_core, year_only = peel_education_date_phrase(line)
        is_year_only = bool(
            _DATE_ONLY_LINE.match(line)
            or (year_only and not year_only_core)
        )
        if education and is_year_only and (
            start or end or re.search(r'(?:19|20)\d{2}', line)
        ):
            if not start and not end:
                peeled = normalize_month_token(line.strip())
                if peeled and peeled.lower() != line.strip().lower():
                    end = peeled
                elif re.fullmatch(r'(?:19|20)\d{2}', line.strip()):
                    end = line.strip()
            prev = education[-1]
            education[-1] = prev.model_copy(
                update={
                    'start': prev.start or start,
                    'end': prev.end or end or (start if not end else end),
                }
            )
            i += 1
            continue
        line_wo_dates = _DATE_RANGE_STRIP.sub('', line).strip(' \t|-–—,') if start else line
        line_wo_dates, row_gpa, row_year = _peel_education_meta(line_wo_dates)
        if row_year and not end:
            end = row_year

        institution = ''
        degree = ''
        field = ''
        gpa = row_gpa
        if line_wo_dates:
            peeled_deg, peeled_field = _degree_bracket_field(line_wo_dates)
            if peeled_field:
                field = peeled_field
                line_wo_dates = peeled_deg

        # Table / KV rows: "B.Tech | XYZ College | 2024" or tab-separated
        if '|' in line_wo_dates or '\t' in line_wo_dates:
            parts = [p.strip() for p in re.split(r'[|\t]', line_wo_dates) if p.strip()]
            headerish = {p.lower().rstrip(':') for p in parts}
            if headerish & {
                'degree',
                'institution',
                'university',
                'college',
                'year',
                'board',
                'percentage',
                'cgpa',
            }:
                i += 1
                continue
            if len(parts) >= 2:
                left, right = parts[0], parts[1]
                right_is_meta = bool(
                    re.match(r'(?i)^(grade|cgpa|gpa|percentage|score)\b', right)
                    or re.fullmatch(
                        r'(?:19|20)\d{2}(?:\s*[-–—]\s*(?:19|20)\d{2}|Present|Current)?',
                        right,
                    )
                    or (extract_date_range(right)[0] and not _INSTITUTION_CUE.search(right))
                )
                if right_is_meta:
                    # "B.Sc. in IT (BSc.IT), Khalsa College, Mumbai | 2025"
                    # Year/GPA already peeled; remaining left is still a one-liner.
                    d2, i2, g2, y2 = split_education_oneliner(left)
                    if d2 and i2:
                        degree, institution = d2, i2
                        gpa = gpa or g2
                        if y2 and not end:
                            end = y2
                    elif _looks_like_degree_line(left) or _DEGREE_PAT.search(left):
                        degree, institution = left, ''
                    else:
                        institution, degree = left, ''
                    if degree or institution:
                        education.append(
                            EducationEntry(
                                degree=degree[:200],
                                field=field,
                                institution=institution[:200],
                                gpa=gpa,
                                start=start,
                                end=end,
                            )
                        )
                        i += 1
                        continue
                if _looks_like_degree_line(left) or _DEGREE_PAT.search(left):
                    degree, institution = left, right
                elif _looks_like_degree_line(right) or _DEGREE_PAT.search(right):
                    institution, degree = left, right
                elif is_institution_like(right) or _INSTITUTION_CUE.search(right):
                    if _has_job_title_cue(left) and not _looks_like_degree_line(left):
                        i += 1
                        continue
                    degree, institution = left, right
                else:
                    if _has_job_title_cue(left) and not _looks_like_degree_line(left):
                        i += 1
                        continue
                    degree, institution = left, right
                if degree or institution:
                    education.append(
                        EducationEntry(
                            degree=degree[:200],
                            field=field,
                            institution=institution[:200],
                            gpa=gpa,
                            start=start,
                            end=end,
                        )
                    )
                    i += 1
                    continue

        # Compact one-liners: degree + college + city + year/CGPA
        if not institution and not degree and _DEGREE_PAT.search(line_wo_dates):
            d2, i2, g2, y2 = split_education_oneliner(line_wo_dates)
            if d2 and i2:
                degree, institution = d2, i2
                gpa = gpa or g2
                if y2 and not end:
                    end = y2
                i += 1
                education.append(
                    EducationEntry(
                        degree=degree[:200],
                        field=field,
                        institution=institution[:200],
                        gpa=gpa,
                        start=start,
                        end=end,
                    )
                )
                continue

        # Prefer splitting "B.com – SV University" before institution-only classification
        if (
            not institution
            and not degree
            and re.search(r'[-–—]', line_wo_dates)
            and _DEGREE_PAT.search(line_wo_dates)
            and not _hyphen_is_inside_parens(line_wo_dates)
        ):
            parts = re.split(r'\s*[-–—]\s*', line_wo_dates, maxsplit=1)
            if len(parts) == 2 and _looks_like_degree_line(parts[0]) and (
                _INSTITUTION_CUE.search(parts[1])
                or is_institution_like(parts[1])
                or (
                    len(parts[1].strip()) >= 4
                    and not re.match(r'(?i)^[A-Z]\.?[A-Z]\.?\)?$', parts[1].strip())
                )
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
                        gpa=gpa,
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
        if (degree and not institution) or (institution and not degree):
            blob = degree or institution
            d2, i2, g2, y2 = split_education_oneliner(blob)
            if d2 and i2:
                degree, institution = d2, i2
                gpa = gpa or g2
                if y2 and not end:
                    end = y2

        # Compact "B.com – SV University, Tirupathi" one-liners (fallback)
        if (
            degree
            and not institution
            and re.search(r'[-–—]', degree)
            and not _hyphen_is_inside_parens(degree)
        ):
            parts = re.split(r'\s*[-–—]\s*', degree, maxsplit=1)
            if len(parts) == 2 and _looks_like_degree_line(parts[0]) and (
                _INSTITUTION_CUE.search(parts[1])
                or is_institution_like(parts[1])
                or (
                    len(parts[1].strip()) >= 4
                    and not re.match(r'(?i)^[A-Z]\.?[A-Z]\.?\)?$', parts[1].strip())
                )
            ):
                degree, institution = parts[0].strip(), parts[1].strip()
        degree = re.sub(r'^[:\-–—\s]+', '', degree or '').strip()
        institution = re.sub(r'^[:\-–—\s]+', '', institution or '').strip()
        if degree or institution:
            # Drop duty / project lines that slipped through
            blob = f'{degree} {institution}'.strip()
            if _EDU_DUTY_LINE.match(blob) or _DUTY_VERB_START.match(blob) or (
                len(blob) > 80
                and not _DEGREE_PAT.search(blob)
                and not _INSTITUTION_CUE.search(blob)
            ):
                continue
            if (
                (_has_job_title_cue(degree) and not _looks_like_degree_line(degree))
                or (_has_job_title_cue(institution) and not _INSTITUTION_CUE.search(institution))
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
            if re.match(
                r'(?i)^(?:ms\s*-?\s*word|ms\s*-?\s*excel|ms\s*-?\s*office|seo|powerpoint)\b',
                degree,
            ) and not _INSTITUTION_CUE.search(institution):
                continue
            if re.match(r'(?i)^(?:soft\s+skills?|technical\s+skills?|skills?)\s*:?\s*$', institution):
                institution = ''
            education.append(
                EducationEntry(
                    degree=degree[:200],
                    field=field,
                    institution=institution[:200],
                    gpa=gpa,
                    start=start,
                    end=end,
                )
            )
    education = _filter_education_rows(coalesce_education(education))
    has_keepable = any(
        (e.degree or '').strip() or (e.institution or '').strip() for e in education
    )
    complete = sum(
        1
        for e in education
        if (e.degree or '').strip() and (e.institution or '').strip()
    )
    if complete == 0 and full_text and not has_keepable:
        body = _unlabeled_education_window(full_text)
        if body and body.strip() != (section_text or '').strip():
            extra = parse_education(body, '')
            extra_ok = [
                e
                for e in extra
                if (e.degree or '').strip() or (e.institution or '').strip()
            ]
            if extra_ok:
                return extra
        # Short/header-only Education must not discard document evidence
        if (section_text or '').strip():
            recovered = parse_education('', full_text)
            if any((e.degree or '').strip() or (e.institution or '').strip() for e in recovered):
                return recovered
    return education


_LABELED_SKILL_LINE_RE = re.compile(
    r'(?im)^(?:\*\*)?(?:(?:other\s+)?(?:technical|key|core|soft|professional|relevant)\s+)?'
    r'(?:skills?|skill\s*sets?|technologies|tech\s+stack|tools?|competencies|'
    r'databases?|operating\s+systems?|cloud\s+platforms?|monitoring(?:\s+tools?)?|'
    r'scripting|frameworks?)'
    r'(?:\*\*)?\s*:\s*(.+)$'
)


def _labeled_skill_values(full_text: str) -> list[str]:
    """Collect values from clearly labeled skill lines only — never prose."""
    out: list[str] = []
    for match in _LABELED_SKILL_LINE_RE.finditer(full_text or ''):
        value = (match.group(1) or '').strip()
        if not value:
            continue
        if is_section_header_line(value) or is_labeled_contact_metadata(value):
            continue
        if re.match(r'(?i)^(?:place|location|address|signature|declaration)\b', value):
            continue
        out.extend(split_list_items(value))
    return out


def parse_skills(section_text: str, full_text: str = '') -> list[SkillEntry]:
    from app.ai.document_intelligence.bullets import split_inline_bullets
    from app.ai.parser.enrichment.resume_text_inference import skill_item_looks_like_prose

    raw = split_inline_bullets(section_text or '').strip()
    identity = (extract_name_from_text(full_text) or '').strip().lower() if full_text else ''
    identity_names = document_identity_names(full_text) if full_text else set()
    if identity:
        identity_names.add(identity)
    raw = re.sub(
        r'(?i)^(?:technical\s+)?skills?(?!\w)(?:\s*,?\s*(?:tools?|platforms?|abilities|technologies?))*(?:\s+and\s+(?:tools?|platforms?|abilities|technologies?))*\s*:?\s*',
        '',
        raw,
    ).strip()
    raw = re.sub(
        r'(?i)^(?:technical\s+proficiency|technical\s+expertise|technical\s+knowledge|'
        r'technicalskill|soft\s+skills?|'
        r'core\s+competencies|areas\s+of\s+expertise|computer\s+skills|it\s+skills|'
        r'software\s+skills)\s*:?\s*',
        '',
        raw,
    ).strip()
    # Drop leftover header crumbs from "SKILLS, TOOLS AND PLATFORMS"
    raw = re.sub(
        r'(?i)^(?:tools?|platforms?|abilities|technologies?)(?:\s+and\s+(?:tools?|platforms?|abilities))?\s*:?\s*',
        '',
        raw,
    ).strip()
    if re.fullmatch(r'(?i)s|set|skills?', raw):
        raw = ''

    filtered_lines: list[str] = []
    for ln in raw.splitlines():
        s = re.sub(r'^[\s•·\-\*●]+', '', ln.strip())
        if not s:
            continue
        if is_labeled_contact_metadata(s):
            continue
        if re.match(r'(?i)^(?:signature|declaration|date)\s*:?\s*$', s):
            continue
        if re.match(r'.{2,40}:\s*$', s):
            continue
        if identity and s.lower() == identity:
            continue
        if identity_matches_person(s.strip('() '), identity_names):
            continue
        cat = re.match(
            r'^(.{2,40}?)\s*:\s+(.+)$',
            s,
        )
        if cat and skill_item_looks_like_prose(cat.group(2).strip()):
            left = cat.group(1).strip()
            if 1 <= len(left.split()) <= 5 and not is_labeled_contact_metadata(left):
                filtered_lines.append(left)
                continue
        filtered_lines.append(ln)
    raw = '\n'.join(filtered_lines).strip()
    from app.ai.parser.enrichment.resume_text_inference import clip_skills_section_at_prose

    raw, _peeled_skills_prose = clip_skills_section_at_prose(raw)

    def _accepted(name: str) -> SkillEntry | None:
        s = (name or '').strip()
        s = re.sub(r'^[\s:•·\-\*●▪▸►✓✔☑]+', '', s).strip()
        s = re.sub(r'[\s:•·\-\*●]+$', '', s).strip()
        if not s:
            return None
        if re.fullmatch(
            r'(?i)(?:(?:technical\s+)?skills?|technical\s+skills?|skill\s*sets?|'
            r'databases?(?:\s*tools?)?|(?:programming\s+|spoken\s+)?languages?|'
            r'operating\s*systems?|tools?|os|'
            r'frameworks?|technologies?|software|special\s+software|'
            r'cloud\s+platforms?|scripting)',
            s,
        ):
            return None
        if identity and s.lower() == identity:
            return None
        if identity_matches_person(s.strip('() '), identity_names):
            return None
        if is_labeled_contact_metadata(s):
            return None
        if re.match(r'(?i)^(?:signature|declaration|date)\s*:?\s*$', s):
            return None
        ok, _ = validate_skill_item(s)
        if not ok:
            return None
        return SkillEntry(name=s, canonical=s)

    if not raw and full_text:
        from app.ai.parser.enrichment.resume_text_inference import extract_skills_from_text

        recovered = [
            entry
            for s in extract_skills_from_text(full_text, allow_unlabeled_lists=False)
            if (entry := _accepted(s))
        ]
        if recovered:
            return recovered
    items = filter_skill_items(split_list_items(raw), max_items=40)
    out: list[SkillEntry] = []
    seen: set[str] = set()
    for s in items:
        entry = _accepted(s)
        if not entry:
            continue
        key = entry.name.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(entry)
    # Supplement from labeled Technical Skills / Key Skills lines only.
    # Never harvest duty prose, Place/Location, or identity lines.
    if full_text:
        extras = _labeled_skill_values(full_text)
        if not extras and not out:
            from app.ai.parser.enrichment.resume_text_inference import extract_skills_from_text

            extras = extract_skills_from_text(full_text, allow_unlabeled_lists=False)
        for s in extras:
            entry = _accepted(s)
            if not entry:
                continue
            key = entry.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
            if len(out) >= 40:
                break
    if not out and full_text:
        from app.ai.parser.enrichment.resume_text_inference import extract_skills_from_text

        recovered = [
            entry
            for s in extract_skills_from_text(full_text, allow_unlabeled_lists=False)
            if (entry := _accepted(s))
        ]
        for entry in recovered:
            key = entry.name.strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(entry)
            if len(out) >= 40:
                break
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
            if is_document_title_line(cand):
                continue
            if re.search(
                r'(?i)\b(?:b\.?\s*tech|m\.?\s*tech|btech|bachelor|diploma|mba|mca|bca)\b',
                cand,
            ):
                continue
            if is_plausible_person_name(cand):
                name = cand.title() if cand.isupper() else cand
                break
    file_name = name_from_resume_filename(source_filename) if source_filename else ''
    name_source = 'deterministic' if name else ''
    # Filename is lowest-confidence evidence. Never override document text.
    if file_name and not name:
        name = file_name
        name_source = 'filename'
    if name and not is_plausible_person_name(name):
        name = ''
        name_source = ''
    if name:
        name = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', name).strip()
        if name.isupper() and len(name.split()) >= 2:
            name = name.title()
    ok, _ = validate_person_name(name) if name else (False, '')
    # If DI validator is stricter than plausible-name check, still keep plausible names
    if name and not ok and is_plausible_person_name(name):
        ok = True
    summary = extract_summary_from_text(text)
    info = PersonalInfo(full_name=name if ok else '', summary=summary)
    # Stash source for merge_resume_sections without changing the PersonalInfo schema
    info._name_source = name_source if ok else ''  # type: ignore[attr-defined]
    return info


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
    """True when the *header* is a project listing, not a real job.

    Duty text often contains 'Client Name/Projects:' or 'academic project' as
    metadata on a genuine job — never scan description for that reason.
    """
    header = f'{role} {company}'.strip()
    if header and _PROJECT_LIKE_EXP.search(header):
        return True
    if not header and description:
        return bool(_PROJECT_LIKE_EXP.search(description.split('\n', 1)[0]))
    return False


def _has_job_title_cue(text: str) -> bool:
    return bool(_JOB_TITLE_CUE.search((text or '').strip()))


def _looks_like_job_location_line(text: str) -> bool:
    """City / multi-city job locations, including 'Thane , Navi Mumbai'."""
    t = re.sub(r'\s+', ' ', (text or '').strip().rstrip('.'))
    if not t:
        return False
    if _CITY_LIKE.match(t) or _CITY_PIN_LINE.match(t):
        return True
    if re.search(r'\b[1-9]\d{5}\b', t):
        city_only = re.sub(r'\s*\b[1-9]\d{5}\b', '', t).strip(' ,.')
        if city_only and (_CITY_LIKE.match(city_only) or _CITY_PIN_LINE.match(f'{city_only} 400001')):
            return True
    parts = [p.strip() for p in re.split(r'\s*,\s*', t) if p.strip()]
    if 2 <= len(parts) <= 3 and all(_CITY_LIKE.match(p) for p in parts):
        return True
    if (
        2 <= len(parts) <= 3
        and any(_CITY_LIKE.match(p) for p in parts)
        and not re.search(r'(?i)\b(?:ltd|inc|pvt|llc|limited|technologies|solutions)\b', t)
    ):
        if len(parts) == 2:
            left, right = parts[0], parts[1]
            if _CITY_LIKE.match(right) and not _CITY_LIKE.match(left):
                if (
                    len(left.split()) >= 2
                    or re.search(
                        r'(?i)\b(?:consultancy|consulting|services|labs|systems|bank)\b',
                        left,
                    )
                    or (len(left) >= 4 and left.isupper())
                ):
                    return False
        return True
    return False


def _split_employer_city_line(text: str) -> tuple[str, str] | None:
    """``Employer Name, City`` / ``Employer Name | City`` — not a location-only line."""
    s = (text or '').strip()
    sep = None
    if '|' in s and s.count('|') == 1:
        sep = '|'
    elif ',' in s:
        sep = ','
    if sep is None:
        return None
    left, right = s.split(sep, 1)
    left, right = left.strip(), right.strip()
    if not left or not right or len(left.split()) > 6:
        return None
    if not (_CITY_LIKE.match(right) or _looks_like_job_location_line(right)):
        return None
    if _CITY_LIKE.match(left) or _has_job_title_cue(left):
        return None
    if left[:1].islower() or _looks_like_degree_line(left):
        return None
    if is_section_header_line(left):
        return None
    return left, right


def _is_employment_date_carrier(text: str) -> bool:
    """True when a line's job is to carry dates (Tenure:/Client:/date-only)."""
    s = re.sub(r'^[\s•·\-\*●]+', '', (text or '').strip())
    if not s:
        return False
    start, _end = extract_date_range(s)
    if not start:
        return False
    leftover = _identity_leftover_after_dates(s)
    leftover = _DATE_CARRIER_PREFIX.sub('', leftover).strip(' \t|-–—,():')
    if not leftover or leftover.lower() in {
        'present', 'current', 'now', 'ongoing', 'till date', 'tilldate',
    }:
        return True
    if _EMPLOYMENT_DURATION_LABEL.match(s) or _DATE_CARRIER_PREFIX.match(s):
        return True
    if is_project_or_employment_meta_label(s):
        return True
    return False


def _looks_like_org_header(text: str) -> bool:
    s = (text or '').strip()
    if not s:
        return False
    return bool(
        re.search(
            r'(?i)\b(?:pvt\.?|ltd\.?|llc|inc|llp|corp|limited|private|'
            r'technologies|solutions|labs|systems|infotech|consult(?:ing|ancy)?|'
            r'services|enterprises|industries|holdings|group)\b',
            s,
        )
    )


def _classify_company_vs_role(left: str, right: str) -> tuple[str, str]:
    """Map two header fragments to (company, role) without assuming order."""
    a, b = (left or '').strip(), (right or '').strip()
    if not a:
        return b, ''
    if not b:
        return a, ''
    a_title = bool(_has_job_title_cue(a) or re.search(r'(?i)\bintern\b', a))
    b_title = bool(_has_job_title_cue(b) or re.search(r'(?i)\bintern\b', b))
    a_org = _looks_like_org_header(a) or (
        _looks_like_company_line(a) and not a_title
    )
    b_org = _looks_like_org_header(b) or (
        _looks_like_company_line(b) and not b_title
    )
    if a_title and not b_title:
        return b, a
    if b_title and not a_title:
        return a, b
    if a_org and b_title:
        return a, b
    if b_org and a_title:
        return b, a
    if a_org and not b_org:
        return a, b
    if b_org and not a_org:
        return b, a
    if a.isupper() and not b.isupper() and len(a.split()) <= 6:
        return a, b
    if b.isupper() and not a.isupper() and len(b.split()) <= 6:
        return b, a
    # Ambiguous two-part pipe: prefer Company | Role (Naukri / tables)
    return a, b


def _looks_like_company_line(text: str, *, identity_names: set[str] | None = None) -> bool:
    """Company/org line without a job-title cue (e.g. Infosenseglobal)."""
    raw = (text or '').strip()
    s = peel_inline_contact(raw).rstrip('.')
    pair = _split_employer_city_line(s)
    if pair:
        s = pair[0]
    if not s or len(s) > 80 or len(s.split()) > 6:
        return False
    if is_labeled_contact_metadata(raw) or is_labeled_contact_metadata(s):
        return False
    if identity_names and s.strip().lower() in identity_names:
        return False
    if raw.endswith('.') and len(s.split()) >= 4:
        return False
    if _has_job_title_cue(s) or _DUTY_VERB_START.match(s) or _CITY_LIKE.match(s):
        return False
    if _BARE_DUTY_HEADER.match(s) or _looks_like_job_location_line(s) or _LABELED_DUTY_LINE.match(s):
        return False
    if looks_like_phone_token(s) or looks_like_email_or_url(s) or looks_like_contact_person_line(s):
        return False
    if is_contact_or_reference_line(s):
        return False
    if extract_date_range(s)[0]:
        return False
    if re.fullmatch(r'\d+[./]?\d*', s):
        return False
    if re.search(r'(?i)\b(?:published|journals?|conferences?)\b', s) and not re.search(
        r'(?i)\b(?:pvt|ltd|llc|inc|llp|limited)\b',
        s,
    ):
        return False
    if s.lower().endswith((' in', ' of', ' /', '/')) and len(s.split()) <= 4:
        return False
    if _is_bullet_or_duty_line(s) or is_section_header_line(s):
        return False
    from app.ai.parser.enrichment.resume_text_inference import looks_like_skill_or_duration_company

    if looks_like_skill_or_duration_company(s):
        return False
    if is_project_or_employment_meta_label(s):
        return False
    if _looks_like_degree_line(s):
        return False
    if _INSTITUTION_CUE.search(s) and not re.search(
        r'(?i)\b(?:pvt|ltd|llc|inc|llp|limited|private)\b',
        s,
    ):
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


def _strip_date_range(text: str) -> str:
    return _DATE_RANGE_STRIP.sub('', text or '').strip(' |-–—,()')


_DATE_RANGE_TOKEN_CRUFT = re.compile(
    r'(?i)\b(?:'
    r'(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?'
    r'|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?'
    r'|(?:19|20)\d{2}'
    r'|present|current|now|ongoing|from|since|to|until|till|date'
    r')\b'
)


def _identity_leftover_after_dates(text: str) -> str:
    """Leftover identity after dates. Does not change global date stripping.

    ``extract_date_range`` already accepts ``9-May-2023`` / ``5-June-2024``.
    ``_DATE_RANGE_STRIP`` does not, so a date-only line would otherwise look
    like leftover identity and become a new first job.
    """
    s = (text or '').strip()
    leftover = _DATE_RANGE_STRIP.sub('', s).strip(' \t|-–—,()')
    if leftover and extract_date_range(s)[0]:
        cruft = _DATE_RANGE_TOKEN_CRUFT.sub('', leftover)
        cruft = re.sub(r'[\s|/\\,.\-–—()]+', ' ', cruft).strip()
        if (
            not cruft
            or cruft.lower() in {
                'present', 'current', 'now', 'ongoing', 'till date', 'tilldate',
            }
            or (
                len(cruft.split()) <= 1
                and not _has_job_title_cue(cruft)
                and not _looks_like_org_header(cruft)
            )
        ):
            return cruft
    return leftover


def _is_date_range_stub_text(text: str) -> bool:
    s = (text or '').strip()
    if not s or not extract_date_range(s)[0]:
        return False
    leftover = _identity_leftover_after_dates(s)
    return not leftover or leftover.lower() in {
        'present', 'current', 'now', 'ongoing', 'till date', 'tilldate',
    }


def _is_date_range_stub_entry(entry: ExperienceEntry) -> bool:
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    if company and _is_date_range_stub_text(company) and (
        not role or role.isdigit() or _is_date_range_stub_text(role)
    ):
        return True
    if company:
        return False
    if _is_date_range_stub_text(role):
        return True
    if role:
        return False
    return bool((entry.start or '').strip())


def _looks_like_role_only_line(text: str) -> bool:
    s = peel_inline_contact((text or '').strip())
    if not s or len(s.split()) > 8 or extract_date_range(s)[0]:
        return False
    if is_labeled_contact_metadata(text or '') or is_labeled_contact_metadata(s):
        return False
    if _DUTY_VERB_START.match(s) or _is_bullet_or_duty_line(s) or is_section_header_line(s):
        return False
    if is_project_or_employment_meta_label(s):
        return False
    if _BARE_DUTY_HEADER.match(s) or _CITY_LIKE.match(s) or _looks_like_job_location_line(s) or _LABELED_DUTY_LINE.match(s):
        return False
    if looks_like_contact_person_line(s) or is_contact_or_reference_line(s):
        return False
    if looks_like_phone_token(s) or looks_like_email_or_url(s):
        return False
    return _has_job_title_cue(s) or (
        is_plausible_job_title(s) and bool(re.search(r'(?i)\bintern\b', s))
    )


def _is_role_comma_company_header(text: str) -> bool:
    """True for 'Role, Company' / 'Role,Company' job headers (not duty prose)."""
    stripped = re.sub(r'^[\s•·\-\*●▪▸►]+', '', (text or '').strip())
    stripped = _strip_date_range(stripped).strip(' ,|-–—')
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
    # Optional city after the company: "Role, Acme Ltd, Mumbai"
    right_company = re.split(r',\s*', right, maxsplit=1)[0].strip()
    if len(left.split()) > 6 or not (1 <= len(right_company.split()) <= 8):
        return False
    # Duty sentences have many clauses / conjunctions on the right
    if re.search(r'(?i)\b(?:resulting|ensuring|improving|including|across|and|wrote|reported)\b', right):
        return False
    return True


_EMPLOYMENT_WITH_AS = re.compile(
    r'(?i)^(?:currently\s+)?(?:working|worked)\s+(?:with|at)\s+'
    r'(.+?)(?:\s*,\s*([^,]+?))?\s+as\s+(?:an?\s+)?(.+?)$'
)
_EMPLOYMENT_WITH_ORG_AS = re.compile(
    r'(?i)^(?:with|at)\s+(.+?)(?:\s*,\s*([A-Za-z][A-Za-z .]{1,28}))?\s+as\s+(?:an?\s+)?(.+)$'
)
_EMPLOYMENT_AS_FOR = re.compile(
    r'(?i)^(?:currently\s+)?(?:working|worked)\s+as\s+(?:an?\s+)?'
    r'(.+?)\s+(?:for|in|at)\s+(.+?)$'
)
_EMPLOYMENT_ORG_AS_ROLE = re.compile(
    r'(?i)^(.+?),\s*([A-Za-z][A-Za-z .]{1,28})\s+as\s+(?:an?\s+)?(.+?)$'
)
_EMPLOYMENT_FOR_ORG = re.compile(
    r'(?i)^(?:currently\s+)?(?:working|worked)\s+for\s+(.+?)$'
)


def _strip_employment_lead_in(line: str) -> str:
    return re.sub(r'^[\s•·\-\*●▪▸►]+', '', (line or '').strip())


def _accept_prose_employer(company: str) -> bool:
    """True when a working-as / in / at tail is an employer, not a workplace noun."""
    c = (company or '').strip(' .,')
    if not c or looks_like_skill_or_duration_company(c):
        return False
    if _CITY_LIKE.match(c) or _looks_like_job_location_line(c) or _CITY_PIN_LINE.match(c):
        return False
    if _NON_ORG_IN_TAIL.search(c):
        return False
    if re.search(
        r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|private|technologies|solutions|'
        r'infotech|systems|services)\b',
        c,
    ):
        return True
    if _looks_like_org_header(c):
        return True
    words = c.split()
    if 2 <= len(words) <= 5 and words[0][:1].isupper() and not _DUTY_VERB_START.match(c):
        return True
    return False


def _parse_employment_sentence(
    line: str,
    *,
    identity_names: set[str] | None = None,
) -> ExperienceEntry | None:
    """Parse one employment prose line into employer / role / dates.

    Understands working-with / working-as / at / for / from–to markers.
    Location tokens after the employer comma stay on location, not company.
    """
    raw = peel_inline_contact(_strip_employment_lead_in(line))
    if not raw or len(raw) < 8:
        return None
    start, end = extract_date_range(raw)
    is_current = bool(
        end and re.match(r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$', end)
    )
    if is_current:
        end = ''
    leftover = _DATE_RANGE_STRIP.sub('', raw).strip(' \t|-–—,')
    leftover = re.sub(r'(?i)^\s*since\s+', '', leftover).strip(' \t|-–—,')
    leftover = re.sub(
        r'(?i)\s+\b(?:experience|education|skills|projects?|certifications?)\s*$',
        '',
        leftover,
    ).strip(' \t|-–—,')
    leftover = re.sub(r'(?i)\s+\bfrom\s*$', '', leftover).strip(' \t|-–—,')
    leftover = leftover.lstrip(':').strip()
    if not leftover:
        return None

    company = ''
    role = ''
    loc = ''
    with_as = _EMPLOYMENT_WITH_AS.match(leftover)
    as_for = _EMPLOYMENT_AS_FOR.match(leftover)
    with_org_as = _EMPLOYMENT_WITH_ORG_AS.match(leftover)
    if with_as:
        company = (with_as.group(1) or '').strip(' ,')
        maybe_loc = (with_as.group(2) or '').strip(' ,')
        role = (with_as.group(3) or '').strip(' ,')
        if maybe_loc and (
            _CITY_LIKE.match(maybe_loc) or _looks_like_job_location_line(maybe_loc)
        ):
            loc = maybe_loc
        elif maybe_loc and not company:
            company = maybe_loc
        elif maybe_loc and company and not (
            _CITY_LIKE.match(maybe_loc) or _looks_like_job_location_line(maybe_loc)
        ):
            # Second clause is not a city — keep it off company unless it looks like an org
            if _INSTITUTION_CUE.search(maybe_loc) or re.search(
                r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|technologies)\b', maybe_loc
            ):
                company = f'{company} {maybe_loc}'.strip()
    elif as_for:
        role = (as_for.group(1) or '').strip(' ,')
        company = (as_for.group(2) or '').strip(' ,')
        if not (_has_job_title_cue(role) or is_plausible_job_title(role)):
            role, company = '', ''
            as_for = None
        elif not _accept_prose_employer(company.split(',')[0].strip()):
            role, company = '', ''
            as_for = None
        elif ',' in company:
            left, _, right = company.partition(',')
            right = right.strip()
            if right and (_CITY_LIKE.match(right) or _looks_like_job_location_line(right)):
                company, loc = left.strip(), right
    elif with_org_as:
        company = (with_org_as.group(1) or '').strip(' ,')
        maybe_loc = (with_org_as.group(2) or '').strip(' ,')
        role = (with_org_as.group(3) or '').strip(' ,.')
        if maybe_loc and (_CITY_LIKE.match(maybe_loc) or _looks_like_job_location_line(maybe_loc)):
            loc = maybe_loc
    else:
        org_as = _EMPLOYMENT_ORG_AS_ROLE.match(leftover)
        if org_as:
            maybe_co = (org_as.group(1) or '').strip(' ,')
            maybe_loc = (org_as.group(2) or '').strip(' ,')
            maybe_role = (org_as.group(3) or '').strip(' ,.')
            if (
                (_has_job_title_cue(maybe_role) or is_plausible_job_title(maybe_role))
                and (
                    re.search(r'(?i)\b(?:pvt|ltd|llc|inc|corp|limited|private)\b', maybe_co)
                    or _looks_like_company_line(maybe_co, identity_names=identity_names)
                )
            ):
                company, role = maybe_co, maybe_role
                if _CITY_LIKE.match(maybe_loc) or _looks_like_job_location_line(maybe_loc):
                    loc = maybe_loc
            else:
                org_as = None
        if not org_as:
            for_org = _EMPLOYMENT_FOR_ORG.match(leftover)
            if for_org and start:
                company = _DATE_RANGE_STRIP.sub('', for_org.group(1)).strip(' ,.')
                company = re.sub(r'(?i)\bfrom\s*$', '', company).strip(' ,.')
            else:
                since_m = re.match(
                    r'(?i)^(.{3,60}?)\s+(?:in\s+[A-Za-z][A-Za-z .]{1,32}\s+)?since\s+'
                    r'((?:19|20)\d{2})\b',
                    leftover,
                )
                if since_m:
                    maybe_role = since_m.group(1).strip(' ,')
                    year = since_m.group(2)
                    if _looks_like_role_only_line(maybe_role) or _has_job_title_cue(maybe_role):
                        if not start:
                            start = year
                        role = maybe_role
                    else:
                        return None
                else:
                    from_as = _FROM_COLON_ORG_AS.match(leftover) if start else None
                    if from_as:
                        maybe_co = (from_as.group(1) or '').strip(' ,')
                        maybe_role = (from_as.group(2) or '').strip(' ,.')
                        if ',' in maybe_co:
                            left, _, right = maybe_co.partition(',')
                            right = right.strip()
                            if right and (
                                _CITY_LIKE.match(right) or _looks_like_job_location_line(right)
                            ):
                                maybe_co, loc = left.strip(), right
                        if (
                            maybe_co
                            and maybe_role
                            and (_has_job_title_cue(maybe_role) or is_plausible_job_title(maybe_role))
                            and (
                                _accept_prose_employer(maybe_co)
                                or re.search(
                                    r'(?i)\b(?:pvt|ltd|llc|inc|limited|private)\b', maybe_co
                                )
                            )
                        ):
                            company, role = maybe_co, maybe_role
                        else:
                            return None
                    else:
                        return None

    if identity_is_employer_value(company, identity_names):
        company = ''
    if identity_is_employer_value(role, identity_names) and not _has_job_title_cue(role):
        role = ''
    role = re.sub(r'(?i)^(currently\s+)?(?:working|worked)\s+(?:with|at|as)\s+', '', role).strip()
    role = re.sub(r'(?i)\s+\bfrom\s*$', '', role).strip(' ,.')
    company = re.sub(r'(?i)[, ]*\bfrom\s*\.?$', '', company).strip(' ,.')
    if not (role or company):
        return None
    if not start and not role:
        return None
    return ExperienceEntry(
        company=company[:200],
        role=role[:200],
        start=start,
        end=end,
        is_current=is_current,
        location=loc[:120],
    )


def _is_bullet_or_duty_line(line: str) -> bool:
    """True for responsibility bullets / duty sentences — never job headers."""
    raw = (line or '').strip()
    if not raw:
        return False
    if _parse_employment_sentence(raw):
        return False
    if raw[:1] in '•·*-●▪▸►' or raw.startswith(('●', '•', '', '')):
        return True
    stripped = re.sub(r'^[\s•·\-\*●▪▸►]+', '', raw).strip()
    from app.ai.document_intelligence.bullets import strip_bullet_prefix

    stripped = strip_bullet_prefix(stripped) or stripped
    if _EXP_META_LINE.match(stripped) or _BARE_DUTY_HEADER.match(stripped):
        return True
    if _DUTY_VERB_START.match(stripped):
        return True
    # Wrap leftovers: "for multiple services." / "and visualization"
    if re.match(r'(?i)^(for|and|with|using|across)\s+\w+', stripped) and len(stripped) < 80:
        return True
    # "AI Trainee, Heavy Engineering Corporation" is a header (often 40–70 chars)
    if _is_role_comma_company_header(stripped):
        return False
    # Company, City | Role, dates — pipe + range is a header, not a comma duty
    if '|' in stripped and extract_date_range(stripped)[0]:
        return False
    start, _end = extract_date_range(stripped)
    wo_dates = _strip_date_range(stripped).strip(' ,|-–—')
    if start and wo_dates:
        # Dated Role, Company / Company, City — not a duty even when > 40 chars
        if _has_job_title_cue(wo_dates) or re.search(r'(?i)\bintern\b', wo_dates):
            return False
        comma_parts = re.split(r',\s*', wo_dates, maxsplit=1)
        if len(comma_parts) == 2:
            right = comma_parts[1].strip()
            city_bit = re.split(r',\s*', right)[-1].strip()
            if _CITY_LIKE.match(right) or _CITY_LIKE.match(city_bit):
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
    if '|' in stripped:
        left, _, right = stripped.partition('|')
        left, right = left.strip(), right.strip()
        if left and _CITY_LIKE.match(right) and not _DUTY_VERB_START.match(left):
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


_DATE_JOIN_TAIL = re.compile(
    r'(?i)^(?:to|till|until|[-–—])?\s*'
    r'(?:present|current|now|till\s*date|ongoing|pursuing|(?:19|20)\d{2})\s*$'
)


def _is_date_line_fragment(s: str) -> bool:
    t = (s or '').strip()
    if not t:
        return False
    if _DATE_ATOM.match(t) or _DATE_ONLY_LINE.match(t) or _DATE_JOIN_TAIL.match(t):
        return True
    if re.match(r'(?i)^(?:from|since)\s+', t) and extract_date_range(t)[0]:
        return True
    return False


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
        if _is_date_line_fragment(s):
            buf.append(s)
            continue
        flush()
        out.append(s)
    flush()
    return out


def _employment_wrap_continuation(prev: str, nxt: str) -> bool:
    """True when nxt continues a wrapped employment sentence/record."""
    from app.ai.document_intelligence.bullets import strip_bullet_prefix

    p = strip_bullet_prefix(prev or '')
    n = strip_bullet_prefix(nxt or '')
    if not p or not n or is_section_header_line(n):
        return False
    already = _parse_employment_sentence(p)
    if (
        already
        and (already.role or '').strip()
        and (already.company or '').strip()
        and extract_date_range(n)[0]
        and len(n.split()) <= 8
    ):
        return False
    if extract_date_range(n)[0] and len(n.split()) <= 8 and re.search(
        r'(?i)\b(?:working|worked|as|for|from|to)\b',
        p,
    ):
        return True
    if re.search(r'(?i)\b(?:currently\s+)?(?:working|worked)\s+(?:with|at|as|for)\b', p):
        if re.match(r'(?i)^(?:as|for|from|to|present|till)\b', n):
            return True
        if p.rstrip().endswith(',') and len(n.split()) <= 10:
            return True
    if p.rstrip().endswith(',') and re.search(
        r'(?i)\b(?:as|for|from|to|present|till|working|worked)\b',
        n,
    ):
        return True
    return False


_BARE_EMPLOYMENT_LABEL = re.compile(
    r'(?i)^(company(?:\s+name)?|employer|organization(?:[\'’]s)?\s*name|'
    r'organisation(?:[\'’]s)?\s*name|name\s+of\s+(?:the\s+)?company|'
    r'client(?:\s+name)?|client\s+company|end\s+client|role|title|'
    r'designation|position|duration|period|tenure|dates?|period\s*/\s*duration|'
    r'(?:current|previous|former|past|last)\s+employer|'
    r'payroll\s+company|consulting\s+company)\s*$'
)
_COLON_VALUE_LINE = re.compile(r'^[:\-–—]\s*(.+)$')


def _join_labeled_experience_fields(lines: list[str]) -> list[str]:
    """Join ``Role`` + ``: value`` / ``Duration`` + next date line."""
    if not lines:
        return []
    out: list[str] = []
    i = 0
    while i < len(lines):
        cur = lines[i].strip()
        nxt = lines[i + 1].strip() if i + 1 < len(lines) else ''
        if nxt and _BARE_EMPLOYMENT_LABEL.match(cur):
            colon = _COLON_VALUE_LINE.match(nxt)
            if colon:
                out.append(f'{cur}: {colon.group(1).strip()}')
                i += 2
                continue
            if (
                nxt
                and not _BARE_EMPLOYMENT_LABEL.match(nxt)
                and not _BARE_DUTY_HEADER.match(nxt)
                and not _EXP_META_LINE.match(nxt)
                and len(nxt.split()) <= 12
            ):
                out.append(f'{cur}: {nxt}')
                i += 2
                continue
        out.append(lines[i])
        i += 1
    return out


def _is_employment_table_header(line: str) -> bool:
    parts = [p.strip().rstrip(':') for p in (line or '').split('|') if p.strip()]
    if len(parts) < 2:
        return False
    hits = sum(
        1
        for p in parts
        if re.fullmatch(
            r'(?i)(?:organization(?:[\'’]s)?\s*name|organisation(?:[\'’]s)?\s*name|'
            r'designation|company(?:\s+name)?|employer|from|to|role|title|'
            r'duration|location|skill\s*set|degree|university(?:/board)?)',
            p,
        )
    )
    return hits >= 2


def _parse_unheaded_employment_row(line: str) -> ExperienceEntry | None:
    """Map ``Company | Role | From | To`` (or ``Company: Role | dates``) rows."""
    s = (line or '').strip()
    if '|' not in s:
        return None
    parts = [p.strip() for p in s.split('|') if p.strip()]
    if len(parts) < 2:
        return None
    blob = ' '.join(parts).lower()
    if re.search(
        r'(?i)\b(?:degree|university(?:/board)?|year of pass|percentage|marital|'
        r'date of birth|permanent address|nationality|'
        r'bachelor|b\.?\s*e\.?|b\.?\s*tech|hsc|ssc|board)\b',
        blob,
    ):
        return None
    if _is_employment_table_header(s):
        return None
    date_cells: list[tuple[str, str, str]] = []
    other: list[str] = []
    for p in parts:
        a, b = extract_date_range(p)
        if a or re.search(r'(?i)\b(?:till\s*date|present|current|now|ongoing)\b', p):
            date_cells.append((a, b, p))
        else:
            other.append(p)
    if len(parts) < 3 and not (other and re.match(r'^.+:.+$', other[0])):
        return None
    if not date_cells and len(parts) < 3:
        return None
    company = role = ''
    if other:
        first = other[0]
        labeled = re.match(r'^(.+?)\s*:\s*(.+)$', first)
        if labeled and (
            _has_job_title_cue(labeled.group(2)) or is_plausible_job_title(labeled.group(2))
        ):
            company, role = labeled.group(1).strip(), labeled.group(2).strip()
        elif len(other) >= 2:
            a, b = other[0], other[1]
            split = _split_title_and_org_blob(a)
            if split and (
                _CITY_LIKE.match(b) or _looks_like_job_location_line(b)
            ):
                role, company = split
            else:
                a_role = _has_job_title_cue(a) or is_plausible_job_title(a)
                b_role = _has_job_title_cue(b)
                if a_role and not b_role:
                    role, company = a, b
                elif b_role or is_plausible_job_title(b):
                    company, role = a, b
                elif a_role:
                    role, company = a, b
                else:
                    company, role = a, b
        elif _has_job_title_cue(first) or is_plausible_job_title(first):
            role = first
        else:
            company = first
    if company and not role:
        split = _split_title_and_org_blob(company)
        if split:
            role, company = split
    if not date_cells:
        return None
    start = date_cells[0][0] or ''
    end = ''
    is_current = False
    last = date_cells[-1]
    if re.search(r'(?i)\b(?:till\s*date|present|current|now|ongoing)\b', last[2]):
        is_current = True
    elif len(date_cells) >= 2:
        end = last[1] or last[0] or ''
        start = date_cells[0][0] or start
    else:
        end = last[1] or ''
        if re.match(r'(?i)^(present|current|now|till\s*date|ongoing)$', end):
            is_current = True
            end = ''
    if not (company or role):
        return None
    return ExperienceEntry(
        company=company[:200],
        role=role[:200],
        start=start,
        end='' if is_current else end,
        is_current=is_current,
    )


def _join_wrapped_experience_lines(lines: list[str]) -> list[str]:
    """Join PDF-wrapped duty lines onto the previous bullet/header."""
    from app.ai.document_intelligence.bullets import is_wrap_continuation, strip_bullet_prefix

    if not lines:
        return []
    out: list[str] = [lines[0]]
    for nxt in lines[1:]:
        prev = out[-1]
        n = nxt.strip()
        p = prev.strip()
        if not n:
            continue
        if is_section_header_line(p) or is_section_header_line(n):
            out.append(n)
            continue
        if _employment_wrap_continuation(p, n):
            out[-1] = f'{p.rstrip()} {strip_bullet_prefix(n)}'.strip()
            continue
        # PDF wrap of an employment date: "... from March 2020 to" + "till date"
        if re.search(r'(?i)\b(?:from|to|until|till|[-–—])\s*$', p) and re.match(
            r'(?i)^(?:(?:to\s+)?till\s*date|present|current|now|ongoing|'
            r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{4}|'
            r'(?:19|20)\d{2})\b',
            strip_bullet_prefix(n),
        ):
            out[-1] = f'{p.rstrip()} {strip_bullet_prefix(n)}'.strip()
            continue
        # Never glue contact/reference/phone lines into a job header
        if (
            is_contact_or_reference_line(n)
            or is_contact_or_reference_line(p)
            or is_labeled_contact_metadata(n)
            or is_labeled_contact_metadata(p)
            or looks_like_phone_token(n)
            or looks_like_phone_token(p)
            or looks_like_contact_person_line(n)
            or looks_like_contact_person_line(p)
        ):
            out.append(n)
            continue
        if (
            _looks_like_job_header_line(n)
            or _is_role_comma_company_header(n)
            or _looks_like_company_line(n)
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
        # Continuation of previous bullet / soft-wrapped sentence only.
        # Do not glue duration or skill-token lines in the job preamble.
        nxt_had_bullet = n[:1] in '•·*●▪▸►' or n.startswith(('●', '•', '', ''))
        prev_is_duty = (
            p[:1] in '•·*●▪▸►'
            or p.startswith(('●', '•', '', ''))
            or _DUTY_VERB_START.match(re.sub(r'^[\s•·\-\*●]+', '', p))
        )
        if (
            prev_is_duty
            and is_wrap_continuation(p, n, nxt_had_bullet=nxt_had_bullet)
            and not _looks_like_job_header_line(n)
            and not _looks_like_job_header_line(p)
            and not _looks_like_role_only_line(p)
            and not _looks_like_company_line(p)
            and not _DUTY_VERB_START.match(re.sub(r'^[\s•·\-\*●]+', '', n))
            and not re.match(r'(?i)^[A-Z][A-Za-z /&]{1,40}:\s+\S', n)
        ):
            out[-1] = f'{p.rstrip()} {strip_bullet_prefix(n)}'.strip()
        else:
            out.append(n)
    return out


def _parse_experience_line(
    line: str,
    *,
    identity_names: set[str] | None = None,
) -> ExperienceEntry | None:
    raw_line = (line or '').strip()
    if not raw_line or is_section_header_line(raw_line) or len(raw_line) < 3:
        return None
    if _LABELED_DUTY_LINE.match(raw_line) or _BARE_DUTY_HEADER.match(raw_line):
        return None

    stripped = peel_inline_contact(_strip_employment_lead_in(raw_line))
    if not stripped:
        return None
    if is_contact_or_reference_line(stripped) or looks_like_contact_person_line(stripped):
        return None
    if is_labeled_contact_metadata(stripped):
        return None
    inline_role = ''
    if not re.match(r'(?i)^(role|title|designation|position|job\s+title)\s*:', stripped):
        labeled_inline = _INLINE_ROLE_LABEL.search(stripped)
        if labeled_inline:
            cand = labeled_inline.group(1).strip(' ,.|')
            if (
                cand
                and len(cand.split()) <= 10
                and (_has_job_title_cue(cand) or is_plausible_job_title(cand))
            ):
                inline_role = cand[:200]
                stripped = re.sub(
                    r'(?i)\s*(?:responsibilit\w*|duties)\s*[:\-–—]\s*.*$',
                    '',
                    stripped,
                )
                stripped = re.sub(r'\s{2,}', ' ', stripped).strip(' ,.|')
    labeled_co = _LABELED_EMPLOYER_LINE.match(stripped)
    if not labeled_co:
        prefixed = _EXPERIENCE_PREFIX_COMPANY.match(stripped)
        if prefixed:
            labeled_co = prefixed
    if _LABELED_CLIENT_LINE.match(stripped):
        return None
    start, end = extract_date_range(stripped)
    is_current = bool(end and re.match(r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$', end))
    if is_current:
        end = ''
    if re.search(r'(?i)\bcurrently\s+working\b', stripped):
        is_current = True
    if labeled_co:
        company = re.sub(r'(?i)\(\s*currently\s+working\s*\)', '', labeled_co.group(1)).strip(' ,')
        paren = _PAREN_CLIENT.match(company)
        if paren:
            company = paren.group(1).strip(' ,')
        if looks_like_education_as_experience_row(company, ''):
            return None
        if is_plausible_person_name(company) and not _looks_like_company_line(
            company, identity_names=identity_names
        ):
            return None
        return _attach_parsed_role(
            ExperienceEntry(
                company=company[:200],
                start=start,
                end=end,
                is_current=is_current,
            ),
            inline_role,
        )
    pair = _split_employer_city_line(stripped)
    if pair:
        start, end = extract_date_range(stripped)
        is_current = bool(end and re.match(r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$', end))
        if is_current:
            end = ''
        return _attach_parsed_role(
            ExperienceEntry(
                company=pair[0][:200],
                location=pair[1][:120],
                start=start,
                end=end,
                is_current=is_current,
            ),
            inline_role,
        )
    if (
        _CITY_LIKE.match(stripped)
        or _looks_like_job_location_line(stripped)
        or is_biodata_or_address_line(stripped)
    ) and not _has_job_title_cue(stripped):
        return None
    prose = _parse_employment_sentence(stripped, identity_names=identity_names)
    if prose:
        return _attach_parsed_role(prose, inline_role)
    if looks_like_phone_token(stripped) or looks_like_email_or_url(stripped):
        return None
    # Never promote bullets / duty sentences / meta labels to experience rows
    if _is_bullet_or_duty_line(stripped) or _EXP_META_LINE.match(stripped):
        return None
    if is_labeled_contact_metadata(stripped):
        return None
    from app.ai.parser.enrichment.resume_text_inference import looks_like_spoken_language_line

    if looks_like_spoken_language_line(stripped):
        return None
    if _is_project_like_experience(stripped):
        return None

    labeled_role = re.match(
        r'(?i)^(role|title|designation|position|job\s+title)\s*:\s*(.+)$',
        stripped,
    )
    if labeled_role:
        role_val = labeled_role.group(2).strip()[:200]
        if looks_like_education_as_experience_row('', role_val):
            return None
        return ExperienceEntry(
            role=role_val,
            start=start,
            end=end,
            is_current=is_current,
        )
    years_tenure = _ROLE_YEARS_TENURE.match(stripped)
    if years_tenure:
        role_val = years_tenure.group(1).strip(' ,|-–—')
        if (
            role_val
            and not _DUTY_VERB_START.match(role_val)
            and (
                _has_job_title_cue(role_val)
                or is_plausible_job_title(role_val)
                or re.search(r'(?i)\bintern\b', role_val)
            )
            and not looks_like_education_as_experience_row('', role_val)
        ):
            return ExperienceEntry(
                role=role_val[:200],
                start=start,
                end=end,
                is_current=is_current,
            )

    paren_client = _PAREN_CLIENT.match(stripped)
    if paren_client:
        company = stripped
        if not looks_like_education_as_experience_row(paren_client.group(1).strip(' ,'), ''):
            return ExperienceEntry(
                company=company[:200],
                start=start,
                end=end,
                is_current=is_current,
            )
    slash_client = _INLINE_SLASH_CLIENT.match(stripped)
    if slash_client:
        company = slash_client.group(1).strip(' ,-–—')
        company = re.sub(r'(?i)\s*[-–—]\s*[A-Za-z .]{2,24}$', '', company).strip()
        if company and not looks_like_education_as_experience_row(company, ''):
            return ExperienceEntry(
                company=company[:200],
                start=start,
                end=end,
                is_current=is_current,
            )

    if looks_like_skill_or_duration_company(stripped):
        return None
    if is_project_or_employment_meta_label(stripped):
        return None

    if _is_employment_table_header(stripped):
        return None
    if looks_like_education_as_experience_row(stripped, '') or (
        _looks_like_degree_line(stripped)
        and not re.search(r'(?i)\b(?:pvt|ltd|llc|llp|inc)\b', stripped)
        and not _has_job_title_cue(stripped)
    ):
        return None
    if re.search(r'(?i)\b(?:bachelor|b\.?\s*e\.?\b|b\.?\s*tech|hsc|ssc|degree)\b', stripped) and re.search(
        r'(?i)\b(?:university|college|board|percentage|cgpa)\b', stripped
    ):
        return None
    pipe_job = _parse_unheaded_employment_row(stripped)
    if pipe_job:
        return _attach_parsed_role(pipe_job, inline_role)

    # Pure geo / City, Region lines are job locations — not roles/companies
    if _CITY_LIKE.match(stripped) or _looks_like_job_location_line(stripped):
        if start:
            return ExperienceEntry(
                start=start,
                end=end,
                is_current=is_current,
                location=stripped[:120],
            )
        return ExperienceEntry(location=stripped[:120])

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

    # Em/en/hyphen: Role — Company  OR  Company — Role (dates)
    # Dates may sit on either side; keep parsing even when a range is present.
    # Do not treat the hyphen inside "Jan 2020 - Present" as Role—Company.
    em = re.match(r'^(.+?)\s+(?:[—–]|-)\s+(.+)$', stripped)
    if em and '|' not in stripped:
        left, right = em.group(1).strip(), em.group(2).strip()
        left_wo = _strip_date_range(left).strip(' ,()')
        right_wo = _strip_date_range(right).strip(' ,()')
        right_is_dateish = bool(
            not right_wo
            or re.match(
                r'(?i)^(present|current|now|till\s*date|tilldate|ongoing|pursuing)$',
                right_wo,
            )
            or (
                extract_date_range(right_wo or right)[0]
                and not _has_job_title_cue(right_wo)
                and len(right_wo.split()) <= 3
            )
        )
        if right_is_dateish:
            em = None
    if em and '|' not in stripped:
        d_start, d_end = start, end
        is_cur = is_current
        if not d_start:
            d_start, d_end = extract_date_range(stripped)
            is_cur = bool(d_end and re.match(r'(?i)^(present|current|now)$', d_end or ''))
            if is_cur:
                d_end = ''
        left_is_co = _looks_like_company_line(left_wo, identity_names=identity_names) or bool(
            re.search(r'(?i)\b(?:pvt\.?|ltd\.?|llc|inc|llp|limited|technologies)\b', left_wo)
        )
        right_is_role = (
            _has_job_title_cue(right_wo)
            or bool(re.search(r'(?i)\b(?:intern|trainee|engineer|developer)\b', right_wo))
        )
        left_is_role = (
            _has_job_title_cue(left_wo)
            or bool(re.search(r'(?i)\bintern\b', left_wo))
        )
        if (
            left_is_co
            and right_is_role
            and not _DUTY_VERB_START.match(right_wo)
            and len(left_wo.split()) <= 10
            and len(right_wo.split()) <= 10
        ):
            return ExperienceEntry(
                company=left_wo[:200],
                role=right_wo[:200],
                start=d_start or '',
                end=d_end or '',
                is_current=is_cur,
            )
        if (
            left_is_role
            and not _DUTY_VERB_START.match(left_wo)
            and not _DUTY_VERB_START.match(right_wo)
            and len(left_wo.split()) <= 8
            and len(right_wo.split()) <= 8
            and not re.search(r'[.]$', stripped)
        ):
            return ExperienceEntry(
                company=right_wo[:200],
                role=left_wo[:200],
                start=d_start or '',
                end=d_end or '',
                is_current=is_cur,
            )

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
            if loc_or_co and (_CITY_LIKE.match(loc_or_co) or _looks_like_job_location_line(loc_or_co)):
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

    # Company, City | Role, dates  (Realatte Ventures Limited, Andheri (E) | Full Stack Developer, April 2026 – July 2026)
    co_city_role = re.match(
        r'^(.+?),\s*([^|,]{2,40})\s*[|]\s*(.+?),\s*('
        r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
        r'.+)$',
        stripped,
        re.I,
    )
    if co_city_role:
        co, city, role, date_blob = (
            co_city_role.group(1).strip(),
            co_city_role.group(2).strip(),
            co_city_role.group(3).strip(),
            co_city_role.group(4).strip(),
        )
        d_start, d_end = extract_date_range(date_blob)
        if (
            d_start
            and role
            and (
                _has_job_title_cue(role)
                or is_plausible_job_title(role)
                or re.search(r'(?i)\bintern\b', role)
            )
            and not _DUTY_VERB_START.match(role)
        ):
            is_cur = bool(d_end and re.match(r'(?i)^(present|current|now)$', d_end))
            return ExperienceEntry(
                company=co[:200],
                role=role[:200],
                start=d_start,
                end='' if is_cur else (d_end or ''),
                is_current=is_cur,
                location=city[:120],
            )

    # Two or three fragments: Role | Company | Dates  OR  Company | Role | Dates
    pipe = _PIPE_EXP.match(stripped)
    if pipe:
        left, mid, date_blob = (
            pipe.group(1).strip(),
            pipe.group(2).strip(),
            pipe.group(3).strip(),
        )
        # Reject date tokens mistaken for Role | Company (e.g. 07/2025 – 10/2025 | Remote)
        if extract_date_range(left)[0] or extract_date_range(mid)[0]:
            left, mid = '', ''
        if not start:
            start, end2 = extract_date_range(date_blob)
            if end2:
                is_current = bool(re.match(r'(?i)^(present|current|now)$', end2))
                end = '' if is_current else end2
        if left and mid and not _DUTY_VERB_START.match(left) and not _DUTY_VERB_START.match(mid):
            loc = ''
            if _CITY_LIKE.match(mid):
                loc, company, role = mid, left, ''
                if _has_job_title_cue(left):
                    company, role = '', left
            else:
                company, role = _classify_company_vs_role(left, mid)
            return ExperienceEntry(
                company=company[:200],
                role=role[:200],
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
                company, role = _classify_company_vs_role(left, leftover)
                return ExperienceEntry(
                    company=company[:200],
                    role=role[:200],
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
                not _DUTY_VERB_START.match(left)
                and not _DUTY_VERB_START.match(right)
                and len(left.split()) <= 10
                and len(right.split()) <= 10
                and (
                    _has_job_title_cue(left)
                    or _has_job_title_cue(right)
                    or re.search(r'(?i)\bintern\b', left)
                    or re.search(r'(?i)\bintern\b', right)
                    or _looks_like_org_header(left)
                    or _looks_like_org_header(right)
                    or _looks_like_company_line(left)
                    or _looks_like_company_line(right)
                )
            ):
                company, role = _classify_company_vs_role(left, right)
                return ExperienceEntry(
                    company=company[:200],
                    role=role[:200],
                    start=start,
                    end=end,
                    is_current=is_current,
                )

    # Role at Company
    line_wo = _strip_date_range(stripped) if start else stripped
    loc_wo = (line_wo or '').strip(' |-–—,()')
    if start and loc_wo and (
        _CITY_LIKE.match(loc_wo) or _looks_like_job_location_line(loc_wo)
    ) and not _has_job_title_cue(loc_wo):
        return ExperienceEntry(
            start=start,
            end=end,
            is_current=is_current,
            location=loc_wo[:120],
        )
    at_m = _AT_EXP.match(line_wo)
    if at_m:
        role, company = at_m.group(1).strip(), at_m.group(2).strip(' ,')
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
        if _looks_like_company_line(line_wo, identity_names=identity_names):
            return ExperienceEntry(company=line_wo.strip(), start=start, end=end, is_current=is_current)
        return ExperienceEntry(role=line_wo.strip(), start=start, end=end, is_current=is_current)

    # Stacked resume layouts: Role and Company on their own lines (dates follow)
    if not start and _looks_like_role_only_line(line_wo):
        return ExperienceEntry(role=line_wo.strip()[:200])
    if not start and _looks_like_company_line(line_wo, identity_names=identity_names):
        return ExperienceEntry(company=line_wo.strip()[:200])
    leftover = (line_wo or '').strip(' |-–—,()')
    if start and not leftover:
        return _attach_parsed_role(
            ExperienceEntry(start=start, end=end, is_current=is_current),
            inline_role,
        )
    if start and leftover:
        recovered = _recover_labeled_role(
            ExperienceEntry(
                company=leftover[:200],
                role=inline_role,
                start=start,
                end=end,
                is_current=is_current,
            )
        )
        if (recovered.company or '').strip() or (recovered.role or '').strip():
            if _looks_like_company_line(
                recovered.company or leftover, identity_names=identity_names
            ) or _looks_like_org_header(recovered.company or leftover):
                return _attach_parsed_role(recovered, inline_role)

    return None


def _coalesce_stacked_experience_entries(rows: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Merge adjacent Role-only + Company|Dates (or reverse) into one job."""
    out: list[ExperienceEntry] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        nxt2 = rows[i + 2] if i + 2 < len(rows) else None
        if nxt:
            cur_role, cur_co = (cur.role or '').strip(), (cur.company or '').strip()
            nxt_role, nxt_co = (nxt.role or '').strip(), (nxt.company or '').strip()
            dates_conflict = bool(cur.start and nxt.start and cur.start != nxt.start)
            n2_role = (nxt2.role or '').strip() if nxt2 else ''
            n2_co = (nxt2.company or '').strip() if nxt2 else ''
            n2_dates_conflict = bool(
                nxt2
                and (
                    (cur.start and nxt2.start and cur.start != nxt2.start)
                    or (nxt.start and nxt2.start and nxt.start != nxt2.start)
                )
            )
            # Company then role then dates on three stacked lines
            if (
                nxt2
                and not n2_dates_conflict
                and cur_co
                and not cur_role
                and nxt_role
                and not nxt_co
                and nxt2.start
                and not n2_role
                and not n2_co
            ):
                out.append(
                    cur.model_copy(
                        update={
                            'role': nxt_role[:200],
                            'start': cur.start or nxt.start or nxt2.start,
                            'end': cur.end or nxt.end or nxt2.end,
                            'is_current': cur.is_current or nxt.is_current or nxt2.is_current,
                            'location': (cur.location or nxt.location or nxt2.location or '')[:120],
                            'description': (
                                cur.description or nxt.description or nxt2.description or ''
                            ).strip(),
                        }
                    )
                )
                i += 3
                continue
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
            if (
                not dates_conflict
                and (cur_role or cur_co)
                and nxt.start
                and not nxt_role
                and not nxt_co
            ):
                out.append(
                    cur.model_copy(
                        update={
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
            # Date-first then company/role, optionally a third complementary line
            if cur.start and not cur_role and not cur_co and (nxt_role or nxt_co):
                if (
                    nxt2
                    and not n2_dates_conflict
                    and (
                        (nxt_co and not nxt_role and n2_role and not n2_co)
                        or (nxt_role and not nxt_co and n2_co and not n2_role)
                    )
                ):
                    out.append(
                        cur.model_copy(
                            update={
                                'company': (nxt_co or n2_co)[:200],
                                'role': (nxt_role or n2_role)[:200],
                                'start': cur.start or nxt.start or nxt2.start,
                                'end': cur.end or nxt.end or nxt2.end,
                                'is_current': cur.is_current or nxt.is_current or nxt2.is_current,
                                'location': (
                                    cur.location or nxt.location or nxt2.location or ''
                                )[:120],
                                'description': (
                                    cur.description or nxt.description or nxt2.description or ''
                                ).strip(),
                            }
                        )
                    )
                    i += 3
                    continue
                if not dates_conflict:
                    out.append(
                        cur.model_copy(
                            update={
                                'company': nxt_co[:200],
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


_PREFIX_DURATION = re.compile(
    r'(?i)^(\d{1,2})\s*[-–—]?\s*(?:month|months)\s+tenure\b|^(\d{1,2})\s+months?\s*$'
)
_PREFIX_STOP = re.compile(
    r'(?i)^(profile|summary|experience|education|skills|email|phone|address|objective)\b'
)
_PREFIX_NAME = re.compile(r'^[A-Z][a-zA-Z\'\.]+(?:\s+[A-Z][a-zA-Z\'\.]+){1,4}$')
_PREFIX_EDU_NOISE = re.compile(r'(?i)score|gpa|cgpa|percentage|%')


def _prefix_tenure_signals(full_text: str) -> list[dict[str, Any]]:
    """Two-column PDF often emits job dates above the name (sidebar)."""
    if not full_text:
        return []
    signals: list[dict[str, Any]] = []
    seen_signal = False
    for line in full_text.splitlines()[:30]:
        s = (line or '').strip()
        if not s:
            continue
        if _PREFIX_STOP.match(s) or (
            seen_signal and _PREFIX_NAME.match(s) and 8 < len(s) <= 60
        ):
            break
        if _PREFIX_EDU_NOISE.search(s) or re.fullmatch(r'(?:19|20)\d{2}', s):
            continue
        dm = _PREFIX_DURATION.search(s)
        if dm:
            signals.append({'months': int(dm.group(1) or dm.group(2))})
            seen_signal = True
            continue
        start, end = extract_date_range(s)
        if start:
            signals.append({'start': start, 'end': end or ''})
            seen_signal = True
    return signals


def _headline_role_from_text(text: str) -> str:
    """Single job-title line above the first section — not a duty or employer."""
    from app.ai.parser.layout.heuristic import normalize_section_header

    found: list[str] = []
    for raw in (text or '').splitlines():
        ln = re.sub(r'^[\s•·\-\*●]+', '', (raw or '').strip())
        if not ln:
            continue
        canon = normalize_section_header(ln)
        if canon in {
            'Experience', 'Education', 'Skills', 'Summary',
            'Projects', 'Certifications', 'Objective',
        }:
            break
        if is_section_header_line(ln) or is_document_title_line(ln):
            continue
        if is_labeled_contact_metadata(ln) or is_contact_or_reference_line(ln):
            continue
        if is_plausible_person_name(ln) or looks_like_phone_token(ln) or looks_like_email_or_url(ln):
            continue
        peeled = peel_inline_contact(ln)
        left = re.split(r'\s*[|]\s*', peeled, maxsplit=1)[0].strip()
        if not left or extract_date_range(left)[0]:
            continue
        if len(left.split()) > 6:
            continue
        if _DUTY_VERB_START.match(left) or _looks_like_company_line(left):
            continue
        if _looks_like_role_only_line(left) or _has_job_title_cue(left):
            found.append(left)
        if len(found) > 2:
            break
    uniq = list(dict.fromkeys(found))
    if len(uniq) == 1:
        return uniq[0][:200]
    return ''


def _attach_headline_role_from_text(
    entries: list[ExperienceEntry],
    full_text: str,
) -> list[ExperienceEntry]:
    """Attach a unique banner title to the first roleless employer."""
    if not entries or not full_text:
        return entries
    if any(
        _has_job_title_cue(e.role or '')
        and (e.company or '').strip()
        and (
            _looks_like_company_line(e.company or '')
            or _looks_like_org_header(e.company or '')
        )
        and not looks_like_skill_or_duration_company(e.company or '')
        for e in entries
    ):
        return entries
    title = _headline_role_from_text(full_text)
    if not title:
        return entries
    out = list(entries)
    for i, e in enumerate(out):
        if (e.role or '').strip() or not (e.company or '').strip():
            continue
        if looks_like_skill_or_duration_company(e.company or ''):
            continue
        out[i] = e.model_copy(update={'role': title})
        break
    return out


def _attach_prefix_tenures(
    entries: list[ExperienceEntry],
    full_text: str,
) -> list[ExperienceEntry]:
    """Zip sidebar date ranges / N-month tenures onto undated job rows."""
    if not entries or not full_text:
        return entries
    undated_idx = [i for i, e in enumerate(entries) if not (e.start or '').strip()]
    if not undated_idx:
        return entries
    signals = _prefix_tenure_signals(full_text)
    if not signals:
        return entries
    n = min(len(undated_idx), len(signals))
    out = list(entries)
    for k in range(n):
        i = undated_idx[k]
        sig = signals[k]
        prev = out[i]
        if sig.get('months'):
            months = int(sig['months'])
            desc = (prev.description or '').strip()
            tag = f'{months}-Month Tenure'
            if tag.lower() not in desc.lower():
                desc = f'{tag}. {desc}'.strip()
            out[i] = prev.model_copy(update={'description': desc[:2000]})
        else:
            out[i] = prev.model_copy(
                update={
                    'start': sig.get('start') or '',
                    'end': sig.get('end') or '',
                }
            )
    return out


def _description_is_job_header_echo(job: ExperienceEntry, desc: str) -> bool:
    """True when description is only a restated role/company/dates header."""
    d = (desc or '').strip()
    if not d or '\n' in d:
        return False
    if len(d) > 90 or _DUTY_VERB_START.match(d):
        return False
    if re.search(
        r'(?i)\b(?:responsible for|developed|managed|implemented|supported|built)\b',
        d,
    ):
        return False
    if _looks_like_job_header_line(d) and extract_date_range(d)[0]:
        return True
    company = (job.company or '').strip().lower()
    role = (job.role or '').strip().lower()
    blob = d.lower()
    if company and company in blob and extract_date_range(d)[0]:
        return True
    if role and company and role in blob and company in blob and len(d.split()) <= 10:
        return True
    return False


def _attach_orphan_dates_to_entries(
    entries: list[ExperienceEntry],
    lines: list[str],
) -> list[ExperienceEntry]:
    """Attach leftover date-only lines to the nearest row missing start or end."""
    if not entries or not lines:
        return entries
    blobs: list[tuple[str, str]] = []
    for ln in lines:
        stripped = re.sub(r'^[\s•·\-\*●]+', '', (ln or '').strip())
        leftover = _identity_leftover_after_dates(stripped)
        d_start, d_end = extract_date_range(stripped)
        if not d_start:
            continue
        if leftover and leftover.lower() not in {
            'present', 'current', 'now', 'ongoing', 'till date', 'tilldate',
        } and len(leftover.split()) > 2:
            continue
        blobs.append((d_start, d_end or ''))
    if not blobs:
        return entries
    out = list(entries)
    used: set[int] = set()
    for i, job in enumerate(out):
        has_start = bool((job.start or '').strip())
        has_end = bool((job.end or '').strip()) or bool(job.is_current)
        if has_start and has_end:
            continue
        for j, (ds, de) in enumerate(blobs):
            if j in used:
                continue
            is_cur = bool(de and re.match(
                r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                de,
            ))
            updates: dict[str, str | bool] = {}
            if not has_start:
                updates['start'] = ds
            if not has_end:
                updates['end'] = '' if is_cur else de
                updates['is_current'] = bool(job.is_current or is_cur)
            if updates:
                out[i] = job.model_copy(update=updates)
                used.add(j)
                break
    return out


def _split_client_annotation(company: str) -> tuple[str, str]:
    """Return (employer, client) when the org string labels a Client."""
    raw = (company or '').strip()
    if not raw:
        return '', ''
    paren = _PAREN_CLIENT.match(raw)
    if paren:
        return paren.group(1).strip(' ,'), paren.group(2).strip(' ,')
    slash = _INLINE_SLASH_CLIENT.match(raw)
    if slash:
        employer = slash.group(1).strip(' ,-–—')
        employer = re.sub(r'(?i)\s*[-–—]\s*[A-Za-z .]{2,24}$', '', employer).strip()
        return employer, slash.group(2).strip(' ,')
    return raw, ''


def _client_name_in_entry(name: str, entry: ExperienceEntry) -> bool:
    """True when `name` is explicitly labeled as a client of this job."""
    needle = (name or '').strip()
    if len(needle) < 4:
        return False
    blob = f'{entry.company or ""} {entry.description or ""} {entry.role or ""}'
    if re.search(
        rf'(?i)\(\s*(?:end\s+)?clients?\s*[:\-–—]\s*.*{re.escape(needle)}',
        blob,
    ):
        return True
    if re.search(
        rf'(?i)(?:^|[•\n/\s])(?:end\s+)?clients?(?:\s+(?:name|company|side|organization|organisation))?\s*[:\-–—]\s*.*{re.escape(needle)}',
        blob,
    ):
        return True
    return False


def _employer_beside_labeled_client(text: str, client_name: str = '') -> str:
    """Recover the org that sits beside an explicit Client annotation."""
    blob = (text or '').strip()
    if not blob:
        return ''
    for line in blob.splitlines():
        s = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
        emp, cli = _split_client_annotation(s)
        if emp and cli:
            if not client_name or client_name.strip().lower() in cli.lower():
                return emp
        slash = _INLINE_SLASH_CLIENT.match(s)
        if slash:
            emp = slash.group(1).strip(' ,-–—')
            emp = re.sub(r'(?i)\s*[-–—]\s*[A-Za-z .]{2,24}$', '', emp).strip()
            if emp:
                return emp
    m = re.search(
        r'(?i)([A-Z][A-Za-z0-9&.\' -]{2,50}?)\s*\(\s*(?:end\s+)?clients?\s*[:\-–—]',
        blob,
    )
    if m:
        return m.group(1).strip(' ,-–—')
    return ''


def _recover_company_from_description(entry: ExperienceEntry) -> str:
    desc = (entry.description or '').strip()
    if not desc:
        return ''
    labeled = _DESC_EMPLOYER_LABEL.search(desc)
    if labeled:
        val = labeled.group(1).strip().strip(' .,;')
        val = re.split(r'\s+[•·]\s+', val)[0].strip()
        if val and not looks_like_skill_or_duration_company(val):
            emp, _cli = _split_client_annotation(val)
            return (emp or val)[:200]
    beside = _employer_beside_labeled_client(desc)
    if beside and not looks_like_skill_or_duration_company(beside):
        return beside[:200]
    first = re.sub(r'^[\s•·\-\*●]+', '', desc.splitlines()[0]).strip()
    prose = _parse_employment_sentence(first)
    if prose and (prose.company or '').strip() and _accept_prose_employer(prose.company):
        return (prose.company or '')[:200]
    emp, cli = _split_client_annotation(first)
    if emp and cli:
        return emp[:200]
    pair = _split_employer_city_line(first)
    if pair:
        return pair[0][:200]
    if _looks_like_org_header(first) or re.search(
        r'(?i)\b(?:pvt\.?|ltd\.?|llc|inc|llp|limited|private)\b',
        first,
    ):
        left = re.split(r'\s+[-–—]\s+', first, maxsplit=1)[0].strip()
        left = left.split('|')[0].strip()
        if left and not looks_like_skill_or_duration_company(left):
            return left[:200]
    return ''


def _peel_header_dates(entry: ExperienceEntry) -> ExperienceEntry:
    """Move dates embedded in company/role into start/end; keep leftover identity."""
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    start, end, is_current = entry.start, entry.end, entry.is_current
    updates: dict[str, str | bool] = {}
    for field in ('company', 'role'):
        raw = company if field == 'company' else role
        if not raw:
            continue
        d_start, d_end = extract_date_range(raw)
        if not d_start:
            continue
        leftover = _strip_date_range(raw).strip(' \t|-–—,():')
        leftover = re.sub(r'(?i)^\s*(?:with|at)\s+', '', leftover).strip()
        if not start:
            updates['start'] = d_start
            start = d_start
        if d_end and not end and not is_current:
            is_cur = bool(re.match(
                r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                d_end,
            ))
            updates['end'] = '' if is_cur else d_end
            updates['is_current'] = bool(is_current or is_cur)
            is_current = bool(updates['is_current'])
            end = updates['end']
        if leftover != raw:
            updates[field] = leftover[:200]
            if field == 'company':
                company = leftover
            else:
                role = leftover
    if updates:
        return entry.model_copy(update=updates)
    return entry


def _promote_leading_date_from_description(entry: ExperienceEntry) -> ExperienceEntry:
    """Move a leading date-only duty line onto an undated job (association, not invention)."""
    if (entry.start or '').strip():
        return entry
    desc = (entry.description or '').strip()
    if not desc:
        return entry
    first, _, rest = desc.partition('\n')
    first = re.sub(r'^[\s•·\-\*●]+', '', first).strip()
    if not _is_date_range_stub_text(first):
        return entry
    d_start, d_end = extract_date_range(first)
    if not d_start:
        return entry
    is_cur = bool(
        d_end
        and re.match(
            r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
            d_end,
        )
    )
    return entry.model_copy(
        update={
            'start': d_start,
            'end': '' if is_cur else (d_end or entry.end or ''),
            'is_current': bool(entry.is_current or is_cur),
            'description': rest.strip()[:2000],
        }
    )


def _attach_parsed_role(entry: ExperienceEntry | None, role: str) -> ExperienceEntry | None:
    if entry is None or not (role or '').strip() or (entry.role or '').strip():
        return entry
    return entry.model_copy(update={'role': role.strip()[:200]})


def _recover_labeled_role(entry: ExperienceEntry) -> ExperienceEntry:
    """Peel ``Role:`` / ``Designation:`` off a company blob or description."""
    if (entry.role or '').strip():
        return entry
    blob = f'{entry.company or ""}\n{entry.description or ""}'
    m = _INLINE_ROLE_LABEL.search(blob)
    if not m:
        return entry
    cand = m.group(1).strip(' ,.|')
    if not cand or len(cand.split()) > 10:
        return entry
    if not (_has_job_title_cue(cand) or is_plausible_job_title(cand)):
        return entry
    company = re.sub(
        r'(?i)\s*(?:role|title|designation|position|job\s+title)\s*[:\-–—]\s*'
        + re.escape(cand),
        '',
        entry.company or '',
    ).strip(' ,.|')
    return entry.model_copy(update={'role': cand[:200], 'company': company[:200]})


def _promote_title_from_description(entry: ExperienceEntry) -> ExperienceEntry:
    """Move a short first-duty title into role when the header left role empty."""
    if (entry.role or '').strip():
        return entry
    desc = (entry.description or '').strip()
    if not desc:
        return entry
    parts = re.split(r'(?:\n|\s+[•·]\s+)', desc, maxsplit=1)
    first = re.sub(r'^[\s•·\-\*●]+', '', parts[0]).strip()
    rest = parts[1].strip() if len(parts) > 1 else ''
    if re.match(r'(?i)^(?:project\s+title|project\s+name)\b', first):
        first = re.sub(
            r'(?i)^(?:project\s+title|project\s+name)\s*[:\-–—]?\s*',
            '',
            first,
        ).strip()
    spaced = re.split(r'\s{2,}', first, maxsplit=1)
    if len(spaced) == 2 and (
        _looks_like_role_only_line(spaced[0]) or (
            _has_job_title_cue(spaced[0]) and len(spaced[0].split()) <= 6
        )
    ):
        first, extra = spaced[0].strip(), spaced[1].strip()
        rest = f'{extra} {rest}'.strip()
    if not first or len(first.split()) > 10 or _DUTY_VERB_START.match(first):
        return entry
    if not (_looks_like_role_only_line(first) or _has_job_title_cue(first)):
        return entry
    if looks_like_skill_or_duration_company(first) or _looks_like_job_location_line(first):
        return entry
    return entry.model_copy(update={'role': first[:200], 'description': rest[:2000]})


def _split_title_and_org_blob(text: str) -> tuple[str, str] | None:
    """Split a same-line title+employer blob without assuming order."""
    s = (text or '').strip()
    if not s or len(s.split()) < 3:
        return None
    m = re.match(
        r'(?i)^(.{3,70}?)\s+'
        r'([A-Z][\w.&\'\- ]{0,70}?'
        r'(?:Pvt\.?|Ltd\.?|LLC|LLP|Inc\.?|Limited|Private|GmbH|PLC)\b.*)$',
        s,
    )
    if m and _has_job_title_cue(m.group(1)) and not _has_job_title_cue(m.group(2)):
        return m.group(1).strip()[:200], m.group(2).strip()[:200]
    words = s.split()
    for i in range(1, len(words)):
        left, right = ' '.join(words[:i]).strip(), ' '.join(words[i:]).strip()
        if not left or not right:
            continue
        if _looks_like_job_location_line(left) or _CITY_LIKE.match(left):
            continue
        left_title = _has_job_title_cue(left)
        right_title = _has_job_title_cue(right)
        left_org = _looks_like_org_header(left) and not left_title
        right_org = _looks_like_org_header(right) and not right_title
        if left_title and right_org and not right_title:
            return left[:200], right[:200]
        if left_org and right_title and not left_title:
            return right[:200], left[:200]
    return None


def _split_role_embedded_company(role: str, company: str) -> tuple[str, str]:
    """``Role : Org`` / ``Role – Org Pvt Ltd`` / same-line title+employer."""
    r, c = (role or '').strip(), (company or '').strip()
    if c and not r:
        split = _split_title_and_org_blob(c)
        if split:
            return split
    if r and not c:
        split = _split_title_and_org_blob(r)
        if split:
            return split
    if c or not r:
        return r, c
    m = re.match(r'^(.+?)\s*[:\-–—]\s*(.+)$', r)
    if not m:
        return r, c
    left, right = m.group(1).strip(), m.group(2).strip()
    right_wo = _strip_date_range(right).strip(' \t|-–—,()')
    if _DUTY_VERB_START.match(right) or _DUTY_VERB_START.match(right_wo):
        return r, c
    if re.match(r'(?i)^present\b', right_wo):
        return r, c
    if (
        (_has_job_title_cue(left) or is_plausible_job_title(left))
        and not _has_job_title_cue(right_wo or right)
        and (
            _looks_like_org_header(right_wo or right)
            or _looks_like_company_line(right_wo or right)
            or (
                len((right_wo or right).split()) <= 6
                and not _has_job_title_cue(right_wo or right)
            )
        )
        and not looks_like_skill_or_duration_company(right_wo or right)
    ):
        return left[:200], right[:200]
    return r, c


def _company_fields_overlap(left: str, right: str) -> bool:
    a, b = (left or '').strip().lower(), (right or '').strip().lower()
    if not a or not b:
        return True
    if a == b:
        return True
    if len(a) >= 4 and a in b:
        return True
    if len(b) >= 4 and b in a:
        return True
    return False


def _company_mentioned_in_entry(company: str, entry: ExperienceEntry) -> bool:
    co = (company or '').strip().lower()
    if len(co) < 4:
        return False
    blob = f'{entry.company or ""} {entry.description or ""} {entry.role or ""}'.lower()
    return co in blob


def _description_looks_like_duties(desc: str) -> bool:
    text = (desc or '').strip()
    if not text:
        return False
    if text[:1] in '•·*●':
        return True
    if _DUTY_VERB_START.match(text):
        return True
    return bool(
        re.search(
            r'(?i)\b(?:developed|managed|administered|configured|implemented|responsible)\b',
            text,
        )
    )


def _pending_desc_is_preamble_noise(lines: list[str]) -> bool:
    """True when leftover lines are contact/summary, not a duty block."""
    if not lines:
        return True
    for raw in lines:
        s = re.sub(r'^[\s•·\-\*●]+', '', (raw or '').strip())
        if not s:
            continue
        if (raw or '').lstrip()[:1] in '•·*●▪▸►':
            return False
        if _DUTY_VERB_START.match(s):
            return False
        if _BARE_DUTY_HEADER.match(s) or _LABELED_DUTY_LINE.match(s):
            return False
    return True


def _is_roleless_company_row(entry: ExperienceEntry) -> bool:
    return bool((entry.company or '').strip() and not (entry.role or '').strip())


def _is_complete_experience_row(entry: ExperienceEntry) -> bool:
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    if not role or not company:
        return False
    if looks_like_skill_or_duration_company(company) or looks_like_skill_or_duration_company(role):
        return False
    if _CITY_LIKE.match(role) or _looks_like_job_location_line(role):
        return False
    if not (_looks_like_company_line(company) or _looks_like_org_header(company)):
        return False
    return bool(
        _has_job_title_cue(role)
        or is_plausible_job_title(role)
        or re.search(r'(?i)\bintern\b', role)
    )


def _is_title_banner_stub(entry: ExperienceEntry) -> bool:
    """True when the row is a title/summary banner, not a real employer job."""
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    if company and looks_like_skill_or_duration_company(company):
        company = ''
    if company and len(company.split()) > 8:
        return True
    if role and not company and (
        _has_job_title_cue(role) or is_plausible_job_title(role)
    ):
        return True
    if (
        company
        and _has_job_title_cue(company)
        and not _looks_like_org_header(company)
        and not _looks_like_company_line(company)
    ):
        return True
    return False


def _is_weak_experience_row(entry: ExperienceEntry) -> bool:
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    desc = (entry.description or '').strip()
    if company and looks_like_skill_or_duration_company(company) and not role:
        return True
    if company and not role and not _description_looks_like_duties(desc):
        if (entry.start or entry.is_current) and (
            _looks_like_org_header(company) or _looks_like_company_line(company)
        ):
            return False
        return True
    if role and looks_like_skill_or_duration_company(role) and not company:
        return True
    return False


def _is_strong_experience_row(entry: ExperienceEntry) -> bool:
    role = (entry.role or '').strip()
    company = (entry.company or '').strip()
    desc = (entry.description or '').strip()
    if company and looks_like_skill_or_duration_company(company):
        company = ''
    if role and looks_like_skill_or_duration_company(role):
        role = ''
    if not role:
        return False
    if role and company:
        return True
    if role and (entry.start or _description_looks_like_duties(desc)):
        return True
    return False


def _merge_experience_pair(cur: ExperienceEntry, nxt: ExperienceEntry) -> ExperienceEntry:
    cur_role, nxt_role = (cur.role or '').strip(), (nxt.role or '').strip()
    cur_co, nxt_co = (cur.company or '').strip(), (nxt.company or '').strip()
    cur_emp, _cur_cli = _split_client_annotation(cur_co)
    nxt_emp, _nxt_cli = _split_client_annotation(nxt_co)
    cur_co = cur_emp or cur_co
    nxt_co = nxt_emp or nxt_co
    strong_nxt = _is_strong_experience_row(nxt)
    strong_cur = _is_strong_experience_row(cur)
    beside_cur = _employer_beside_labeled_client(
        f'{nxt.company or ""} {nxt.description or ""}', cur_co
    )
    beside_nxt = _employer_beside_labeled_client(
        f'{cur.company or ""} {cur.description or ""}', nxt_co
    )
    if beside_cur:
        nxt_co = nxt_co or beside_cur
    if beside_nxt:
        cur_co = cur_co or beside_nxt
    if cur_co and nxt_co and _client_name_in_entry(cur_co, nxt) and nxt_co:
        company = nxt_co
    elif nxt_co and cur_co and _client_name_in_entry(nxt_co, cur) and cur_co:
        company = cur_co
    elif strong_nxt and nxt_co:
        company = nxt_co
    elif strong_cur and cur_co:
        company = cur_co
    else:
        company = nxt_co or cur_co
        if cur_co and nxt_co and len(cur_co) > len(company):
            company = cur_co
    if strong_nxt and nxt.start:
        start, end, is_current = nxt.start, nxt.end, nxt.is_current
        if not end and not is_current:
            end = cur.end
            is_current = cur.is_current
    else:
        start = cur.start or nxt.start
        end = cur.end or nxt.end
        is_current = cur.is_current or nxt.is_current
    desc = (cur.description or nxt.description or '').strip()
    if (nxt.description or '').strip() and len((nxt.description or '').strip()) > len(desc):
        desc = (nxt.description or '').strip()
    return cur.model_copy(
        update={
            'company': (company or '')[:200],
            'role': (nxt_role or cur_role)[:200],
            'start': start,
            'end': end,
            'is_current': is_current,
            'location': ((cur.location or nxt.location) or '')[:120],
            'description': desc[:2000],
        }
    )


def _experience_rows_complement(cur: ExperienceEntry, nxt: ExperienceEntry) -> bool:
    cur_role, nxt_role = (cur.role or '').strip(), (nxt.role or '').strip()
    cur_co, nxt_co = (cur.company or '').strip(), (nxt.company or '').strip()
    if cur_role and nxt_role and cur_role.lower() != nxt_role.lower():
        return False
    if looks_like_skill_or_duration_company(cur_co) or looks_like_skill_or_duration_company(nxt_co):
        return False
    dates_conflict = bool(cur.start and nxt.start and cur.start != nxt.start)
    weak_cur = bool(cur_co and not cur_role)
    weak_nxt = bool(nxt_co and not nxt_role)
    client_pair = False
    if cur_co and nxt_co:
        if _client_name_in_entry(cur_co, nxt) or _client_name_in_entry(nxt_co, cur):
            client_pair = True
        else:
            beside = _employer_beside_labeled_client(
                f'{nxt.company or ""} {nxt.description or ""}', cur_co
            ) or _employer_beside_labeled_client(
                f'{cur.company or ""} {cur.description or ""}', nxt_co
            )
            if beside:
                client_pair = True
    if client_pair:
        return True
    if cur_role and not cur_co and nxt_co:
        if (not nxt_role or nxt_role.lower() == cur_role.lower()) and not dates_conflict:
            return True
    if nxt_role and not nxt_co and cur_co:
        if (not cur_role or cur_role.lower() == nxt_role.lower()) and not dates_conflict:
            return True
    if weak_cur and _is_strong_experience_row(nxt):
        if _company_mentioned_in_entry(cur_co, nxt):
            return True
        if cur_co and nxt_co and _company_fields_overlap(cur_co, nxt_co):
            return True
        if not nxt_co and not dates_conflict:
            return True
    if weak_nxt and _is_strong_experience_row(cur):
        if _company_mentioned_in_entry(nxt_co, cur):
            return True
        if cur_co and nxt_co and _company_fields_overlap(cur_co, nxt_co):
            return True
        if not cur_co and not dates_conflict:
            return True
    if dates_conflict:
        return False
    if not cur_role and nxt_role and _company_fields_overlap(cur_co, nxt_co):
        return True
    if cur_role and not nxt_role and _company_fields_overlap(cur_co, nxt_co):
        return True
    return False


def _absorb_weak_experience_rows(rows: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Attach company/tenure metadata to a compatible job; drop leftover stubs."""
    if len(rows) < 2:
        return rows
    merged: list[ExperienceEntry] = []
    i = 0
    while i < len(rows):
        cur = rows[i]
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt is not None and _experience_rows_complement(cur, nxt):
            merged.append(_merge_experience_pair(cur, nxt))
            i += 2
            continue
        merged.append(cur)
        i += 1
    strong_idx = [i for i, e in enumerate(merged) if _is_strong_experience_row(e)]
    if not strong_idx:
        return merged
    drop: set[int] = set()
    for i, e in enumerate(merged):
        if i in strong_idx:
            continue
        if not (_is_weak_experience_row(e) or _is_roleless_company_row(e)):
            continue
        for si in strong_idx:
            if i in drop:
                break
            s = merged[si]
            if _experience_rows_complement(e, s) or _company_mentioned_in_entry(e.company or '', s):
                merged[si] = _merge_experience_pair(s, e)
                drop.add(i)
                break
    kept = [e for i, e in enumerate(merged) if i not in drop]
    if any(_is_strong_experience_row(e) for e in kept):
        kept = [e for e in kept if not _is_weak_experience_row(e)]
    return kept or merged


def _finalize_experience_entries(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Swap inverted headers, attach trailing duty/date stubs, keep strong rows first."""
    if not entries:
        return entries
    fixed: list[ExperienceEntry] = []
    for e in entries:
        e = _peel_header_dates(e)
        e = _promote_leading_date_from_description(e)
        role, company = (e.role or '').strip(), (e.company or '').strip()
        prefixed = _EXPERIENCE_PREFIX_COMPANY.match(company)
        if prefixed:
            company = prefixed.group(1).strip()
            emp, _cli = _split_client_annotation(company)
            company = emp or company
            e = e.model_copy(update={'company': company[:200]})
        role, company = _split_role_embedded_company(role, company)
        if role != (e.role or '').strip() or company != (e.company or '').strip():
            e = e.model_copy(update={'role': role[:200], 'company': company[:200]})
        e = _recover_labeled_role(e)
        e = _promote_title_from_description(e)
        role, company = (e.role or '').strip(), (e.company or '').strip()
        if not company:
            recovered = _recover_company_from_description(e)
            if recovered:
                company = recovered
                e = e.model_copy(update={'company': company[:200]})
        if company and looks_like_skill_or_duration_company(company):
            if not role:
                continue
            e = e.model_copy(update={'company': ''})
            company = ''
        if role and company:
            if _has_job_title_cue(company) and not _has_job_title_cue(role):
                e = e.model_copy(update={'company': role[:200], 'role': company[:200]})
        fixed.append(e)
    merged: list[ExperienceEntry] = []
    i = 0
    while i < len(fixed):
        cur = fixed[i]
        nxt = fixed[i + 1] if i + 1 < len(fixed) else None
        if nxt is not None:
            nxt_header = bool((nxt.role or '').strip() or (nxt.company or '').strip())
            nxt_desc = (nxt.description or '').strip()
            cur_desc = (cur.description or '').strip()
            if not nxt_header and nxt_desc and not cur_desc:
                cur = cur.model_copy(update={'description': nxt_desc[:2000]})
                merged.append(cur)
                i += 2
                continue
            if (
                not nxt_header
                and (nxt.start or '').strip()
                and not (cur.start or '').strip()
            ):
                cur = cur.model_copy(
                    update={
                        'start': nxt.start,
                        'end': cur.end or nxt.end,
                        'is_current': cur.is_current or nxt.is_current,
                    }
                )
                if nxt_desc and not cur_desc:
                    cur = cur.model_copy(update={'description': nxt_desc[:2000]})
                merged.append(cur)
                i += 2
                continue
            if (
                _is_title_banner_stub(cur)
                and (cur.start or '').strip()
                and (nxt.role or '').strip()
                and (nxt.company or '').strip()
                and not (nxt.start or '').strip()
                and not _is_title_banner_stub(nxt)
            ):
                nxt = nxt.model_copy(
                    update={
                        'start': cur.start,
                        'end': nxt.end or cur.end,
                        'is_current': nxt.is_current or cur.is_current,
                    }
                )
                merged.append(nxt)
                i += 2
                continue
            if (
                _is_date_range_stub_entry(nxt)
                and not (cur.start or '').strip()
                and ((cur.role or '').strip() or (cur.company or '').strip())
            ):
                stub_start, stub_end = nxt.start, nxt.end
                if not stub_start:
                    stub_start, stub_end = extract_date_range(nxt.role or '')
                is_cur = bool(
                    nxt.is_current
                    or (
                        stub_end
                        and re.match(
                            r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                            stub_end,
                        )
                    )
                )
                cur = cur.model_copy(
                    update={
                        'start': stub_start or cur.start,
                        'end': cur.end or ('' if is_cur else (stub_end or nxt.end or '')),
                        'is_current': cur.is_current or is_cur,
                    }
                )
                merged.append(cur)
                i += 2
                continue
            if _experience_rows_complement(cur, nxt):
                merged.append(_merge_experience_pair(cur, nxt))
                i += 2
                continue
        merged.append(cur)
        i += 1
    merged = _absorb_weak_experience_rows(merged)
    peeled: list[ExperienceEntry] = []
    for e in merged:
        emp, _cli = _split_client_annotation(e.company or '')
        if emp and emp != (e.company or '').strip():
            e = e.model_copy(update={'company': emp[:200]})
        peeled.append(e)
    merged = peeled
    complete: list[ExperienceEntry] = []
    partial: list[ExperienceEntry] = []
    dated: list[ExperienceEntry] = []
    for e in merged:
        if not (e.role or e.company or e.start or e.is_current):
            continue
        if _is_complete_experience_row(e):
            complete.append(e)
        elif e.role or e.company:
            partial.append(e)
        else:
            dated.append(e)
    ordered = complete + partial + dated
    deduped: list[ExperienceEntry] = []
    for e in ordered:
        if deduped:
            prev = deduped[-1]
            same = (
                (e.company or '').strip().lower() == (prev.company or '').strip().lower()
                and (e.role or '').strip().lower() == (prev.role or '').strip().lower()
                and (e.start or '') == (prev.start or '')
            )
            if same:
                if (e.description or '').strip() and not (prev.description or '').strip():
                    deduped[-1] = e
                continue
            if _experience_rows_complement(prev, e):
                deduped[-1] = _merge_experience_pair(prev, e)
                continue
        deduped.append(e)
    collapsed = _collapse_duplicate_identity_dates(deduped)
    return [e for e in collapsed if not _is_date_range_stub_entry(e)]


def _collapse_duplicate_identity_dates(entries: list[ExperienceEntry]) -> list[ExperienceEntry]:
    """Keep first role+company occurrence; copy dates from later duplicates."""
    first: dict[tuple[str, str], int] = {}
    out: list[ExperienceEntry] = []
    for e in entries:
        role = (e.role or '').strip().lower()
        company = (e.company or '').strip().lower()
        if not role or not company:
            out.append(e)
            continue
        key = (company, role)
        if key not in first:
            first[key] = len(out)
            out.append(e)
            continue
        prev = out[first[key]]
        updates: dict[str, str | bool] = {}
        if not (prev.start or '').strip() and (e.start or '').strip():
            updates['start'] = e.start
            updates['end'] = prev.end or e.end or ''
            updates['is_current'] = bool(prev.is_current or e.is_current)
        if (e.description or '').strip() and not (prev.description or '').strip():
            updates['description'] = e.description
        if updates:
            out[first[key]] = prev.model_copy(update=updates)
    return out


def parse_experience(section_text: str, full_text: str = '') -> list[ExperienceEntry]:
    """
    Parse experience ONLY from the Experience section span.
    Empty section → [] (fresher / projects-only resumes). Never scrape Projects via full-text fallback.
    Supports 'Role - Company - (dates)' headers. Consecutive headers before a shared
    Responsibilities block each become their own row and share that description.
    Two-column sidebar dates (extracted above the name) are zipped onto undated jobs.
    """
    from app.ai.document_intelligence.bullets import (
        is_glyph_crumb,
        join_duty_lines,
        restore_inferred_list_markers,
        split_inline_bullets,
    )

    raw = restore_inferred_list_markers(split_inline_bullets(section_text or '')).strip()
    if not raw:
        return []

    table_lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    first_parts = [p.strip() for p in re.split(r'[|\t]', table_lines[0]) if p.strip()] if table_lines else []
    exp_roles = _experience_header_roles(first_parts) if len(first_parts) >= 2 else None
    if exp_roles and len(table_lines) >= 2:
        table_jobs: list[ExperienceEntry] = []
        for ln in table_lines[1:]:
            if _is_employment_table_header(ln):
                continue
            parts = [p.strip() for p in re.split(r'[|\t]', ln)]
            if len([p for p in parts if p]) < 2:
                continue
            company = role = start = end = ''
            is_current = False
            desc_bits: list[str] = []
            for cell, role_key in zip(parts, exp_roles):
                if not cell:
                    continue
                if role_key == 'company':
                    company = cell
                elif role_key == 'role':
                    role = cell
                elif role_key == 'start':
                    a, b = extract_date_range(cell)
                    start = a or start
                    if re.search(r'(?i)\b(?:present|current|now|till\s*date|ongoing)\b', cell):
                        is_current = True
                elif role_key == 'end':
                    a, b = extract_date_range(cell)
                    if re.search(r'(?i)\b(?:present|current|now|till\s*date|ongoing)\b', cell):
                        is_current = True
                        end = ''
                    else:
                        end = b or a or end
                elif role_key == 'dates':
                    a, b = extract_date_range(cell)
                    start = start or a
                    if re.search(r'(?i)\b(?:present|current|now|till\s*date|ongoing)\b', cell):
                        is_current = True
                    else:
                        end = end or b
                else:
                    desc_bits.append(cell)
            if company or role:
                table_jobs.append(
                    ExperienceEntry(
                        company=company[:200],
                        role=role[:200],
                        start=start,
                        end=end,
                        is_current=is_current,
                        description=join_duty_lines(desc_bits)[:2000],
                    )
                )
        if table_jobs:
            stacked = _coalesce_stacked_experience_entries(table_jobs)
            stacked = _attach_headline_role_from_text(stacked, full_text)
            return _attach_prefix_tenures(
                _finalize_experience_entries(stacked),
                full_text,
            )

    from app.ai.document_intelligence.bullets import is_bullet_line

    lines = [
        ln.strip()
        for ln in raw.splitlines()
        if ln.strip() and not is_glyph_crumb(ln)
    ]
    lines = _join_labeled_experience_fields(lines)
    lines = _join_wrapped_date_lines(lines)
    lines = _join_wrapped_experience_lines(lines)

    entries: list[ExperienceEntry] = []
    pending_jobs: list[ExperienceEntry] = []
    pending_desc: list[str] = []
    in_contact_block = False
    in_project_block = False
    pending_project_tenure: tuple[str, str, bool] | None = None
    identity_names = document_identity_names(full_text)

    def _flush_pending() -> None:
        nonlocal pending_jobs, pending_desc
        from app.ai.document_intelligence.bullets import join_duty_lines

        desc = join_duty_lines(pending_desc).strip()
        pending_desc = []
        if not pending_jobs:
            return
        for job in pending_jobs:
            if _is_project_like_experience(job.role, job.company, desc):
                continue
            if is_non_job_experience_record(job):
                continue
            job_desc = desc or (job.description or '')
            if job_desc and _description_is_job_header_echo(job, job_desc):
                job_desc = ''
            if job_desc:
                job = job.model_copy(update={'description': job_desc})
            entries.append(job)
        pending_jobs = []

    def _attach_duration_to_row(target: ExperienceEntry, blob: str) -> ExperienceEntry | None:
        d_start, d_end = extract_date_range(blob)
        if not d_start:
            return None
        is_cur = bool(
            d_end
            and re.match(
                r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                d_end,
            )
        )
        return target.model_copy(
            update={
                'start': target.start or d_start,
                'end': target.end or ('' if is_cur else (d_end or '')),
                'is_current': target.is_current or is_cur,
            }
        )

    def _row_needs_duration(target: ExperienceEntry) -> bool:
        return (not (target.start or '').strip()) or (
            not (target.end or '').strip() and not target.is_current
        )

    def _attach_duration_to_pending(blob: str) -> bool:
        if pending_jobs and _row_needs_duration(pending_jobs[-1]):
            updated = _attach_duration_to_row(pending_jobs[-1], blob)
            if updated is None:
                return False
            pending_jobs[-1] = updated
            return True
        if entries and _row_needs_duration(entries[-1]):
            updated = _attach_duration_to_row(entries[-1], blob)
            if updated is None:
                return False
            entries[-1] = updated
            return True
        return False

    for line in lines:
        header_probe = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
        if _EXP_SECTION_STOP.match(header_probe):
            _flush_pending()
            break
        if is_section_header_line(header_probe):
            try:
                from app.ai.parser.layout.heuristic import normalize_section_header

                canon = (normalize_section_header(header_probe) or '').strip()
            except Exception:
                canon = ''
            if canon.lower() == 'experience':
                continue
            if canon in {
                'Education', 'Skills', 'Projects', 'Summary', 'Certifications',
                'Languages', 'Declaration',
            }:
                _flush_pending()
                break
            continue
        if _PROJECT_BLOCK_HEADING.match(header_probe):
            _flush_pending()
            in_project_block = True
            a, b = extract_date_range(header_probe)
            if a:
                is_cur = bool(
                    b
                    and re.match(
                        r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                        b,
                    )
                )
                pending_project_tenure = (a, '' if is_cur else (b or ''), is_cur)
            continue
        if (
            re.match(r'(?i)^projects?\s*[:\-–—]', header_probe)
            and not re.match(r'(?i)^project\s+(?:title|name)\b', header_probe)
            and not _LABELED_EMPLOYER_LINE.match(header_probe)
            and extract_date_range(header_probe)[0]
        ):
            a, b = extract_date_range(header_probe)
            is_cur = bool(
                b
                and re.match(
                    r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                    b,
                )
            )
            pending_project_tenure = (a, '' if is_cur else (b or ''), is_cur)
            continue
        if in_project_block:
            if is_labeled_contact_metadata(header_probe) or is_contact_or_reference_line(header_probe):
                continue
            if _EXP_META_LINE.match(header_probe) or _BARE_DUTY_HEADER.match(header_probe):
                continue
            if _is_project_like_experience(header_probe):
                continue
            probe_entry = _parse_experience_line(line, identity_names=identity_names)
            if probe_entry and (probe_entry.role or probe_entry.company) and (
                probe_entry.start
                or _has_job_title_cue(probe_entry.role or '')
                or _looks_like_company_line(probe_entry.company or '', identity_names=identity_names)
            ):
                in_project_block = False
            else:
                continue
        peeled_probe = peel_inline_contact(header_probe)
        if is_labeled_contact_metadata(peeled_probe):
            continue
        if identity_is_employer_value(peeled_probe, identity_names):
            continue
        if is_contact_section_label(header_probe) or (
            is_contact_or_reference_line(header_probe) and len(peeled_probe.split()) < 2
        ):
            in_contact_block = True
            continue
        if in_contact_block:
            if (
                looks_like_phone_token(header_probe)
                or looks_like_email_or_url(header_probe)
                or looks_like_contact_person_line(header_probe)
                or is_plausible_person_name(header_probe)
                or header_probe in '-–—'
            ):
                continue
            if _CITY_LIKE.match(header_probe) or _looks_like_job_location_line(header_probe):
                continue
            in_contact_block = False
        from app.ai.document_intelligence.bullets import is_bullet_line as _is_bul

        if _is_bul(line):
            peeled = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
            labeled_job = bool(
                _LABELED_EMPLOYER_LINE.match(peeled)
                or _EMPLOYMENT_DURATION_LABEL.match(peeled)
                or _is_employment_date_carrier(peeled)
            )
            if labeled_job:
                line = peeled
                header_probe = peeled
            else:
                probe = _parse_experience_line(line, identity_names=identity_names)
                jobbish = bool(
                    probe
                    and (probe.role or probe.company)
                    and probe.start
                )
                if not jobbish:
                    if pending_jobs:
                        leftover = _identity_leftover_after_dates(peeled)
                        if extract_date_range(peeled)[0] and (
                            not leftover
                            or leftover.lower() in {'present', 'current', 'now', 'ongoing'}
                            or len(leftover.split()) <= 1
                        ):
                            if _attach_duration_to_pending(peeled):
                                continue
                        pending_desc.append(line)
                    continue
        duration_m = _EMPLOYMENT_DURATION_LABEL.match(header_probe)
        if duration_m and not in_project_block:
            blob = duration_m.group(1) or header_probe
            if _attach_duration_to_pending(blob):
                continue
            d_start, d_end = extract_date_range(blob)
            if d_start:
                is_cur = bool(
                    d_end
                    and re.match(
                        r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                        d_end,
                    )
                )
                pending_jobs.append(
                    ExperienceEntry(
                        start=d_start,
                        end='' if is_cur else (d_end or ''),
                        is_current=is_cur,
                    )
                )
                continue
        entry = _parse_experience_line(line, identity_names=identity_names)
        if entry and (entry.role or entry.company or entry.start or entry.location):
            if _is_project_like_experience(entry.role, entry.company):
                a, b = (entry.start or ''), (entry.end or '')
                if not a:
                    a, b = extract_date_range(line)
                if a:
                    is_cur = bool(
                        entry.is_current
                        or (
                            b
                            and re.match(
                                r'(?i)^(present|current|now|till\s*date|ongoing|pursuing)$',
                                b,
                            )
                        )
                    )
                    pending_project_tenure = (a, '' if is_cur else (b or ''), is_cur)
                continue
            if (
                pending_project_tenure
                and (entry.company or '').strip()
                and not (entry.start or '').strip()
                and (
                    _looks_like_org_header(entry.company)
                    or _looks_like_company_line(entry.company)
                )
            ):
                ps, pe, pc = pending_project_tenure
                entry = entry.model_copy(
                    update={'start': ps, 'end': pe, 'is_current': bool(entry.is_current or pc)}
                )
                pending_project_tenure = None
            # Date/location-only line → attach to the open job (even after duties)
            # when that job has no start yet. If the open job already has dates,
            # this line starts the next date-first row.
            date_only = (
                not (entry.role or '').strip()
                and not (entry.company or '').strip()
                and bool(entry.start or entry.location)
            )
            if date_only and pending_jobs and not (pending_jobs[-1].start or '').strip():
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
            if (
                date_only
                and pending_jobs
                and (pending_jobs[-1].start or '').strip()
                and not (pending_jobs[-1].end or '').strip()
                and not pending_jobs[-1].is_current
                and (entry.start or '')
                and not (entry.end or '').strip()
                and not entry.is_current
            ):
                prev = pending_jobs[-1]
                pending_jobs[-1] = prev.model_copy(update={'end': entry.start})
                continue
            if (
                date_only
                and not pending_jobs
                and entries
                and not (entries[-1].start or '').strip()
            ):
                prev = entries[-1]
                entries[-1] = prev.model_copy(
                    update={
                        'start': prev.start or entry.start,
                        'end': prev.end or entry.end,
                        'is_current': prev.is_current or entry.is_current,
                        'location': (prev.location or entry.location or '')[:120],
                    }
                )
                continue
            # Date-only pending + company-only header → one metadata object
            if (
                pending_jobs
                and not pending_desc
                and not (pending_jobs[-1].role or '').strip()
                and not (pending_jobs[-1].company or '').strip()
                and (pending_jobs[-1].start or '').strip()
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
                and not (pending_jobs[-1].role or '').strip()
                and (pending_jobs[-1].company or '').strip()
                and (entry.role or '').strip()
                and not (entry.company or '').strip()
                and (
                    not pending_desc
                    or _pending_desc_is_preamble_noise(pending_desc)
                )
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
                and (
                    not pending_desc
                    or _pending_desc_is_preamble_noise(pending_desc)
                )
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
            if pending_jobs and pending_desc:
                _flush_pending()
            elif (
                pending_jobs
                and not pending_desc
                and _is_weak_experience_row(pending_jobs[-1])
                and _is_strong_experience_row(entry)
                and _experience_rows_complement(pending_jobs[-1], entry)
            ):
                pending_jobs[-1] = _merge_experience_pair(pending_jobs[-1], entry)
                continue
            if (
                pending_jobs
                and (entry.company or '').strip()
                and _experience_rows_complement(pending_jobs[-1], entry)
            ):
                pending_jobs[-1] = _merge_experience_pair(pending_jobs[-1], entry)
                continue
            pending_jobs.append(entry)
            continue
        stripped = re.sub(r'^[\s•·\-\*●]+', '', line.strip())
        if not stripped or stripped in '-–—' or is_section_header_line(stripped):
            continue
        if _BARE_DUTY_HEADER.match(stripped):
            continue
        duration_m = _EMPLOYMENT_DURATION_LABEL.match(stripped)
        if duration_m and pending_jobs:
            if _attach_duration_to_pending(duration_m.group(1) or stripped):
                continue
        if _EXP_META_LINE.match(stripped) or _LABELED_DUTY_LINE.match(stripped):
            if _is_employment_date_carrier(stripped) and _attach_duration_to_pending(stripped):
                continue
            if pending_jobs:
                pending_desc.append(line)
            continue
        if is_contact_or_reference_line(stripped) or looks_like_contact_person_line(stripped):
            in_contact_block = True
            continue
        leftover = _identity_leftover_after_dates(stripped)
        if _is_employment_date_carrier(stripped) or (
            extract_date_range(stripped)[0] and (
                not leftover
                or leftover.lower() in {'present', 'current', 'now', 'ongoing', 'till date'}
                or len(leftover.split()) <= 1
            )
        ):
            if _attach_duration_to_pending(stripped):
                continue
        if pending_jobs and _looks_like_job_location_line(stripped) and not extract_date_range(stripped)[0]:
            prev = pending_jobs[-1]
            if not (prev.location or '').strip():
                pending_jobs[-1] = prev.model_copy(update={'location': stripped[:120]})
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
            and _looks_like_company_line(stripped, identity_names=identity_names)
        ):
            prev = pending_jobs[-1]
            pending_jobs[-1] = prev.model_copy(update={'company': stripped[:200]})
            continue
        if pending_jobs:
            last = pending_jobs[-1]
            if (
                not (last.role or '').strip()
                and ((last.company or '').strip() or (last.start or '').strip())
                and _looks_like_role_only_line(stripped)
            ):
                pending_jobs[-1] = last.model_copy(update={'role': stripped[:200]})
                continue
            pending_desc.append(line)

    _flush_pending()
    entries[:] = _attach_orphan_dates_to_entries(entries, lines)

    cleaned: list[ExperienceEntry] = []
    for e in entries:
        role = peel_inline_contact((e.role or '').strip())
        company = peel_inline_contact((e.company or '').strip())
        if identity_is_employer_value(company, identity_names):
            company = ''
        if identity_is_employer_value(role, identity_names) and not _has_job_title_cue(role):
            role = ''
        if role != (e.role or '').strip() or company != (e.company or '').strip():
            e = e.model_copy(update={'role': role, 'company': company})
        if _DUTY_VERB_START.match(role) or _DUTY_VERB_START.match(company):
            continue
        if is_non_job_experience_record(e):
            continue
        if (role and role[:1] in '•·*●') or (company and company[:1] in '•·*●'):
            continue
        if not (role or company or e.start):
            continue
        if _TRAINING_ONLY_COMPANY.match(company) and not _has_job_title_cue(role):
            continue
        if e.start or (role and company and not _is_bullet_or_duty_line(role)):
            cleaned.append(e)
        elif role and e.start and (
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
        elif company and (e.description or '').strip():
            cleaned.append(e)
    stacked = _coalesce_stacked_experience_entries(cleaned)
    stacked = _attach_headline_role_from_text(stacked, full_text)
    return _attach_prefix_tenures(_finalize_experience_entries(stacked), full_text)


def parse_summary(section_text: str, full_text: str = '') -> str:
    """Prefer full-text section-aware extraction; section body only when clearly better."""
    from app.ai.parser.enrichment.resume_text_inference import (
        SUMMARY_HEADING_PRIORITY,
        _normalize_summary_body,
        is_section_header_line,
    )

    full = extract_summary_from_text(full_text) if full_text else ''
    if full and is_valid_summary(full):
        return full

    raw = (section_text or '').strip()
    if raw:
        compact = ' '.join(raw.split()).strip().rstrip(':').strip()
        # Heading-only section blobs are not summaries
        if compact.lower() in SUMMARY_HEADING_PRIORITY or is_section_header_line(compact):
            return full if is_valid_summary(full) else ''
        cleaned = _normalize_summary_body(raw, max_len=2000)
        if (
            cleaned
            and is_valid_summary(cleaned)
            and len(cleaned) >= 80
            and not re.match(r'(?i)^(?:responsibilit|roles?\s+and)', cleaned)
        ):
            return cleaned
    return full if is_valid_summary(full) else ''


_CERT_HEADING_LINE = re.compile(
    r'(?i)^(?:\*\*)?(?:certifications?|certificates?|licenses?|'
    r'professional\s+certifications?|courses?)\s*:?\s*(.*)$'
)


def _certificate_entries_from_extract(full_text: str) -> list[CertificateEntry]:
    from app.ai.parser.enrichment.resume_text_inference import extract_certifications_from_text

    certs: list[CertificateEntry] = []
    for c in extract_certifications_from_text(full_text or ''):
        if isinstance(c, str) and c.strip():
            certs.append(CertificateEntry(name=c.strip()[:200]))
        elif isinstance(c, dict):
            name = str(c.get('name') or '').strip()
            if name:
                certs.append(
                    CertificateEntry(
                        name=name[:200],
                        issuer=str(c.get('issuer') or '')[:200],
                    )
                )
    return certs


def _split_inline_cert_tokens(blob: str) -> list[CertificateEntry]:
    from app.ai.parser.enrichment.resume_text_inference import is_plausible_cert_name

    out: list[CertificateEntry] = []
    for piece in re.split(r'[,;/|]', blob or ''):
        name = re.sub(r'^[\s•·\-\*]+', '', piece.strip())
        if len(name) < 3 or is_section_header_line(name):
            continue
        if is_plausible_cert_name(name) or (len(name.split()) <= 8 and name[0].isupper()):
            out.append(CertificateEntry(name=name[:200]))
    return out


def parse_certifications(section_text: str, full_text: str = '') -> list[CertificateEntry]:
    raw = (section_text or '').strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()] if raw else []
    out: list[CertificateEntry] = []
    if lines:
        head = _CERT_HEADING_LINE.match(lines[0])
        if head:
            trailing = (head.group(1) or '').strip()
            if trailing:
                out.extend(_split_inline_cert_tokens(trailing))
            lines = lines[1:]
        for line in lines:
            stripped = re.sub(r'^[\s•·\-\*\d\.]+', '', line.strip())
            if not stripped or is_section_header_line(stripped):
                continue
            if extract_date_range(stripped)[0] and len(stripped.split()) <= 4:
                continue
            parts = re.split(r'\s+[-–—|]\s+|\s+from\s+|\s+by\s+', stripped, maxsplit=1, flags=re.I)
            name = parts[0].strip()
            if len(name) < 3:
                continue
            out.append(
                CertificateEntry(
                    name=name[:200],
                    issuer=parts[1].strip()[:200] if len(parts) > 1 else '',
                )
            )
    if out:
        return out
    if full_text:
        return _certificate_entries_from_extract(full_text)
    return []


_PROJECT_STOP_LINE = re.compile(
    r'(?i)^(?:strengths?|key\s+strengths?|achievements?(?:\s*/\s*tasks)?|'
    r'awards|honou?rs|certifications?|education|skills?|languages?|'
    r'hobbies|declaration|personal\s+details|interests?|references?|'
    r'science\s*-|information\s+technology)\s*:?\s*$'
)
_PROJECT_PAGE_NOISE = re.compile(
    r'(?i)^(?:page\s+\d+(?:\s+of\s+\d+)?|curriculum vitae|confidential(?:\s+resume)?)$'
)
_PROJECT_META_LINE = re.compile(
    r'(?i)^(?:client|organization|organisation|role|duration|period|'
    r'technolog(?:y|ies)|tech\s*stack|tools?|environment|team\s+size|'
    r'project\s+title|project\s+name)\s*:'
)
_PROJECT_DUTY_START = re.compile(
    r'(?i)^(?:'
    r'managed|executed|coordinated|collaborated|utilized|maintained|'
    r'facilitated|developed|designed|created|built|led|drove|implemented|'
    r'optimized|improved|increased|worked|assisted|supported|handled|'
    r'performed|conducted|analyzed|monitored|delivered|owned|spearheaded|'
    r'researched|prepared|observed|catalogued|reviewed|refactored|'
    r'designing|developing|implementing|creating|building|improving|'
    r'reducing|leveraging|maintaining|supporting|leading|writing|'
    r'responsible\s+for|created\s+and|wrote\s+complex'
    r')\b'
)


def _mostly_upper_title(text: str) -> bool:
    letters = [c for c in (text or '') if c.isalpha()]
    if len(letters) < 4:
        return False
    return (sum(1 for c in letters if c.isupper()) / len(letters)) >= 0.72


def _is_project_body_line(text: str) -> bool:
    s = (text or '').strip()
    if not s:
        return False
    from app.ai.document_intelligence.bullets import is_bullet_line, looks_like_list_item

    if is_bullet_line(s) or looks_like_list_item(s):
        return True
    if _PROJECT_DUTY_START.match(s) or _PROJECT_META_LINE.match(s):
        return True
    if s[:1].islower():
        return True
    if _DATE_ONLY_LINE.match(s) or re.match(r'^\(.*\d{4}.*\)\s*$', s):
        return True
    return False


def _is_credible_project_heading(text: str, *, has_current: bool, current_has_body: bool) -> bool:
    """New project only with heading-like evidence — never a bullet or wrap."""
    s = (text or '').strip()
    if not s or _PROJECT_STOP_LINE.match(s) or _PROJECT_PAGE_NOISE.match(s):
        return False
    if _is_project_body_line(s):
        return False
    if extract_date_range(s)[0] and not _mostly_upper_title(s):
        return False
    words = s.split()
    if len(words) > 14:
        return False
    if s.endswith('.') and len(words) > 4:
        return False
    if looks_like_phone_token(s) or looks_like_email_or_url(s):
        return False
    strong = _mostly_upper_title(s) or bool(
        re.search(r'(?i)\b(?:project|portal|system|application|app|tool|platform|website)\b', s)
    )
    if not has_current:
        return True
    if current_has_body and (strong or (s[:1].isupper() and len(words) <= 10 and not s.endswith(','))):
        return True
    # Title wrap: ALL-CAPS continuation belongs to the current name, not a new project
    if strong and not current_has_body:
        return False
    return False


def _coalesce_exploded_projects(rows: list[ProjectEntry]) -> list[ProjectEntry]:
    """Merge fragment rows that are wrap/duty text mistaken for names."""
    if len(rows) <= 1:
        return rows
    out: list[ProjectEntry] = []
    for row in rows:
        name = (row.name or '').strip()
        desc = (row.description or '').strip()
        if not name:
            if out and desc:
                prev = out[-1]
                out[-1] = prev.model_copy(
                    update={'description': f'{prev.description}\n{desc}'.strip()[:2000]}
                )
            continue
        fragment = _is_project_body_line(name) or name[:1].islower()
        if out and fragment and not _mostly_upper_title(name):
            prev = out[-1]
            extra = name if not desc else f'{name}\n{desc}'
            out[-1] = prev.model_copy(
                update={'description': f'{prev.description}\n{extra}'.strip()[:2000]}
            )
            continue
        out.append(row)
    # Explosion guard: too many empty names relative to populated ones
    if len(out) > 8:
        populated = [r for r in out if (r.description or '').strip()]
        if populated and len(out) > len(populated) * 3:
            merged: list[ProjectEntry] = []
            for r in out:
                if merged and not (r.description or '').strip() and not _mostly_upper_title(r.name):
                    prev = merged[-1]
                    merged[-1] = prev.model_copy(
                        update={'description': f'{prev.description}\n{r.name}'.strip()[:2000]}
                    )
                else:
                    merged.append(r)
            out = merged
    return [r for r in out if (r.name or '').strip()]


def parse_projects(section_text: str) -> list[ProjectEntry]:
    from app.ai.document_intelligence.bullets import (
        is_bullet_line,
        is_glyph_crumb,
        join_duty_lines,
        restore_inferred_list_markers,
        split_inline_bullets,
        strip_bullet_prefix,
    )

    lines = [
        ln.strip()
        for ln in restore_inferred_list_markers(
            split_inline_bullets(section_text or '')
        ).splitlines()
        if ln.strip() and not is_glyph_crumb(ln)
    ]
    out: list[ProjectEntry] = []
    current_name = ''
    current_desc: list[str] = []

    def _flush() -> None:
        nonlocal current_name, current_desc
        name = (current_name or '').strip()
        desc = join_duty_lines(current_desc).strip()
        if name or desc:
            techs: list[str] = []
            m_tech = re.search(
                r'(?i)(?:tech(?:nolog(?:y|ies))?|stack|tools?)\s*:\s*(.+)$',
                desc,
            )
            if m_tech:
                techs = [
                    t.strip()
                    for t in re.split(r'[,|/]', m_tech.group(1))
                    if t.strip() and len(t.strip()) < 40
                ]
            if not name and desc:
                first, _, rest = desc.partition('\n')
                first = re.sub(r'^•\s*', '', first).strip()
                if _is_credible_project_heading(first, has_current=False, current_has_body=False):
                    name, desc = first[:200], rest.strip()
                else:
                    name = first[:200]
            if name and not _PROJECT_STOP_LINE.match(name):
                out.append(
                    ProjectEntry(
                        name=name[:200],
                        description=desc[:2000],
                        technologies=techs[:12],
                    )
                )
        current_name = ''
        current_desc = []

    for line in lines:
        probe = re.sub(r'^[\s•·\-\*●]+', '', line)
        if _PROJECT_PAGE_NOISE.match(probe):
            continue
        if is_section_header_line(probe) or _PROJECT_STOP_LINE.match(probe):
            from app.ai.parser.layout.heuristic import normalize_section_header

            lab = normalize_section_header(probe) or ''
            if lab == 'Projects':
                continue
            _flush()
            break
        bullet = is_bullet_line(line)
        body = strip_bullet_prefix(line) if bullet else line
        has_current = bool(current_name or current_desc)
        current_has_body = bool(current_desc)
        if bullet or _is_project_body_line(body):
            current_desc.append(line)
            continue
        if current_name and not current_has_body and (
            _mostly_upper_title(body) or _PROJECT_META_LINE.match(body)
        ):
            # Title wrap / client line stays on the open project
            if _PROJECT_META_LINE.match(body) or extract_date_range(body)[0]:
                current_desc.append(line)
            else:
                current_name = f'{current_name} {body}'.strip()[:200]
            continue
        if _is_credible_project_heading(
            body, has_current=has_current, current_has_body=current_has_body
        ):
            _flush()
            current_name = body[:200]
            continue
        if not current_name:
            current_name = body[:200]
            continue
        current_desc.append(line)
    _flush()
    return _coalesce_exploded_projects(out)


def parse_languages(section_text: str) -> list[LanguageEntry]:
    blob = re.sub(r'(?i)\s*(?:&|and|/)\s*', ', ', section_text or '')
    items = split_list_items(blob)
    return [LanguageEntry(name=i) for i in items if i and len(i) < 40]


def languages_from_labeled_text(text: str) -> list[LanguageEntry]:
    """Pull 'Languages: a, b & c' / 'Linguistic Proficiency:' from any section."""
    if not (text or '').strip():
        return []
    m = re.search(
        r'(?im)^(?:linguistic\s+proficiency|languages?(?:\s+known)?|language\s+skills)\s*:\s*(.+)$',
        text,
    )
    if not m:
        return []
    return parse_languages(m.group(1))


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
    extra_meta: dict[str, Any] | None = None,
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
        field_meta=dict(extra_meta or {}),
    )
    return sanitize_candidate_profile(profile, source_text=source_text or '')


_INTERNISH_ROLE_RE = re.compile(r'(?i)\b(?:intern(?:ship)?s?|trainee|apprentice)\b')


def _merge_internships_listed_under_education(
    experience: list[ExperienceEntry],
    edu_text: str,
) -> list[ExperienceEntry]:
    """Jobs (including internships) sometimes sit under Education after a degree list."""
    if not (edu_text or '').strip():
        return experience
    extra = parse_experience(edu_text, '')
    seen = {
        ((e.role or '').strip().lower(), (e.company or '').strip().lower())
        for e in experience
    }
    out = list(experience)
    for e in extra:
        blob = f'{e.role or ""} {e.company or ""}'
        internish = bool(_INTERNISH_ROLE_RE.search(blob))
        if not internish and not _is_strong_experience_row(e):
            continue
        if is_non_job_experience_record(e):
            continue
        key = ((e.role or '').strip().lower(), (e.company or '').strip().lower())
        if key in seen or not (e.role or e.company):
            continue
        seen.add(key)
        out.append(e)
    if out is experience or out == experience:
        return experience
    return _finalize_experience_entries(out)


_CONTACT_TENURE_TAIL = re.compile(
    r'(?i)(?:[-–—]\s*)?(?:from\s+)?('
    r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|'
    r'dec(?:ember)?)\s+(?:19|20)\d{2}\s*(?:[-–—]|to)\s*'
    r'(?:still(?:\s+date)?|present|current|now|till\s*date|ongoing|(?:19|20)\d{2})'
    r')\s*[-–—]*$'
)


def _split_glued_contact_tenure_lines(text: str) -> str:
    """Peel 'email  -FROM SEP 2020 TO STILL DATE-' into contact + tenure lines."""
    out: list[str] = []
    for line in (text or '').splitlines():
        s = (line or '').rstrip()
        m = _CONTACT_TENURE_TAIL.search(s)
        if m and ('@' in s or looks_like_phone_token(s[: m.start()])):
            head = s[: m.start()].strip(' \t-–—')
            if head:
                out.append(head)
            out.append(m.group(0).strip(' \t-–—'))
            continue
        out.append(line)
    return '\n'.join(out)


_LABELED_EMPLOYMENT_LINE = re.compile(
    r'(?i)^(?:(?:current|previous|former|past|last)\s+)?'
    r'(?:(?:work\s+)?experience|company(?:\s+name)?|employer|'
    r'organization(?:[\'’]s)?(?:\s+name)?|'
    r'organisation(?:[\'’]s)?(?:\s+name)?|'
    r'role|title|'
    r'designation|position|duration|period|tenure)\s*:'
)


def _keeps_adjacent_employment_line(text: str) -> bool:
    s = (text or '').strip()
    if not s or is_section_header_line(s):
        return False
    if is_project_or_employment_meta_label(s):
        return _is_employment_date_carrier(s)
    if _LABELED_EMPLOYMENT_LINE.match(s) or _parse_unheaded_employment_row(s):
        return True
    if _LABELED_EMPLOYER_LINE.match(s) or _is_employment_date_carrier(s):
        return True
    prose = _parse_employment_sentence(s)
    if prose and (prose.role or '').strip() and (prose.company or '').strip():
        return True
    if extract_date_range(s)[0]:
        return True
    if _looks_like_role_only_line(s) or _looks_like_company_line(s):
        return True
    if _EMPLOYMENT_DURATION_LABEL.match(s):
        return True
    if re.search(r'(?i)\b(?:since|from)\s+(?:19|20)\d{2}\b', s) and (
        _has_job_title_cue(s) or _looks_like_role_only_line(s.split(',')[0].strip())
    ):
        return True
    return False


def _structural_employment_window(text: str) -> str:
    """Keep labeled/table employment lines only — never duty prose harvest."""
    lines = [(ln or '').strip() for ln in (text or '').splitlines()]
    keep: set[int] = set()
    for i, s in enumerate(lines):
        if not s:
            continue
        labeled = bool(_LABELED_EMPLOYMENT_LINE.match(s) or _parse_unheaded_employment_row(s))
        if not labeled:
            prose = _parse_employment_sentence(s)
            labeled = bool(
                prose
                and (prose.role or '').strip()
                and (prose.company or '').strip()
            )
        title_at = bool(
            re.search(r'(?i)\bat\s+[A-Z]', s)
            and (
                _has_job_title_cue(s.split(' at ')[0] if ' at ' in s.lower() else s)
                or _looks_like_role_only_line(re.split(r'(?i)\bat\s+', s, maxsplit=1)[0].strip())
            )
        )
        pipe_title = '|' in s and (
            _has_job_title_cue(s.split('|', 1)[0].strip())
            or _looks_like_role_only_line(s.split('|', 1)[0].strip())
        )
        if not labeled and not title_at and not pipe_title:
            continue
        keep.add(i)
        for j in (i - 2, i - 1, i + 1, i + 2):
            if 0 <= j < len(lines) and _keeps_adjacent_employment_line(lines[j]):
                keep.add(j)
    kept = [lines[i] for i in sorted(keep) if lines[i]]
    return '\n'.join(kept).strip()


def _keep_credible_jobs(jobs: list[ExperienceEntry]) -> list[ExperienceEntry]:
    kept: list[ExperienceEntry] = []
    for job in jobs:
        role = (job.role or '').strip()
        start, end = extract_date_range(role)
        if start:
            updates = {'role': ''}
            if not (job.start or '').strip():
                updates['start'] = start
                updates['end'] = end or job.end
                updates['is_current'] = (end or '').lower() == 'present' or job.is_current
            job = job.model_copy(update=updates)
        blob = f'{job.company or ""} {job.role or ""} {job.description or ""}'
        if is_fresher_or_years_only_experience_line(blob):
            continue
        if is_non_job_experience_record(job):
            continue
        if not has_credible_employment_evidence(job):
            continue
        kept.append(job)
    return kept


def _blob_has_employment_evidence(blob: str) -> bool:
    """True when a misplaced span looks like employment, not a skill list."""
    text = (blob or '').strip()
    if len(text) < 24:
        return False
    has_title = bool(_JOB_TITLE_CUE.search(text) or re.search(r'(?i)\bas\s+(?:a\s+)?[A-Z]', text))
    has_org = bool(
        any(_LABELED_EMPLOYER_LINE.match(ln.strip()) for ln in text.splitlines())
        or re.search(r'(?i)\b(?:pvt\.?|ltd\.?|llc|llp|inc\.?|limited|private)\b', text)
    )
    has_date = False
    for line in text.splitlines()[:80]:
        if extract_date_range(line)[0]:
            has_date = True
            break
    return bool((has_title and has_org) or (has_title and has_date) or (has_org and has_date))


_NON_EMPLOYMENT_DATE_SECTIONS = {
    'education', 'academic', 'certifications', 'certificates', 'awards',
    'honors', 'honours', 'personal details', 'declaration', 'publications',
}


def _orphan_employment_date_lines(
    sections: list[SectionSpan] | None,
) -> list[str]:
    """Date-only lines from non-education sections (two-column bleed)."""
    lines: list[str] = []
    for span in sections or []:
        label = (getattr(span, 'label', '') or '').strip().lower()
        if label in _NON_EMPLOYMENT_DATE_SECTIONS or 'education' in label:
            continue
        for ln in (getattr(span, 'text', '') or '').splitlines():
            s = (ln or '').strip()
            if s and (_is_employment_date_carrier(s) or _is_date_range_stub_text(s)):
                lines.append(s)
    return lines


def _recover_jobs_from_unlabeled_preamble(
    experience: list[ExperienceEntry],
    sections: list[SectionSpan],
    preamble: str,
    full_text: str = '',
) -> list[ExperienceEntry]:
    """When Experience is missing or only metadata stubs, recover structural jobs."""
    if experience and any(_is_strong_experience_row(e) for e in experience):
        if any(not (e.start or '').strip() for e in experience):
            extra = _orphan_employment_date_lines(sections)
            if extra:
                experience = _attach_orphan_dates_to_entries(experience, extra)
        return experience
    misplaced: list[str] = []
    for span in sections or []:
        label = (getattr(span, 'label', '') or '').strip().lower()
        if 'project' in label:
            continue
        if label in {
            'languages', 'education', 'declaration',
        }:
            continue
        blob = (span.text or '').strip()
        if blob and blob not in misplaced and _blob_has_employment_evidence(blob):
            misplaced.append(blob)
        elif label in {
            'skills', 'unclassified', 'summary', 'objective', 'preamble',
        }:
            if blob and blob not in misplaced:
                misplaced.append(blob)
    structural = _structural_employment_window('\n'.join(misplaced))
    if full_text:
        extra = _structural_employment_window(full_text)
        if extra:
            structural = f'{structural}\n{extra}'.strip()
    recovered: list[ExperienceEntry] = []
    if structural:
        recovered = _keep_credible_jobs(parse_experience('Experience\n' + structural, full_text or ''))
    if not recovered:
        for blob in misplaced:
            if not _blob_has_employment_evidence(blob):
                continue
            kept = _keep_credible_jobs(parse_experience('Experience\n' + blob, full_text or ''))
            for job in kept:
                recovered.append(job)
    if recovered:
        return _finalize_experience_entries(list(experience or []) + recovered)
    parts: list[str] = []
    if (preamble or '').strip():
        parts.append(preamble)
    for span in sections or []:
        if getattr(span, 'source', '') == 'unclassified-preamble':
            blob = (span.text or '').strip()
            if blob and blob not in parts:
                parts.append(blob)
    window = _split_glued_contact_tenure_lines('\n'.join(parts).strip())
    if not window:
        return experience
    return _keep_credible_jobs(parse_experience(window, ''))


_SKILL_LABEL_LINE = re.compile(
    r'(?i)^(?:(?:technical|key|core|soft)\s+)?skills?\s*:|'
    r'^technical\s+(?:skills?|proficiency|expertise|knowledge)\s*:|'
    r'^technicalskill\s*:|'
    r'^(?:tools?|technologies?|tech\s+stack|competencies?)\s*(?:used)?\s*:'
)


def _skillish_unclassified_lines(blob: str) -> str:
    """Keep labeled skill lines and short tool tokens from sidebar Unclassified."""
    from app.ai.document_intelligence.bullets import strip_bullet_prefix
    from app.ai.parser.enrichment.resume_text_inference import (
        is_biodata_or_address_line,
        is_plausible_skill_item,
        split_list_items,
    )

    kept: list[str] = []
    for line in (blob or '').splitlines():
        s = strip_bullet_prefix(line)
        if not s:
            continue
        if is_biodata_or_address_line(s):
            continue
        if is_labeled_contact_metadata(s):
            continue
        if _SKILL_LABEL_LINE.match(s):
            kept.append(s)
            continue
        if ',' in s or '|' in s:
            parts = split_list_items(s)
            if (
                2 <= len(parts) <= 12
                and all(len(p.split()) <= 4 and is_plausible_skill_item(p) for p in parts)
            ):
                kept.extend(parts)
            continue
        if len(s) > 80 or len(s.split()) > 8:
            continue
        if not is_plausible_skill_item(s):
            continue
        ok, _ = validate_skill_item(s)
        if ok:
            kept.append(s)
    return '\n'.join(kept)


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
        'Employment History',
        'Work History',
        'Career History',
        'Internship',
        'Internships',
        'Internship Experience',
        'Industrial Training',
        'Summer Internship',
        'Management Internship',
        'Research Internship',
        'Graduate Internship',
        'Training Experience',
        'Technical Experience',
    )
    edu_text = pick_section(
        sections,
        'Education',
        'Academic Background',
        'Academic Qualifications',
        'Academic Qualification',
        'Academics',
        'Academic Details',
        'Educational Qualifications',
        'Educational Background',
        'Educational Qualification',
        'Qualifications',
        'Scholastic Record',
    )
    skills_text = pick_section(
        sections,
        'Skills',
        'Technical Skills',
        'Professional Skills',
        'Relevant Skills',
        'Technical Proficiency',
        'Technical Expertise',
        'Technical Knowledge',
        'Core Skills',
        'Core Competencies',
        'Key Skills',
        'Technologies',
        'Tools',
        'Areas of Expertise',
        'Computer Skills',
        'IT Skills',
        'Software Skills',
        'Additional Skills',
        'Skills Highlights',
        'Knowledge and Skills',
        'Knowledge & Skills',
        'Technical Skills and Tools',
        'Skill Set',
        'Skillset',
        'Other Technical Skills',
    )
    # Prefer explicit summary/objective labels (aliases also map to Summary).
    summary_text = pick_section(
        sections,
        'Career Objective',
        'Professional Objective',
        'Professional Summary',
        'Professional Profile',
        'Personal Profile',
        'Profile Summary',
        'Summary',
        'Objective',
        'Profile',
        'About Me',
        'Career Profile',
        'Career Summary',
    )
    cert_text = pick_section(
        sections,
        'Certifications',
        'Certificates',
        'Licenses',
        'Professional Certifications',
        'Courses',
    )
    proj_text = pick_section(
        sections,
        'Projects',
        'Project',
        'Academic Projects',
        'Personal Projects',
        'Major Projects',
        'Key Projects',
        'Key Project',
        'Project Experience',
        'Project Details',
    )
    lang_text = pick_section(
        sections,
        'Languages',
        'Linguistic Proficiency',
        'Language Skills',
        'Languages Known',
    )
    ach_text = pick_section(
        sections,
        'Achievements',
        'Accomplishments',
        'Awards',
        'Honors',
        'Honours',
        'Extracurricular Achievements',
    )
    act_text = pick_section(
        sections,
        'Activities',
        'Extracurricular Activities',
        'Extra Curricular',
        'Leadership Activities',
        'Co-curricular Activities',
    )
    unclassified = '\n'.join(
        (s.text or '')
        for s in sections
        if s.label == 'Unclassified' and s.source != 'unclassified-preamble'
    ).strip()
    unclassified_all = '\n'.join(
        (s.text or '')
        for s in sections
        if s.label == 'Unclassified'
    ).strip()
    # Weak section boundaries must not drop lines. Sidebar/preamble Unclassified
    # can recover short skill tokens only — never Experience, never preamble dumps
    # into Education.
    if not (skills_text or '').strip() and unclassified_all:
        skillish = _skillish_unclassified_lines(unclassified_all)
        if skillish:
            skills_text = skillish.strip()
    if unclassified and len((edu_text or '').strip()) < 40:
        edu_text = f'{edu_text}\n{unclassified}'.strip()
    if len((edu_text or '').strip()) < 80 and full_text:
        pipe_edu = [
            ln.strip()
            for ln in full_text.splitlines()
            if '|' in ln and re.search(
                r'(?i)\b(?:degree|university|college|bachelor|b\.?\s*e|hsc|ssc)\b',
                ln,
            )
        ]
        if pipe_edu:
            edu_text = 'Education\n' + '\n'.join(pipe_edu)

    results: dict[str, Any] = {}
    # Sequential section parsing — avoids import/thread deadlocks under Flask workers
    results['personal'] = parse_personal(full_text, preamble, source_filename=source_filename)
    results['contact'] = parse_contact(full_text, preamble)
    results['experience'] = parse_experience(exp_text, full_text)
    results['education'] = parse_education(edu_text, full_text)
    results['experience'] = _merge_internships_listed_under_education(
        results['experience'],
        edu_text,
    )
    results['experience'] = _recover_jobs_from_unlabeled_preamble(
        results['experience'],
        sections,
        preamble,
        full_text,
    )
    results['skills'] = parse_skills(skills_text, full_text)
    results['summary'] = parse_summary(summary_text, full_text)
    results['summary_trace'] = extract_summary_details(full_text)
    results['certs'] = parse_certifications(cert_text, full_text)
    results['projects'] = parse_projects(proj_text)
    results['languages'] = parse_languages(lang_text)
    if not results['languages']:
        results['languages'] = languages_from_labeled_text(full_text)
        if not results['languages']:
            personal_blob = pick_section(
                sections,
                'Personal Details',
                'Personal Information',
                'Biodata',
            )
            results['languages'] = languages_from_labeled_text(personal_blob)
    _ = max_workers  # retained for API compat / future parallel profiles

    personal: PersonalInfo = results['personal']
    summary = results['summary'] or ''
    if summary and not is_valid_summary(summary):
        summary = ''
    if not summary:
        # Prefer validated section-aware extraction over preamble heuristics
        traced = results.get('summary_trace') or extract_summary_details(full_text)
        summary = (traced.get('value') or '') if isinstance(traced, dict) else ''
    if not summary and preamble:
        # Unlabeled intro paragraph after contact (common in Indian resumes).
        # Never accept contact / phone / email blocks as summary.
        from app.ai.parser.enrichment.resume_text_inference import _normalize_summary_body

        paras = [p.strip() for p in re.split(r'\n\s*\n', preamble) if p.strip()]
        for p in paras:
            candidate = _normalize_summary_body(p, max_len=2000)
            # Require substantial unlabeled prose — not a name/contact crumb
            if len(candidate) < 40:
                continue
            if not re.search(
                r'(?i)\b(?:seeking|years?|professional|skilled|dedicated|motivated|'
                r'aspiring|objective|experience\s+as|proficient|graduate)\b',
                candidate,
            ):
                continue
            if is_valid_summary(candidate):
                summary = candidate
                break
        if not summary:
            # Single-block preamble (no blank lines) still may hold intro prose
            candidate = _normalize_summary_body(preamble, max_len=2000)
            if (
                len(candidate) >= 40
                and is_valid_summary(candidate)
                and re.search(
                    r'(?i)\b(?:seeking|years?|professional|skilled|dedicated|motivated|'
                    r'aspiring|objective|experience\s+as|proficient|graduate)\b',
                    candidate,
                )
            ):
                summary = candidate
    # Keep personal.summary only when validated; scrub contact bleed when possible
    personal_summary = ''
    if personal.summary:
        if is_valid_summary(personal.summary):
            personal_summary = personal.summary.strip()
        else:
            from app.ai.parser.enrichment.resume_text_inference import _normalize_summary_body

            scrubbed = _normalize_summary_body(personal.summary, max_len=2000)
            if is_valid_summary(scrubbed):
                personal_summary = scrubbed
    if summary and is_valid_summary(summary):
        personal = personal.model_copy(update={'summary': summary})
    elif personal_summary:
        personal = personal.model_copy(update={'summary': personal_summary})
    else:
        personal = personal.model_copy(update={'summary': ''})

    extra_meta: dict[str, Any] = {}
    name_source = getattr(personal, '_name_source', '') or (
        'deterministic' if (personal.full_name or '').strip() else ''
    )
    extra_meta['_field_provenance'] = {
        'personal.full_name': name_source,
        'experience': 'deterministic',
        'education': 'deterministic',
        'skills': 'deterministic',
        'contact': 'deterministic',
    }
    from app.ai.document_intelligence.bullets import split_bullet_items

    if ach_text:
        extra_meta['achievements'] = split_bullet_items(ach_text)
    if act_text:
        extra_meta['activities'] = split_bullet_items(act_text)
    str_text = pick_section(sections, 'Strengths', 'Key Strengths')
    if str_text:
        extra_meta['strengths'] = split_bullet_items(str_text)
    hobby = re.search(r'(?im)^hobbies?\s*:\s*(.+)$', full_text or '')
    if hobby:
        extra_meta['hobbies'] = hobby.group(1).strip()[:400]

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
        extra_meta=extra_meta,
    )
