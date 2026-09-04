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
    r'experience|work\s+experience|professional\s+experience|technical\s+experience|'
    r'employment|work\s+history|'
    r'projects?|certifications?|certificates?|licenses?|credentials?|'
    r'languages?|awards?|interests?|references?|'
    r'career\s+objective|professional\s+objective|professional\s+summary|'
    r'profile\s+summary|career\s+profile|'
    r'career\s+summary|summary|objective|profile|about\s+me'
)

SKILL_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:'
    r'technical\s+proficiency|technical\s+expertise|technical\s+knowledge|'
    r'technical\s+skills?|technicalskill|soft\s+skills?|'
    r'core\s+skills?|key\s+skills?|skill\s*sets?|skills?\s*sets?|'
    r'skills?\s+and\s+abilities|skills?\s+&\s+abilities|'
    r'tech\s+stack|programming\s+languages?|'
    r'skills?\b|tools?\b|technologies?\b|frameworks?\b|competencies?\b|expertise\b'
    r')(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?(?:' + SKILL_SECTION_STOP + r')\b|\Z)',
)

# Priority order for summary / objective section headings (highest first).
SUMMARY_HEADING_PRIORITY: tuple[str, ...] = (
    'professional objective',
    'career objective',
    'professional summary',
    'professional profile',
    'personal profile',
    'profile summary',
    'summary',
    'objective',
    'profile',
    'about me',
    'career profile',
    'career summary',
    'overview',
)

# Known headers that terminate a summary/objective body (line-anchored).
_SUMMARY_BODY_STOP = (
    r'education|academic\s+background|academics|academic\s+details|qualifications?|'
    r'educational\s+(?:qualification|background)s?|'
    r'course\s*/?\s*degree|college\s*/?\s*university|year\s+of\s+passing|aggregate|'
    r'professional\s+snapshot|functional\s+skills?|core\s+competenc(?:y|ies)|'
    r'areas?\s+of\s+expertise|technical\s+proficienc(?:y|ies)|'
    r'experience|work\s+experience|professional\s+experience|employment|work\s+history|'
    r'internship|internships|industrial\s+training|summer\s+internship|'
    r'technical\s+skills?|core\s+skills?|key\s+skills?|skill\s*sets?|skills?|'
    r'tools?|technologies?|tech\s+stack|competencies?|expertise|'
    r'operating\s+systems?(?:\s+distros?)?|distros?|'
    r'projects?|key\s+projects?|certifications?|certificates?|licenses?|'
    r'languages?|awards?|achievements?|interests?|references?|'
    r'personal\s+details|personal\s+information|biodata|bio\s+data|'
    r'contact(?:\s+details)?|declaration|social\s+links?'
)

# Legacy pattern kept for any external imports; prefer extract_summary_from_text.
SUMMARY_SECTION_PATTERN = re.compile(
    r'(?im)^(?:\*\*)?(?:career\s+objective|professional\s+objective|'
    r'professional\s+summary|profile\s+summary|'
    r'career\s+profile|career\s+summary|summary|objective|profile|about\s+me|overview)'
    r'(?:\*\*)?\s*:?\s*(?:\n+|\s+)([\s\S]*?)'
    r'(?=^\s*(?:\*\*)?(?:' + _SUMMARY_BODY_STOP + r')(?:\*\*)?\s*:?\s*$|\Z)',
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
    'professional experience', 'employment', 'employment history', 'education',
    'skills', 'technical skills',
    'technical skill', 'technicalskill', 'soft skills', 'softskills',
    'core skills', 'core skill', 'key skills', 'key skill',
    'skill set', 'skills set', 'skills and abilities', 'abilities',
    'technical proficiency', 'technical expertise', 'technical knowledge',
    'technical experience',
    'core competencies', 'areas of expertise', 'computer skills', 'it skills',
    'software skills',
    'tools', 'technologies', 'tech stack', 'project', 'projects',
    'key project', 'key projects', 'academic projects', 'academic project',
    'personal projects', 'personal project', 'major projects', 'major project',
    'project experience', 'project details',
    'certifications', 'certificates', 'certifications and licenses', 'licenses',
    'professional certifications', 'courses',
    'languages', 'language skills', 'linguistic proficiency', 'languages known',
    'awards', 'honors', 'honours', 'accomplishments', 'interests',
    'references', 'contact', 'resume', 'curriculum vitae', 'cv', 'about me',
    'work history', 'career history', 'qualification', 'qualifications',
    'achievements', 'extracurricular achievements', 'extra curricular achievements',
    'extracurricular activities', 'extra curricular',
    'extra curricular activities', 'co curricular activities',
    'co-curricular activities', 'leadership activities', 'activities',
    'strengths', 'key strengths',
    'extra curricular activities', 'co curricular activities',
    'co-curricular activities', 'leadership activities', 'activities',
    'internship', 'internships', 'internship experience', 'industrial training',
    'summer internship', 'management internship', 'research internship',
    'graduate internship', 'training experience',
    'trainings', 'training', 'apprenticeship',
    'internship / training',
    'academic details', 'academic background', 'academic qualifications',
    'academic qualification', 'academics',
    'educational qualifications', 'educational qualification',
    'educational background',
    'personal details', 'personal information', 'personalinformation',
    'personaldetails',
    'biodata', 'bio data', 'contact details',
    'hobbies', 'areas of strength', 'work summary', 'worksummary',
    'personal summary', 'personalsummary',
    'experience summary', 'experiencesummary',
    'other technical skills', 'skillset',
    'declaration', 'permanent address', 'present address', 'correspondence address',
    'current address', 'residential address',
    'profile summary', 'professional summary', 'professional objective',
    'career objective', 'career summary',
    'professional profile', 'personal profile',
    'organisational experience', 'organizational experience',
    'overview', 'role overview',
    'professional synopsis', 'educational credentials',
    'social link', 'social links', 'social media', 'key skills',
})

# Words that almost never appear in a real person name (role / UI / product).
_NAME_FORBIDDEN_WORDS = frozenset({
    'admin', 'administrator', 'engineer', 'developer', 'manager', 'analyst',
    'consultant', 'generation', 'summary', 'profile', 'objective', 'company',
    'link', 'links', 'social', 'database', 'middleware', 'powerpoint', 'excel',
    'oracle', 'mongodb', 'postgresql', 'mysql', 'mssql', 'dba', 'lead',
    'specialist', 'architect', 'officer', 'executive', 'intern', 'fresher',
    'resume', 'curriculum', 'vitae', 'overview', 'skills', 'experience', 'education',
    'certification', 'certifications', 'designation', 'contact', 'address',
    'location', 'technologies', 'technology', 'framework', 'frameworks',
    'marketing', 'sales', 'recruiter', 'hr', 'internship', 'trainee',
    'associate', 'director', 'founder', 'ceo', 'cto', 'devops', 'webmaster',
    'wordpress', 'javascript', 'typescript', 'react', 'angular', 'python',
    'java', 'linux', 'windows', 'android', 'ios',
    'project', 'projects',
    # Degree / academic tokens
    'btech', 'mtech', 'bsc', 'msc', 'bcom', 'mcom', 'bca', 'mca', 'bba', 'mba',
    'bachelor', 'master', 'masters', 'doctorate', 'diploma', 'phd', 'honours',
    'honors', 'science', 'commerce', 'arts', 'engineering', 'technology',
    'computer', 'information', 'electronics', 'mechanical', 'civil', 'electrical',
})

