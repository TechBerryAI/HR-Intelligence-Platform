"""Shared value normalizers.

Both sides of every comparison run through this module, so a score never
reflects a formatting difference the product does not care about.
"""
from __future__ import annotations

import difflib
import re
import unicodedata

# ---------------------------------------------------------------- text basics

_BULLET_CHARS = '•●▪◦⁃∙·'
_DASHES = '‐‑‒–—―−'
_QUOTES = {'‘': "'", '’': "'", '“': '"', '”': '"', '´': "'"}


def clean_text(value: object) -> str:
    """NFKC, unify dashes/quotes/bullets, collapse horizontal whitespace."""
    if value is None:
        return ''
    text = unicodedata.normalize('NFKC', str(value))
    for src, dst in _QUOTES.items():
        text = text.replace(src, dst)
    for ch in _DASHES:
        text = text.replace(ch, '-')
    for ch in _BULLET_CHARS:
        text = text.replace(ch, ' ')
    text = text.replace(' ', ' ')
    return re.sub(r'[ \t]+', ' ', text).strip()


def norm(value: object) -> str:
    """Lowercased, punctuation-light single-line form used for comparisons."""
    text = clean_text(value).lower()
    text = re.sub(r'[^a-z0-9+#./&\- ]+', ' ', text)
    return re.sub(r'\s+', ' ', text).strip()


def tokens(value: object) -> set[str]:
    return {t for t in re.split(r'[^a-z0-9+#]+', norm(value)) if len(t) > 1 or t.isdigit()}


