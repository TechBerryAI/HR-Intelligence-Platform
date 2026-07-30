"""
Extract Resume TOON fields from unstructured resume text.
Used by the inference stage after repair, normalization, and enrichment.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any


SKILL_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:'
    r'technical\s+skills?|core\s+skills?|key\s+skills?|skills?|tools?|technologies?|'
    r'tech\s+stack|frameworks?|programming\s+languages?|competencies?|expertise'
    r')(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?[A-Z][^\n]{2,40}(?:\*\*)?\s*:|\Z)',
)

SUMMARY_SECTION_PATTERN = re.compile(
    r'(?i)(?:\*\*)?(?:professional\s+summary|summary|objective|profile|about\s+me)(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?[A-Z]|\Z)',
)

EDUCATION_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:education|academic\s+background|academics|qualifications)(?:\*\*)?\s*:?\s*'
    r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|work\s+experience|employment|skills|projects?|'
    r'certifications?|languages?|awards?)\b|\Z)',
)

CERT_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:certifications?|certificates?|licenses?|credentials?)(?:\*\*)?\s*:?\s*'
    r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:experience|education|skills|projects?|languages?|awards?)\b|\Z)',
)

SECTION_HEADERS = frozenset({
    'summary', 'objective', 'profile', 'experience', 'work experience',
    'professional experience', 'employment', 'education', 'skills', 'technical skills',
    'projects', 'certifications', 'certificates', 'languages', 'awards', 'interests',
    'references', 'contact', 'resume', 'curriculum vitae', 'cv', 'about me',
    'work history', 'qualifications', 'achievements',
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


def is_plausible_job_title(title: str | None) -> bool:
    """Reject summary/objective sentence fragments that are not job titles."""
    t = (title or '').strip()
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
    # Lowercase multi-word prose (e.g. "to help the company achieve…")
    if t[0].islower() and len(words) >= 4:
        return False
    return True


DATE_RANGE_PATTERN = re.compile(
    r'(?i)('
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}'
    r'|\d{1,2}[/\-]\d{4}'
    r'|\d{4}[/\-]\d{1,2}'
    r'|\d{4}-\d{2}'
    r'|\d{4}'
    r')'
    r'\s*(?:[-–—to]+|\s+to\s+)\s*'
    r'('
    r'(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?\s+\d{4}'
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
    """Split comma, pipe, or newline-separated prose into trimmed non-empty lines."""
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    if '|' in raw:
        parts = [p.strip() for p in raw.split('|')]
    elif ',' in raw and '\n' not in raw:
        parts = [p.strip() for p in raw.split(',')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
    result: list[str] = []
    for part in parts:
        cleaned = re.sub(r'^[\s•·\-\*]+', '', part).strip()
        cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
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
    """Approximate total years from experience date ranges."""
    if not experience:
        return None
    total_months = 0
    for exp in experience:
        if not isinstance(exp, dict):
            continue
        start = _parse_year_month(str(exp.get('from') or ''))
        end_raw = str(exp.get('to') or '')
        if re.match(r'(?i)^(present|current|now)$', end_raw.strip()):
            end = _parse_year_month('Present')
        else:
            end = _parse_year_month(end_raw)
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


def is_section_header_line(line: str) -> bool:
    cleaned = re.sub(r'^[\s#*•\-]+|[\s#:]+$', '', (line or '').strip()).strip()
    if not cleaned:
        return True
    return cleaned.lower() in SECTION_HEADERS


def extract_name_from_text(text: str) -> str:
    """Pick a plausible person name from early resume lines, skipping section headers."""
    if not text:
        return ''
    for line in text.split('\n')[:15]:
        stripped = line.strip()
        if not stripped or stripped.startswith(('#', '*', '-', '•')):
            continue
        if '@' in stripped or 'http' in stripped.lower() or 'www.' in stripped.lower():
            continue
        if re.match(r'^\+?\d[\d\s\-().]{7,}$', stripped):
            continue
        if is_section_header_line(stripped):
            continue
        if re.search(r'\d{5,}', stripped):
            continue
        # Prefer 2–5 word capitalized / title-case names
        words = stripped.split()
        if 1 <= len(words) <= 6 and 2 <= len(stripped) <= 80:
            if any(c.isalpha() for c in stripped):
                return stripped[:80]
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
                r'^tools?\s*:?\s*$|^technologies?\s*:?\s*$|^tech\s+stack\s*:?\s*$|^competencies?\s*:?\s*$',
                stripped,
            ):
                in_section = True
                inline = re.sub(r'(?i)^[^:]+:\s*', '', stripped).strip()
                if inline:
                    skills.extend(split_list_items(inline))
                continue
            if in_section:
                if re.match(
                    r'(?i)^(?:experience|education|projects?|certifications?|employment|work\s+history)\b',
                    stripped,
                ):
                    break
                item = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if item and len(item) > 1 and len(item) < 80:
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

    return dedupe_skills(skills, max_items)


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


def extract_location_from_text(text: str) -> str:
    """Labeled location, Remote/Hybrid, City ST, or common city names in header."""
    if not text:
        return ''
    patterns = [
        r'(?i)(?:location|current\s*location|address|city|based\s*in)\s*[:\-]\s*([^\n]+)',
        r'(?i)\b(remote|hybrid|work\s+from\s+home|wfh)\b',
        r'\b([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*),\s*([A-Z]{2})\b',
    ]
    for pat in patterns:
        m = re.search(pat, text[:800])
        if not m:
            continue
        if m.lastindex and m.lastindex >= 2 and pat.endswith(r'\b'):
            loc = f'{m.group(1)}, {m.group(2)}'
        else:
            loc = m.group(1).strip().strip('.,;:')
        if 2 <= len(loc) <= 80:
            return loc

    header = text[:500]
    cities = [
        'Mumbai', 'Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai',
        'Kolkata', 'Pune', 'Ahmedabad', 'Gurgaon', 'Gurugram', 'Noida',
        'Faridabad', 'Jaipur', 'Lucknow', 'Austin', 'Seattle', 'San Francisco',
        'New York', 'London', 'Toronto', 'Singapore', 'Dubai',
    ]
    for city in cities:
        if city in header:
            return city
    return ''


def extract_experience_from_text(text: str, max_items: int = 10) -> list[dict[str, Any]]:
    """Lightweight experience lines when structured experience is missing."""
    if not text:
        return []
    experiences: list[dict[str, Any]] = []
    # Require section header at line start so mid-sentence "experience" (e.g. objective) is ignored.
    block_match = re.search(
        r'(?i)(?:^|\n)\s*(?:\*\*)?(?:work\s+experience|professional\s+experience|experience|'
        r'employment|work\s+history)(?:\*\*)?\s*:?\s*'
        r'([\s\S]*?)(?=\n\s*(?:\*\*)?(?:education|skills|projects|certifications)|\Z)',
        text,
    )
    if not block_match:
        return []
    raw = block_match.group(1) or ''
    for line in raw.split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        stripped = re.sub(r'^\d+[\.\)]\s*', '', stripped).strip()
        if not stripped or len(stripped) < 5 or is_section_header_line(stripped):
            continue
        from_d, to_d = extract_date_range_from_line(stripped)
        line_wo_dates = DATE_RANGE_PATTERN.sub('', stripped).strip(' |-–—,')
        parts = re.split(r'\s+at\s+|\s+@\s+|,\s+', line_wo_dates, maxsplit=1)
        title = parts[0].strip() if parts else line_wo_dates
        company = parts[1].strip() if len(parts) > 1 else ''
        if not is_plausible_job_title(title):
            # Description / objective bullets are not roles
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
    degree_pat = re.compile(
        r'(?i)\b((?:B\.?\s?Tech|B\.?\s?E\.?|B\.?\s?S\.?|B\.?\s?A\.?|B\.?\s?Com|'
        r'M\.?\s?Tech|M\.?\s?S\.?|M\.?\s?A\.?|M\.?\s?B\.?\s?A\.?|M\.?\s?Com|'
        r'Ph\.?\s?D\.?|Bachelor(?:\'?s)?|Master(?:\'?s)?|Diploma|Associate)'
        r'(?:\s+(?:of|in)\s+[A-Za-z &\-/]+)?)',
    )
    for line in raw.split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        if not stripped or len(stripped) < 4 or is_section_header_line(stripped):
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
        rest = degree_pat.sub('', stripped) if degree_m else stripped
        rest = DATE_RANGE_PATTERN.sub('', rest)
        rest = re.sub(r'\b(19|20)\d{2}\b', '', rest)
        rest = re.sub(r'(?i)\b(?:gpa|cgpa|percentage)\s*[:=]?\s*[\d.]+%?', '', rest)
        institution = re.sub(r'^[\s,\-|–—]+|[\s,\-|–—]+$', '', rest).strip()
        gpa_m = re.search(r'(?i)(?:gpa|cgpa|percentage)\s*[:=]?\s*([\d.]+%?)', stripped)
        gpa = gpa_m.group(1) if gpa_m else ''
        if degree or institution:
            education.append({
                'degree': degree[:200],
                'institution': institution[:200],
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
        parts = re.split(r'\s+[-–—|]\s+|\s+from\s+|\s+by\s+', stripped, maxsplit=1, flags=re.I)
        name = parts[0].strip()
        issuer = parts[1].strip() if len(parts) > 1 else ''
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