# Degree / academic lines wrongly captured as person names ("BTech CS", "B.E. IT").
_NAME_DEGREE_RE = re.compile(
    r'(?i)\b(?:'
    r'(?:bachelor|master|doctor)(?:\'?s)?(?:\s+of)?|'
    r'diploma|doctorate|phd|ph\.?\s*d|'
    r'b\.?\s*tech|m\.?\s*tech|btech|mtech|'
    r'b\.?\s*e\.?(?![a-z])|m\.?\s*e\.?(?![a-z])|'
    r'b\.?\s*sc|m\.?\s*sc|bsc|msc|'
    r'b\.?\s*com|m\.?\s*com|bcom|mcom|'
    r'b\.?\s*a\.?(?![a-z])|m\.?\s*a\.?(?![a-z])|'
    r'b\.?\s*s\.?(?![a-z])|m\.?\s*s\.?(?![a-z])|'
    r'mba|mca|bca|bba|ll\.?\s*b|ll\.?\s*m|'
    r'hsc|ssc|cbse|icse|puc|'
    r'(?:10|12)(?:th)?\s*(?:std|standard|grade)?'
    r')\b'
)
_NAME_ACADEMIC_FIELD_RE = re.compile(
    r'(?i)^(?:'
    r'cs|it|ise|ece|eee|cse|mech|civil|comp(?:uter)?(?:\s+science)?|'
    r'information\s+technology|electronics|mechanical|electrical|'
    r'computer\s+science(?:\s+and\s+engineering)?'
    r')$'
)
# Stop name search once body sections begin (avoid Education/Experience bleed).
_NAME_SECTION_STOP_RE = re.compile(
    r'(?i)^(education|experience|work\s+experience|professional\s+experience|'
    r'employment|skills|technical\s+skills|projects?|certifications?|'
    r'internship|internships|qualifications?|academic)\b'
)

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
    r'temporary\s+address|residential\s+address|address|'
    r'father(?:[\'’‘]?s)?\s*name|mother(?:[\'’‘]?s)?\s*name|spouse|'
    r'nationality|religion|languages?\s+known|blood\s+group|'
    r'passport|aadhaar|aadhar|pan(?:\s*card)?|'
    r'personal\s+details|personal\s+information|biodata|bio\s*data|contact\s+details|'
    r'declaration'
    r')\b'
)
_SEX_VALUE = re.compile(r'(?i)^(?:male|female)$')
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
    r'tal(?:uka)?|district|dist[\s\-–—]|pin(?:code)?|'
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
    'html', 'css', 'html5', 'css3', 'sql', 'java', 'python', 'javascript', 'typescript', 'react',
    'angular', 'nodejs', 'docker', 'kubernetes', 'aws', 'azure', 'linux', 'git',
    'c++', 'c#', '.net', '.net core', 'mongodb', 'mysql', 'oracle', 'redis', 'kafka',
    'powerpoint', 'excel', 'outlook', 'word', 'sharepoint', 'tableau', 'powerbi',
    'agile', 'multi-threading', 'data structure',
})
_SKILL_CRUMB_TOKENS = frozenset({
    'set', 'tools', 'technologies', 'technology', 'skills', 'skill', 'expertise',
    'competencies', 'frameworks', 'languages', 'platforms', 'tools and platforms',
    'skills tools and platforms', 'and platforms', 'and tools',
    'certification', 'certifications', 'certified', 'fundamentals',
    'university/board', '% of marks', 'configure', 'configuration',
    'databases', 'database', 'frameworks', 'operating systems', 'operating system',
})
# Role / product tokens that contaminate names derived from filenames.
_FILENAME_NAME_NOISE = frozenset({
    'resume', 'cv', 'updated', 'dba', 'hr', 'mongo', 'mongodb', 'mysql',
    'postgresql', 'postgres', 'oracle', 'expertia', 'ai', 'consultant',
    'specialist', 'analyst', 'architect', 'engineer', 'developer',
    'administrator', 'admin', 'database', 'middleware', 'network', 'fresher',
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
    if _SEX_VALUE.match(t):
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
    'career objective', 'professional objective', 'professional summary',
    'professional', 'summary', 'overview', 'role overview',
    'middleware administrator', 'middleware admin', 'oracle dba', 'sql dba', 'mssql dba',
    'fresher', 'experienced', 'immediate joining',
    'designation', 'certification', 'certifications', 'skills',
    'it team lead', 'assistant professor', 'curriculum vitae',
    'lead generation', 'social link', 'social links', 'profile summary',
    'company', 'powerpoint', 'video editor', 'marketing lead', 'ai engineer',
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

# Document / section titles that must never become a person's full_name.
_DOCUMENT_TITLE_NAMES = frozenset({
    'overview', 'role overview', 'resume', 'curriculum vitae', 'cv',
    'profile', 'summary', 'professional summary', 'professional objective',
    'career objective', 'objective', 'experience', 'education', 'skills',
    'projects', 'project', 'certifications', 'certification',
    'work experience', 'professional experience', 'employment',
    'personal profile', 'professional profile', 'profile summary',
    'career summary', 'career profile', 'about me', 'contact',
    'contact details', 'personal details', 'personal information',
})
# Header-like lines that should not stop the name scan (skip and keep looking).
_NAME_SKIP_BUT_CONTINUE = frozenset({
    'summary', 'objective', 'profile', 'about me', 'career objective',
    'professional summary', 'professional objective', 'profile summary',
    'contact', 'contact details', 'overview', 'role overview',
    'resume', 'curriculum vitae', 'cv',
})


def is_document_title_line(line: str | None) -> bool:
    """True for resume/section titles such as Overview — never a person name."""
    t = re.sub(r'^[\s#*•\-]+|[\s#:]+$', '', (line or '').strip()).strip()
    if not t:
        return False
    return t.lower() in _DOCUMENT_TITLE_NAMES


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
        'professional objective', 'overview', 'role overview',
        'address', 'contact', 'email', 'phone', 'mobile', 'unknown',
        'designation', 'certification', 'skills', 'summary', 'company',
        'powerpoint', 'profile summary', 'social link', 'social links',
        'lead generation', 'middleware admin', 'fundamentals',
        'english', 'hindi', 'marathi', 'tamil', 'telugu', 'kannada', 'gujarati',
        'bengali', 'urdu', 'punjabi', 'malayalam', 'odia', 'french', 'german',
        'spanish', 'japanese', 'korean', 'chinese',
    }:
        return False
    if is_document_title_line(t):
        return False
    if t.lower() in _JOB_TITLE_NAME_BLOCKLIST:
        return False
    if t.lower() in _PLACE_NAME_BLOCKLIST:
        return False
    if is_biodata_or_address_line(t):
        return False
    # Degrees / academic programs are not person names
    if _NAME_DEGREE_RE.search(t):
        return False
    if _NAME_ACADEMIC_FIELD_RE.match(t):
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
    # Role / product / UI / tech tokens are not person-name tokens
    for w in words:
        cleaned = w.strip(".,'").lower()
        if cleaned in _NAME_FORBIDDEN_WORDS or cleaned in _TECH_SINGLE_TOKEN:
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
    # DOCX extracts often leave later tokens uncapitalized ("First last").
    _NAME_STOP = {
        'a', 'an', 'the', 'of', 'in', 'for', 'with', 'and', 'or', 'to', 'as',
        'from', 'by', 'on', 'at',
    }
    if any(w.strip(".,'").lower() in _NAME_STOP for w in words):
        return False
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
    if alpha_words >= 2:
        return True
    return bool(words and words[0][0].isupper() and 2 <= len(words) <= 4)


def is_date_range_only_line(line: str) -> bool:
    """True when the line is essentially just a date range (e.g. 06/2016 - 06/2017)."""
    s = (line or '').strip()
    if not s:
        return False
    m = DATE_RANGE_PATTERN.fullmatch(s) or DATE_RANGE_PATTERN.fullmatch(
        re.sub(r'^[\s•·\-\*]+', '', s).strip()
    )
    return bool(m)


_SKILLS_PROSE_TRANSITION = re.compile(
    r'(?i)^(?:'
    r'project(?:s|ive)?(?:\s+(?:description|details|experience|name|title|summary))?'
    r'|achievements?|accomplishments?|awards?|performance\s+achievements?'
    r'|responsibilit(?:y|ies)|roles?\s*(?:and|&)\s*responsibilit(?:y|ies)'
    r'|major\s+activit(?:y|ies)(?:\s+performed)?'
    r'|activit(?:y|ies)\s+performed'
    r'|professional\s+(?:experience|certifications?|summary)'
    r'|work\s+experience|employment(?:\s+(?:history|details))?'
    r'|experience|work\s+history'
    r'|certifications?'
    r')\b'
)
_SKILL_CATEGORY_PREFIX = re.compile(
    r'(?i)^(?:os|operating\s+systems?|databases?|languages?|tools?|'
    r'frameworks?|technologies?|special\s+software|software|'
    r'(?:technical|key|core|soft)\s+skills?)\s*:\s*(.*)$'
)
_SKILL_REGION_HEADING = re.compile(
    r'(?i)^(?:(?:technical|key|core|soft)\s+)?skills?'
    r'(?:\s*(?:,|&|and)\s*(?:tools?|platforms?))?\s*:?\s*$'
)


def skill_item_looks_like_prose(item: str | None) -> bool:
    """True when a skill candidate is a sentence / project / duty paragraph."""
    text = (item or '').strip()
    if not text:
        return False
    words = text.split()
    n = len(words)
    if n >= 10:
        return True
    if re.search(r'[.!?]\s+\w', text):
        return True
    if text.endswith(('.', '!', '?')) and n >= 6:
        return True
    if re.match(r'(?i)^(?:i|we|my|our)\b', text) and n >= 5:
        return True
    if n >= 7 and re.search(r'(?i)\b(?:\w+ed|\w+ing)\b', text) and re.search(
        r'(?i)\b(?:the|a|an|for|with|to|of|by|from|into)\b', text
    ):
        return True
    if n >= 8 and re.search(r'(?i)\b(?:19|20)\d{2}\b', text):
        return True
    if n >= 5 and _SKILLS_PROSE_TRANSITION.search(text):
        return True
    return False


def _is_skill_token_or_category_line(line: str) -> bool:
    s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not s:
        return False
    if _SKILL_CATEGORY_PREFIX.match(s):
        return True
    parts = [p.strip() for p in re.split(r'[,|/]', s) if p.strip()]
    if 2 <= len(parts) <= 16 and all(1 <= len(p.split()) <= 5 for p in parts):
        if not any(skill_item_looks_like_prose(p) for p in parts):
            return True
    words = s.split()
    if 1 <= len(words) <= 4 and not s.endswith('.') and not skill_item_looks_like_prose(s):
        if not re.match(r'(?i)^(?:i|we|responsible|developed|worked|successfully)\b', s):
            return True
    return False


def clip_skills_section_at_prose(text: str) -> tuple[str, str]:
    """Split a Skills body when token lists give way to project/duty prose.

    Returns (kept_skills_text, peeled_prose). Peeled text must be preserved
    by the caller as Unclassified — never discarded.
    """
    lines = (text or '').splitlines()
    skill_seen = False
    cut: int | None = None
    for i, ln in enumerate(lines):
        s = ln.strip()
        if not s:
            continue
        if _SKILL_REGION_HEADING.match(s):
            continue
        if _is_skill_token_or_category_line(s):
            skill_seen = True
            continue
        if skill_seen and (
            _SKILLS_PROSE_TRANSITION.match(s) or skill_item_looks_like_prose(s)
        ):
            cut = i
            break
    if cut is None:
        return (text or '').strip(), ''
    return '\n'.join(lines[:cut]).strip(), '\n'.join(lines[cut:]).strip()


def is_plausible_skill_item(item: str | None) -> bool:
    """Reject section headers and bare date ranges from skills lists."""
    s = (item or '').strip()
    if not s or len(s) < 2 or len(s) > 80:
        return False
    s = s.lstrip(':').strip()
    if not s or len(s) < 2:
        return False
    if skill_item_looks_like_prose(s):
        return False
    if is_section_header_line(s):
        return False
    if is_date_range_only_line(s):
        return False
    if DATE_RANGE_PATTERN.fullmatch(s):
        return False
    if looks_like_phone_token(s) or looks_like_email_or_url(s):
        return False
    if is_labeled_contact_metadata(s):
        return False
    if re.match(r'(?i)^(email|phone|mobile|linkedin|github|contact|references?|place|location|address)\b', s):
        return False
    if s.lower() in _PLACE_NAME_BLOCKLIST:
        return False
    if re.fullmatch(
        r'(?i)(?:indian|american|british|canadian|australian|nationality)',
        s,
    ):
        return False
    if re.search(r'(?i)\b\d+\s+of\s+\d+\b', s) or re.match(r'(?i)^page\s+\d+', s):
        return False
    if re.search(
        r'(?i)(?:year of passing|board/university|school/college|degree\s*:|'
        r'university\s*,\s*[A-Za-z]|%\s*of\s*marks)',
        s,
    ):
        return False
    if re.match(
        r'(?i)^(?:build|built|develop|developed|implement|implemented|manage|'
        r'managed|create|created|ensure|ensuring)\b',
        s,
    ) and len(s.split()) >= 4:
        return False
    if re.search(
        r'(?i)\b(?:maharashtra|karnataka|tamil\s+nadu|telangana|gujarat|'
        r'kerala|rajasthan|west\s+bengal|andhra\s+pradesh|uttar\s+pradesh)\b',
        s,
    ) and (',' in s or len(s.split()) <= 4):
        if not re.search(r'(?i)(?:python|java|sql|aws|azure|react|\.net)', s):
            return False
    if re.match(
        r'(?i)^(?:ensuring|managing|performing|maintaining|creating|configured|'
        r'working\s+knowledge|good\s+knowledge)\b',
        s,
    ):
        return False
    if re.match(
        r'(?i)^(?:project(?:s)?(?:\s+name)?(?:\s*[-:]?\s*\d+)?|organization|'
        r'organisation|duration|company|employer|role|designation)\s*[:\-–—]',
        s,
    ):
        return False
    if re.match(r'(?i)^\d+\s+years?\s+of\s+experience\b', s):
        return False
    if re.search(r'(?i)\b(?:hsc|ssc|cbse|icse|u\.?p\.?\s*board)\b', s) and len(s.split()) <= 6:
        return False
    if is_biodata_or_address_line(s):
        return False
    if re.search(r'(?i)work\s+experience\s*=', s):
        return False
    if re.search(
        r'(?i)(?:certificate of participation|committee of|'
        r'father[\'’‘]?s?\s*name|mother[\'’‘]?s?\s*name)',
        s,
    ):
        return False
    if s.endswith('.') and len(s.split()) >= 6:
        return False
    # Leftover from matching "Skill" inside "Skilled in c#"
    if re.match(r'(?i)^ed\s+in\b', s):
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
    if re.match(r'(?i)^(?:&|and)\s+(?:platforms?|tools?|abilities|technologies?)\b', s):
        return False
    if re.search(r'(?i)university\s*/\s*board|%\s*of\s*marks', s) and len(s.split()) <= 6:
        return False
    if re.match(r'(?i)^(?:district|taluka|tehsil|pincode|pin\s*code)\b', s):
        return False
    if re.fullmatch(r'(?:[A-Za-z]\s+){2,}[A-Za-z]', s):
        return False
    if re.fullmatch(r'(?i)x\)|\)', s):
        return False
    if re.match(r'(?i)^(?:and\s+)?(?:troubleshoot|configure|install|unwanted)\b', s):
        return False
    if re.search(r'(?i)skills?\s*:\s*(?:professional\s+)?summary', s):
        return False
    if re.match(r'(?i)^[A-Za-z]{1,4}:\s*$', s) or re.match(r'(?i)^[A-Z][A-Z\s]{3,40}:\s*$', s):
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


_SKILL_GLUE_WORDS = frozenset({
    'and', 'or', 'of', 'the', 'for', 'with', 'in', 'to', 'on', 'at', 'by', 'from',
    'as', 'into', 'over', 'under', 'via', 'using',
    'skills', 'skill', 'management', 'communication', 'research', 'content',
    'strategy', 'engagement', 'making', 'team', 'time', 'organizational',
    'organisation', 'development', 'analysis',
    # Common English nouns that appear in product phrases — blocking these
    # prevents false splits such as "MS server studio". Not a product vocabulary.
    'server', 'studio', 'office', 'services', 'system', 'systems',
    'application', 'applications', 'software', 'database', 'databases',
})


def _token_has_tech_morphology(tok: str) -> bool:
    """Structural tech-token shape — not a vocabulary of product names."""
    t = (tok or '').strip()
    if not t or len(t) > 14:
        return False
    if t.lower() in _SKILL_GLUE_WORDS:
        return False
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9+#./]{1,13}', t):
        return False
    if t.isupper() and 2 <= len(t) <= 10:
        return True
    if re.search(r'[0-9/#+.]', t):
        return True
    if re.search(r'[a-z][A-Z]', t):
        return True
    return 2 <= len(t) <= 7


_TRAILING_SKILL_CATEGORY = re.compile(
    r'(?i)\s+(?:languages?|databases?|frameworks?|operating\s+systems?|'
    r'special\s+software)\s*$'
)


def _peel_trailing_category_before_glue_split(s: str) -> str:
    """Drop a trailing category word only when leftover is a glued tech blob."""
    m = re.match(
        r'(?i)^(.+?)\s+(?:skills?|tools?|languages?|databases?|frameworks?)$',
        (s or '').strip(),
    )
    if not m:
        return (s or '').strip()
    left = m.group(1).strip()
    words = left.split()
    if 3 <= len(words) <= 6 and all(_token_has_tech_morphology(w) for w in words):
        return left
    return (s or '').strip()


def maybe_split_glued_skill_tokens(raw: str) -> list[str]:
    """Split space-glued short tech tokens when morphology is consistent.

    Conservative: 2-word phrases, versioned products, and English noun phrases
    stay intact. False splits are worse than leaving a glued item.
    """
    s = _peel_trailing_category_before_glue_split(raw)
    if not s or re.search(r'[,|/]', s):
        return [s] if s else []
    words = s.split()
    if not (3 <= len(words) <= 6):
        return [s]
    if any(w.lower() in _SKILL_GLUE_WORDS for w in words):
        return [s]
    if not all(_token_has_tech_morphology(w) for w in words):
        return [s]
    casings = set()
    for w in words:
        if w.isupper():
            casings.add('upper')
        elif re.search(r'[a-z][A-Z]', w):
            casings.add('camel')
        elif w[:1].islower():
            casings.add('lower')
        else:
            casings.add('title')
    has_strong = any(
        w.isupper() or re.search(r'[0-9/#+.]', w) or re.search(r'[a-z][A-Z]', w)
        for w in words
    )
    # Mixed extract casings or an ALLCAPS/camel/version token among 3+ shorts.
    if len(casings) >= 2 or has_strong:
        return words
    return [s]


def filter_skill_items(skills: list[str], max_items: int = 40) -> list[str]:
    """Dedupe and drop header/date junk from skill lists."""
    expanded: list[str] = []
    for s in skills:
        raw = (s or '').strip()
        if not raw:
            continue
        raw = re.sub(r'^[\s•·\-\*●➢]+', '', raw).strip()
        if not raw:
            continue
        cat = re.match(
            r'(?i)^(core\s+lang(?:uage)?s?|languages?|frameworks?|databases?|'
            r'tools?(?:\s+used)?|technologies?(?:\s+used)?|programming|programmes?|os|'
            r'operating\s+systems?|soft\s+skills?|technical(?:\s+skills?)?|'
            r'tech(?:nolog(?:y|ies))?\s+used|special\s+software|software)\s*:\s*(.*)$',
            raw,
        )
        if cat:
            raw = (cat.group(2) or '').strip()
            if not raw:
                continue
        raw = _TRAILING_SKILL_CATEGORY.sub('', raw).strip()
        raw = re.sub(r'(?i)\bc\s+#', 'C#', raw)
        if not raw:
            continue
        for piece in split_list_items(raw):
            expanded.extend(maybe_split_glued_skill_tokens(piece))
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


# Common Indian surnames used to unglue all-lowercase portal filenames (Aparnamishra).
_COMMON_SURNAME_SUFFIXES = tuple(sorted(
    (
        'choudhary', 'choudhury', 'agarwal', 'agrawal', 'mukherjee', 'banerjee',
        'chatterjee', 'srivastava', 'tripathi', 'trivedi', 'sharma', 'shukla',
        'mishra', 'misra', 'kumar', 'reddy', 'patel', 'singh', 'gupta', 'joshi',
        'mehta', 'nair', 'iyer', 'iyengar', 'rao', 'das', 'ghosh', 'bose',
        'verma', 'varma', 'yadav', 'pandey', 'tiwari', 'dubey', 'saxena',
        'malhotra', 'kapoor', 'khanna', 'chopra', 'bhatia', 'arora', 'gohil',
        'kosta', 'desai', 'shetty', 'pillai', 'menon', 'krishnan', 'ramanan',
    ),
    key=len,
    reverse=True,
))


def _unglue_common_surname(token: str) -> str:
    """Split Aparnamishra → Aparna Mishra when a known surname suffix matches."""
    t = (token or '').strip()
    if not t or ' ' in t or len(t) < 8:
        return t
    low = t.lower()
    for suf in _COMMON_SURNAME_SUFFIXES:
        if len(low) <= len(suf) + 2:
            continue
        if low.endswith(suf):
            given = t[: len(t) - len(suf)]
            if len(given) >= 3 and given.isalpha() and suf.isalpha():
                return f'{given} {suf}'
    return t


def _title_case_name_tokens(base: str) -> str:
    parts: list[str] = []
    for w in base.split():
        if not w.isalpha():
            parts.append(w)
            continue
        # Keep 1–2 letter tokens as initials (RM, S)
        if len(w) <= 2:
            parts.append(w.upper())
        else:
            parts.append(w[:1].upper() + w[1:].lower())
    return ' '.join(parts)


def name_from_resume_filename(filename: str | None) -> str:
    """Derive a person name from resume filename when body has no header name.

    Examples:
      'ABHISHEK KUMAR.pdf' → Abhishek Kumar
      'Naukri_AnushkaGohil4y_0m.pdf' → Anushka Gohil
      '01_Furqan_Khan_-_HR.pdf' → Furqan Khan
    """
    if not filename:
        return ''
    base = str(filename).replace('\\', '/').split('/')[-1].strip()
    base = re.sub(r'\.[A-Za-z0-9]{1,5}$', '', base).strip()
    # Job-board / portal prefixes
    base = re.sub(
        r'(?i)^(?:naukri|indeed|linkedin|monster|foundit|shine|timesjobs)[_\-\s]*',
        '',
        base,
    )
    # Drop leading indexes / hashes
    base = re.sub(r'^(?:#?\d+[_\-\s]+)+', '', base)
    # Experience markers: 4y_0m, 4yrs, 2y3m
    base = re.sub(r'(?i)\d+\s*y(?:ea)?r?s?\s*[_\-]?\s*\d*\s*m(?:onths?)?', ' ', base)
    base = re.sub(r'(?i)[_\-]?\d+y\d*m?', ' ', base)
    base = re.sub(r'[_\-]+', ' ', base)
    # CamelCase → words (AnushkaGohil, AshishAdityaTripathi)
    base = re.sub(r'([a-z])([A-Z])', r'\1 \2', base)
    base = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1 \2', base)
    base = re.sub(r'\s+', ' ', base).strip()
    # Cut at role/keyword separators
    base = re.split(
        r'(?i)\s+(?:-|–|—)\s+|\s+(?:resume|cv|updated|dba|hr|network|fresher|'
        r'admin|administrator|engineer|developer|database|middleware|'
        r'mongo(?:db)?|mysql|postgresql|postgres|oracle|expertia|'
        r'consultant|specialist|analyst|architect)\b',
        base,
        maxsplit=1,
    )[0].strip()
    base = re.sub(r'\(\d+\)$', '', base).strip()
    if not base:
        return ''
    # Single glued lowercase token: try common surname split
    if ' ' not in base and base.isalpha():
        base = _unglue_common_surname(base)
    if base.isupper() or base.islower():
        cand = _title_case_name_tokens(base)
    else:
        cand = _title_case_name_tokens(base)
    # Drop leftover role/tech tokens so they cannot poison an otherwise valid name
    cleaned_words = [
        w for w in cand.split()
        if w.lower() not in _TECH_SINGLE_TOKEN
        and w.lower() not in _FILENAME_NAME_NOISE
    ]
    cand = ' '.join(cleaned_words).strip()
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
    r'|present|current|now|till\s*date|tilldate|ongoing|pursuing|still(?:\s+date)?'
    r')',
)