def token_set_f1(a: object, b: object) -> float:
    ta, tb = tokens(a), tokens(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    if not inter:
        return 0.0
    precision = inter / len(tb)
    recall = inter / len(ta)
    return 2 * precision * recall / (precision + recall)


def ratio(a: object, b: object) -> float:
    """Best of sequence similarity and token-set F1 - order insensitive."""
    na, nb = norm(a), norm(b)
    if not na and not nb:
        return 1.0
    if not na or not nb:
        return 0.0
    seq = difflib.SequenceMatcher(None, na, nb).ratio()
    return max(seq, token_set_f1(na, nb))


def containment(needle: object, haystack: object) -> float:
    """Fraction of ``needle`` tokens present in ``haystack``."""
    tn, th = tokens(needle), tokens(haystack)
    if not tn:
        return 1.0
    return len(tn & th) / len(tn)


# ------------------------------------------------------------------- identity

_NAME_NOISE = {
    'mr', 'mrs', 'ms', 'dr', 'resume', 'cv', 'curriculum', 'vitae', 'profile',
    'name', 'candidate',
}


def name_key(value: object) -> str:
    parts = [t for t in re.split(r'[^a-z]+', norm(value)) if t and t not in _NAME_NOISE]
    return ' '.join(parts)


def name_score(gold: object, pred: object) -> float:
    g, p = name_key(gold), name_key(pred)
    if not g or not p:
        return 0.0
    if g == p:
        return 1.0
    gt, pt = set(g.split()), set(p.split())
    if gt and pt and (gt <= pt or pt <= gt):
        # Middle name / surname present on one side only - still the same person.
        return 0.95
    return token_set_f1(g, p)


_EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')


def emails(value: object) -> set[str]:
    return {m.group(0).lower().rstrip('.') for m in _EMAIL_RE.finditer(clean_text(value))}


def phones(value: object) -> set[str]:
    """Last-10-digit keys for every phone-shaped run in ``value``."""
    out: set[str] = set()
    for run in re.findall(r'\d[\d\s\-().]{6,}\d', clean_text(value)):
        digits = re.sub(r'\D', '', run)
        # A run can concatenate two numbers when the separator was stripped.
        while len(digits) >= 10:
            out.add(digits[-10:])
            digits = digits[:-10]
    return out


_URL_STRIP = re.compile(r'^(https?://)?(www\.)?', re.I)


def url_key(value: object) -> str:
    text = clean_text(value).strip().strip('<>()[],;').rstrip('/')
    if not text:
        return ''
    text = _URL_STRIP.sub('', text).lower()
    text = text.split('?', 1)[0].split('#', 1)[0].rstrip('/')
    return text


def url_score(gold: object, pred: object) -> float:
    g, p = url_key(gold), url_key(pred)
    if not g or not p:
        return 0.0
    if g == p:
        return 1.0
    # linkedin.com/in/x vs in/x, or a trailing locale segment.
    gs = [s for s in g.split('/') if s]
    ps = [s for s in p.split('/') if s]
    if len(gs) > 1 or len(ps) > 1:
        # Profile URLs are identified by their handle: /in/alice != /in/bob,
        # however similar the surrounding path looks.
        return 0.95 if (gs and ps and gs[-1] == ps[-1]) else 0.0
    r = ratio(g, p)
    return r if r >= 0.9 else 0.0


# ------------------------------------------------------------------- location

# Region / country qualifiers. A city match is what matters; the state it sits
# in is noise on either side of the comparison.
_LOCATION_NOISE_TOKENS = {
    'india', 'bharat', 'maharashtra', 'telangana', 'karnataka', 'kerala', 'gujarat',
    'rajasthan', 'punjab', 'haryana', 'bengal', 'odisha', 'bihar', 'jharkhand',
    'assam', 'goa', 'uttarakhand', 'uttar', 'madhya', 'andhra', 'tamil', 'nadu',
    'pradesh', 'state', 'dist', 'district', 'pin', 'pincode', 'ncr', 'area',
}
_LOCATION_NOISE = re.compile(
    r'^(' + '|'.join(sorted(_LOCATION_NOISE_TOKENS)) + r'|west bengal|uttar pradesh)$'
)
_ADDRESS_NOISE = re.compile(
    r'\b(house|flat|plot|road|rd|street|nagar|compound|sector|near|opp|baugh)\b'
)


def location_key(value: object) -> str:
    text = norm(value)
    text = re.sub(r'\b\d{5,6}\b', ' ', text)
    text = re.sub(r'\bno\.?\s*\d+\b', ' ', text)
    return re.sub(r'\s+', ' ', text).strip(' ,-')


def location_parts(value: object) -> list[str]:
    key = location_key(value)
    parts = [p.strip() for p in re.split(r'[,/|]+', key) if p.strip()]
    keep = [p for p in parts if not _LOCATION_NOISE.match(p) and not _ADDRESS_NOISE.search(p)]
    return keep or parts


_DIRECTIONS = {'east', 'west', 'north', 'south'}


def _place_tokens(value: object) -> set[str]:
    raw = {t for part in location_parts(value) for t in part.split()}
    raw -= _DIRECTIONS
    stripped = raw - _LOCATION_NOISE_TOKENS
    # "Maharashtra" alone is still a location; only drop qualifiers that had a
    # city to qualify.
    return stripped or raw


def location_score(gold: object, pred: object) -> float:
    gp, pp = location_parts(gold), location_parts(pred)
    if not gp or not pp:
        return 0.0
    gset, pset = _place_tokens(gold), _place_tokens(pred)
    if not gset:
        return 1.0 if not pset else 0.0
    overlap = len(gset & pset) / len(gset)
    if overlap >= 0.99:
        return 1.0
    # A city named in gold appearing anywhere in the prediction still counts.
    if gset & pset:
        return max(overlap, 0.75)
    return 0.0


# ---------------------------------------------------------------------- level

_LEVEL_WORDS = (
    ('intern', 'intern'),
    ('entry level', 'intern'),
    ('entry', 'intern'),
    ('trainee', 'intern'),
    ('fresher', 'fresher'),
    ('fresh', 'fresher'),
    ('graduate', 'fresher'),
    ('experienced', 'experienced'),
    ('experience', 'experienced'),
    ('professional', 'experienced'),
    ('senior', 'experienced'),
    ('mid', 'experienced'),
)


def level_key(value: object) -> str:
    text = norm(value)
    if not text:
        return ''
    for word, mapped in _LEVEL_WORDS:
        if re.search(rf'\b{re.escape(word)}\b', text):
            return mapped
    return text


def level_score(gold: object, pred: object) -> float:
    g, p = level_key(gold), level_key(pred)
    if not g or not p:
        return 0.0
    if g == p:
        return 1.0
    # intern and fresher are adjacent buckets; both mean "not experienced".
    if {g, p} == {'intern', 'fresher'}:
        return 0.5
    return 0.0


# --------------------------------------------------------------------- skills

_SKILL_ALIAS = {
    'js': 'javascript',
    'node': 'nodejs',
    'node.js': 'nodejs',
    'reactjs': 'react',
    'react.js': 'react',
    'postgres': 'postgresql',
    'ms sql': 'mssql',
    'sql server': 'mssql',
    'oracle sql': 'oracle',
    'pl/sql': 'plsql',
    'pl sql': 'plsql',
    'ms excel': 'excel',
    'ms office': 'msoffice',
    'golang': 'go',
    'c++': 'cpp',
    'c#': 'csharp',
    'dot net': 'dotnet',
    '.net': 'dotnet',
    'k8s': 'kubernetes',
    'ci/cd': 'cicd',
}

_SKILL_LABEL_PREFIX = re.compile(
    r'^\s*(programming language|language|database|tools?|technolog(?:y|ies)|skills?|'
    r'operating system|os|framework|platform|cloud|soft skills?|technical skills?)s?'
    r'\s*[:\-]\s*',
    re.I,
)


# Words that only ever appear in a skills-section heading. A piece made up
# entirely of these is a category label the spreadsheet author kept, not a skill
# the parser should reproduce.
_SKILL_HEADER_WORDS = frozenset({
    'technical', 'technicals', 'core', 'key', 'other', 'others', 'additional',
    'professional', 'programming', 'web', 'scripting', 'script', 'gui', 'ide',
    'cloud', 'data', 'base', 'database', 'databases', 'language', 'languages',
    'tool', 'tools', 'technology', 'technologies', 'framework', 'frameworks',
    'library', 'libraries', 'skill', 'skills', 'operating', 'system', 'systems',
    'platform', 'platforms', 'environment', 'environments', 'expertise',
    'competency', 'competencies', 'soft', 'misc', 'miscellaneous', 'area', 'areas',
    'summary', 'and', 'of', 'the',
})


def is_skill_category_header(value: object) -> bool:
    words = [w for w in norm(value).replace('&', ' ').split() if w]
    return bool(words) and all(w in _SKILL_HEADER_WORDS for w in words)


def skill_key(value: object) -> str:
    text = norm(value).strip(' .;')
    text = re.sub(r'\s+', ' ', text)
    if text in _SKILL_ALIAS:
        return _SKILL_ALIAS[text]
    collapsed = text.replace(' ', '')
    return _SKILL_ALIAS.get(collapsed, text)


def split_skills(value: object, *, drop_headers: bool = False) -> list[str]:
    """Split a free-form skills cell or string into normalized skill keys.

    ``drop_headers`` removes category labels ("TECHNICAL SKILLS", "FRAMEWORKS").
    It is applied to the spreadsheet side only: a heading the author kept is
    benchmark noise, whereas a heading the parser emits as a skill is a real
    precision defect and must stay visible.
    """
    if value is None:
        return []
    if isinstance(value, (list, tuple, set)):
        raw_parts = [str(v) for v in value]
    else:
        raw_parts = re.split(r'[\n;|]+', clean_text(value))
    out: list[str] = []
    seen: set[str] = set()
    for part in raw_parts:
        part = _SKILL_LABEL_PREFIX.sub('', part)
        # A label may still be glued mid-line: "DATABASE: Oracle 12c".
        if ':' in part and len(part.split(':', 1)[0].split()) <= 3:
            part = part.split(':', 1)[1]
        for piece in re.split(r'[,/]+', part):
            if drop_headers and is_skill_category_header(piece):
                continue
            key = skill_key(piece)
            if not key or len(key) < 2 or key.isdigit() or key in seen:
                continue
            seen.add(key)
            out.append(key)
    return out


def _skill_matches(gold_skill: str, pred_skills: set[str]) -> bool:
    if gold_skill in pred_skills:
        return True
    gt = set(gold_skill.split())
    for pred in pred_skills:
        if gold_skill in pred or pred in gold_skill:
            return True
        pt = set(pred.split())
        if gt and pt and (gt <= pt or pt <= gt):
            return True
        if len(gold_skill) > 5 and difflib.SequenceMatcher(None, gold_skill, pred).ratio() >= 0.9:
            return True
    return False


def skills_prf(gold: object, pred: object) -> tuple[float, float, float, list[str], list[str]]:
    """Return ``(precision, recall, f1, missed_gold, extra_pred)``."""
    gold_list = split_skills(gold, drop_headers=True)
    pred_list = split_skills(pred)
    gold_set, pred_set = set(gold_list), set(pred_list)
    if not gold_set and not pred_set:
        return 1.0, 1.0, 1.0, [], []
    if not gold_set or not pred_set:
        return 0.0, 0.0, 0.0, gold_list, pred_list
    missed = [g for g in gold_list if not _skill_matches(g, pred_set)]
    extra = [p for p in pred_list if not _skill_matches(p, gold_set)]
    recall = 1 - len(missed) / len(gold_list)
    precision = 1 - len(extra) / len(pred_list)
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0
    return precision, recall, f1, missed, extra


# ----------------------------------------------------------------------- date

_MONTHS = {
    'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
    'jul': 7, 'aug': 8, 'sep': 9, 'sept': 9, 'oct': 10, 'nov': 11, 'dec': 12,
}
_PRESENT = re.compile(r'\b(present|current|till date|to date|now|ongoing)\b', re.I)


def year_tokens(value: object) -> set[str]:
    """Four-digit years plus two-digit years in ``'09`` / ``Feb'14`` form."""
    text = clean_text(value)
    out = set(re.findall(r'\b(?:19[7-9]\d|20[0-4]\d)\b', text))
    for two in re.findall(r"'(\d{2})\b", text):
        out.add(('19' if int(two) > 50 else '20') + two)
    return out


def month_key(value: object) -> str:
    """Best-effort ``YYYY-MM`` (or ``YYYY``) key for a date-ish string."""
    text = clean_text(value)
    if not text:
        return ''
    if _PRESENT.search(text):
        return 'present'
    iso = re.search(r'\b((?:19|20)\d{2})-(\d{1,2})\b', text)
    if iso:
        return f'{iso.group(1)}-{int(iso.group(2)):02d}'
    slash = re.search(r'\b(\d{1,2})[/\-]((?:19|20)\d{2})\b', text)
    if slash:
        return f'{slash.group(2)}-{int(slash.group(1)):02d}'
    named = re.search(r"\b([a-z]{3,4})[a-z]*\.?\s*['’]?\s*((?:19|20)?\d{2})\b", text, re.I)
    if named and named.group(1)[:3].lower() in _MONTHS:
        year = named.group(2)
        if len(year) == 2:
            year = ('19' if int(year) > 50 else '20') + year
        return f'{year}-{_MONTHS[named.group(1)[:3].lower()]:02d}'
    year = re.search(r'\b(?:19[7-9]\d|20[0-4]\d)\b', text)
    return year.group(0) if year else ''
