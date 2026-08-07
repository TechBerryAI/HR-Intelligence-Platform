"""Deterministic extractors — never use AI for these fields."""
from __future__ import annotations

import re
from typing import Tuple

_EMAIL_RE = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')
_PHONE_PATTERNS = [
    re.compile(r'\+?\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{4}'),
    re.compile(r'\b\d{10}\b'),
    # Indian mobile with optional mid-space / hyphen
    re.compile(r'\b[6-9]\d{4}[\s\-]?\d{5}\b'),
    re.compile(r'\b0\d{2,4}[\s\-]?\d{6,8}\b'),
]
_LINKEDIN_RE = re.compile(
    r'(?i)(?:https?://)?(?:www\.)?linkedin\.com/in/[A-Za-z0-9_\-/%]+',
)
_GITHUB_RE = re.compile(
    r'(?i)(?:https?://)?(?:www\.)?github\.com/[A-Za-z0-9_\-]+/?',
)
_URL_RE = re.compile(r'(?i)https?://[^\s<>\"\']+|www\.[^\s<>\"\']+')
_MONTH_MAP = {
    'jan': '01', 'january': '01', 'feb': '02', 'february': '02',
    'mar': '03', 'march': '03', 'apr': '04', 'april': '04',
    'may': '05', 'jun': '06', 'june': '06', 'jul': '07', 'july': '07',
    'aug': '08', 'august': '08', 'sep': '09', 'sept': '09', 'september': '09',
    'oct': '10', 'october': '10', 'nov': '11', 'november': '11',
    'dec': '12', 'december': '12',
}
_DATE_RANGE_RE = re.compile(
    r'(?i)\b('
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}(?:[/\-](?:0?[1-9]|1[0-2]))?'
    r')\s*(?:[-–—]|to)\s*('
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}(?:[/\-](?:0?[1-9]|1[0-2]))?'
    r'|Present|Current|Now'
    r')\b'
)


def extract_email(text: str) -> str:
    if not text:
        return ''
    # Heal OCR/PDF line breaks inside emails: "aditi.patil2904\n@gmail.com"
    healed = re.sub(
        r'([A-Za-z0-9._%+\-]+)\s*[\r\n]+\s*(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
        r'\1\2',
        text,
    )
    healed = re.sub(
        r'([A-Za-z0-9._%+\-]+)\s+(@[A-Za-z0-9.\-]+\.[A-Za-z]{2,})',
        r'\1\2',
        healed,
    )
    # Labeled email lines (common in headers / footers)
    m_label = re.search(
        r'(?i)(?:e[\-\s]?mail|mail\s*id|email\s*id)\s*[:.\-–—]?\s*'
        r'([a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,})',
        healed,
    )
    if m_label:
        return m_label.group(1).strip()
    m = _EMAIL_RE.search(healed)
    if m:
        return m.group(0).strip()
    m = _EMAIL_RE.search(text)
    return m.group(0).strip() if m else ''


def extract_phone(text: str) -> str:
    # VALIDATION_FIX_whole_doc_phone_scan
    if not text:
        return ''

    def _normalize_phone_blob(blob: str) -> str:
        # Collapse digit groups separated by spaces: "+91- 99 70 38 80 01" → "+91-9970388001"
        return re.sub(r'(?<=\d)\s+(?=\d)', '', blob or '')

    # Prefer header/preamble, then fall back to whole document
    for window in (text[:2500], text):
        normalized = _normalize_phone_blob(window)
        for pat in _PHONE_PATTERNS:
            m = pat.search(normalized)
            if m:
                return m.group(0).strip()
        for pat in _PHONE_PATTERNS:
            m = pat.search(window)
            if m:
                return m.group(0).strip()
    # Labeled phone lines anywhere in the doc
    m2 = re.search(
        r'(?i)(?:phone|mobile|mob|cell|tel|contact(?:\s*no)?)\s*[:.\-–—]?\s*([+\d][\d\s().-]{7,}\d)',
        text,
    )
    if m2:
        return _normalize_phone_blob(m2.group(1)).strip()
    # Spaced Indian mobiles: 99 70 38 80 01 or 99703 88001
    m3 = re.search(r'(?:\+91[\s\-]*)?([6-9](?:\s*\d){9})', text)
    if m3:
        digits = re.sub(r'\D', '', m3.group(1))
        if len(digits) == 10:
            return digits
    return ''


def _ensure_https(url: str) -> str:
    u = (url or '').strip().rstrip('/.,;')
    if not u:
        return ''
    if u.lower().startswith('www.'):
        return f'https://{u}'
    if not re.match(r'(?i)^https?://', u):
        return f'https://{u}'
    return u


def extract_linkedin(text: str) -> str:
    if not text:
        return ''
    m = _LINKEDIN_RE.search(text)
    if m:
        return _ensure_https(m.group(0))
    # Labeled form without full URL
    m2 = re.search(r'(?i)linkedin\s*:\s*(\S+)', text)
    if m2:
        val = m2.group(1).strip()
        if 'linkedin' in val.lower() or '/' in val:
            return _ensure_https(val if 'linkedin' in val.lower() else f'linkedin.com/in/{val}')
    return ''