MONTH_MAP = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}


def split_list_items(text: str, *, max_item_len: int = 120) -> list[str]:
    """Split comma, pipe (ASCII/Unicode), or newline-separated prose into items.

    ``max_item_len`` defaults to 120 for skill/token lists. Do not use this helper
    for long-form summary/objective prose — use whitespace normalization instead.
    """
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

    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    multi = len(lines) > 1
    pipe_wrap_only = bool(
        multi
        and any('|' in ln for ln in lines)
        and all(
            '|' in ln or ln.endswith('|') or (i > 0 and lines[i - 1].endswith('|'))
            for i, ln in enumerate(lines)
        )
    )
    if '|' in raw and (not multi or pipe_wrap_only):
        # Single-line pipes, or a wrapped pipe list — not a mixed Skills body.
        flat = ' '.join(lines) if pipe_wrap_only else raw
        parts = [p.strip() for p in flat.split('|')]
        expanded: list[str] = []
        for p in parts:
            if ',' in p and not _is_institutionish(p):
                from app.ai.parser.enrichment.jd_text_inference import (
                    _split_skill_list_preserving_parens,
                )
                expanded.extend(x.strip() for x in _split_skill_list_preserving_parens(p) if x.strip())
            else:
                expanded.append(p)
        parts = expanded
    elif ',' in raw and not multi:
        parts = [p.strip() for p in raw.split(',')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
        expanded: list[str] = []
        for p in parts:
            p2 = re.sub(r'[│︱｜¦]', '|', p)
            if '|' in p2:
                for x in (t.strip() for t in p2.split('|')):
                    if not x:
                        continue
                    if ',' in x and not _is_institutionish(x):
                        from app.ai.parser.enrichment.jd_text_inference import (
                            _split_skill_list_preserving_parens,
                        )
                        expanded.extend(
                            y.strip() for y in _split_skill_list_preserving_parens(x) if y.strip()
                        )
                    else:
                        expanded.append(x)
            elif ',' in p2 and not _is_institutionish(p2):
                from app.ai.parser.enrichment.jd_text_inference import (
                    _split_skill_list_preserving_parens,
                )

                expanded.extend(_split_skill_list_preserving_parens(p2))
            else:
                expanded.append(p)
        parts = expanded
    result: list[str] = []
    limit = max(8, int(max_item_len or 120))
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
        if re.fullmatch(r'(?i)(?:and\s+)?abilities?', cleaned):
            continue
        if cleaned and len(cleaned) > 1:
            result.append(cleaned[:limit])
    coalesced: list[str] = []
    for part in result:
        if coalesced and _is_skill_wrap_continuation(coalesced[-1], part):
            coalesced[-1] = f'{coalesced[-1]} {part}'.strip()
        else:
            coalesced.append(part)
    return coalesced


def _is_skill_wrap_continuation(prev: str, nxt: str) -> bool:
    """Join PDF-wrapped skill/cert tails without merging adjacent tokens like Python / SQL."""
    p = (prev or '').rstrip()
    n = (nxt or '').strip()
    if not p or not n:
        return False
    if n[:1].islower() or n[:1] in ',;':
        return True
    if p.endswith(('-', '–', '—', ',', '/', '&', '(')):
        return True
    if re.search(
        r'(?i)(?:[-–—,;/&]|\b(?:with|of|in|and|the|for|to|a|an|as|by|on|from)\s*)$',
        p,
    ):
        return True
    if re.search(r'\([^)]*$', p) and re.match(r'(?i)^[\w.x]+\)?$', n):
        return True
    if re.fullmatch(r'(?i)x\)|\)', n):
        return True
    # Multi-word unfinished line + one-word Title-Case tail (cert wrap).
    # Do not join adjacent skills such as "Object Oriented Programming" / "Data Structures".
    if (
        not re.search(r'[.!?]$', p)
        and len(p.split()) >= 3
        and len(n.split()) == 1
        and n[:1].isupper()
        and n.lower() not in _TECH_SINGLE_TOKEN
    ):
        return True
    return False


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
    """Return (from, to) using the shared deterministic date extractor."""
    from app.ai.document_intelligence.deterministic import extract_date_range

    return extract_date_range(line or '')


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
    low = s.lower().strip('.,;:| ')
    if low in _LOCATION_SECTION_NOISE or low in SECTION_HEADERS:
        return ''
    if re.search(
        r'(?i)^(?:professional\s+profile|personal\s+profile|certificate|certifications?)\b',
        s,
    ):
        return ''
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


_HEADING_CONNECTORS = frozenset({'and', 'of', 'the', '&', '/', 'in', 'for', 'to', 'or'})
_HEADING_CORE_WORDS = frozenset({
    'summary', 'objective', 'profile', 'experience', 'education', 'skills', 'skill',
    'employment', 'projects', 'project', 'certifications', 'certificates', 'awards',
    'achievements', 'accomplishments', 'honors', 'honours', 'interests', 'hobbies',
    'references', 'contact', 'declaration', 'languages', 'qualification', 'qualifications',
    'internship', 'internships', 'training', 'trainings', 'apprenticeship',
    'biodata', 'overview', 'strengths', 'activities', 'licenses', 'courses',
    'academics', 'expertise', 'competencies', 'abilities', 'knowledge',
    'resume', 'cv', 'vitae',
})
_HEADING_CRUMB_WORDS = frozenset({
    'info', 'information', 'details', 'detail', 'section', 'known', 'set', 'sets',
    'background', 'history', 'record', 'handled', 'synopsis', 'credentials',
    'personal', 'professional', 'technical', 'academic', 'educational', 'work',
    'career', 'key', 'core', 'other', 'extra', 'curricular', 'co', 'about',
    'me', 'link', 'links', 'media', 'soft', 'computer', 'tools',
    'technologies', 'stack', 'areas', 'highlights', 'misc', 'additional',
})


def letter_spaced_alpha_compact(line: str) -> str:
    """Compact OCR letter-spaced lines: ``W O R K E X P`` → ``WORKEXP`` / ``WORK EXPERIENCE``."""
    raw = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', (line or '')).replace('\xa0', ' ')
    stripped = raw.strip()
    if not stripped:
        return ''
    core = re.sub(r'\([^)]*\)', ' ', stripped)
    core = re.sub(r'^[\s#*•\-_=]+|[\s#:_\-=]+$', '', core).strip()
    tokens = core.split()
    if len(tokens) >= 4 and all(len(t) == 1 and t.isalpha() for t in tokens):
        return ''.join(tokens)
    if re.search(r'\s{2,}|\t', core):
        parts = re.split(r'(?:\s{2,}|\t)+', core)
        words: list[str] = []
        for part in parts:
            toks = [t for t in part.split() if t]
            if not toks or not all(len(t) == 1 and t.isalpha() for t in toks):
                return ''
            if len(toks) < 2:
                return ''
            words.append(''.join(toks))
        if 1 <= len(words) <= 6:
            return ' '.join(words)
    return ''


def _is_structural_section_heading(cleaned: str, words: list[str]) -> bool:
    """True for unseen heading-like labels (not employers): PROFILE INFO, AWARDS AND ACHIEVEMENTS."""
    if not cleaned or not words:
        return False
    if re.search(r'(?:19|20)\d{2}', cleaned):
        return False
    if '#' in cleaned or re.search(r'\d', cleaned):
        return False
    if _ORG_EMPLOYMENT_CUE_RE.search(cleaned) and not re.search(
        r'(?i)\b(?:university|college|school|institute)\b',
        cleaned,
    ):
        return False
    words_low = [re.sub(r'[^a-z]', '', w.lower()) for w in words]
    content = [w for w in words_low if w and w not in _HEADING_CONNECTORS]
    if not content or len(content) > 6:
        return False
    if not any(w in _HEADING_CORE_WORDS for w in content):
        return False
    return all(w in _HEADING_CORE_WORDS or w in _HEADING_CRUMB_WORDS for w in content)


def is_section_header_line(line: str) -> bool:
    cleaned = re.sub(r'^[\s#*•\-_=]+|[\s#:_\-=]+$', '', (line or '').strip()).strip()
    if not cleaned:
        return True
    # Word decorative headers: ___CAREER OBJECTIVE___
    cleaned = re.sub(r'[_\-=~]{2,}', ' ', cleaned)
    cleaned = ' '.join(cleaned.split()).strip(' :*-')
    if not cleaned:
        return True
    words = cleaned.split()
    if len(words) > 8:
        return False
    if cleaned.endswith('.') and len(words) > 2:
        return False
    if cleaned.lower() in SECTION_HEADERS:
        return True
    compact = letter_spaced_alpha_compact(cleaned)
    if compact:
        low = compact.lower()
        glued = re.sub(r'[^a-z0-9]', '', low)
        if low in SECTION_HEADERS or glued in SECTION_HEADERS:
            return True
        compact_words = compact.split() if ' ' in compact else [compact]
        if _is_structural_section_heading(compact, compact_words):
            return True
    return _is_structural_section_heading(cleaned, words)


# Contact / reference lines that must never be parsed as employment.
_PHONE_TOKEN_RE = re.compile(r'^\+?[\d\s\-().]{7,20}$')
_EMAIL_IN_TEXT_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[A-Za-z]{2,}')
_URL_TOKEN_RE = re.compile(
    r'(?i)^(https?://|www\.)|'
    r'^(?:linkedin|github)\.com/|'
    r'^[A-Za-z0-9\-]+(?:\.[A-Za-z0-9\-]+)+\.[A-Za-z]{2,}(/.*)?$'
)
_CONTACT_LABEL_RE = re.compile(
    r'(?i)^(?:contact|contacts|references?|referees?|reporting\s+to|reported\s+to)\s*:?\s*(.*)$'
)
_CONTACT_PERSON_LINE_RE = re.compile(
    r'(?i)^(.+?)\s*\(\s*(?:'
    r'project\s+head|project\s+manager|reporting\s+manager|team\s+lead|'
    r'manager|lead|director|supervisor|hod|mentor|head|hr|recruiter'
    r')s?\s*\)\s*(?:[-–—]\s*.*)?$'
)
_ORG_EMPLOYMENT_CUE_RE = re.compile(
    r'(?i)\b(?:pvt|ltd|llc|inc|corp|llp|limited|private|bank|corporation|'
    r'technologies|technology|solutions|labs|'
    r'systems|consultancy|consulting|services|exchange|university|college)\b'
)
_IN_JOB_CONTACT_LABELS = frozenset({'contact', 'reference', 'references'})


def looks_like_phone_token(value: str | None) -> bool:
    """True when the whole string is primarily a phone number, not an org name."""
    s = (value or '').strip()
    if not s:
        return False
    digits = re.sub(r'\D', '', s)
    if not (7 <= len(digits) <= 15):
        return False
    if _PHONE_TOKEN_RE.match(s):
        return True
    rest = re.sub(r'(?i)^(?:phone|mobile|mob|cell|tel)\s*[:.\-–—]?\s*', '', s).strip()
    return bool(rest and _PHONE_TOKEN_RE.match(rest))


def looks_like_email_or_url(value: str | None) -> bool:
    s = (value or '').strip()
    if not s or len(s) > 120:
        return False
    if _EMAIL_IN_TEXT_RE.search(s) and s.count(' ') <= 2:
        return True
    if _URL_TOKEN_RE.search(s) and s.count(' ') <= 1:
        return True
    return False


def is_contact_section_label(line: str | None) -> bool:
    """Bare Contact/Reference heading (not 'Contact Details' / 'Contact: Name')."""
    s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not s:
        return False
    m = _CONTACT_LABEL_RE.match(s)
    if not m:
        return False
    rest = (m.group(1) or '').strip().strip(':').strip()
    label = re.split(r'\s*:', s, maxsplit=1)[0].strip().lower()
    if label not in _IN_JOB_CONTACT_LABELS:
        return False
    return (not rest) or rest in '-–—'


def looks_like_contact_person_line(line: str | None) -> bool:
    """Person name + (Project Head|Manager|…) — a reference, not a job title."""
    s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not s:
        return False
    labeled = _CONTACT_LABEL_RE.match(s)
    if labeled:
        rest = (labeled.group(1) or '').strip()
        head = re.split(r'\s*:', s, maxsplit=1)[0].strip().lower()
        if head not in _IN_JOB_CONTACT_LABELS:
            return False
        if not rest:
            return False
        s = rest
    s = re.sub(r'(?:\s*[-–—]\s*|\s+)\+?\d[\d\s\-().]{6,18}\d\s*$', '', s).strip()
    s = re.sub(r'\s+' + _EMAIL_IN_TEXT_RE.pattern + r'\s*$', '', s).strip()
    m = _CONTACT_PERSON_LINE_RE.match(s)
    if not m:
        return False
    name = (m.group(1) or '').strip()
    if labeled:
        return True
    return is_plausible_person_name(name)


def is_contact_or_reference_line(line: str | None) -> bool:
    """True for contact labels, reference people, phones, emails, and URLs."""
    s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not s or s in '-–—':
        return False
    if is_contact_section_label(s):
        return True
    if looks_like_phone_token(s) or looks_like_email_or_url(s):
        return True
    if looks_like_contact_person_line(s):
        return True
    labeled = _CONTACT_LABEL_RE.match(s)
    if not labeled:
        return False
    rest = (labeled.group(1) or '').strip()
    head = re.split(r'\s*:', s, maxsplit=1)[0].strip().lower()
    if head not in _IN_JOB_CONTACT_LABELS or not rest:
        return False
    name_part = re.split(r'\s*[-–—|]\s*', rest)[0].strip()
    name_part = re.sub(r'\s*\([^)]*\)\s*$', '', name_part).strip()
    return (
        looks_like_phone_token(rest)
        or looks_like_email_or_url(rest)
        or is_plausible_person_name(name_part)
    )


# Structural contact labels — never Role/Company/Skill/Degree content.
_CONTACT_FIELD_LABEL = (
    r'(?:e[\-\s]?mail|email|mail|phone|mobile|mob\.?|tel(?:ephone)?|contact|'
    r'place|location|address|linkedin|website|github|url)'
)
_LABELED_CONTACT_LINE_RE = re.compile(
    rf'(?i)^{_CONTACT_FIELD_LABEL}\s*[:\-–—]'
)
_INLINE_CONTACT_LABEL_RE = re.compile(
    rf'(?i)\s+{_CONTACT_FIELD_LABEL}\s*[:\-–—]'
)
# PDF two-column glue: "AdministratorE-mail:" / "NamePlace:" — capital starts a new label.
# Must not split "Workplace:" (lowercase "place" inside a word).
_GLUED_CONTACT_LABEL_RE = re.compile(
    r'(?<=[a-z0-9])(?='
    r'(?:E[\-\s]?mail|Email|EMAIL|Phone|PHONE|Mobile|MOBILE|Mob\.?|MOB\.?|'
    r'Contact|CONTACT|Place|PLACE|Location|LOCATION|Address|ADDRESS|'
    r'LinkedIn|LINKEDIN|Website|WEBSITE|GitHub|GITHUB)'
    r'(?:\s*[:\-–—]|\s*\+?\d)'
    r')'
)
_TRAILING_EMAIL_OR_PHONE_RE = re.compile(
    r'(?i)\s+(?:'
    r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}'
    r'|\+?\d[\d\s\-().]{7,}'
    r')\s*$'
)


