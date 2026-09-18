"""Turn the human-authored spreadsheet cells into machine-comparable gold.

The Education / Experience / Certifications cells are free text written by a
recruiter in a loose ``Education 1: ...`` convention. This module splits them
into entries and, for each entry, the set of *facts* a parser must recover.

Facts - not rows - are the primary unit of scoring. Human authors split one
degree across two numbered entries, merge a company and role onto one line, and
occasionally paste the wrong cell entirely. Row-by-row alignment would punish a
correct parser for those; fact recall does not.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from . import normalize as nz

# ``Education 1:``, ``Experience 2:-``, ``Certification 3 -`` anywhere in the cell.
_ENTRY_SPLIT = re.compile(
    r'(?:^|\s)(Education|Experience|Certification|Certifications|Project)\s*(\d+)\s*(?::-|:|-)\s*',
    re.I,
)

_INSTITUTION_HINT = re.compile(
    r'\b(college|university|institute|institution|school|academy|vidyalaya|vidyapeeth|'
    r'polytechnic|iit|nit|bits|junior college|jr\.? college|board)\b',
    re.I,
)
_DEGREE_HINT = re.compile(
    r'\b(b\.?\s?e|b\.?\s?tech|b\.?\s?sc|b\.?\s?com|b\.?\s?a|b\.?\s?c\.?\s?a|bba|bms|'
    r'm\.?\s?e|m\.?\s?tech|m\.?\s?sc|m\.?\s?com|m\.?\s?a|m\.?\s?c\.?\s?a|mba|ms|phd|'
    r'diploma|bachelor|master|doctor|hsc|ssc|12th|10th|intermediate|graduation|'
    r'post ?graduat|engineering|secondary)\b',
    re.I,
)
_COMPANY_HINT = re.compile(
    r'\b(ltd|limited|pvt|private|inc|llp|llc|technologies|technology|solutions|systems|'
    r'services|software|consultancy|consulting|infotech|labs|corp|corporation|group|bank|'
    r'industries|enterprises|global)\b',
    re.I,
)
_ROLE_HINT = re.compile(
    r'\b(engineer|developer|analyst|manager|consultant|administrator|admin|lead|architect|'
    r'specialist|executive|associate|intern|trainee|officer|designer|scientist|tester|'
    r'strategist|recruiter|dba|support|coordinator|assistant|director|head|president|'
    r'programmer|technician)\b',
    re.I,
)
_LABEL = re.compile(r'^\s*(company|role|designation|organisation|organization|employer|'
                    r'position|title|institute|institution|college|university|degree|'
                    r'course|issuer|issued by)\s*[:\-]\s*', re.I)
_DATE_RANGE = re.compile(
    r"((?:\d{1,2}[/\-])?(?:19|20)\d{2}|[a-z]{3,9}\.?\s*['’]?\s*(?:19|20)?\d{2})"
    r"\s*(?:-|to|till|until)\s*"
    r"((?:\d{1,2}[/\-])?(?:19|20)\d{2}|[a-z]{3,9}\.?\s*['’]?\s*(?:19|20)?\d{2}|"
    r"present|current|till date|to date|now)",
    re.I,
)
_FROM_ISSUER = re.compile(r'\bfrom\s+([^.(\n]{2,60})', re.I)
_BULLET_LINE = re.compile(r'^\s*(role\s*&\s*responsibilit|responsibilit|key result|duties)', re.I)

_NOISE_PREFIX = re.compile(r'^\s*[\-•o]\s*')


@dataclass
class GoldEntry:
    """One numbered block inside a section cell."""

    index: int
    raw: str
    primary: str = ''
    """Best guess at the headline value (degree / role / certificate name)."""

    secondary: str = ''
    """Best guess at the counterpart (institution / company / issuer)."""

    start: str = ''
    end: str = ''
    facts: list[str] = field(default_factory=list)
    """Normalized strings the parser must surface somewhere in this section."""

    years: set[str] = field(default_factory=set)

    def to_dict(self) -> dict:
        return {
            'index': self.index,
            'raw': self.raw,
            'primary': self.primary,
            'secondary': self.secondary,
            'start': self.start,
            'end': self.end,
            'facts': self.facts,
            'years': sorted(self.years),
        }


def _clean_line(line: str) -> str:
    return _NOISE_PREFIX.sub('', nz.clean_text(line)).strip(' .,;:-')


def _split_entries(cell: object) -> list[tuple[int, str]]:
    """Split a section cell into ``(index, block_text)`` pairs."""
    text = nz.clean_text(cell)
    if not text:
        return []
    matches = list(_ENTRY_SPLIT.finditer(text))
    if not matches:
        return [(1, text)]
    blocks: list[tuple[int, str]] = []
    preamble = text[: matches[0].start()].strip()
    if len(preamble) > 25:
        blocks.append((0, preamble))
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[m.end():end].strip()
        if body:
            blocks.append((int(m.group(2)), body))
    return blocks


def _informative_lines(block: str) -> list[str]:
    """Lines worth treating as entity text - drops bullet prose."""
    out: list[str] = []
    for raw_line in block.splitlines():
        line = _clean_line(raw_line)
        if not line or len(line) < 3:
            continue
        if _BULLET_LINE.match(line):
            continue
        # Long sentences are achievement prose, not entity names.
        if len(line.split()) > 18:
            continue
        out.append(_LABEL.sub('', line))
    return out


def _dates(block: str) -> tuple[str, str]:
    m = _DATE_RANGE.search(block)
    if m:
        return nz.month_key(m.group(1)), nz.month_key(m.group(2))
    single = nz.month_key(block)
    return (single, '') if single else ('', '')


def _score_lines(lines: list[str], hint: re.Pattern[str]) -> list[tuple[float, str]]:
    return sorted(
        ((1.0 if hint.search(ln) else 0.0, ln) for ln in lines),
        key=lambda pair: -pair[0],
    )


_DATE_ONLY = re.compile(
    r"^[\s\-/,.()]*(?:(?:\d{1,2}[/\-])?(?:19|20)?\d{2}|[a-z]{3,9}\.?\s*['’]?\s*(?:19|20)?\d{2}|"
    r"present|current|till date|to date|now|-|to|till|since|duration|cgpa|gpa|percentage|"
    r"\d+(?:\.\d+)?%?)[\s\-/,.()]*$",
    re.I,
)


def _is_date_only(line: str) -> bool:
    stripped = re.sub(r'\b(19[7-9]\d|20[0-4]\d)\b', ' ', line)
    stripped = re.sub(r'[\s\-/,.()–]+', ' ', stripped).strip()
    if not stripped:
        return True
    if _DATE_ONLY.match(line.strip()):
        return True
    words = [w for w in stripped.lower().split() if w]
    date_words = {
        'jan', 'feb', 'mar', 'apr', 'may', 'jun', 'jul', 'aug', 'sep', 'sept', 'oct',
        'nov', 'dec', 'january', 'february', 'march', 'april', 'june', 'july', 'august',
        'september', 'october', 'november', 'december', 'present', 'current', 'till',
        'date', 'to', 'now', 'since', 'cgpa', 'gpa', 'percentage',
    }
    return bool(words) and all(w.strip('.-') in date_words or w.isdigit() for w in words)


_MONTH_WORD = (
    r'jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|jul(?:y)?|'
    r'aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?'
)
_DATE_TAIL = re.compile(
    rf'[\s.,\-]*(?:\b(?:{_MONTH_WORD})\b|\bto\b|\btill\b|\buntil\b|\bnow\b|\bpresent\b|'
    r'\bcurrent\b|\bdate\b|\bsince\b|\bfrom\b|\bin\b|\bon\b|\bat\b|[\d\-/.]+)+$',
    re.I,
)
_ROLE_PROSE = re.compile(
    r'^\s*(?:working|worked|serving|served|currently working)\s+(?:as\s+)?(?:a|an|the)?\s*',
    re.I,
)
_ROLE_TAIL = re.compile(
    r'\s+(?:responsible|responsibl\w*|handling|involved|managing|reporting|where|who)\b.*$',
    re.I,
)


def _clean_fact(key: str) -> str:
    """Trim date tails and prose wrappers so a fact is just the entity name."""
    key = _ROLE_PROSE.sub('', key)
    key = _ROLE_TAIL.sub('', key)
    key = re.sub(r'\b(19[7-9]\d|20[0-4]\d)\b', ' ', key)
    key = re.sub(r'\s+', ' ', key).strip(' .,-')
    previous = None
    while previous != key:
        previous = key
        key = _DATE_TAIL.sub('', key).strip(' .,-')
    return key


def _entity_facts(lines: list[str], limit: int = 4) -> list[str]:
    """Normalized, de-duplicated entity strings from a block."""
    facts: list[str] = []
    seen: set[str] = set()
    for line in lines:
        if _is_date_only(line):
            continue
        # Split "Company | Role" / "Company, Role" style one-liners too.
        for piece in re.split(r'\s*[|]\s*', line):
            key = _clean_fact(nz.norm(piece).strip())
            if len(key) < 3 or key in seen or key.isdigit():
                continue
            seen.add(key)
            facts.append(key)
            if len(facts) >= limit:
                return facts
    return facts


def parse_education(cell: object) -> list[GoldEntry]:
    entries: list[GoldEntry] = []
    for index, block in _split_entries(cell):
        lines = _informative_lines(block)
        if not lines:
            continue
        degrees = [ln for ln in lines if _DEGREE_HINT.search(ln)]
        institutions = [ln for ln in lines if _INSTITUTION_HINT.search(ln)]
        start, end = _dates(block)
        # Degree and institution lines are what the form rows must carry; other
        # lines only fill in when neither hint fired.
        preferred = degrees + [i for i in institutions if i not in degrees]
        entry = GoldEntry(
            index=index,
            raw=block,
            primary=degrees[0] if degrees else (lines[0] if lines else ''),
            secondary=next((i for i in institutions if i not in degrees[:1]), ''),
            start=start,
            end=end,
            facts=_entity_facts(preferred or lines[:2]),
            years=nz.year_tokens(block),
        )
        entries.append(entry)
    return entries


def parse_experience(cell: object) -> list[GoldEntry]:
    entries: list[GoldEntry] = []
    for index, block in _split_entries(cell):
        lines = _informative_lines(block)
        if not lines:
            continue
        # A headline often packs role + company + dates onto one line.
        head_parts = [p for p in re.split(r'\s*[,|]\s*', lines[0]) if p.strip()]
        candidates = head_parts + lines[:3]
        roles = [ln for ln in candidates if _ROLE_HINT.search(ln) and len(ln.split()) <= 10]
        companies = [ln for ln in candidates if _COMPANY_HINT.search(ln)]
        start, end = _dates(block)
        # Company and role text are what the form rows must carry; the first
        # line is the fallback when neither hint fires.
        preferred = companies + [r for r in roles if r not in companies]
        entry = GoldEntry(
            index=index,
            raw=block,
            primary=roles[0] if roles else lines[0],
            secondary=next((c for c in companies if c not in roles[:1]), ''),
            start=start,
            end=end,
            facts=_entity_facts(preferred or lines[:2]),
            years=nz.year_tokens(block),
        )
        entries.append(entry)
    return entries


def parse_certifications(cell: object) -> list[GoldEntry]:
    entries: list[GoldEntry] = []
    for index, block in _split_entries(cell):
        text = nz.clean_text(block)
        if len(text) < 3:
            continue
        issuer_match = _FROM_ISSUER.search(text)
        issuer = _clean_line(issuer_match.group(1)) if issuer_match else ''
        name = text[: issuer_match.start()] if issuer_match else text
        name = _clean_line(re.sub(r'\([^)]*\)', ' ', name))
        entry = GoldEntry(
            index=index,
            raw=text,
            primary=name,
            secondary=issuer,
            start='',
            end=nz.month_key(text),
            facts=[f for f in (nz.norm(name), nz.norm(issuer)) if len(f) >= 3],
            years=nz.year_tokens(text),
        )
        entries.append(entry)
    return entries


SECTION_PARSERS = {
    'education': parse_education,
    'experiences': parse_experience,
    'certifications': parse_certifications,
}


def parse_section(section_key: str, cell: object) -> list[GoldEntry]:
    parser = SECTION_PARSERS.get(section_key)
    return parser(cell) if parser else []


# ------------------------------------------------------------- gold sanity QA

_SUSPECT_LOCATION = re.compile(
    r'\b(migration|installation|upgrad|administration|support|developer|engineer|sql|'
    r'oracle|database)\b',
    re.I,
)


def audit_row(row: dict) -> list[str]:
    """Flag cells that look mis-authored so the benchmark itself can be fixed.

    A benchmark is only as good as its gold. These warnings surface in the
    corpus manifest and in the scorecard so bad cells get corrected rather than
    silently capping the achievable score.
    """
    issues: list[str] = []
    email = row.get('Email')
    if email and not nz.emails(email):
        issues.append(f'email_unparseable: {email!r}')
    phone = row.get('Phone')
    if phone and not nz.phones(phone):
        issues.append(f'phone_unparseable: {phone!r}')
    loc = row.get('Current location')
    if loc and _SUSPECT_LOCATION.search(str(loc)):
        issues.append(f'location_looks_like_skills: {str(loc)[:60]!r}')
    if loc and len(str(loc)) > 60:
        issues.append('location_is_full_address')
    for col, key in (('Education', 'education'), ('Experience', 'experiences'),
                     ('Certifications', 'certifications')):
        cell = row.get(col)
        if cell and not parse_section(key, cell):
            issues.append(f'{key}_cell_unparseable')
    for col in ('LinkedIn URL', 'Portfolio', 'GitHub URL'):
        val = row.get(col)
        if val and not nz.url_key(val):
            issues.append(f'{col}_unparseable')
    if row.get('GitHub URL') and 'github' not in str(row['GitHub URL']).lower():
        issues.append('github_url_not_github')
    if row.get('LinkedIn URL') and 'linkedin' not in str(row['LinkedIn URL']).lower():
        issues.append('linkedin_url_not_linkedin')
    return issues