def extract_github(text: str) -> str:
    if not text:
        return ''
    m = _GITHUB_RE.search(text)
    if m:
        return _ensure_https(m.group(0))
    m2 = re.search(r'(?i)github\s*:\s*(\S+)', text)
    if m2:
        val = m2.group(1).strip()
        if 'github' in val.lower():
            return _ensure_https(val)
        return _ensure_https(f'github.com/{val}')
    return ''


def extract_portfolio(text: str) -> str:
    """Non-LinkedIn/GitHub personal URL."""
    if not text:
        return ''
    m = re.search(r'(?i)(?:portfolio|website|personal\s+site)\s*:\s*(\S+)', text)
    if m:
        url = _ensure_https(m.group(1))
        low = url.lower()
        if 'linkedin.com' in low or 'github.com' in low:
            return ''
        return url
    return ''


def normalize_month_token(token: str) -> str:
    t = (token or '').strip()
    if not t:
        return ''
    if re.match(r'(?i)^(present|current|now)$', t):
        return 'Present'
    m = re.match(
        r'(?i)^(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+((?:19|20)\d{2})$',
        t,
    )
    if m:
        mon = _MONTH_MAP.get(m.group(1).lower()[:3], '01')
        return f'{m.group(2)}-{mon}'
    m2 = re.match(r'^(0?[1-9]|1[0-2])[/\-]((?:19|20)\d{2})$', t)
    if m2:
        return f'{m2.group(2)}-{int(m2.group(1)):02d}'
    m3 = re.match(r'^((?:19|20)\d{2})(?:[/\-](0?[1-9]|1[0-2]))?$', t)
    if m3:
        if m3.group(2):
            return f'{m3.group(1)}-{int(m3.group(2)):02d}'
        return m3.group(1)
    return t


def extract_date_range(line: str) -> Tuple[str, str]:
    m = _DATE_RANGE_RE.search(line or '')
    if not m:
        return '', ''
    return normalize_month_token(m.group(1)), normalize_month_token(m.group(2))


def extract_simple_location(text: str) -> str:
    from app.ai.parser.enrichment.resume_text_inference import extract_location_from_text

    loc = extract_location_from_text(text or '')
    if loc:
        return loc
    # Labeled location lines anywhere in the header/body
    m_label = re.search(
        r'(?i)(?:current\s+location|location|based\s+in|residing\s+(?:in|at)|address)\s*[:.\-–—]?\s*'
        r'([A-Za-z][A-Za-z0-9 .,\-/()]{2,80})',
        text or '',
    )
    if m_label:
        candidate = m_label.group(1).strip().rstrip(',.;')
        if candidate and '@' not in candidate and 'http' not in candidate.lower():
            # Prefer city token when address is long
            if len(candidate) > 50:
                for city in (
                    'Mumbai', 'Delhi', 'Bangalore', 'Bengaluru', 'Hyderabad', 'Chennai',
                    'Pune', 'Thane', 'Navi Mumbai', 'Kolkata', 'Noida', 'Gurugram',
                ):
                    if city.lower() in candidate.lower():
                        return city
            return candidate
    # Pipe-header city before phone/email
    m_pipe = re.search(
        r'(?im)^([A-Za-z][A-Za-z .,]{2,40})\s*[|•·]\s*(?:mobile|phone|tel|\+?\d|[a-z0-9._%+\-]+@)',
        text or '',
    )
    if m_pipe:
        cand = m_pipe.group(1).strip().strip(',')
        if cand and '@' not in cand and len(cand) <= 60:
            return cand
    # City, State / City, Country unlabeled
    m_cs = re.search(
        r'(?im)^([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*),\s*'
        r'([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*)\s*$',
        '\n'.join((text or '').splitlines()[:15]),
    )
    if m_cs:
        return f'{m_cs.group(1)}, {m_cs.group(2)}'.strip()[:80]
    # Preamble fallback: short city line between contact and sections
    # VALIDATION_FIX_location_cities
    cities = {
        'mumbai', 'delhi', 'new delhi', 'bangalore', 'bengaluru', 'hyderabad', 'chennai',
        'kolkata', 'pune', 'ahmedabad', 'gurgaon', 'gurugram', 'noida',
        'faridabad', 'jaipur', 'lucknow', 'nagpur', 'indore', 'bhopal', 'surat',
        'vadodara', 'coimbatore', 'kochi', 'thiruvananthapuram', 'chandigarh',
        'mysore', 'mysuru', 'visakhapatnam', 'vijayawada', 'patna', 'ranchi',
        'bhubaneswar', 'guwahati', 'thane', 'navi mumbai', 'andheri', 'powai',
        'austin', 'seattle', 'san francisco',
        'new york', 'london', 'toronto', 'singapore', 'dubai', 'berlin',
        'remote', 'austin, tx', 'san francisco, ca', 'seattle, wa',
    }
    for line in (text or '').splitlines()[:12]:
        s = line.strip().strip(',')
        if not s or '@' in s or 'http' in s.lower() or 'linkedin' in s.lower() or 'github' in s.lower():
            continue
        if re.match(r'^\+?\d', s):
            continue
        low = s.lower()
        if low in cities or any(c in low for c in cities if ',' in c or ' ' in c):
            return s
        # "City, ST" pattern
        if re.match(r'^[A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*,\s*[A-Z]{2}$', s):
            return s
        if low in {'berlin', 'remote', 'london', 'paris', 'tokyo', 'sydney'}:
            return s
    return ''