def is_labeled_contact_metadata(line: str | None) -> bool:
    """True when the line is a labeled contact/header field (Place:, E-mail:, …)."""
    s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
    if not s:
        return False
    if _LABELED_CONTACT_LINE_RE.match(s):
        return True
    return is_contact_or_reference_line(s)


def peel_inline_contact(text: str | None) -> str:
    """Keep the non-contact remainder of a mixed title/contact line.

    ``Middleware Administrator E-mail: a@b.com`` → ``Middleware Administrator``
    """
    s = (text or '').strip()
    if not s:
        return ''
    m = _INLINE_CONTACT_LABEL_RE.search(s)
    if m and m.start() > 0:
        s = s[: m.start()].strip()
    else:
        glued = _GLUED_CONTACT_LABEL_RE.search(s)
        if glued and glued.start() > 0:
            s = s[: glued.start()].strip()
        m2 = _TRAILING_EMAIL_OR_PHONE_RE.search(s)
        if m2 and m2.start() > 0:
            tail = m2.group(0)
            # Year tokens are employment/education dates, not phone numbers.
            if not re.search(r'(?:19|20)\d{2}', tail):
                head = s[: m2.start()].strip()
                if head and not _LABELED_CONTACT_LINE_RE.match(head):
                    s = head
    return s.strip(' |,;:-–—')


def is_in_job_contact_header(header: str | None, current_section: str | None) -> bool:
    """Contact/References inside an Experience section is not a top-level header."""
    if (current_section or '').strip().lower() != 'experience':
        return False
    return (header or '').strip().lower() in _IN_JOB_CONTACT_LABELS


def experience_lacks_employment_evidence(
    role: str = '',
    company: str = '',
    start: str = '',
    end: str = '',
) -> bool:
    """No dates and no org-like company — not credible employment."""
    if (start or '').strip() or (end or '').strip():
        return False
    if _ORG_EMPLOYMENT_CUE_RE.search(company or ''):
        return False
    if re.search(r'(?i)\bintern(?:ship)?\b', role or ''):
        return False
    return True


_DURATION_ONLY_COMPANY = re.compile(
    r'(?i)^(?:\d+(?:\.\d+)?\s*(?:years?|yrs?|months?|mos?\.?)(?:\s+\d+\s*(?:years?|yrs?|months?|mos?\.?))*)\s*$'
)
_SKILL_AS_COMPANY = re.compile(
    r'(?i)^(?:'
    r'linux|unix|windows|python|java|sql|mysql|postgresql|postgres|mongodb|mongo\s*db|'
    r'oracle|nosql|html5?|css3?|javascript|typescript|react|angular|node(?:\.?js)?|'
    r'shell\s+scripting|server\s+monitoring|backup(?:\s*(?:and|&)\s*restore)?|'
    r'performance\s+tuning|upgradation|database\s+migration|'
    r'data\s+transformation\s+services|replication|sharding|indexing|'
    r'aws\s+redshift|azure\s+synapse(?:\s+analytics)?|'
    r'roles?\s+and\s+highlights|award\)?|'
    r'postgresql\s+administration|mongodb\s+administration'
    r')\.?$'
)
_FRESHER_OR_YEARS_ONLY_EXP = re.compile(
    r'(?i)(?:'
    r'(?:work\s*)?experience\s*[=:]\s*(?:fresher|nil|none|n/?a|0(?:\s*years?)?)\b'
    r'|^(?:fresher|no\s+(?:work\s+)?experience)\b'
    r'|total\s+experience\s*:\s*[\d.]+\s*years?\s*$'
    r'|^(?:teaching\s+)?experience\s*:\s*[\d.]+\s*years?\s*$'
    r')'
)


_EMPLOYMENT_HEADER_ROLES = frozenset({
    'internship', 'internships', 'summer internship', 'industrial training',
    'research internship', 'graduate internship', 'management internship',
    'internship experience', 'training experience', 'training', 'trainings',
    'apprenticeship', 'experience', 'work experience', 'professional experience',
    'employment', 'employment history', 'work history', 'career history',
})


def _is_employment_header_role(value: str) -> bool:
    s = (value or '').strip().rstrip(':').lower()
    return s in _EMPLOYMENT_HEADER_ROLES


_NON_JOB_COMPANY_HEADER = re.compile(
    r'(?i)^(?:'
    r'hobbies?|areas?\s+of\s+strength|strengths?|key\s+strengths?|'
    r'personal\s+summary|personal\s+information|personalinformation|'
    r'work\s+summary|career\s+summary|professional\s+summary|'
    r'technical\s+expert(?:ise|ies)?|technical\s+skills?|technicalskill|'
    r'soft\s+skills?|skills?(?:\s+and\s+abilities)?|'
    r'duration|organization|organisation|project(?:s)?(?:\s+name)?|'
    r'recruitments?|onboarding|responsibilities|work\s+summary|'
    r'declaration|objective|profile|about\s+me'
    r')\s*:?\s*$'
)
_PROJECT_TITLE_AS_COMPANY = re.compile(
    r'(?i)^(?:[A-Za-z][\w.+#]{1,24}\s+)+projects?\s*$'
)
_LABELED_DUTY_CRUMB = re.compile(
    r'(?i)^[A-Za-z][A-Za-z /&]{1,32}:\s*[A-Za-z].{0,40}$'
)
# Project headings and employment-metadata labels — never Company or Role.
# Organisation/Duration with a payload are labeled employment fields, not bare labels.
_PROJECT_OR_META_LABEL_RE = re.compile(
    r'(?i)^(?:'
    r'projects?\s*(?:#|no\.?\s*|number\s+)?\s*\d+'
    r'|projects?\s*[:\-–—]'
    r'|clients?(?:\s*name)?(?:\s*/\s*projects?)?\s*[:\-–—]'
    r'|duration\s*[:\-–—]\s*$'
    r'|environment\s*[:\-–—]'
    r'|technologies?\s+used\s*[:\-–—]'
    r'|(?:organization|organisation)\s*[:\-–—]\s*$'
    r'|project\s+(?:title|name|code|id)\s*[:\-–—]?'
    r'|(?:clients?|duration|environment|organization|organisation)\s*$'
    r')'
)


def is_project_or_employment_meta_label(value: str | None) -> bool:
    """True for Project #N / Client: / Duration: / Environment: style labels."""
    raw = (value or '').strip()
    if not raw:
        return False
    if _PROJECT_OR_META_LABEL_RE.match(raw):
        return True
    low = raw.lower().rstrip(':').strip()
    if low in {
        'client', 'clients', 'duration', 'environment', 'organization',
        'organisation', 'project', 'projects',
    }:
        return True
    return False


