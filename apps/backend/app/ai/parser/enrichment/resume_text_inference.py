"""
Extract Resume TOON fields from unstructured resume text.
Used by the inference stage after repair, normalization, and enrichment.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


SKILL_SECTION_STOP = (
    r'education|academic\s+background|academics|qualifications|'
    r'experience|work\s+experience|professional\s+experience|employment|work\s+history|'
    r'projects?|certifications?|certificates?|licenses?|credentials?|'
    r'languages?|awards?|interests?|references?|'
    r'professional\s+summary|summary|objective|profile|about\s+me'
)

SKILL_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:'
    r'technical\s+skills?|core\s+skills?|key\s+skills?|skill\s*sets?|skills?\s*sets?|'
    r'skills?\s+and\s+abilities|skills?\s+&\s+abilities|'
    r'skills?|tools?|technologies?|'
    r'tech\s+stack|frameworks?|programming\s+languages?|competencies?|expertise'
    r')(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?(?:' + SKILL_SECTION_STOP + r')\b|\Z)',
)

SUMMARY_SECTION_PATTERN = re.compile(
    r'(?i)(?:\*\*)?(?:professional\s+summary|summary|objective|profile|about\s+me)(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?[A-Z]|\Z)',
)

EDUCATION_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:education(?:al)?\s*(?:qualification|background|details)?s?'
    r'|academic\s+(?:background|details|qualifications?)|academics|qualifications)(?:\*\*)?\s*:?\s*'
    r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|work\s+experience|professional\s+experience|'
    r'employment|work\s+history|technical\s+skills?|core\s+skills?|key\s+skills?|skill\s*sets?|'
    r'skills?|tools?|technologies?|tech\s+stack|projects?|certifications?|certificates?|'
    r'languages?|awards?|personal\s+details|personal\s+information|biodata)\b|\Z)',
)

CERT_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:certifications?|certificates?|licenses?|credentials?)(?:\*\*)?\s*:?\s*'
    r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|work\s+experience|professional\s+experience|'
    r'employment|work\s+history|education|skills|technical\s+skills?|projects?|'
    r'languages?|awards?)\b|\Z)',
)

SECTION_HEADERS = frozenset({
    'summary', 'objective', 'profile', 'experience', 'work experience',
    'workexperience', 'professionalexperience',
    'professional experience', 'employment', 'education', 'skills', 'technical skills',
    'technical skill', 'core skills', 'core skill', 'key skills', 'key skill',
    'skill set', 'skills set', 'skills and abilities', 'abilities',
    'tools', 'technologies', 'tech stack', 'project', 'projects',
    'key project', 'key projects',
    'certifications', 'certificates', 'certifications and licenses', 'licenses',
    'languages', 'awards', 'interests',
    'references', 'contact', 'resume', 'curriculum vitae', 'cv', 'about me',
    'work history', 'qualification', 'qualifications', 'achievements',
    'internship', 'internships', 'internship experience', 'industrial training',
    'summer internship', 'trainings', 'training', 'apprenticeship',
    'internship / training',
    'academic details', 'academic background', 'academics',
    'educational qualifications', 'educational background',
    'personal details', 'personal information', 'biodata', 'bio data', 'contact details',
    'declaration', 'permanent address', 'present address', 'correspondence address',
    'current address', 'residential address',
})

# Career-objective / summary prose wrongly assigned as job titles by LLMs or line scrapers.
_OBJECTIVE_LIKE_TITLE = re.compile(
    r'(?i)^(?:'
    r'to\s+(?:help|work|seek|obtain|secure|contribute|become|build|develop|gain|pursue|'
    r'leverage|support|drive|create|deliver|learn|grow|join|explore)|'
    r'(?:seeking|looking\s+for|aspiring|motivated|passionate|dedicated|results[- ]oriented)|'
    r'(?:i\s+am|i\'m|my\s+(?:goal|objective|aim))'
    r')'
)
_HAS_OBJECTIVE_WORD = re.compile(r'(?i)\bobjectives?\b')

_NAME_LABEL_PREFIX = re.compile(
    r'(?i)^(percentage|percent|gpa|cgpa|score|marks?|grade|phone|mobile|email|e-?mail|'
    r'address|location|dob|date\s+of\s+birth|age|gender|father|mother|nationality|'
    r'passport|linkedin|github|portfolio|website|http|www)\b'
)
_BIODATA_LABEL = re.compile(
    r'(?i)^(?:'
    r'name|full\s*name|candidate\s*name|'
    r'date\s+of\s+birth|d\.?\s*o\.?\s*b\.?|dob|'
    r'gender|sex|marital\s+status|married|unmarried|single|'
    r'permanent\s+address|present\s+address|current\s+address|correspondence\s+address|'
    r'residential\s+address|address|'
    r'father(?:\'?s)?\s*name|mother(?:\'?s)?\s*name|spouse|'
    r'nationality|religion|languages?\s+known|blood\s+group|'
    r'passport|aadhaar|aadhar|pan(?:\s*card)?|'
    r'personal\s+details|personal\s+information|biodata|bio\s*data|contact\s+details|'
    r'declaration'
    r')\b'
)
_CALENDAR_DATE = re.compile(
    r'(?i)^(?:'
    # 20 November 1992 / 20th Nov 1992
    r'\d{1,2}(?:st|nd|rd|th)?\s+'
    r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s*,?\s*\d{4}'
    r'|'
    # November 20, 1992
    r'(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)'
    r'\s+\d{1,2}(?:st|nd|rd|th)?\s*,?\s*\d{4}'
    r'|'
    r'\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}'
    r'|'
    r'\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}'
    r')$'
)
_ADDRESS_LIKE = re.compile(
    r'(?i)\b(?:'
    r'colony|nagar|society|apartment|flat|plot|survey|'
    r'tal(?:uka)?[\s\-]|dist(?:rict)?[\s\-]|pin(?:code)?|'
    r'h\.?\s*no\.?|s\.?\s*no\.?|house\s*no|at\s+post|near\s+'
    r')\b'
    r'|^\d{6}$'  # Indian PIN alone
)
_JOB_BULLET_INSTITUTION = re.compile(
    r'(?i)^(?:'
    r'configured|reorganize|rebuilding|issues?\s+for|responsible|worked|managed|'
    r'database\s+administrator|dba\b|developed|implemented|maintained|performed|'
    r'monitoring|backup|restore|till\s+da'
    r')'
)
_TECH_SINGLE_TOKEN = frozenset({
    'html', 'css', 'sql', 'java', 'python', 'javascript', 'typescript', 'react',
    'angular', 'nodejs', 'docker', 'kubernetes', 'aws', 'azure', 'linux', 'git',
    'c++', 'c#', '.net', 'mongodb', 'mysql', 'oracle', 'redis', 'kafka',
})
_SKILL_CRUMB_TOKENS = frozenset({
    'set', 'tools', 'technologies', 'technology', 'skills', 'skill', 'expertise',
    'competencies', 'frameworks', 'languages', 'platforms', 'tools and platforms',
    'skills tools and platforms', 'and platforms', 'and tools',
})
_INSTITUTION_LIKE = re.compile(
    r'(?i)\b(?:university|college|school|institute|academy|polytechnic|vidyalaya|'
    r'iit|nit|iiit|bits|mit)\b'
)
_CERT_CUE = re.compile(
    r'(?i)\b(?:certif|licensed?|licence|aws|azure|google|oracle|course|training|'
    r'diploma|nanodegree|accreditation|credential)\b'
)
_DEGREE_FRAGMENT = re.compile(r'(?i)^(ma|ba|be|bs|ms|me|bsc|msc|mca|bca)$')


def is_biodata_or_address_line(line: str | None) -> bool:
    """True for personal-details labels, calendar DOBs, and address fragments."""
    t = (line or '').strip().lstrip(':').strip()
    if not t:
        return False
    # Strip leading label punctuation like ": Married"
    if _BIODATA_LABEL.search(t):
        return True
    if t.startswith(':') and _BIODATA_LABEL.search(t.lstrip(':').strip()):
        return True
    if _CALENDAR_DATE.match(t):
        return True
    if _ADDRESS_LIKE.search(t) and not re.search(
        r'(?i)\b(?:engineer|developer|manager|analyst|consultant|administrator|dba)\b',
        t,
    ):
        return True
    return False


# Real title cue — comma / KPI list fragments may pass length checks without these.
_JOB_TITLE_CUE = re.compile(
    r'(?i)\b(?:'
    r'intern(?:ship)?|trainee|engineer|developer|analyst|architect|manager|lead|'
    r'consultant|specialist|administrator|scientist|designer|officer|executive|'
    r'associate|coordinator|director|founder|ceo|cto|cfo|sde|swe|qa|devops|'
    r'programmer|technician|support|recruiter|hr\b|teacher|professor|researcher'
    r')\b'
)
_TITLE_KPI_LIST = re.compile(
    r'(?i)(?:,\s*and\b)|(?:\bkpis?\b)|(?:\brevenue\b)|(?:\btrends?\b)'
)


def is_plausible_job_title(title: str | None) -> bool:
    """Reject summary/objective/biodata/address fragments that are not job titles."""
    t = (title or '').strip().lstrip(':').strip()
    if not t:
        return False
    if len(t) > 100:
        return False
    words = t.split()
    if len(words) > 8:
        return False
    if _OBJECTIVE_LIKE_TITLE.search(t):
        return False
    if _HAS_OBJECTIVE_WORD.search(t):
        return False
    if is_section_header_line(t):
        return False
    if is_biodata_or_address_line(t):
        return False
    # Lowercase lines are duty wrap / prose, not titles
    if t[0].islower():
        return False
    # Duty/KPI fragments: "Trends, and Revenue KPIs…" — require a real title cue
    if ',' in t and not _JOB_TITLE_CUE.search(t):
        return False
    if _TITLE_KPI_LIST.search(t) and not _JOB_TITLE_CUE.search(t):
        return False
    return True


_JOB_TITLE_NAME_BLOCKLIST = frozenset({
    'human resources', 'system administrator', 'systems administrator',
    'data engineer', 'software engineer', 'software developer', 'team lead',
    'project manager', 'delivery manager', 'database administrator',
    'linux administrator', 'network engineer', 'devops engineer',
    'career objective', 'professional summary', 'professional', 'summary',
    'middleware administrator', 'oracle dba', 'sql dba', 'mssql dba',
    'fresher', 'experienced', 'immediate joining',
    'designation', 'certification', 'certifications', 'skills',
    'it team lead', 'assistant professor', 'curriculum vitae',
})

# Cities / regions often appear alone on early resume lines and get mistaken for names.
_PLACE_NAME_BLOCKLIST = frozenset({
    'mumbai', 'delhi', 'new delhi', 'bangalore', 'bengaluru', 'hyderabad', 'chennai',
    'kolkata', 'pune', 'ahmedabad', 'gurgaon', 'gurugram', 'noida', 'faridabad',
    'jaipur', 'lucknow', 'nagpur', 'indore', 'bhopal', 'surat', 'vadodara',
    'coimbatore', 'kochi', 'chandigarh', 'mysore', 'mysuru', 'thane', 'navi mumbai',
    'andheri', 'powai', 'bandra', 'mehdipatnam', 'ranchi', 'kota', 'tirupathi',
    'tirupati', 'india', 'remote', 'hybrid', 'wfh', 'work from home',
    'austin', 'seattle', 'san francisco', 'new york', 'london', 'toronto',
    'singapore', 'dubai', 'berlin',
})


def is_plausible_person_name(name: str | None) -> bool:
    """Reject metrics, labels, headers, and tech tokens misread as person names."""
    t = (name or '').strip()
    # PDF/Word often appends zero-width spaces to header names
    t = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', t).replace('\xa0', ' ').strip()
    # Honorific prefixes common on Indian resumes
    t = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', t).strip()
    # Trailing punctuation / form separators ("Career Objective-")
    t = t.rstrip('-:–—|').strip()
    if not t or len(t) < 2 or len(t) > 80:
        return False
    # Placeholder / form labels wrongly captured as names
    if t.lower() in {
        'name', 'full name', 'your name', 'candidate name', 'student', 'resume',
        'curriculum vitae', 'cv', 'objective', 'career objective', 'profile',
        'address', 'contact', 'email', 'phone', 'mobile', 'unknown',
        'designation', 'certification', 'skills', 'summary',
    }:
        return False
    if t.lower() in _JOB_TITLE_NAME_BLOCKLIST:
        return False
    if t.lower() in _PLACE_NAME_BLOCKLIST:
        return False
    # Reject sentence / duty fragments
    if t.endswith('.'):
        return False
    if len(t.split()) >= 4 and re.search(
        r'(?i)\b(?:and|with|the|for|from|processes?|performing|managing|achieved)\b', t
    ):
        return False
    if '@' in t or 'http' in t.lower() or 'www.' in t.lower():
        return False
    if ':' in t or ',' in t or '|' in t:
        return False
    if re.search(r'\d', t):
        return False
    if _NAME_LABEL_PREFIX.search(t):
        return False
    if is_section_header_line(t):
        return False
    if re.match(r'^\+?\d[\d\s\-().]{6,}$', t):
        return False
    words = t.split()
    if not (1 <= len(words) <= 5):
        return False
    # Skill lists / tech stacks are not names
    for w in words:
        cleaned = w.strip(".,'").lower()
        if cleaned in _TECH_SINGLE_TOKEN:
            return False
    if len(words) == 1:
        token = words[0].strip('.,')
        if not token[0].isupper():
            return False
        if not token.replace("'", '').replace('-', '').isalpha():
            return False
        # Reject ALL-CAPS short acronyms (HTML, SQL, AWS)
        if token.isupper() and len(token) <= 5:
            return False
        return True
    # Multi-word names: allow ALL-CAPS resume headers (RAHUL SURESH SURVASE).
    # Only reject short ALL-CAPS tokens when they look like tech acronyms (<=3 chars).
    alpha_words = 0
    for w in words:
        cleaned = w.strip(".,'")
        if not cleaned:
            continue
        if not re.match(r"^[A-Za-z][A-Za-z'\-]*$", cleaned):
            return False
        if cleaned.isupper() and len(cleaned) <= 3 and cleaned.lower() in _TECH_SINGLE_TOKEN:
            return False
        if cleaned[0].isupper():
            alpha_words += 1
    return alpha_words >= 2


def is_date_range_only_line(line: str) -> bool:
    """True when the line is essentially just a date range (e.g. 06/2016 - 06/2017)."""
    s = (line or '').strip()
    if not s:
        return False
    m = DATE_RANGE_PATTERN.fullmatch(s) or DATE_RANGE_PATTERN.fullmatch(
        re.sub(r'^[\s•·\-\*]+', '', s).strip()
    )
    return bool(m)


def is_plausible_skill_item(item: str | None) -> bool:
    """Reject section headers and bare date ranges from skills lists."""
    s = (item or '').strip()
    if not s or len(s) < 2 or len(s) > 80:
        return False
    if is_section_header_line(s):
        return False
    if is_date_range_only_line(s):
        return False
    if DATE_RANGE_PATTERN.fullmatch(s):
        return False
    # Pure year or month/year alone
    if re.fullmatch(r'(?i)\d{1,2}[/\-]\d{4}|\d{4}|present|current|now', s):
        return False
    # Reject labeled section lines that leaked into skills
    if re.match(
        r'(?i)^(professional\s+summary|summary|objective|profile|about\s+me)\s*:',
        s,
    ):
        return False
    # Leftover from "SKILL SET" header or category crumbs
    if s.lower() in _SKILL_CRUMB_TOKENS:
        return False
    # Category labels like "Databases - SQL 2016" without a comma-separated list
    if re.match(r'^[A-Za-z][A-Za-z /&+]{1,30}\s*[-:]\s*.+$', s):
        # Allow if the part after dash looks like a known tech token list
        after = re.split(r'\s*[-:]\s*', s, maxsplit=1)[1].strip()
        tokens = re.split(r'[,|/]', after)
        if len(tokens) <= 1 and after.lower() not in _TECH_SINGLE_TOKEN:
            # Single category crumb — reject unless the whole string is a known skill
            if s.lower() not in _TECH_SINGLE_TOKEN and not any(
                t in s.lower() for t in ('python', 'java', 'sql server', 'mssql', 'oracle')
            ):
                # Keep "SQL Server 2016" style; drop "Databases - SQL 2016" category headers
                if re.match(r'(?i)^(databases?|tools?|technologies?|frameworks?|languages?)\b', s):
                    return False
    return True


def filter_skill_items(skills: list[str], max_items: int = 40) -> list[str]:
    """Dedupe and drop header/date junk from skill lists."""
    expanded: list[str] = []
    for s in skills:
        raw = (s or '').strip()
        if not raw:
            continue
        # Expand leftover comma/pipe groups from section captures
        if (',' in raw or '|' in raw) and '\n' not in raw:
            expanded.extend(split_list_items(raw))
        else:
            expanded.append(raw)
    cleaned = [s for s in expanded if is_plausible_skill_item(s)]
    return dedupe_skills(cleaned, max_items)


def is_institution_like(text: str | None) -> bool:
    return bool(_INSTITUTION_LIKE.search(text or ''))


def is_plausible_cert_name(name: str | None) -> bool:
    """Reject long prose / company blurbs without credential cues."""
    t = (name or '').strip()
    if not t or len(t) < 3:
        return False
    if is_section_header_line(t) or is_date_range_only_line(t):
        return False
    words = t.split()
    if len(words) > 12:
        return False
    if _CERT_CUE.search(t):
        return True
    # Short Title-Case credential without cue (e.g. "PMP", "CompTIA A+")
    if len(words) <= 8 and t[0].isupper():
        # Reject company-only "Acme Corp: Web Developme" style without cue when > 4 words
        # and contains a colon (often employer: description)
        if ':' in t and not _CERT_CUE.search(t):
            return False
        return True
    return False


def name_from_email_local_part(email: str | None) -> str:
    """
    Best-effort name when local-part has clear separators (dot/underscore/hyphen).
    Does not invent spaced names from glued locals like anjalibansode0227.
    """
    if not email or '@' not in email:
        return ''
    local = email.split('@', 1)[0].strip()
    local = re.sub(r'\d+$', '', local)
    if not local or not re.search(r'[._\-]', local):
        return ''
    parts = [p for p in re.split(r'[._\-]+', local) if p and p.isalpha()]
    if len(parts) < 2:
        return ''
    candidate = ' '.join(p.capitalize() for p in parts[:4])
    return candidate if is_plausible_person_name(candidate) else ''


def name_from_resume_filename(filename: str | None) -> str:
    """Derive a person name from resume filename when body has no header name.

    Examples: 'ABHISHEK KUMAR.pdf', '01_Furqan_Khan_-_HR.pdf' → plausible names only.
    """
    if not filename:
        return ''
    base = re.sub(r'\.[A-Za-z0-9]{1,5}$', '', str(filename)).strip()
    # Drop leading indexes / hashes
    base = re.sub(r'^(?:#?\d+[_\-\s]+)+', '', base)
    base = re.sub(r'[_\-]+', ' ', base)
    base = re.sub(r'\s+', ' ', base).strip()
    # Cut at role/keyword separators
    base = re.split(
        r'(?i)\s+(?:-|–|—)\s+|\s+(?:resume|cv|updated|dba|hr|network|fresher)\b',
        base,
        maxsplit=1,
    )[0].strip()
    base = re.sub(r'\(\d+\)$', '', base).strip()
    if not base:
        return ''
    # Title-case ALL CAPS tokens for plausibility
    cand = base.title() if base.isupper() else base
    return cand[:80] if is_plausible_person_name(cand) else ''


DATE_RANGE_PATTERN = re.compile(
    r'(?i)('
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}'
    r'|\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
    r'|\d{1,2}[/\-]\d{4}'
    r'|\d{4}[/\-]\d{1,2}'
    r'|\d{4}-\d{2}'
    r'|\d{4}'
    r')'
    r'\s*(?:[-–—to]+|\s+to\s+)\s*'
    r'('
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}'
    r'|\d{1,2}[/\-]\d{1,2}[/\-]\d{4}'
    r'|\d{1,2}[/\-]\d{4}'
    r'|\d{4}[/\-]\d{1,2}'
    r'|\d{4}-\d{2}'
    r'|\d{4}'
    r'|present|current|now'
    r')',
)

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def split_list_items(text: str) -> list[str]:
    """Split comma, pipe (ASCII/Unicode), or newline-separated prose into items."""
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    # Strip leftover section-header crumbs (e.g. "AND ABILITIES" after matching "SKILLS")
    raw = re.sub(r'(?i)^(?:and\s+)?abilities\s*[:\-–—]?\s*', '', raw).strip()
    # Normalize Unicode box-drawing / fullwidth pipes to ASCII
    raw = re.sub(r'[│︱｜¦]', '|', raw)

    def _is_institutionish(s: str) -> bool:
        return bool(
            re.search(r'(?i)\b(?:university|college|school|institute|commerce)\b', s)
        )

    if '|' in raw:
        # Flatten newlines inside pipe lists (PDF wrap mid-skill)
        flat = re.sub(r'\s*\n\s*', ' ', raw)
        parts = [p.strip() for p in flat.split('|')]
    elif ',' in raw and '\n' not in raw:
        parts = [p.strip() for p in raw.split(',')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
        expanded: list[str] = []
        for p in parts:
            p2 = re.sub(r'[│︱｜¦]', '|', p)
            if '|' in p2:
                expanded.extend(x.strip() for x in p2.split('|'))
            elif ',' in p2 and not _is_institutionish(p2):
                from app.ai.parser.enrichment.jd_text_inference import (
                    _split_skill_list_preserving_parens,
                )

                expanded.extend(_split_skill_list_preserving_parens(p2))
            else:
                expanded.append(p)
        parts = expanded
    result: list[str] = []
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
        if re.fullmatch(r'(?i)(?:and\s+)?abilities?', cleaned):
            continue
        if cleaned and len(cleaned) > 1:
            result.append(cleaned[:120])
    return result


def dedupe_skills(skills: list[str], max_items: int = 40) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in skills:
        if not item or not str(item).strip():
            continue
        key = str(item).strip().lower()
        if key not in seen:
            seen.add(key)
            result.append(str(item).strip())
        if len(result) >= max_items:
            break
    return result


def normalize_date_token(token: str) -> str:
    """Normalize a date token to YYYY-MM, YYYY, or Present."""
    if not token:
        return ''
    s = str(token).strip()
    if re.match(r'(?i)^(present|current|now)$', s):
        return 'Present'
    if re.match(r'^\d{4}-\d{2}$', s):
        return s
    if re.match(r'^\d{4}$', s):
        return s
    m = re.match(r'^(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})$', s)
    if m:
        day, month, year = int(m.group(1)), int(m.group(2)), m.group(3)
        if 1 <= month <= 12 and 1 <= day <= 31:
            return f'{year}-{month:02d}'
        if 1 <= day <= 12 and 1 <= month <= 31:
            # Ambiguous; prefer month-first when first token is 1-12
            return f'{year}-{day:02d}'
    m = re.match(r'(?i)^(jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+(\d{4})$', s)
    if m:
        key = m.group(1).lower()
        if key.startswith('sept'):
            key = 'sept'
        else:
            key = key[:3]
        month = MONTH_MAP.get(key, 1)
        return f'{m.group(2)}-{month:02d}'
    m = re.match(r'^(\d{1,2})[/\-](\d{4})$', s)
    if m:
        month = int(m.group(1))
        if 1 <= month <= 12:
            return f'{m.group(2)}-{month:02d}'
    m = re.match(r'^(\d{4})[/\-](\d{1,2})$', s)
    if m:
        month = int(m.group(2))
        if 1 <= month <= 12:
            return f'{m.group(1)}-{month:02d}'
    return s


def extract_date_range_from_line(line: str) -> tuple[str, str]:
    """Return (from, to) date strings from a line when a range is present."""
    if not line:
        return '', ''
    m = DATE_RANGE_PATTERN.search(line)
    if not m:
        return '', ''
    return normalize_date_token(m.group(1)), normalize_date_token(m.group(2))


def _parse_year_month(token: str) -> tuple[int, int] | None:
    token = normalize_date_token(token)
    if not token or token == 'Present':
        now = datetime.now(timezone.utc)
        return now.year, now.month
    if re.match(r'^\d{4}-\d{2}$', token):
        y, m = token.split('-')
        return int(y), int(m)
    if re.match(r'^\d{4}$', token):
        return int(token), 1
    return None


def compute_total_experience_years(experience: list[dict[str, Any]]) -> float | None:
    """Approximate total years from experience date ranges (from/to, start/end, or description)."""
    if not experience:
        return None
    total_months = 0
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        start_tok = str(exp.get('from') or exp.get('start') or '').strip()
        end_tok = str(exp.get('to') or exp.get('end') or '').strip()
        blob = ' '.join(
            str(exp.get(k) or '')
            for k in ('description', 'title', 'role', 'company')
        )
        # Peel dates from description when structured dates missing (Excel safety net)
        if not start_tok or not end_tok:
            fr, to = extract_date_range_from_line(blob)
            if fr and not start_tok:
                start_tok = fr
            if to and not end_tok:
                end_tok = to
        if not start_tok:
            dm = re.search(
                r'(?i)\b(\d{1,2})\s*[-–—]?\s*(?:months?)\s*(?:tenure)?\b',
                blob,
            )
            if dm:
                total_months += int(dm.group(1))
                continue
        if not end_tok and (
            exp.get('is_current') or exp.get('isCurrent')
        ):
            end_tok = 'Present'
        start = _parse_year_month(start_tok) if start_tok else None
        if re.match(r'(?i)^(present|current|now)$', end_tok):
            end = _parse_year_month('Present')
        else:
            end = _parse_year_month(end_tok) if end_tok else None
        if not start or not end:
            years = exp.get('years')
            if isinstance(years, (int, float)):
                total_months += int(float(years) * 12)
            continue
        months = (end[0] - start[0]) * 12 + (end[1] - start[1])
        if months > 0:
            total_months += months
    if total_months <= 0:
        return None
    return round(total_months / 12.0, 1)


_PROSE_YEARS_RE = re.compile(
    r'(?i)(?:'
    r'(?:total\s+)?(?:work\s+)?experience\s*(?:of|:)?\s*(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)'
    r'|'
    r'(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:total\s+)?(?:work\s+)?experience'
    r'|'
    r'(?:total\s+experience|overall\s+experience)\s*[:\-–—]\s*(\d{1,2}(?:\.\d)?)\+?\s*(?:years?|yrs?)?'
    r')'
)


def extract_total_experience_years_from_text(text: str) -> float | None:
    """Grounded prose years only when explicit 'N years' evidence exists in source text."""
    if not text:
        return None
    # Prefer header/summary zone to avoid project "2 years" noise mid-body
    window = text[:3500]
    best: float | None = None
    for m in _PROSE_YEARS_RE.finditer(window):
        raw = next((g for g in m.groups() if g), None)
        if not raw:
            continue
        try:
            val = float(raw)
        except ValueError:
            continue
        if val <= 0 or val > 45:
            continue
        if best is None or val > best:
            best = val
    return round(best, 1) if best is not None else None


def merge_experience_years(
    date_years: float | None,
    prose_years: float | None,
) -> float | None:
    """Prefer date-sum; use prose when dates missing; max when both consistent."""
    if date_years is None and prose_years is None:
        return None
    if date_years is None:
        return prose_years
    if prose_years is None:
        return date_years
    # Consistent if within ~2 years; otherwise trust dated ranges
    if abs(date_years - prose_years) <= 2.0:
        return max(date_years, prose_years)
    return date_years


def heal_location_candidate(value: str) -> str:
    """Strip Company|City / phone⋄City bleed and return a city-like token when possible."""
    s = (value or '').strip()
    if not s:
        return ''
    if '\n' in s or '\r' in s:
        s = s.splitlines()[0].strip()
    # phone ⋄ City / +91…·City
    s = re.sub(r'(?i)^\+?\d[\d\s\-().]{6,}\s*[⋄·•|]*\s*', '', s).strip()
    s = re.sub(r'(?i)[⋄·•]\s*', ' ', s).strip()
    if '|' in s:
        parts = [p.strip() for p in s.split('|') if p.strip()]
        for p in reversed(parts):
            healed = heal_location_candidate(p) if ('|' in p or '⋄' in p) else p
            if healed and is_plausible_location_value(healed):
                return canonicalize_location_city(healed)
            for city in _KNOWN_LOCATION_CITIES:
                if city.lower() == healed.lower() or city.lower() == p.lower():
                    return canonicalize_location_city(city)
        return ''
    # Prefer known city substring from polluted strings
    if not is_plausible_location_value(s):
        low = s.lower()
        for city in sorted(_KNOWN_LOCATION_CITIES, key=len, reverse=True):
            if city.lower() in low and not _LOCATION_TECH_NOISE.search(city):
                # Avoid matching short tokens inside tech words
                if re.search(rf'(?i)\b{re.escape(city)}\b', s):
                    return canonicalize_location_city(city)
        return ''
    return canonicalize_location_city(s)


def is_section_header_line(line: str) -> bool:
    cleaned = re.sub(r'^[\s#*•\-]+|[\s#:]+$', '', (line or '').strip()).strip()
    if not cleaned:
        return True
    return cleaned.lower() in SECTION_HEADERS


def extract_name_from_text(text: str) -> str:
    """Pick a plausible person name from early resume lines, skipping section headers."""
    if not text:
        return ''
    # Labeled biodata: "Name: Ms. Saloni V. Dhuru" / "Name\n: Ms. Saloni V. Dhuru"
    labeled = re.search(
        r'(?im)^(?:\*\*)?(?:full\s*)?name(?:\*\*)?\s*[:\-–—]\s*(.+?)\s*$',
        text[:2500],
    )
    if not labeled:
        labeled = re.search(
            r'(?is)(?:^|\n)\s*(?:\*\*)?(?:full\s*)?name(?:\*\*)?\s*\n\s*[:\-–—]\s*(.+?)(?:\n|$)',
            text[:2500],
        )
    if labeled:
        cand = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', labeled.group(1).strip())
        cand = cand.rstrip('-:–—|').strip()
        # Stop at next biodata label glued on same line
        cand = re.split(
            r'(?i)\s{2,}|\t|(?=designation|email|phone|mobile|address|location|dob)\b',
            cand,
            maxsplit=1,
        )[0].strip()
        if is_plausible_person_name(cand):
            return (cand.title() if cand.isupper() else cand)[:80]

    # Join consecutive ALL-CAPS single-token name lines (PyPDF2 word-per-line layouts)
    early_lines: list[str] = []
    for line in text.split('\n')[:25]:
        stripped = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', line).replace('\xa0', ' ').strip()
        if stripped:
            early_lines.append(stripped)

    # Collapse runs of single ALL-CAPS alpha tokens at the top into one name candidate
    caps_run: list[str] = []
    for stripped in early_lines[:8]:
        if re.fullmatch(r"[A-Z][A-Z\-']{1,24}", stripped) and stripped not in {
            'SEO', 'API', 'AWS', 'HTML', 'CSS', 'SQL', 'USA', 'UAE', 'CV',
        }:
            caps_run.append(stripped.title() if stripped.isupper() else stripped)
            if len(caps_run) >= 2:
                joined = ' '.join(caps_run)
                if is_plausible_person_name(joined):
                    return joined[:80]
            continue
        break

    for stripped in early_lines[:20]:
        if stripped.startswith(('#', '*', '-', '•')):
            continue
        if '@' in stripped or 'http' in stripped.lower() or 'www.' in stripped.lower():
            continue
        if re.match(r'^\+?\d[\d\s\-().]{7,}$', stripped):
            continue
        if is_section_header_line(stripped):
            continue
        # PDF spaced letters: "R O S H A N  P A N I C K E R" → "Roshan Panicker"
        if re.fullmatch(r'(?:[A-Za-z]\s+){2,}[A-Za-z](?:\s{2,}(?:[A-Za-z]\s+)*[A-Za-z])?', stripped):
            parts = re.split(r'\s{2,}', stripped)
            words = []
            for part in parts:
                chars = [c for c in part.split() if len(c) == 1 and c.isalpha()]
                if chars and len(chars) == len(part.split()):
                    words.append(''.join(chars).title())
            if 2 <= len(words) <= 5:
                return ' '.join(words)[:80]
        if re.search(r'\d', stripped):
            continue
        words = stripped.split()
        # Prefer 2–4 Title-Case alphabetic name tokens
        if 1 <= len(words) <= 5 and 2 <= len(stripped) <= 80:
            if is_plausible_person_name(stripped):
                # Title-case ALL-CAPS full names for form display
                if stripped.isupper() and len(words) >= 2:
                    return stripped.title()[:80]
                return stripped[:80]
    # Separated email locals only (anjali.bansode) — never glued locals
    email = extract_email_from_text(text)
    derived = name_from_email_local_part(email)
    if derived:
        return derived
    return ''


def extract_skills_from_text(text: str, max_items: int = 40) -> list[str]:
    """Parse skills sections and inline skill lines from resume prose."""
    if not text:
        return []
    skills: list[str] = []

    for match in SKILL_SECTION_PATTERN.finditer(text):
        block = match.group(1) or ''
        skills.extend(split_list_items(block))

    if not skills:
        in_section = False
        for line in text.split('\n'):
            stripped = line.strip()
            if re.match(
                r'(?i)^(?:technical\s+)?skills?\s*:?\s*$|^(?:core|key)\s+skills?\s*:?\s*$|'
                r'^skill\s*sets?\s*:?\s*$|^skills?\s*sets?\s*:?\s*$|'
                r'^tools?\s*:?\s*$|^technologies?\s*:?\s*$|^tech\s+stack\s*:?\s*$|^competencies?\s*:?\s*$',
                stripped,
            ):
                in_section = True
                # Do not treat leftover "SET" from "SKILL SET" as an inline skill
                if re.match(r'(?i)^skill\s*sets?\s*:?\s*$|^skills?\s*sets?\s*:?\s*$', stripped):
                    continue
                inline = re.sub(r'(?i)^[^:]+:\s*', '', stripped).strip()
                if inline and not is_section_header_line(inline) and inline.lower() not in _SKILL_CRUMB_TOKENS:
                    skills.extend(split_list_items(inline))
                continue
            if in_section:
                if re.match(
                    r'(?i)^(?:experience|work\s+experience|professional\s+experience|'
                    r'education|projects?|certifications?|employment|work\s+history|'
                    r'personal\s+details|personal\s+information)\b',
                    stripped,
                ) or is_section_header_line(stripped):
                    break
                item = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if item and is_plausible_skill_item(item):
                    skills.append(item)
                if len(skills) >= max_items:
                    break

    if not skills:
        for line in text.split('\n')[:30]:
            if re.search(r'(?i)\bskills?\s*:', line):
                after = re.split(r'(?i)skills?\s*:', line, maxsplit=1)
                if len(after) > 1 and after[1].strip():
                    skills.extend(split_list_items(after[1]))
                    break

    return filter_skill_items(skills, max_items)


def extract_email_from_text(text: str) -> str:
    if not text:
        return ''
    match = re.search(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}', text)
    return match.group(0).strip() if match else ''


def extract_phone_from_text(text: str) -> str:
    if not text:
        return ''
    patterns = [
        r'\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}',
        r'\b\d{10}\b',
    ]
    for pat in patterns:
        match = re.search(pat, text[:2000])
        if match:
            return match.group(0).strip()
    return ''


def extract_summary_from_text(text: str, max_len: int = 2000) -> str:
    if not text:
        return ''
    match = SUMMARY_SECTION_PATTERN.search(text)
    if match and match.group(1):
        summary = ' '.join(split_list_items(match.group(1)))
        if summary:
            return summary[:max_len]
    return ''


_LOCATION_TECH_NOISE = re.compile(
    r'(?i)\b(?:html|css|javascript|typescript|python|java|react|node\.?js|sql|aws|'
    r'docker|kubernetes|devops|ci/?cd|nlp|ml|ai|excel|bootstrap|bitbucket|postman|'
    r'jupyter|mongodb|postgresql|mysql|linux|git|github|vscode|vs\s*code|'
    r'ansible|patching|technical\s+support|incident\s+management|cloud\s+devops|'
    r'net\s+development)\b'
)
_LOCATION_PROSE_NOISE = re.compile(
    r'(?i)\b(?:analyzed|building|practice|automation|dashboards?|binaries|'
    r'process|workflow|objective|summary|experience\s+in|hands[- ]on|'
    r'communication|financial|curriculum|vitae|marketing|accounting)\b'
)
_KNOWN_LOCATION_CITIES = (
    'Mumbai', 'Delhi', 'New Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai',
    'Kolkata', 'Pune', 'Ahmedabad', 'Gurgaon', 'Gurugram', 'Noida', 'Nagpur',
    'Indore', 'Thane', 'Navi Mumbai', 'Mulund', 'Kandivali', 'Andheri', 'Powai',
    'Faridabad', 'Jaipur', 'Lucknow', 'Bhopal', 'Surat', 'Vadodara', 'Coimbatore',
    'Kochi', 'Chandigarh', 'Mysore', 'Mysuru', 'Visakhapatnam', 'Mehdipatnam',
    'Kalwa', 'Nashik', 'Nasik', 'Ambernath', 'Dombivli', 'Dombivili', 'Sindhudurg',
    'Sewree', 'Solapur', 'Kalyan', 'Vasai', 'Virar', 'Panvel', 'Aurangabad', 'Kolhapur',
    'Bhubaneswar', 'Vellore', 'Berhampur', 'Kanpur', 'Mangalore', 'Shevgaon',
    'Austin', 'Seattle', 'San Francisco', 'New York', 'London',
    'Toronto', 'Singapore', 'Dubai',
)
# Spelling / OCR aliases → canonical city for Excel
_LOCATION_ALIASES = {
    'nasik': 'Nashik',
    'bengaluru': 'Bengaluru',
    'bangalore': 'Bangalore',
    'gurgaon': 'Gurugram',
    'gurugram': 'Gurugram',
    'bombay': 'Mumbai',
    'calcutta': 'Kolkata',
    'madras': 'Chennai',
    'bhubaneshwar': 'Bhubaneswar',
}
# Institute / university cues → city (only when structured peel needs it)
_INSTITUTE_CITY_PEEL = (
    (re.compile(r'(?i)\bvellore\s+institute\s+of\s+technology\b|\bvit\b'), 'Vellore'),
    (re.compile(r'(?i)\biit\s+bombay\b|\biitb\b'), 'Mumbai'),
    (re.compile(r'(?i)\biit\s+madras\b'), 'Chennai'),
    (re.compile(r'(?i)\biit\s+delhi\b'), 'Delhi'),
    (re.compile(r'(?i)\biit\s+kanpur\b'), 'Kanpur'),
    (re.compile(r'(?i)\bnitk?\s+surathkal\b'), 'Mangalore'),
)
_KNOWN_REGIONS = frozenset({
    'maharashtra', 'maharastra', 'karnataka', 'tamil nadu', 'telangana', 'andhra pradesh',
    'gujarat', 'rajasthan', 'uttar pradesh', 'west bengal', 'kerala', 'punjab',
    'haryana', 'odisha', 'india', 'usa', 'uk', 'uae', 'tx', 'ca', 'wa', 'ny',
})


def known_location_cities() -> tuple[str, ...]:
    """Shared city allowlist for location heal / evidence / extract."""
    return _KNOWN_LOCATION_CITIES


def location_tokens_in_source(value: str) -> list[str]:
    """Canonical city plus spelling aliases so Nashik matches Nasik in source text."""
    s = (value or '').strip()
    if not s:
        return []
    out = [s]
    low = s.lower()
    canon = _LOCATION_ALIASES.get(low, s)
    if canon not in out:
        out.append(canon)
    for alias, target in _LOCATION_ALIASES.items():
        if target.lower() == low or target.lower() == canon.lower() or alias == low:
            if alias not in {x.lower() for x in out}:
                out.append(alias)
            if target not in out:
                out.append(target)
    return out


def canonicalize_location_city(value: str) -> str:
    """Map aliases (Nasik→Nashik) and return best known city token if present."""
    s = (value or '').strip()
    if not s:
        return ''
    low = s.lower()
    if low in _LOCATION_ALIASES:
        return _LOCATION_ALIASES[low]
    for alias, canon in _LOCATION_ALIASES.items():
        if re.search(rf'(?i)\b{re.escape(alias)}\b', s):
            return canon
    for city in sorted(_KNOWN_LOCATION_CITIES, key=len, reverse=True):
        if re.search(rf'(?i)\b{re.escape(city)}\b', s):
            return _LOCATION_ALIASES.get(city.lower(), city)
    return s


def peel_location_from_structured(
    *,
    experience: list | None = None,
    education: list | None = None,
    raw_text: str = '',
) -> str:
    """
    Recover current location from job/edu structured fields then institute peel.
    Never invents from random body prose.
    """
    for e in experience or []:
        if not isinstance(e, dict):
            continue
        loc = str(e.get('location') or '').strip()
        if not loc:
            continue
        healed = heal_location_candidate(loc)
        cand = canonicalize_location_city(healed or loc)
        if cand and is_plausible_location_value(cand):
            return cand
        for city in sorted(_KNOWN_LOCATION_CITIES, key=len, reverse=True):
            if re.search(rf'(?i)\b{re.escape(city)}\b', loc):
                return canonicalize_location_city(city)

    for e in education or []:
        if not isinstance(e, dict):
            continue
        blob = ' '.join(
            str(e.get(k) or '')
            for k in ('institution', 'university', 'college', 'location', 'degree', 'field')
        )
        if not blob.strip():
            continue
        for city in sorted(_KNOWN_LOCATION_CITIES, key=len, reverse=True):
            if re.search(rf'(?i)\b{re.escape(city)}\b', blob):
                return canonicalize_location_city(city)
        for pat, city in _INSTITUTE_CITY_PEEL:
            if pat.search(blob):
                return city

    head = '\n'.join((raw_text or '').splitlines()[:12])
    for pat, city in _INSTITUTE_CITY_PEEL:
        if pat.search(head):
            return city
    for city in sorted(_KNOWN_LOCATION_CITIES, key=len, reverse=True):
        if re.search(rf'(?i)\b{re.escape(city)}\b', head):
            return canonicalize_location_city(city)
    return ''


def is_plausible_location_value(value: str) -> bool:
    """True for city/region/remote strings; false for skill/summary pollution."""
    s = (value or '').strip()
    if not s or len(s) < 2 or len(s) > 80:
        return False
    if '\n' in s or '\r' in s:
        s = s.splitlines()[0].strip()
        if not s or len(s) > 80:
            return False
    low = s.lower()
    if '@' in s or 'http' in low or 'linkedin' in low or 'github' in low:
        return False
    if '|' in s or '⋄' in s or re.search(r'\+?\d[\d\s\-]{8,}\d', s):
        return False
    if low in (
        'education', 'experience', 'skills', 'summary', 'objective', 'projects',
        'certifications', 'internship', 'profile', 'curriculum vitae', 'cv',
        'resume',
    ):
        return False
    if low in _JOB_TITLE_NAME_BLOCKLIST:
        return False
    if _JOB_TITLE_CUE.search(s) and not any(c.lower() in low for c in _KNOWN_LOCATION_CITIES):
        return False
    # Reject person-name lines mistaken for location (header bleed)
    if (
        not any(c.lower() == low or c.lower() in low for c in _KNOWN_LOCATION_CITIES)
        and low not in ('remote', 'hybrid', 'wfh', 'work from home', 'india')
        and ',' not in s
    ):
        try:
            if is_plausible_person_name(s) and len(s.split()) >= 2:
                return False
        except Exception:
            pass
    # Reject if line looks like a person name glued after city
    if re.search(r'(?i),\s*india\s+\w+', s):
        return False
    if _LOCATION_TECH_NOISE.search(s) and not any(c.lower() in low for c in _KNOWN_LOCATION_CITIES):
        return False
    if _LOCATION_PROSE_NOISE.search(s) and not any(c.lower() in low for c in _KNOWN_LOCATION_CITIES):
        return False
    if low in ('remote', 'hybrid', 'wfh', 'work from home', 'india'):
        return True
    if any(c.lower() == low or c.lower() in low for c in _KNOWN_LOCATION_CITIES):
        return True
    # City, Region where both sides look geographic (not HTML, JS)
    m = re.match(
        r'^([A-Za-z][A-Za-z .]{1,40}),\s*([A-Za-z][A-Za-z .]{1,40})$',
        s,
    )
    if m:
        a, b = m.group(1).strip().lower(), m.group(2).strip().lower()
        if _LOCATION_TECH_NOISE.search(a) or _LOCATION_TECH_NOISE.search(b):
            return False
        if _LOCATION_PROSE_NOISE.search(a) or _LOCATION_PROSE_NOISE.search(b):
            return False
        if a in _KNOWN_REGIONS or b in _KNOWN_REGIONS:
            return True
        if any(c.lower() == a or c.lower() == b for c in _KNOWN_LOCATION_CITIES):
            return True
        # Unknown Title-Case pairs (skill/soft-skill) are not cities
        return False
    # Single short place token
    if re.match(r'^[A-Z][a-zA-Z .]{1,40}$', s) and len(s.split()) <= 4:
        if _LOCATION_TECH_NOISE.search(s) or _LOCATION_PROSE_NOISE.search(s):
            return False
        return True
    return False


def extract_location_from_text(text: str) -> str:
    """Labeled location, Remote/Hybrid, City ST, or common city names in header."""
    if not text:
        return ''

    def _clean_loc(raw: str) -> str:
        s = (raw or '').strip()
        # Strip emoji / bullets / labels
        s = re.sub(r'^[\U0001F300-\U0001FAFF\u2600-\u27BF📍📞✉️🔗·•|\-–—o]+\s*', '', s)
        s = re.sub(
            r'(?i)^(address|location|current\s*location|place|city|based\s*in)\s*[:\-]\s*',
            '',
            s,
        ).strip()
        # Common OCR/biodata form: "Location: - Bandra, Mumbai"
        s = re.sub(r'^[\-–—•·]+\s*', '', s).strip()
        # Drop trailing date ranges / job metadata
        s = re.sub(
            r'(?i)\s*[|•·]\s*(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec|'
            r'present|current|\d{4}).*$',
            '',
            s,
        ).strip()
        s = s.strip('.,;:| ')
        low = s.lower()
        if any(
            tok in low
            for tok in (
                'technologies', 'skills', 'experience', 'summary', 'objective',
                'linkedin', 'github', 'http', '@', 'vlan', 'configuration',
                'switchover', 'switchback', 'university', 'college', 'institute',
                'school', 'cgpi', 'sgpi',
            )
        ):
            for city in _KNOWN_LOCATION_CITIES:
                if city.lower() in low:
                    return city
            return ''
        if _LOCATION_TECH_NOISE.search(s) or _LOCATION_PROSE_NOISE.search(s):
            for city in _KNOWN_LOCATION_CITIES:
                if city.lower() in low:
                    return city
            return ''
        if len(s) > 50:
            for city in _KNOWN_LOCATION_CITIES:
                if city.lower() in low:
                    return city
            return ''
        if len(s) < 2:
            return ''
        if not is_plausible_location_value(s):
            for city in _KNOWN_LOCATION_CITIES:
                if city.lower() in low:
                    return city
            return ''
        return s

    header = text[:800]
    patterns = [
        # Require delimiter after label to avoid "…location … skills…" prose
        r'(?i)(?:location|current\s*location|address|city|based\s+in|place|residing\s+(?:in|at))\s*[:\-–—]\s*([^\n]+)',
        r'\b([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*),\s*([A-Z]{2})\b',
        # Pipe header: City | phone | email
        r'(?im)^([A-Za-z][A-Za-z .,]{2,40})\s*[|•·]\s*(?:mobile|phone|tel|\+?\d)',
        # Emoji / pin style: 📍 Nagpur, Maharashtra, India
        r'(?:📍|📌)\s*([^\n]+)',
    ]
    for pat in patterns:
        m = re.search(pat, header)
        if not m:
            continue
        if m.lastindex and m.lastindex >= 2 and '([A-Z]{2})' in pat:
            loc = f'{m.group(1)}, {m.group(2)}'
        else:
            loc = m.group(1).strip().strip('.,;:')
        cleaned = _clean_loc(loc)
        if cleaned and is_plausible_location_value(cleaned):
            return cleaned

    # City, Region only when at least one side is a known city/region (header lines)
    m_cs = re.search(
        r'(?im)^([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*),\s*'
        r'([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*)\s*$',
        '\n'.join((text or '').splitlines()[:20]),
    )
    if m_cs:
        loc = f'{m_cs.group(1)}, {m_cs.group(2)}'.strip()
        if is_plausible_location_value(loc):
            return loc[:80]

    # Prefer known cities in the contact header over job-line "Remote"
    for window in (header, text[:5000]):
        for city in _KNOWN_LOCATION_CITIES:
            if city not in window:
                continue
            for line in window.splitlines():
                if city in line and len(line.strip()) <= 100 and '@' not in line:
                    if _LOCATION_TECH_NOISE.search(line) and city.lower() not in line.lower():
                        continue
                    cleaned = _clean_loc(line)
                    if cleaned and is_plausible_location_value(cleaned):
                        if len(cleaned) > 60:
                            return city
                        return cleaned
            return city

    # Remote/Hybrid only from header/contact zone (not experience "Remote" job lines)
    m_remote = re.search(r'(?i)\b(remote|hybrid|work\s+from\s+home|wfh)\b', header)
    if m_remote:
        return m_remote.group(1).strip()

    # Single allowlisted city from early body when not inside Skills/Summary sections
    section_break = re.search(
        r'(?im)^(?:education|experience|skills|summary|objective|projects|'
        r'certifications|internship|work\s+history)\b',
        text[:4000],
    )
    body_end = section_break.start() if section_break else min(len(text), 2500)
    early_body = text[:body_end]
    for city in _KNOWN_LOCATION_CITIES:
        if re.search(rf'(?i)\b{re.escape(city)}\b', early_body):
            # Prefer labeled hits; otherwise single short-line hit
            labeled = re.search(
                rf'(?i)(?:location|address|based\s+in|city)\s*[:\-–—]\s*[^\n]*\b{re.escape(city)}\b',
                early_body,
            )
            if labeled:
                return city
            for line in early_body.splitlines()[:25]:
                if city.lower() in line.lower() and len(line.strip()) <= 60:
                    if _LOCATION_TECH_NOISE.search(line) or _LOCATION_PROSE_NOISE.search(line):
                        continue
                    if is_section_header_line(line):
                        continue
                    cleaned = heal_location_candidate(line)
                    if cleaned and is_plausible_location_value(cleaned):
                        return cleaned if len(cleaned) <= 60 else city
            return city

    # Country-only last resort when clearly labeled
    if re.search(r'(?i)(?:^|\n)\s*India\s*(?:\n|$)', text[:600]):
        return 'India'
    return ''


def extract_experience_from_text(text: str, max_items: int = 10) -> list[dict[str, Any]]:
    """Lightweight experience lines when structured experience is missing."""
    if not text:
        return []
    experiences: list[dict[str, Any]] = []
    # Require section header at line start so mid-sentence "experience" (e.g. objective) is ignored.
    block_match = re.search(
        r'(?im)(?:^|\n)\s*(?:\*\*)?(?:work\s+experience|professional\s+experience|experience|'
        r'employment|work\s+history|internships?|industrial\s+training|summer\s+internship)'
        r'(?:\*\*)?\s*:?\s*'
        r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:education|academic\s+background|skills|skill\s*sets?|'
        r'technical\s+skills?|projects?|certifications?|'
        r'personal\s+details|personal\s+information|biodata|declaration)(?:\*\*)?\s*:?\s*$|\Z)',
        text,
    )
    if not block_match:
        return []
    raw = block_match.group(1) or ''
    _title_cue = re.compile(
        r'(?i)\b(?:intern|engineer|developer|analyst|trainee|manager|officer|'
        r'associate|consultant|lead|executive|specialist|administrator|admin|'
        r'dba|architect|designer|scientist|director)\b'
    )
    for line in raw.split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        stripped = re.sub(r'^\d+[\.\)]\s*', '', stripped).strip()
        if not stripped or len(stripped) < 5 or is_section_header_line(stripped):
            continue
        if is_biodata_or_address_line(stripped):
            continue
        from_d, to_d = extract_date_range_from_line(stripped)
        leftover = DATE_RANGE_PATTERN.sub('', stripped).strip(' |-–—,')
        has_cue = bool(_title_cue.search(leftover) or re.search(r'(?i)\bintern\b', leftover))
        if from_d and leftover and not has_cue:
            if experiences and not str(experiences[-1].get('company') or '').strip():
                experiences[-1]['company'] = leftover[:200]
                if not experiences[-1].get('from'):
                    experiences[-1]['from'] = from_d
                    experiences[-1]['to'] = to_d
            else:
                experiences.append({
                    'title': '',
                    'company': leftover[:200],
                    'from': from_d,
                    'to': to_d,
                    'years': None,
                    'description': '',
                })
            if len(experiences) >= max_items:
                break
            continue
        if not has_cue:
            if leftover and experiences and not str(experiences[-1].get('company') or '').strip() and len(leftover.split()) <= 6:
                experiences[-1]['company'] = leftover[:200]
            continue
        parts = re.split(r'\s+at\s+|\s+@\s+|,\s+', leftover, maxsplit=1)
        title = parts[0].strip() if parts else leftover
        company = parts[1].strip() if len(parts) > 1 else ''
        if company and is_biodata_or_address_line(company):
            company = ''
        if not is_plausible_job_title(title) and not re.search(r'(?i)\bintern\b', title):
            continue
        if title:
            experiences.append({
                'title': title[:200],
                'company': company[:200],
                'from': from_d,
                'to': to_d,
                'years': None,
                'description': '',
            })
        if len(experiences) >= max_items:
            break
    return experiences


def extract_education_from_text(text: str, max_items: int = 8) -> list[dict[str, Any]]:
    """Parse education section into degree/institution entries."""
    if not text:
        return []
    match = EDUCATION_SECTION_PATTERN.search(text)
    if not match:
        return []
    raw = match.group(1) or ''
    education: list[dict[str, Any]] = []
    # Full words BEFORE abbreviated M.A./B.A. so "Master" is not cut to "Ma"
    degree_pat = re.compile(
        r'(?i)\b('
        r'Master(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?|'
        r'Bachelor(?:\'?s)?(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?|'
        r'Associate(?:\'?s)?(?:\s+(?:of|in|degree)\s+[A-Za-z &\-/]+)?|'
        r'BACHELOR\s+OF\s+ENGINEERING(?:\s*[-–—]?\s*[A-Za-z &\-/]+)?|'
        r'B\.?\s?Tech|B\.?\s?E\.?(?![a-z])|B\.?\s?S\.?(?![a-z])|B\.?\s?Com|'
        r'M\.?\s?Tech|M\.?\s?S\.?(?![a-z])|M\.?\s?Com|'
        r'M\.?\s?B\.?\s?A\.?(?![a-z])|M\.?\s?C\.?\s?A\.?(?![a-z])|'
        r'B\.?\s?C\.?\s?A\.?(?![a-z])|B\.?\s?B\.?\s?A\.?(?![a-z])|'
        r'Ph\.?\s?D\.?(?![a-z])|'
        r'Diploma(?:\s+in\s+[A-Za-z &\-/]+)?|'
        r'Pre[\s\-]?University|Higher\s+Secondary|Senior\s+Secondary|'
        r'M\.?\s?A\.?(?![a-z])|B\.?\s?A\.?(?![a-z])'
        r')\b',
    )
    for line in raw.split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not stripped or len(stripped) < 4 or is_section_header_line(stripped):
            continue
        if is_date_range_only_line(stripped) or is_biodata_or_address_line(stripped):
            continue
        if _JOB_BULLET_INSTITUTION.search(stripped):
            continue
        if re.search(
            r'(?i)\b(?:intern(?:ship)?s?|trainee|apprentice)\b',
            stripped,
        ) and not degree_pat.search(stripped):
            continue
        from_d, to_d = extract_date_range_from_line(stripped)
        year = ''
        if to_d and to_d != 'Present':
            year = to_d[:4] if re.match(r'^\d{4}', to_d) else to_d
        elif not from_d:
            ym = re.search(r'\b(19|20)\d{2}\b', stripped)
            if ym:
                year = ym.group(0)
        degree_m = degree_pat.search(stripped)
        degree = degree_m.group(1).strip() if degree_m else ''
        # Drop abbreviation-prefix fragments (Ma, Ba, Be) without punctuation
        if degree and _DEGREE_FRAGMENT.match(degree.replace('.', '').replace(' ', '')):
            if '.' not in (degree_m.group(0) if degree_m else ''):
                # Allow only if original token had dots (M.A.) — bare "Ma" from Master is bad
                if len(degree) <= 2:
                    degree = ''
        rest = degree_pat.sub('', stripped) if degree_m and degree else stripped
        if degree_m and not degree:
            rest = stripped
        rest = DATE_RANGE_PATTERN.sub('', rest)
        rest = re.sub(r'\b(19|20)\d{2}\b', '', rest)
        rest = re.sub(r'(?i)\b(?:gpa|cgpa|percentage)\s*[:=]?\s*[\d.]+%?', '', rest)
        institution = re.sub(r'^[\s,\-|–—]+|[\s,\-|–—]+$', '', rest).strip()
        gpa_m = re.search(r'(?i)(?:gpa|cgpa|percentage)\s*[:=]?\s*([\d.]+%?)', stripped)
        gpa = gpa_m.group(1) if gpa_m else ''

        if institution and (
            _JOB_BULLET_INSTITUTION.search(institution) or is_biodata_or_address_line(institution)
        ):
            institution = ''

        # Keep only real degrees or institution-like schools
        degree_ok = bool(degree) and len(degree) >= 3 and not _DEGREE_FRAGMENT.match(
            degree.replace('.', '').replace(' ', '')
        )
        # Re-allow proper abbreviated degrees with dots/all-caps
        if degree and re.match(r'(?i)^(M\.?\s?A\.?|B\.?\s?A\.?|B\.?\s?E\.?|M\.?\s?S\.?|B\.?\s?S\.?|'
                               r'M\.?\s?B\.?\s?A\.?|Ph\.?\s?D\.?)$', degree.strip()):
            degree_ok = True
        if not degree_ok and not is_institution_like(institution):
            continue
        if degree_ok or is_institution_like(institution):
            education.append({
                'degree': degree[:200] if degree_ok else '',
                'institution': (
                    institution[:200]
                    if is_institution_like(institution) or (degree_ok and institution)
                    else ''
                ),
                'field': '',
                'year': year,
                'from': from_d,
                'to': to_d if to_d != 'Present' else year,
                'gpa': gpa,
            })
        if len(education) >= max_items:
            break
    return education


def extract_certifications_from_text(text: str, max_items: int = 15) -> list[Any]:
    """Parse certifications section into name strings or objects."""
    if not text:
        return []
    match = CERT_SECTION_PATTERN.search(text)
    if not match:
        return []
    certs: list[Any] = []
    for line in (match.group(1) or '').split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        stripped = re.sub(r'^\d+[\.\)]\s*', '', stripped).strip()
        if not stripped or len(stripped) < 3 or is_section_header_line(stripped):
            continue
        if is_date_range_only_line(stripped):
            continue
        parts = re.split(r'\s+[-–—|]\s+|\s+from\s+|\s+by\s+', stripped, maxsplit=1, flags=re.I)
        name = parts[0].strip()
        issuer = parts[1].strip() if len(parts) > 1 else ''
        # "Company: description" often lacks a credential cue — use full line for cue check
        if not is_plausible_cert_name(stripped) and not is_plausible_cert_name(name):
            continue
        if name:
            if issuer:
                certs.append({'name': name[:200], 'issuer': issuer[:200]})
            else:
                certs.append(name[:200])
        if len(certs) >= max_items:
            break
    return certs


def infer_resume_fields_from_text(text: str) -> dict[str, Any]:
    """Return partial canonical resume fragments inferable from raw text."""
    experience = extract_experience_from_text(text)
    return {
        'skills': extract_skills_from_text(text),
        'summary': extract_summary_from_text(text),
        'person': {
            'email': extract_email_from_text(text),
            'phone': extract_phone_from_text(text),
            'name': extract_name_from_text(text),
            'location': extract_location_from_text(text),
        },
        'experience': experience,
        'education': extract_education_from_text(text),
        'certifications': extract_certifications_from_text(text),
        'total_experience_years': compute_total_experience_years(experience),
    }
