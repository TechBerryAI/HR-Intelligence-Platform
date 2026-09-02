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
_DATE_ATOM = (
    r'(?:'
    r'(?:(?:0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+)?'
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+(?:19|20)\d{2}'
    r'|(?:0?[1-9]|[12]\d|3[01])[/\-](?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:0?[1-9]|1[0-2])[/\-](?:19|20)\d{2}'
    r'|(?:19|20)\d{2}(?:[/\-](?:0?[1-9]|1[0-2]))?'
    r')'
)
_PRESENT_ATOM = r'(?:Present|Current|Now|Till\s*Date|Tilldate|Ongoing|Pursuing)'
_DATE_RANGE_RE = re.compile(
    rf'(?i)\b({_DATE_ATOM})\s*(?:[-–—]|to)\s*({_DATE_ATOM}|{_PRESENT_ATOM})\b'
)
_PRESENT_TOKEN_RE = re.compile(
    r'(?i)^(present|current|now|till\s*date|tilldate|ongoing|pursuing)$'
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


def _looks_like_year_digit_soup(digits: str) -> bool:
    """True when digits are concatenated calendar years (e.g. 2026201820202025)."""
    d = re.sub(r'\D', '', digits or '')
    if len(d) < 12:
        return False
    years = re.findall(r'(?:19|20)\d{2}', d)
    if len(years) >= 2 and ''.join(years) in d:
        return True
    # Long run made only of year-like chunks
    if len(d) >= 12 and re.fullmatch(r'(?:(?:19|20)\d{2}){3,}', d):
        return True
    return False


def _phone_candidate_ok(raw: str) -> bool:
    digits = re.sub(r'\D', '', raw or '')
    if not digits or _looks_like_year_digit_soup(digits):
        return False
    if len(digits) == 10 and digits[0] in '6789':
        return True
    if len(digits) == 12 and digits.startswith('91') and digits[2] in '6789':
        return True
    if len(digits) == 11 and digits.startswith('0'):
        return True
    # Keep short international with + but reject year soup lengths
    if 7 <= len(digits) <= 13 and not re.search(r'(?:19|20)\d{2}(?:19|20)\d{2}', digits):
        return True
    return False


def extract_phone(text: str) -> str:
    # VALIDATION_FIX_whole_doc_phone_scan + year-soup rejection
    if not text:
        return ''

    def _normalize_phone_blob(blob: str) -> str:
        # Collapse digit groups separated by spaces: "+91- 99 70 38 80 01" → "+91-9970388001"
        return re.sub(r'(?<=\d)\s+(?=\d)', '', blob or '')

    # Prefer labeled lines, then header, then whole document
    m2 = re.search(
        r'(?i)(?:phone|mobile|mob|cell|tel|contact(?:\s*no)?)\s*[:.\-–—]?\s*([+\d][\d\s().-]{7,}\d)',
        text,
    )
    if m2:
        cand = _normalize_phone_blob(m2.group(1)).strip()
        if _phone_candidate_ok(cand):
            return cand
    m_plus = re.search(r'(\+91[\s\-]?\d[\d\s\-]{8,12}\d)', text[:2500])
    if m_plus:
        cand = _normalize_phone_blob(m_plus.group(1)).strip()
        if _phone_candidate_ok(cand):
            return cand

    for window in (text[:2500], text):
        # Do not collapse spaces across the whole window (glues years into phone soup)
        for pat in _PHONE_PATTERNS:
            for m in pat.finditer(window):
                cand = m.group(0).strip()
                if _phone_candidate_ok(cand):
                    return cand
        normalized = _normalize_phone_blob(window)
        for pat in _PHONE_PATTERNS:
            for m in pat.finditer(normalized):
                cand = m.group(0).strip()
                if _phone_candidate_ok(cand):
                    return cand
    # Spaced Indian mobiles: 99 70 38 80 01 or 99703 88001
    m3 = re.search(r'(?:\+91[\s\-]*)?([6-9](?:\s*\d){9})', text)
    if m3:
        digits = re.sub(r'\D', '', m3.group(1))
        if len(digits) == 10 and _phone_candidate_ok(digits):
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
        host = re.sub(r'(?i)^https?://', '', low).split('/')[0]
        if re.match(
            r'^(?:bsc|msc|bcom|mcom|bca|mca|bba|mba|btech|mtech|be|me|ba|ma|phd)\.[a-z]{2,6}$',
            host,
        ):
            return ''
        if not re.search(r'(?i)https?://|www\.|/', m.group(1)) and not re.search(
            r'(?i)\.(?:com|dev|io|net|org|co|app|in|me)(?:/|$)',
            m.group(1),
        ):
            return ''
        return url
    return ''


def normalize_month_token(token: str) -> str:
    t = (token or '').strip()
    if not t:
        return ''
    if _PRESENT_TOKEN_RE.match(t):
        return 'Present'
    m_dmy = re.match(
        r'^(0?[1-9]|[12]\d|3[01])[/\-](0?[1-9]|1[0-2])[/\-]((?:19|20)\d{2})$',
        t,
    )
    if m_dmy:
        return f'{m_dmy.group(3)}-{int(m_dmy.group(2)):02d}'
    m_ord = re.match(
        r'(?i)^(0?[1-9]|[12]\d|3[01])(?:st|nd|rd|th)?\s+'
        r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+'
        r'((?:19|20)\d{2})$',
        t,
    )
    if m_ord:
        mon = _MONTH_MAP.get(m_ord.group(2).lower()[:3], '01')
        return f'{m_ord.group(3)}-{mon}'
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
    from app.ai.parser.enrichment.resume_text_inference import (
        extract_location_from_text,
        heal_location_candidate,
        is_plausible_location_value,
    )

    loc = extract_location_from_text(text or '')
    if loc and is_plausible_location_value(loc):
        return loc
    # Labeled location lines — require delimiter to avoid prose captures
    m_label = re.search(
        r'(?i)(?:current\s+location|location|based\s+in|residing\s+(?:in|at)|address)\s*[:.\-–—]\s*'
        r'([A-Za-z][A-Za-z0-9 .,\-/()]{2,80})',
        text or '',
    )
    if m_label:
        candidate = heal_location_candidate(m_label.group(1).strip().rstrip(',.;'))
        if candidate and is_plausible_location_value(candidate):
            return candidate
        if candidate and '@' not in candidate and 'http' not in candidate.lower():
            from app.ai.parser.enrichment.resume_text_inference import known_location_cities

            for city in known_location_cities():
                if city.lower() in candidate.lower():
                    from app.ai.parser.enrichment.resume_text_inference import (
                        canonicalize_location_city,
                    )

                    return canonicalize_location_city(city)
    # Pipe-header city before phone/email
    m_pipe = re.search(
        r'(?im)^([A-Za-z][A-Za-z .,]{2,40})\s*[|•·]\s*(?:mobile|phone|tel|\+?\d|[a-z0-9._%+\-]+@)',
        text or '',
    )
    if m_pipe:
        cand = heal_location_candidate(m_pipe.group(1).strip().strip(','))
        if cand and is_plausible_location_value(cand):
            return cand
    # City, State / City, Country unlabeled
    m_cs = re.search(
        r'(?im)^([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*),\s*'
        r'([A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*)\s*$',
        '\n'.join((text or '').splitlines()[:15]),
    )
    if m_cs:
        cand = f'{m_cs.group(1)}, {m_cs.group(2)}'.strip().splitlines()[0][:80]
        if is_plausible_location_value(cand):
            return cand
    # Preamble fallback: short city line before Skills/Summary (not from those sections)
    # VALIDATION_FIX_location_cities — shared allowlist
    from app.ai.parser.enrichment.resume_text_inference import known_location_cities

    cities = {c.lower() for c in known_location_cities()} | {
        'remote', 'austin, tx', 'san francisco, ca', 'seattle, wa', 'new delhi',
    }
    section_hdr = re.compile(
        r'(?i)^(?:education|experience|skills|summary|objective|projects|'
        r'certifications|internship|work\s+history)\b'
    )
    for line in (text or '').splitlines()[:20]:
        s = line.strip().strip(',')
        if not s or '@' in s or 'http' in s.lower() or 'linkedin' in s.lower() or 'github' in s.lower():
            continue
        if section_hdr.match(s):
            break
        if re.match(r'^\+?\d', s):
            continue
        healed = heal_location_candidate(s)
        if healed and is_plausible_location_value(healed):
            return healed
        low = s.lower()
        if low in cities or any(c in low for c in cities if ',' in c or ' ' in c):
            return s if is_plausible_location_value(s) else healed or ''
        # "City, ST" pattern
        if re.match(r'^[A-Z][a-zA-Z\.]+(?:\s+[A-Z][a-zA-Z\.]+)*,\s*[A-Z]{2}$', s):
            return s
        if low in {'berlin', 'remote', 'london', 'paris', 'tokyo', 'sydney'}:
            return s
    return ''