def looks_like_skill_or_duration_company(value: str) -> bool:
    """True when a company field is a skill, duration, or header crumb — not an employer."""
    raw = (value or '').strip()
    if not raw:
        return False
    if is_project_or_employment_meta_label(raw):
        return True
    if is_section_header_line(raw) and not _ORG_EMPLOYMENT_CUE_RE.search(raw):
        if not _is_employment_header_role(raw):
            return True
    if raw in {'|', '-', '–', '—', '/', '\\'} or set(raw) <= {'|', '-', '–', '—', '/', '\\', '.', ' '}:
        return True
    if re.match(r'(?i)^(?:total\s+)?experience$', raw):
        return True
    if re.match(r'(?i)^(?:duration|organization|organisation)\s*:?\s*$', raw):
        return True
    if re.match(
        r'(?i)^(?:successfully|working\s+knowledge|good\s+knowledge|'
        r'extensive\s+experience|configured|creating)\b',
        raw,
    ):
        return True
    if raw.lower() in {
        'english', 'hindi', 'marathi', 'tamil', 'telugu', 'kannada', 'gujarati',
        'bengali', 'urdu', 'punjabi', 'malayalam', 'odia', 'french', 'german',
        'spanish', 'japanese', 'korean', 'chinese',
    }:
        return True
    if re.search(r'(?i)\b(?:nagar|road|cross|street|colony|layout)\b', raw) and not _ORG_EMPLOYMENT_CUE_RE.search(raw):
        return True
    if re.match(r'(?i)^in\s+[A-Za-z]{2,16}$', raw) and not _ORG_EMPLOYMENT_CUE_RE.search(raw):
        return True
    s = raw.strip(':-–—|.').strip()
    if not s:
        return False
    if _NON_JOB_COMPANY_HEADER.match(s) or _NON_JOB_COMPANY_HEADER.match(raw):
        return True
    if _PROJECT_TITLE_AS_COMPANY.match(s):
        return True
    if (
        _LABELED_DUTY_CRUMB.match(s)
        and not _ORG_EMPLOYMENT_CUE_RE.search(s)
        and not re.match(
            r'(?i)^(?:company|employer|organization|organisation|role|title|'
            r'designation|position|job\s+title)\s*:',
            s,
        )
    ):
        return True
    if _DURATION_ONLY_COMPANY.match(s):
        return True
    if _SKILL_AS_COMPANY.match(s):
        return True
    if s.lower() in _TECH_SINGLE_TOKEN:
        return True
    return False


def is_fresher_or_years_only_experience_line(line: str) -> bool:
    """True for 'Work experience = fresher' / 'Total Experience: 4.7 Years' (not a job section)."""
    return bool(_FRESHER_OR_YEARS_ONLY_EXP.search((line or '').strip()))


_EDU_AS_JOB_INST_CUE = re.compile(
    r'(?i)\b(?:university|college|school|institute|academy|vidyalaya|'
    r'polytechnic|board)\b'
)
_EDU_AS_JOB_DEGREE_CUE = re.compile(
    r'(?i)\b(?:'
    r'(?:bachelor|master|doctor)(?:\'?s)?(?:\s+of)?|'
    r'b\.?\s?tech|m\.?\s?tech|b\.?\s?e\.?\b|m\.?\s?e\.?\b|'
    r'b\.?\s?sc|m\.?\s?sc|b\.?\s?com|m\.?\s?com|'
    r'b\.?\s?ca|m\.?\s?ca|bca|mca|bba|mba|pgdm|phd|diploma|'
    r'hsc|ssc|matric|intermediate|higher\s+secondary'
    r')\b'
)
_EDU_AS_JOB_EMPLOYER = re.compile(
    r'(?i)\b(?:pvt\.?|ltd\.?|llc|llp|inc\.?|limited|private)\b'
)


def looks_like_education_as_experience_row(company: str | None, role: str | None) -> bool:
    """True when Company/Role is a degree or institution block, not employment."""
    company = (company or '').strip()
    role = (role or '').strip()
    blob = f'{company} {role}'.strip()
    if not blob:
        return False
    if _EDU_AS_JOB_EMPLOYER.search(blob):
        return False
    degree = bool(_EDU_AS_JOB_DEGREE_CUE.search(blob))
    institution = bool(_EDU_AS_JOB_INST_CUE.search(blob))
    if degree and institution:
        return True
    if degree and not _is_employment_header_role(role) and not _is_employment_header_role(company):
        return True
    if institution and not (
        _is_employment_header_role(role)
        or re.search(
            r'(?i)\b(?:intern|engineer|analyst|manager|developer|consultant|'
            r'administrator|officer|associate|lead)\b',
            role,
        )
    ):
        return True
    return False


def is_non_job_experience_record(row: Any) -> bool:
    """
    True when a candidate experience row is a contact/reference, not a job.

    Operates on the structure of the record (company/role/dates), not on
    phones or manager names that merely appear in a job description.
    """
    if isinstance(row, dict):
        role = str(row.get('role') or row.get('title') or '').strip()
        company = str(row.get('company') or '').strip()
        start = str(row.get('start') or row.get('from') or '').strip()
        end = str(row.get('end') or row.get('to') or '').strip()
    else:
        role = (getattr(row, 'role', '') or '').strip()
        company = (getattr(row, 'company', '') or '').strip()
        start = (getattr(row, 'start', '') or '').strip()
        end = (getattr(row, 'end', '') or '').strip()

    company_meta = is_project_or_employment_meta_label(company)
    role_meta = is_project_or_employment_meta_label(role)
    if company_meta and role_meta:
        return True
    if company_meta and not role and not start and not end:
        return True
    if role_meta and not start and not (company and not company_meta):
        return True
    if looks_like_skill_or_duration_company(company) and not company_meta:
        return True
    if looks_like_skill_or_duration_company(role) and not role_meta:
        return True
    if looks_like_phone_token(company) or looks_like_email_or_url(company):
        return True
    if looks_like_phone_token(role) or looks_like_email_or_url(role):
        return True
    if is_contact_section_label(role) or is_contact_section_label(company):
        return True
    if company and is_section_header_line(company) and not _is_employment_header_role(company):
        return True
    if role and is_section_header_line(role) and not _is_employment_header_role(role):
        return True
    if looks_like_education_as_experience_row(company, role):
        return True
    # Person-name token as employer with no org cue (sidebar identity bleed)
    if (
        company
        and is_plausible_person_name(company)
        and not _ORG_EMPLOYMENT_CUE_RE.search(company)
        and experience_lacks_employment_evidence(role, company, start, end)
    ):
        return True
    if looks_like_contact_person_line(role) and experience_lacks_employment_evidence(
        role, company, start, end
    ):
        return True
    if looks_like_contact_person_line(company) and experience_lacks_employment_evidence(
        role, company, start, end
    ):
        return True
    return False


def has_credible_employment_evidence(row: Any) -> bool:
    """True only when a row has employer/role context — not skills or headers."""
    if is_non_job_experience_record(row):
        return False
    if isinstance(row, dict):
        role = str(row.get('role') or row.get('title') or '').strip()
        company = str(row.get('company') or '').strip()
        start = str(row.get('start') or row.get('from') or '').strip()
        end = str(row.get('end') or row.get('to') or '').strip()
    else:
        role = (getattr(row, 'role', '') or '').strip()
        company = (getattr(row, 'company', '') or '').strip()
        start = (getattr(row, 'start', '') or '').strip()
        end = (getattr(row, 'end', '') or '').strip()
    if is_project_or_employment_meta_label(company):
        company = ''
    if is_project_or_employment_meta_label(role):
        role = ''
    if looks_like_skill_or_duration_company(company):
        return False
    if company and (role or start or end):
        return True
    if role and (start or end) and (
        _is_employment_header_role(role)
        or re.search(r'(?i)\bintern\b', role)
        or is_plausible_job_title(role)
    ):
        return True
    return False


def join_spaced_letter_name(line: str) -> str:
    """Join PDF spaced-letter identity lines without assuming a specific name.

    Examples:
      ``R O S H A N  P A N I C K E R`` → ``Roshan Panicker``
      ``P A D M I N I P`` → ``Padmini P``
    """
    raw = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', (line or '')).replace('\xa0', ' ')
    stripped = raw.strip()
    if not stripped:
        return ''
    # Word groups separated by 2+ spaces, each group being single letters
    if re.search(r'\s{2,}', stripped):
        parts = re.split(r'\s{2,}', stripped)
        words: list[str] = []
        for part in parts:
            tokens = part.split()
            chars = [c for c in tokens if len(c) == 1 and c.isalpha()]
            if chars and len(chars) == len(tokens):
                words.append(''.join(chars).title())
            else:
                return ''
        cand = ' '.join(words)
        return cand[:80] if 2 <= len(words) <= 5 and is_plausible_person_name(cand) else ''
    tokens = stripped.split()
    if not tokens or not all(len(t) == 1 and t.isalpha() for t in tokens):
        return ''
    if not (4 <= len(tokens) <= 16):
        return ''
    compact = ''.join(tokens)
    if compact.lower() in SECTION_HEADERS or is_section_header_line(compact):
        return ''
    if is_section_header_line(stripped):
        return ''
    # Last letter is often a surname initial when the rest forms a given name
    if 5 <= len(tokens) <= 8:
        given = ''.join(tokens[:-1]).title()
        initial = tokens[-1].upper()
        cand = f'{given} {initial}'
        if is_plausible_person_name(cand) and not is_section_header_line(cand):
            return cand[:80]
    joined = ''.join(tokens).title()
    return joined[:80] if is_plausible_person_name(joined) else ''


def extract_name_from_text(text: str) -> str:
    """Pick a plausible person name from early resume lines, skipping section headers."""
    if not text:
        return ''
    # Labeled biodata may sit in a trailing personal-details table.
    labeled = re.search(
        r'(?im)^(?:\*\*)?(?:full\s*)?name(?:\*\*)?\s*[:\-–—|]+\s*(?:[:\-–—|]\s*)*(.+?)\s*$',
        text,
    )
    if not labeled:
        labeled = re.search(
            r'(?is)(?:^|\n)\s*(?:\*\*)?(?:full\s*)?name(?:\*\*)?\s*\n\s*[:\-–—]\s*(.+?)(?:\n|$)',
            text,
        )
    if labeled:
        cand = re.sub(r'(?i)^(mr|mrs|ms|miss|dr|prof)\.?\s+', '', labeled.group(1).strip())
        cand = cand.strip(':–—| ').strip()
        cand = cand.rstrip('-:–—|').strip()
        # Stop at next biodata label glued on same line
        cand = re.split(
            r'(?i)\s{2,}|\t|(?=designation|email|phone|mobile|address|location|dob)\b',
            cand,
            maxsplit=1,
        )[0].strip()
        if is_plausible_person_name(cand):
            try:
                from app.ai.parser.layout.heuristic import normalize_section_header

                if normalize_section_header(cand):
                    cand = ''
            except Exception:
                pass
        if cand and is_plausible_person_name(cand):
            if cand.isupper() or any(w[:1].islower() for w in cand.split() if w):
                cand = cand.title()
            return cand[:80]

    # Join consecutive ALL-CAPS single-token name lines (PyPDF2 word-per-line layouts)
    early_lines: list[str] = []
    for line in text.split('\n')[:30]:
        stripped = re.sub(r'[\u200b\u200c\u200d\u2060\ufeff\u00ad]', '', line).replace('\xa0', ' ').strip()
        if not stripped:
            continue
        # Do not scan Education / Experience / Skills bodies for names
        if _NAME_SECTION_STOP_RE.match(stripped):
            break
        title_key = stripped.lower().rstrip(':').strip()
        if is_document_title_line(stripped) or title_key in _NAME_SKIP_BUT_CONTINUE:
            early_lines.append(stripped)
            continue
        if is_section_header_line(stripped) and title_key not in _NAME_SKIP_BUT_CONTINUE:
            break
        early_lines.append(stripped)

    # Collapse runs of single ALL-CAPS alpha tokens at the top into one name candidate
    caps_run: list[str] = []
    for stripped in early_lines[:8]:
        if is_document_title_line(stripped) or is_section_header_line(stripped):
            if caps_run:
                break
            continue
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

    contact_idxs = [
        i
        for i, ln in enumerate(early_lines)
        if '@' in ln
        or re.search(r'(?i)\b(?:email|phone|mobile|tel)\b', ln)
        or (
            re.search(r'\+?\d[\d\s\-().]{8,}', ln)
            and not re.search(r'(?:19|20)\d{2}', ln)
        )
    ]

    def _name_candidate_score(idx: int, cand: str) -> int:
        words = cand.split()
        score = 4 if len(words) >= 2 else 0
        if contact_idxs:
            dist = min(abs(idx - c) for c in contact_idxs)
            if dist <= 8:
                score += 12 - dist
        elif idx <= 6 and len(words) >= 2:
            score += 3
        return score

    scored: list[tuple[int, int, str]] = []
    for idx, stripped in enumerate(early_lines[:20]):
        if stripped.startswith(('#', '*', '-', '•')):
            continue
        if is_document_title_line(stripped) or is_section_header_line(stripped):
            continue
        if _NAME_DEGREE_RE.search(stripped):
            continue
        if re.match(r'^\+?\d[\d\s\-().]{7,}$', stripped):
            continue
        joined = join_spaced_letter_name(stripped)
        nxt = early_lines[idx + 1] if idx + 1 < len(early_lines) else ''
        nxt_joined = join_spaced_letter_name(nxt) if nxt else ''
        if joined and nxt_joined:
            combined = f'{joined} {nxt_joined}'.strip()
            if is_plausible_person_name(combined) and not is_section_header_line(combined):
                scored.append((_name_candidate_score(idx, combined) + 3, -idx, combined[:80]))
        if joined:
            scored.append((_name_candidate_score(idx, joined), -idx, joined[:80]))
            continue
        probe = stripped
        if '@' in stripped or 'http' in stripped.lower() or 'www.' in stripped.lower():
            probe = re.sub(r'[A-Za-z0-9._%+\-]+@.*$', '', stripped).strip(' |,;:-–—')
        if not probe or re.search(r'\d', probe):
            continue
        words = probe.split()
        if 1 <= len(words) <= 5 and 2 <= len(probe) <= 80 and is_plausible_person_name(probe):
            display = probe[:80]
            if len(words) >= 2 and (probe.isupper() or any(w[:1].islower() for w in words)):
                display = probe.title()[:80]
            scored.append((_name_candidate_score(idx, display), -idx, display))

    if scored:
        scored.sort(reverse=True)
        best_score, _, best = scored[0]
        # Require a 2+ word name, or a 1-word name sitting next to contact
        if best_score >= 4:
            return best

    # Separated email locals only (anjali.bansode) — never glued locals
    email = extract_email_from_text(text)
    derived = name_from_email_local_part(email)
    if derived:
        return derived
    return ''


def document_identity_names(text: str | None) -> set[str]:
    """Person-name strings strongly identified from header/contact context.

    Used as a cross-field penalty: the same string must not later become
    Company, Role, Skill, or Institution merely because it is title-case.
    """
    names: set[str] = set()
    blob = text or ''
    extracted = (extract_name_from_text(blob) or '').strip()
    if extracted:
        names.add(extracted.lower())
        compact = identity_compact_key(extracted)
        if compact:
            names.add(compact)
    early: list[str] = []
    for line in blob.splitlines()[:24]:
        s = re.sub(r'^[\s•·\-\*●]+', '', (line or '').strip())
        if not s:
            continue
        if re.match(
            r'(?i)^(experience|work\s+experience|professional\s+experience|'
            r'education|skills?|projects?|summary|objective|certifications?)\b',
            s,
        ):
            break
        early.append(s)
    contact_idxs = [
        i
        for i, ln in enumerate(early)
        if is_labeled_contact_metadata(ln)
        or '@' in ln
        or looks_like_phone_token(ln)
        or re.search(r'(?i)\b(?:e[\-\s]?mail|email|phone|mobile|place|location|address)\b', ln)
    ]
    if not contact_idxs:
        return names
    for i, ln in enumerate(early):
        if is_labeled_contact_metadata(ln):
            continue
        cand = peel_inline_contact(ln)
        if not is_plausible_person_name(cand):
            continue
        dist = min(abs(i - c) for c in contact_idxs)
        if dist <= 6:
            names.add(cand.strip().lower())
            compact = identity_compact_key(cand)
            if compact:
                names.add(compact)
    return names


def identity_compact_key(value: str | None) -> str:
    """Compare names despite PDF spacing/punctuation differences."""
    return re.sub(r'[^a-z0-9]', '', (value or '').lower())


def identity_matches_person(value: str | None, identity_names: set[str] | None) -> bool:
    """True when value is the same person as a collected identity string."""
    s = (value or '').strip()
    if not s or not identity_names:
        return False
    if s.lower() in identity_names:
        return True
    compact = identity_compact_key(s)
    if compact and compact in identity_names:
        return True
    return any(identity_compact_key(n) == compact for n in identity_names if n)


def identity_is_employer_value(value: str | None, identity_names: set[str] | None) -> bool:
    """True when ``value`` is the document person-name, not an employer.

    Org suffixes (Ltd/Inc/…) are treated as explicit employer evidence.
    """
    s = (value or '').strip()
    if not identity_matches_person(s, identity_names):
        return False
    if re.search(
        r'(?i)\b(?:pvt\.?|ltd\.?|llc|inc\.?|corp\.?|limited|technologies|'
        r'solutions|labs|systems|bank|university|college)\b',
        s,
    ):
        return False
    return True


def extract_skills_from_text(
    text: str,
    max_items: int = 40,
    *,
    allow_unlabeled_lists: bool = False,
) -> list[str]:
    """Parse skills sections and inline skill lines from resume prose.

    ``allow_unlabeled_lists`` recovers compact comma/pipe tech rows with no
    Skills heading. Off by default so duty/prose lists are not harvested.
    """
    if not text:
        return []
    skills: list[str] = []

    for match in SKILL_SECTION_PATTERN.finditer(text):
        block = match.group(1) or ''
        skills.extend(split_list_items(block))
    skills = [s for s in skills if is_plausible_skill_item(s)]

    if not skills:
        in_section = False
        for line in text.split('\n'):
            stripped = line.strip()
            if re.match(
                r'(?i)^(?:technical\s+)?skills?\s*:?\s*$|^(?:core|key|soft)\s+skills?\s*:?\s*$|'
                r'^technicalskill\s*:?\s*$|'
                r'^skill\s*sets?\s*:?\s*$|^skills?\s*sets?\s*:?\s*$|'
                r'^technical\s+(?:proficiency|expertise|knowledge)\s*:?\s*$|'
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
                    r'personal\s+details|personal\s+information|strengths|achievements)\b',
                    stripped,
                ) or is_section_header_line(stripped):
                    break
                item = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if is_labeled_contact_metadata(item):
                    continue
                if item and is_plausible_skill_item(item):
                    skills.append(item)
                if len(skills) >= max_items:
                    break

    if not skills:
        # Only explicit skill-list headings — never "Skilled in …" summary sentences
        for line in text.split('\n')[:40]:
            if re.match(
                r'(?i)^(?:technical\s+proficiency|technical\s+expertise|'
                r'technical\s+knowledge|technical\s+skills?|technicalskill|'
                r'core\s+skills?|key\s+skills?|soft\s+skills?|skills?|technologies)\s*:',
                line.strip(),
            ) and not re.match(r'(?i)^skilled\b', line.strip()):
                after = re.split(r'(?i)^[^:]+:\s*', line.strip(), maxsplit=1)
                if len(after) > 1 and after[1].strip():
                    skills.extend(split_list_items(after[1]))
                    break

    if not skills and allow_unlabeled_lists:
        # Document-wide recovery: compact comma/pipe tech lists without a Skills heading
        for line in text.split('\n'):
            stripped = line.strip()
            if not stripped or is_section_header_line(stripped):
                continue
            if ',' not in stripped and '|' not in stripped and '/' not in stripped:
                continue
            items = [i for i in split_list_items(stripped) if is_plausible_skill_item(i)]
            if len(items) < 2 or any(len(i.split()) > 4 for i in items):
                continue
            techish = sum(
                1
                for i in items
                if i.lower() in _TECH_SINGLE_TOKEN or re.match(r'(?i)^[A-Za-z.#+]{1,20}$', i)
            )
            if techish >= 2:
                skills.extend(items)
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


_SUMMARY_PHONE_RE = re.compile(
    r'(?:\+?\d[\d\s\-().]{7,}\d)|\b\d{10}\b'
)
_SUMMARY_EMAIL_RE = re.compile(
    r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}'
)
_SUMMARY_URL_RE = re.compile(
    r'(?i)\b(?:https?://|www\.)\S+'
    r'|(?:linkedin|github|gitlab|bitbucket|facebook|twitter|instagram|behance)\.com/\S*'
)
_SUMMARY_CONTACT_LABEL_RE = re.compile(
    r'(?i)\b(?:contact|phone|mobile|e[\-\s]?mail|address|linkedin|github)\b'
)
_SUMMARY_ADDRESS_ONLY_RE = re.compile(
    r'(?i)^(?:[\w.\-]+\s*){0,4}'
    r'(?:road|rd\.?|street|st\.|nagar|colony|apartment|flat|floor|pin|pincode|'
    r'district|state|india|mumbai|delhi|bangalore|bengaluru|pune|hyderabad)\b'
    r'[\w\s,.\-/]*$'
)
# Inline bleed cutters inside a joined summary body (education tables, skills blocks).
# Do NOT match mid-sentence "software" / "diploma in …" capability bullets.
_SUMMARY_INLINE_BLEED_RE = re.compile(
    r'(?i)\s+(?:'
    r'course\s*/?\s*degree|college\s*/?\s*university|year\s+of\s+passing|aggregate|'
    r'professional\s+snapshot|functional\s+skills?|core\s+competenc(?:y|ies)|'
    r'areas?\s+of\s+expertise|technical\s+skills?|key\s+skills?|skill\s*sets?|'
    r'work\s+experience|professional\s+experience|employment\s+history|'
    r'operating\s+systems?(?:\s+distros?)?|distros?|'
    r'certifications?|educational\s+qualifications?|'
    r'softwares?\s*:|'
    r'(?:bachelor\'?s?|master\'?s?)\s+of\s+(?:engineering|technology|science|arts|commerce)\b|'
    r'diploma\s+in\s+(?:engineering|technology|computer)\b'
    r')'
)
_SUMMARY_SOFT_STOP_LINE_RE = re.compile(
    r'(?i)^(?:'
    r'course\s*/?\s*degree|college\s*/?\s*university|year\s+of\s+passing|aggregate|'
    r'professional\s+snapshot|functional\s+skills?|core\s+competenc(?:y|ies)|'
    r'areas?\s+of\s+expertise|it\s+engineer|software\s+engineer|'
    r'work\s+experience|professional\s+experience|'
    r'operating\s+systems?(?:\s+distros?)?|distros?|'
    r'erp\s+platforms?|tools\s*:|modules\s*:|'
    r'date\s+of\s+birth|nationality|gender'
    r')\b|^softwares?\s*:?\s*$'
)
_SUMMARY_SKILL_LIST_RE = re.compile(
    r'(?i)^(?:expertise|technical\s+skills?|key\s+skills?|skills?\s*:|'
    r'core\s+competenc(?:y|ies)|tools?\s*(?:known|used)?\s*:)'
)
_SUMMARY_EXPERIENCE_CRUMB_RE = re.compile(
    r'(?i)^(?:work\s+experience|professional\s+experience|employment|experience)\b'
    r'.{0,40}\b(?:years?|yrs?|months?)\b'
)
_SUMMARY_SPACED_HEADING_RE = re.compile(
    r'(?i)^(?:(?:[A-Za-z]\s+){4,}[A-Za-z])(?:\s*[_\W]*)+'
)
_SUMMARY_PROSE_CUE_RE = re.compile(
    r'(?i)\b(?:engineer|developer|architect|seeking|willing|motivated|experienced|'
    r'professional|years?|aspiring|dedicated|passionate|results|objective|summary|'
    r'specialist|analyst|manager|consultant|support|software|backend|frontend|'
    r'full[\s\-]?stack|graduate|internship|career|proven|track\s+record|'
    r'specializing|expertise\s+in|looking\s+(?:out\s+)?for|opportunity|'
    r'proficient|successfully|contributed|leverage|implementing|designing|'
    r'obtain\s+a\s+position|to\s+leverage|working\s+as|administrator|'
    r'production\s+environment|database)\b'
)


def _is_real_phone_fragment(frag: str) -> bool:
    """True for phone-like digit runs; false for dates / year+marks (2019 60.81, 15-04-2021)."""
    raw = (frag or '').strip()
    if not raw:
        return False
    # Explicit calendar dates
    if re.fullmatch(
        r'(?:0?[1-9]|[12]\d|3[01])[-/.](?:0?[1-9]|1[0-2])[-/.](?:19|20)\d{2}',
        raw,
    ):
        return False
    if re.fullmatch(
        r'(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:19|20)\d{2}',
        raw,
    ):
        return False
    # Graduation year + percentage / marks
    if re.fullmatch(r'(?:19|20)\d{2}\s+\d{1,3}(?:\.\d+)?%?', raw):
        return False
    digits = re.sub(r'\D', '', raw)
    # Real phones are typically 10+ digits; dd-mm-yyyy is 8
    return len(digits) >= 10


def _summary_has_phone(text: str) -> bool:
    for match in _SUMMARY_PHONE_RE.finditer(text or ''):
        if _is_real_phone_fragment(match.group(0)):
            return True
    return False


def _strip_contact_tokens(text: str) -> str:
    """Remove email / URL / phone tokens from prose while keeping surrounding sentences."""
    s = text or ''
    s = _SUMMARY_EMAIL_RE.sub(' ', s)
    s = _SUMMARY_URL_RE.sub(' ', s)
    parts: list[str] = []
    last = 0
    for match in _SUMMARY_PHONE_RE.finditer(s):
        if _is_real_phone_fragment(match.group(0)):
            parts.append(s[last:match.start()])
            last = match.end()
    parts.append(s[last:])
    s = ' '.join(''.join(parts).split())
    return s.strip()


def _is_contactish_summary_line(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return True
    # Never drop clear professional prose as "contact"
    if _SUMMARY_PROSE_CUE_RE.search(s) and len(s) >= 28:
        return False
    if _SUMMARY_EMAIL_RE.search(s) or _SUMMARY_URL_RE.search(s):
        return True
    # Split LinkedIn / share URLs across lines (utm_ / linkedin.com fragments)
    if re.search(r'(?i)(?:utm_source|utm_campaign|utm_medium|utm_content|linkedin\.com)', s):
        return True
    if _summary_has_phone(s):
        return True
    if re.match(r'(?i)^(?:contact|phone|mobile|e[\-\s]?mail|address|linkedin|github)\b', s):
        return True
    alpha_words = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", s)
    if _SUMMARY_CONTACT_LABEL_RE.search(s) and len(alpha_words) < 8:
        return True
    if _SUMMARY_ADDRESS_ONLY_RE.match(s) and len(alpha_words) < 12:
        return True
    return False


def summary_rejection_reason(summary: str | None) -> str | None:
    """Return a machine-readable reason if summary must be rejected, else None."""
    s = ' '.join((summary or '').split()).strip()
    if not s:
        return 'empty'
    low = s.lower().rstrip(':').strip()
    if low in SUMMARY_HEADING_PRIORITY or is_section_header_line(s):
        return 'section_heading_only'
    if _SUMMARY_EXPERIENCE_CRUMB_RE.match(s):
        return 'experience_header'
    # Skill-section headings / dumps must never become the Summary cell
    if _SUMMARY_SKILL_LIST_RE.match(s):
        return 'skills_list'
    # Skill / tool dumps: many commas or pipes, almost no verbs/prose cues.
    # Real summaries often list a few tech tokens (C#, ASP.NET) — keep those.
    comma_like = s.count(',') + s.count('|') + s.count(';')
    has_sentence = bool(re.search(r'[.!?]\s+\S', s)) or len(s) >= 100
    if (
        comma_like >= 4
        and not _SUMMARY_PROSE_CUE_RE.search(s)
        and not has_sentence
    ):
        return 'skills_list'
    # Event / schedule tables wrongly labeled as summary
    if re.search(r'(?i)\bevents?\s*done\b|\bday\s+event\s+company\b', s):
        return 'non_summary_content'
    if _SUMMARY_EMAIL_RE.search(s):
        return 'contains_email'
    if _summary_has_phone(s):
        return 'contains_phone_number'
    if _SUMMARY_URL_RE.search(s):
        return 'contains_social_or_url'
    # Contact / phone / email labels as the dominant signal (not prose mentioning "contact")
    if re.match(r'(?i)^(?:contact|phone|mobile|e[\-\s]?mail|address)\b', s):
        return 'contact_information'
    alpha_words = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", s)
    if _SUMMARY_CONTACT_LABEL_RE.search(s) and len(alpha_words) < 8:
        return 'contact_information'
    # Allow short professional blurbs; reject tiny crumbs / labels / bare names
    if len(s) < 12 or len(alpha_words) < 2:
        return 'too_short'
    has_prose_cue = bool(_SUMMARY_PROSE_CUE_RE.search(s))
    if len(alpha_words) < 4 and len(s) < 40 and not has_prose_cue:
        return 'too_short'
    if _SUMMARY_ADDRESS_ONLY_RE.match(s) and len(alpha_words) < 12:
        return 'address_only'
    digit_ratio = sum(ch.isdigit() for ch in s) / max(len(s), 1)
    if digit_ratio > 0.25 and len(alpha_words) < 10:
        return 'contact_information'
    return None


def is_valid_summary(summary: str | None) -> bool:
    """True when summary is meaningful prose and not contact / heading noise."""
    return summary_rejection_reason(summary) is None


def _normalize_summary_body(body: str, max_len: int = 2000) -> str:
    """Scrub contact bleed and section tails; keep bullet lists as newline items."""
    if not body:
        return ''
    from app.ai.document_intelligence.bullets import (
        has_list_evidence,
        is_glyph_crumb,
        join_duty_lines,
        strip_bullet_prefix,
    )

    kept_raw: list[str] = []
    for line in (body or '').splitlines():
        raw = (line or '').strip()
        if not raw or is_glyph_crumb(raw):
            continue
        cleaned = strip_bullet_prefix(raw)
        # Drop OCR-spaced heading prefixes glued onto the first content line
        cleaned = _SUMMARY_SPACED_HEADING_RE.sub('', cleaned).strip(' _-\t')
        if not cleaned:
            continue
        if is_section_header_line(cleaned) or _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned):
            if kept_raw:
                break
            continue
        if _is_contactish_summary_line(cleaned):
            # Contact block after prose → stop; contact-only lines before prose → skip
            if kept_raw:
                break
            continue
        kept_raw.append(raw)
        joined_so_far = ' '.join(strip_bullet_prefix(x) for x in kept_raw)
        if len(joined_so_far) >= 40 and _SUMMARY_INLINE_BLEED_RE.search(' ' + cleaned):
            kept_raw.pop()
            break
    if not kept_raw:
        text = ' '.join((body or '').split())
        is_list = False
    elif has_list_evidence(kept_raw):
        text = join_duty_lines(kept_raw, mark_bullets=True)
        is_list = True
    else:
        text = ' '.join(strip_bullet_prefix(x) for x in kept_raw)
        is_list = False
    if is_list:
        rebuilt: list[str] = []
        for ln in text.splitlines():
            bit = _strip_contact_tokens(strip_bullet_prefix(ln)).replace('**', '').strip()
            if not bit:
                continue
            if rebuilt and _SUMMARY_INLINE_BLEED_RE.search(' ' + bit):
                break
            rebuilt.append(bit if bit.lstrip().startswith(('•', '●', '-', '*')) else f'• {bit}')
        text = '\n'.join(rebuilt)
    else:
        text = _strip_contact_tokens(text)
        # Drop leading icon / bullet glyphs only — keep digits ("3.6 Yrs of experience…")
        text = re.sub(r'^[\u0080-\uFFFF•·▪▫►▸‣\*\#\|\-–—_]+', '', text).strip()
        text = text.replace('**', '')
        bleed = _SUMMARY_INLINE_BLEED_RE.search(text)
        if bleed and bleed.start() >= 40:
            text = text[: bleed.start()].strip()
        text = ' '.join(text.split()).strip()
    return text[:max_len]


def _heading_to_regex(heading: str) -> str:
    return r'\s+'.join(re.escape(p) for p in heading.split())


def _extract_body_for_summary_heading(text: str, heading: str) -> str:
    """Extract body text for a whole-line (or Heading: body) summary heading."""
    if not text or not heading:
        return ''
    h = _heading_to_regex(heading)
    stop = _SUMMARY_BODY_STOP
    other_headings = '|'.join(
        _heading_to_regex(x) for x in SUMMARY_HEADING_PRIORITY if x != heading
    )
    # Allow Word-style underscore/dash padding around the heading title.
    deco = r'[_\-=~*\s]*'
    # Multiline: heading on its own line, body until next known section header
    block = re.search(
        rf'(?im)^(?:\*\*)?{deco}{h}{deco}(?:\*\*)?\s*:?\s*$\n+'
        rf'([\s\S]*?)'
        rf'(?=^\s*(?:\*\*)?(?:{stop}|{other_headings})(?:\*\*)?\s*:?\s*$|\Z)',
        text,
    )
    if block and block.group(1):
        return _continue_past_false_section_stops(text, block.group(1).strip())
    # Same-line: "Professional Summary: Experienced engineer..."
    inline = re.search(
        rf'(?im)^(?:\*\*)?{deco}{h}{deco}(?:\*\*)?\s*:\s+(.+?)\s*$',
        text,
    )
    if inline and inline.group(1):
        return inline.group(1).strip()
    return ''


_INCOMPLETE_SUMMARY_TAIL_RE = re.compile(
    r'(?i)\b(?:with|of|in|and|the|for|to|a|an|as|by)\s*$'
)
_FALSE_MID_SUMMARY_STOP_RE = re.compile(
    r'(?i)^(?:experience|skills?|profile|summary|objective)\s*:?\s*$'
)


def _continue_past_false_section_stops(text: str, body: str) -> str:
    """
    Resume bodies sometimes put 'Experience' / 'Skills' mid-sentence (word-per-line PDFs).

    If the captured body ends on an incomplete phrase, keep reading past those false stops.
    """
    if not body or not text:
        return body
    compact = ' '.join(body.split())
    if not _INCOMPLETE_SUMMARY_TAIL_RE.search(compact):
        return body
    # Anchor at the body's own location (avoid matching short words like "of" earlier in the file)
    anchor = body.strip()
    idx = text.find(anchor)
    if idx < 0:
        # Fall back to last non-trivial line (>= 3 chars)
        last_line = next(
            (
                ln.strip()
                for ln in reversed(body.splitlines())
                if len(ln.strip()) >= 3
            ),
            '',
        )
        if not last_line:
            return body
        idx = text.find(last_line)
        if idx < 0:
            return body
        start_from = idx + len(last_line)
    else:
        start_from = idx + len(anchor)
    extra: list[str] = []
    for line in text[start_from:].splitlines():
        cleaned = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not cleaned:
            continue
        if _FALSE_MID_SUMMARY_STOP_RE.match(cleaned):
            continue
        if _is_contactish_summary_line(cleaned):
            break
        if _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned):
            break
        if is_section_header_line(cleaned) and not _FALSE_MID_SUMMARY_STOP_RE.match(cleaned):
            if re.match(
                r'(?i)^(?:education|certifications?|contact|projects?|languages?)\b',
                cleaned,
            ):
                break
            if extra and len(' '.join(extra)) > 40:
                break
            continue
        extra.append(cleaned)
        joined = compact + ' ' + ' '.join(extra)
        if len(joined) >= 2000:
            break
        if len(joined) >= 100 and re.search(r'[.!?]\s*$', cleaned):
            break
        if len(joined) >= 220:
            break
    if not extra:
        return body
    return body + '\n' + '\n'.join(extra)


def extract_summary_details(text: str, max_len: int = 2000) -> dict[str, str]:
    """
    Section-aware summary extraction with validation provenance.

    Returns keys: value, source_section, raw_value, validation, reason, fallback_section.
    """
    empty = {
        'value': '',
        'source_section': '',
        'raw_value': '',
        'validation': 'failed',
        'reason': 'empty',
        'fallback_section': '',
    }
    if not (text or '').strip():
        return empty

    first_rejected: dict[str, str] | None = None
    for heading in SUMMARY_HEADING_PRIORITY:
        raw = _extract_body_for_summary_heading(text, heading)
        if not raw.strip():
            continue
        normalized = _normalize_summary_body(raw, max_len=max_len)
        reason = summary_rejection_reason(normalized)
        if reason is None:
            # Thin one-liner from a bullet list — prefer richer Experience lead-in if present
            if len(normalized) < 80:
                exp_lead = _extract_experience_lead_prose(text, max_len=max_len)
                if exp_lead and len(exp_lead) >= max(len(normalized) + 40, 80):
                    return {
                        'value': exp_lead,
                        'source_section': 'EXPERIENCE_LEAD',
                        'raw_value': exp_lead,
                        'validation': 'passed',
                        'reason': f'thin_{heading.upper()};upgrade_EXPERIENCE_LEAD',
                        'fallback_section': heading.upper(),
                    }
            details = {
                'value': normalized,
                'source_section': heading.upper(),
                'raw_value': normalized,
                'validation': 'passed',
                'reason': 'ok',
                'fallback_section': '',
            }
            if first_rejected is not None:
                details['fallback_section'] = heading.upper()
                details['reason'] = (
                    f"rejected_{first_rejected['reason']};"
                    f"fallback_{heading.upper()}"
                )
                # Preserve rejected candidate for debugging consumers
                details['raw_value'] = normalized
            return details
        if first_rejected is None:
            first_rejected = {
                'value': '',
                'source_section': heading.upper(),
                'raw_value': normalized or raw[:max_len],
                'validation': 'failed',
                'reason': reason,
                'fallback_section': '',
            }

    # Experience-section lead-in (prose parked under Experience before first job).
    exp_lead = _extract_experience_lead_prose(text, max_len=max_len)
    if exp_lead:
        details = {
            'value': exp_lead,
            'source_section': 'EXPERIENCE_LEAD',
            'raw_value': exp_lead,
            'validation': 'passed',
            'reason': 'ok',
            'fallback_section': 'EXPERIENCE_LEAD',
        }
        if first_rejected is not None:
            details['reason'] = (
                f"rejected_{first_rejected['reason']};fallback_EXPERIENCE_LEAD"
            )
        return details

    # Unlabeled intro paragraph (common when "Summary" heading is empty / split).
    intro = _extract_unlabeled_intro_summary(text, max_len=max_len)
    if intro:
        details = {
            'value': intro,
            'source_section': 'PREAMBLE',
            'raw_value': intro,
            'validation': 'passed',
            'reason': 'ok',
            'fallback_section': 'PREAMBLE',
        }
        if first_rejected is not None:
            details['reason'] = (
                f"rejected_{first_rejected['reason']};fallback_PREAMBLE"
            )
        return details

    # Mis-sectioned blurbs (e.g. objective prose parked under Education in 2-col PDFs)
    blurb = _extract_objective_like_prose(text, max_len=max_len)
    if blurb:
        details = {
            'value': blurb,
            'source_section': 'PROSE',
            'raw_value': blurb,
            'validation': 'passed',
            'reason': 'ok',
            'fallback_section': 'PROSE',
        }
        if first_rejected is not None:
            details['reason'] = (
                f"rejected_{first_rejected['reason']};fallback_PROSE"
            )
        return details

    # Last resort: first-job duty highlights when resume has no Summary/Objective at all
    highlights = _extract_experience_highlights_summary(text, max_len=min(max_len, 900))
    if highlights:
        details = {
            'value': highlights,
            'source_section': 'EXPERIENCE_HIGHLIGHTS',
            'raw_value': highlights,
            'validation': 'passed',
            'reason': 'ok',
            'fallback_section': 'EXPERIENCE_HIGHLIGHTS',
        }
        if first_rejected is not None:
            details['reason'] = (
                f"rejected_{first_rejected['reason']};fallback_EXPERIENCE_HIGHLIGHTS"
            )
        return details

    if first_rejected is not None:
        return first_rejected
    return empty


_EXPERIENCE_LEAD_STOP_RE = re.compile(
    r'(?i)^(?:'
    r'company|employer|client|organization|organisation|firm|'
    r'position|designation|role|title|job\s+title'
    r')\s*[:\-–—]|'
    r'^(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|'
    r'jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|'
    r'dec(?:ember)?)\s+\d{2,4}\b|'
    r'^\d{1,2}[-/]\d{4}\b|'
    r'^(?:19|20)\d{2}\s*[-–—]'
)


def _extract_experience_lead_prose(text: str, max_len: int = 2000) -> str:
    """
    Capture summary-like prose under Experience before the first job entry.

    Some Naukri/PDF layouts put a career blurb under 'Experience' and only then
    list companies — treat that lead-in as a summary candidate.
    """
    if not (text or '').strip():
        return ''
    heading = re.search(
        r'(?im)^(?:\*\*)?(?:experience|work\s+experience|professional\s+experience|'
        r'employment|work\s+history)(?:\*\*)?\s*:?\s*$',
        text,
    )
    if not heading:
        return ''
    collected: list[str] = []
    for line in text[heading.end():].splitlines()[:40]:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not cleaned:
            if collected and len(' '.join(collected)) >= 60:
                break
            continue
        if is_section_header_line(cleaned) or _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned):
            break
        if _EXPERIENCE_LEAD_STOP_RE.match(cleaned):
            break
        if _is_contactish_summary_line(cleaned):
            continue
        # Skip bare bullets that are duty crumbs once we already have prose
        alpha_words = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", cleaned)
        if (
            collected
            and len(alpha_words) <= 6
            and not _SUMMARY_PROSE_CUE_RE.search(cleaned)
            and not re.search(r'[.!?]$', cleaned)
        ):
            break
        collected.append(cleaned)
        if len(' '.join(collected)) >= max_len:
            break
    if not collected:
        return ''
    normalized = _normalize_summary_body('\n'.join(collected), max_len=max_len)
    if len(normalized) < 60 or summary_rejection_reason(normalized) is not None:
        return ''
    # Require a professional / role cue so duty lists alone do not become Summary
    if not re.search(
        r'(?i)\b(?:working\s+as|administrator|engineer|developer|consultant|'
        r'professional|responsible\s+for|experience\s+in|management|'
        r'administration|production\s+environment|years?\s+of)\b',
        normalized,
    ):
        return ''
    return normalized


def _extract_experience_highlights_summary(text: str, max_len: int = 900) -> str:
    """
    When a resume has no Summary/Objective, use the first role's duty bullets.

    Common for TBI/Naukri templates that only list Personal info → Education → Experience.
    """
    if not (text or '').strip():
        return ''
    heading = re.search(
        r'(?im)^(?:\*\*)?(?:experience|work\s+experience|professional\s+experience|'
        r'employment|work\s+history)(?:\*\*)?\s*:?\s*$',
        text,
    )
    if not heading:
        return ''
    body = text[heading.end():]
    # Prefer content after the first Position/Designation line
    pos = re.search(
        r'(?im)^(?:\*\*)?(?:position|designation|role|title|job\s+title)'
        r'(?:\*\*)?\s*[:\-–—]\s*(.+?)\s*$',
        body,
    )
    start_at = pos.end() if pos else 0
    role = (pos.group(1).strip() if pos else '').strip()
    bullets: list[str] = []
    for line in body[start_at:].splitlines()[:50]:
        cleaned = re.sub(r'^[\s•·\-\*▪▫►▸‣]+', '', line.strip())
        if not cleaned:
            continue
        if is_section_header_line(cleaned) or _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned):
            break
        if _EXPERIENCE_LEAD_STOP_RE.match(cleaned):
            # Next company / position → stop (keep what we have)
            if bullets:
                break
            continue
        if _is_contactish_summary_line(cleaned):
            continue
        if len(cleaned) < 18:
            continue
        bullets.append(cleaned)
        if len(bullets) >= 8 or len('\n'.join(bullets)) >= max_len:
            break
    if len(bullets) < 3:
        return ''
    joined = '\n'.join(f'• {b}' if not b.lstrip().startswith(('•', '-', '*')) else b for b in bullets)
    if role and len(role) >= 4 and not re.search(re.escape(role), joined, re.I):
        joined = f'{role}.\n{joined}'
    normalized = _normalize_summary_body(joined, max_len=max_len)
    # Soften validation: duty lists rarely look like prose objectives
    if len(normalized) < 100:
        return ''
    if summary_rejection_reason(normalized) in {
        'empty',
        'contact_information',
        'contains_email',
        'contains_phone_number',
        'contains_social_or_url',
        'section_heading_only',
        'experience_header',
    }:
        return ''
    # Reject pure comma skill dumps
    if _SUMMARY_SKILL_LIST_RE.match(normalized):
        return ''
    return normalized


def _extract_unlabeled_intro_summary(text: str, max_len: int = 2000) -> str:
    """
    Capture intro prose before the first real section header.

    Handles layouts where a Summary heading is empty / split (e.g. PROFESSIONAL\\nSummary)
    but a solid blurb sits under the name/contact block.
    """
    if not (text or '').strip():
        return ''
    collected: list[str] = []
    for line in text.splitlines()[:80]:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not cleaned:
            if collected and len(' '.join(collected)) >= 80:
                break
            continue
        low = cleaned.lower().rstrip(':').strip()
        if low in SUMMARY_HEADING_PRIORITY:
            if collected:
                break
            continue
        if _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned):
            break
        if is_section_header_line(cleaned):
            # Skip early contact/personal headers; hard-stop on experience/education/skills
            if re.match(r'(?i)^(?:contact|personal(?:\s+details|\s+information)?|declaration)\b', low):
                continue
            break
        if _is_contactish_summary_line(cleaned):
            continue
        # Skip sidebar skill dumps before the real intro blurb
        if re.match(
            r'(?i)^(?:-\s*)?(?:erp\s+platforms?|tools\s*:|modules\s*:|skills?\b)',
            cleaned,
        ):
            if collected:
                break
            continue
        # Skip bare person-name / location crumbs at the very top
        alpha_words = re.findall(r"[A-Za-z][A-Za-z\-']{1,}", cleaned)
        if len(alpha_words) <= 4 and not _SUMMARY_PROSE_CUE_RE.search(cleaned):
            if not collected:
                continue
        collected.append(cleaned)
        if len(' '.join(collected)) >= max_len:
            break
    if not collected:
        return ''
    normalized = _normalize_summary_body('\n'.join(collected), max_len=max_len)
    # Intro crumbs like "Developer at Co" / skill dumps must not become Summary
    if len(normalized) < 40 or not _SUMMARY_PROSE_CUE_RE.search(normalized):
        return ''
    if summary_rejection_reason(normalized) is not None:
        return ''
    if _SUMMARY_SKILL_LIST_RE.match(normalized) or normalized.lstrip().startswith('-'):
        return ''
    if re.search(r'(?i)utm_source|erp\s+platforms?|\btools\s*:', normalized):
        return ''
    return normalized


def _extract_objective_like_prose(text: str, max_len: int = 2000) -> str:
    """Find the first early objective/summary-like paragraph when headings fail."""
    if not (text or '').strip():
        return ''
    strong_cue = re.compile(
        r'(?i)\b(?:seeking|looking\s+(?:out\s+)?for|willing|motivated|passionate|'
        r'graduate|objective|proven\s+track|specializing|dedicated|aspiring|'
        r'opportunity|professional\s+with|years?\s+of\s+experience|'
        r'i\s+am\s+a\b|complete\s+solution|working\s+as|'
        r'database\s+administrator|production\s+environment)\b'
    )
    # Prefer blank-line paragraphs, then sliding windows of consecutive lines
    chunks: list[str] = []
    for para in re.split(r'\n\s*\n', text[:4000]):
        if para.strip():
            chunks.append(para.strip())
    window: list[str] = []
    for line in text.splitlines()[:60]:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if (
            not cleaned
            or is_section_header_line(cleaned)
            or _is_contactish_summary_line(cleaned)
            or _SUMMARY_SOFT_STOP_LINE_RE.match(cleaned)
            or re.match(r'(?i)^(?:-\s*)?(?:erp\s+platforms?|tools\s*:|modules\s*:)', cleaned)
        ):
            if window:
                chunks.append('\n'.join(window))
                window = []
            continue
        window.append(cleaned)
        if len(window) >= 6:
            chunks.append('\n'.join(window))
            window = window[-2:]
    if window:
        chunks.append('\n'.join(window))

    best = ''
    best_score = -1
    for chunk in chunks:
        cand = _normalize_summary_body(chunk, max_len=max_len)
        if len(cand) < 60 or not is_valid_summary(cand):
            continue
        if not strong_cue.search(cand):
            continue
        # Skip job-entry crumbs ("Developer at Acme, Jan 2020")
        if re.match(
            r'(?i)^.{0,60}\bat\b.{0,40}\b(?:19|20)\d{2}\b',
            cand,
        ):
            continue
        # Education / marks blocks wrongly scored via a trailing "LOOKING FOR"
        if re.search(r'(?i)\b(?:cgpa|score\s+\d|%\s*be\b|diploma\s+in)\b', cand):
            if not strong_cue.search(cand[:120]):
                continue
        # Cut URL / skills-sidebar pollution that precedes the real blurb
        if re.search(r'(?i)utm_source|erp\s+platforms?|\btools\s*:', cand):
            role_blurb = re.search(
                r'(?i)((?:oracle|java|\.net|python|aws|azure|devops|software|technical|senior|'
                r'lead|principal)?\s*(?:fusion\s*&?\s*ebs\s+)?(?:technical\s+)?'
                r'(?:consultant|engineer|developer|architect|specialist|professional)\b[\s\S]{60,})',
                cand,
            )
            if not role_blurb:
                continue
            cand = _normalize_summary_body(role_blurb.group(1), max_len=max_len)
            if len(cand) < 60 or not is_valid_summary(cand) or not strong_cue.search(cand):
                continue
        # Prefer cues near the start of the blurb
        score = min(len(cand), 600)
        if strong_cue.search(cand[:140]):
            score += 300
        elif strong_cue.search(cand):
            score += 80
        # Penalize leftover contact / skills debris
        if re.search(r'(?i)utm_|linkedin\.com|@|erp\s+platforms?', cand):
            score -= 250
        if score > best_score:
            best = cand
            best_score = score
            if score >= 360 and not re.search(r'(?i)utm_|erp\s+platforms?', cand):
                break
    return best


def extract_summary_from_text(text: str, max_len: int = 2000) -> str:
    """Extract a validated summary/objective section body, or '' if none is safe."""
    return extract_summary_details(text, max_len=max_len).get('value') or ''


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
    r'communication|financial|curriculum|vitae|marketing|accounting|'
    r'certificate|certification|college|university|institute|school|'
    r'professional\s+profile|personal\s+profile)\b'
)
# Resume section titles that must never appear in Current/Preferred Location
_LOCATION_SECTION_NOISE = frozenset({
    'professional profile', 'personal profile', 'certificate', 'certificates',
    'certification', 'certifications', 'profile', 'summary', 'objective',
    'experience', 'education', 'skills', 'projects', 'project', 'declaration',
    'professional summary', 'career objective', 'about me', 'contact',
    'personal details', 'personal information', 'career profile', 'career summary',
    'profile summary', 'work experience', 'technical skills',
    'name', 'full name', 'designation', 'specialization', 'area of',
    'teaching', 'total experience',
})

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
    # Never accept resume section headings as location (Professional Profile, Certificate, …)
    if low in _LOCATION_SECTION_NOISE or low in SECTION_HEADERS:
        return False
    if re.search(
        r'(?i)\b(?:professional\s+profile|personal\s+profile|certificate|certification|'
        r'curriculum\s+vitae)\b',
        s,
    ):
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
    # Single short place token — reject section-ish words
    if re.match(r'^[A-Z][a-zA-Z .]{1,40}$', s) and len(s.split()) <= 4:
        if _LOCATION_TECH_NOISE.search(s) or _LOCATION_PROSE_NOISE.search(s):
            return False
        if re.search(
            r'(?i)\b(?:profile|certificate|summary|objective|experience|education|'
            r'skills?|projects?|declaration|contact)\b',
            s,
        ):
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
                'school', 'cgpi', 'sgpi', 'certificate', 'certification',
                'professional profile', 'personal profile',
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
    """Reuse the deterministic experience parser — no second comma-split path."""
    if not text:
        return []
    from app.ai.document_intelligence.coverage.resume_coverage import _experience_section_text
    from app.ai.document_intelligence.parsers.resume import parse_experience

    body = _experience_section_text(text) or ''
    if not body.strip():
        return []
    out: list[dict[str, Any]] = []
    for job in parse_experience(body, text)[:max_items]:
        end = (job.end or '').strip()
        if not end and job.is_current:
            end = 'Present'
        out.append({
            'title': (job.role or '')[:200],
            'company': (job.company or '')[:200],
            'from': job.start or '',
            'to': end,
            'years': None,
            'description': (job.description or '')[:2000],
        })
    return out


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
