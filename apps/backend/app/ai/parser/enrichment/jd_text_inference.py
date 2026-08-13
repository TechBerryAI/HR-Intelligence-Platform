"""
Extract JD TOON fields from unstructured job description text.
Shared by the parse pipeline and synthetic TOON builders (ATS fallback).
"""
from __future__ import annotations

import re
from typing import Any

# Headings that mean a real Key Responsibilities / duties section exists in the JD.
RESPONSIBILITY_HEADING_RE = (
    r'(?:key\s+)?responsibilities|duties|key\s+accountabilit(?:y|ies)|'
    r'what\s+you(?:\'|’)?ll\s+do|what\s+you\s+will\s+do|'
    r'in\s+this\s+role\s+you\s+will|you\s+will|'
    r'your\s+role|role\s+responsibilities|day[- ]to[- ]day|'
    r'responsibilities\s*(?:&|and)\s*duties'
)


def _has_list_marker(text: str) -> bool:
    """True when a line starts with a bullet/number/letter list marker."""
    s = str(text or '').strip()
    if not s:
        return False
    return bool(
        re.match(
            r'^(?:[\s]*(?:\*\*|__)?[\s]*)'
            r'(?:[•·▪▫▸►●○◆◇■□–—\-*\u2022\u2023\u25E6\u2043\u2219]+|'
            r'\d+[\.\)]|[a-zA-Z][\.\)])'
            r'[\s]+',
            s,
        )
        or re.match(r'^[\s•·\-–—*]+.', s)
        # PDF letter-bullet without punctuation: "o Proficiency…"
        or re.match(r'^[oO]\s+[A-Z]', s)
    )


def _strip_list_marker(text: str) -> str:
    """Remove JD bullet/number markers; keep the sentence text only."""
    cleaned = str(text or '').strip()
    if not cleaned:
        return ''
    # Leading bullets / dashes / arrows (including markdown **, and unicode)
    cleaned = re.sub(
        r'^(?:[\s]*(?:\*\*|__)?[\s]*)'
        r'(?:[•·▪▫▸►●○◆◇■□–—\-*\u2022\u2023\u25E6\u2043\u2219]+|'
        r'\d+[\.\)]|[a-zA-Z][\.\)])'
        r'[\s]+',
        '',
        cleaned,
    )
    cleaned = re.sub(r'^[\s•·\-–—*]+', '', cleaned).strip()
    cleaned = re.sub(r'^\d+[\.\)]\s*', '', cleaned).strip()
    # PDF letter-bullets without punctuation: "o Proficiency in Figma…"
    cleaned = re.sub(r'^[oO]\s+(?=[A-Z])', '', cleaned).strip()
    # Trailing markdown bold leftovers
    cleaned = cleaned.strip('*').strip()
    return cleaned.strip()


def strip_source_bullets_to_prose(text: str) -> str:
    """Ignore source JD bullets; return plain sentences for the Description overview."""
    if not text or not str(text).strip():
        return ''
    lines: list[str] = []
    for raw in str(text).replace('\r\n', '\n').split('\n'):
        if not raw.strip():
            if lines and lines[-1] != '':
                lines.append('')
            continue
        cleaned = _strip_list_marker(raw)
        if cleaned:
            lines.append(cleaned)
    # Collapse runs of blank lines; keep paragraph breaks
    prose = re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()
    return prose


def has_responsibilities_section(text: str) -> bool:
    """True only when the JD explicitly has a responsibilities / duties section."""
    if not text or not str(text).strip():
        return False
    desc = str(text)
    if re.search(rf'(?i)(?:^|\n)\s*(?:\*\*)?(?:{RESPONSIBILITY_HEADING_RE})(?:\*\*)?\s*:?\s*(?:\n|$)', desc):
        return True
    if re.search(rf'(?i)(?:\*\*)?(?:{RESPONSIBILITY_HEADING_RE})(?:\*\*)?\s*:', desc):
        return True
    return False


def _merge_softwrapped_lines(lines: list[str]) -> list[str]:
    """Join PDF soft-wrap continuations; keep true bullet/number items separate."""
    merged: list[str] = []
    for raw in lines:
        line = (raw or '').strip()
        if not line:
            continue
        if not merged:
            merged.append(line)
            continue
        prev = merged[-1]
        # New list item always starts a new entry
        if _has_list_marker(line):
            merged.append(line)
            continue
        prev_clean = _strip_list_marker(prev)
        # Previous ended a sentence → new item/paragraph
        if re.search(r'[.!?…]["\')\]]*\s*$', prev_clean):
            merged.append(line)
            continue
        first = line.lstrip()[:1]
        # Soft wrap: continuation starts lowercase, or previous ends mid-clause
        if (
            (first and first.islower())
            or prev_clean.endswith((',', ';', ':', '-', '–', '—', '/', '&'))
        ):
            if prev.rstrip().endswith('-') and not prev.rstrip().endswith(('--', '–', '—')):
                merged[-1] = prev.rstrip()[:-1] + line.lstrip()
            else:
                merged[-1] = f'{prev.rstrip()} {line.lstrip()}'
        else:
            merged.append(line)
    return merged


def _split_list_items(text: str) -> list[str]:
    """Split bullet/pipe/newline-separated prose into items. Never split on commas.

    Soft-wrapped PDF lines are merged. True list markers stay separate items.
    Strips source bullet markers so callers can rebuild clean • bullets.
    """
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    if '|' in raw and '\n' not in raw:
        parts = [p.strip() for p in raw.split('|')]
    else:
        parts = _merge_softwrapped_lines([p for p in re.split(r'\n+', raw) if p.strip()])
    result: list[str] = []
    for part in parts:
        cleaned = _strip_list_marker(part)
        if cleaned and len(cleaned) > 2:
            result.append(cleaned[:500])
    return result


_SKILL_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:required\s+|core\s+|mandatory\s+|technical\s+|primary\s+|key\s+|must[- ]?have\s+)?'
    r'(?:skills?(?:\s*(?:&|and)\s*experience)?|tech\s*stack)(?:\*\*)?\s*:?\s*$'
)
_SKILL_INLINE_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:required\s+|core\s+|mandatory\s+|technical\s+|primary\s+|key\s+|must[- ]?have\s+)?'
    r'(?:skills?(?:\s*(?:&|and)\s*experience)?|tech\s*stack)(?:\*\*)?\s*[:\-][ \t]*(.+)$'
)
_SKILL_STOP_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:responsibilities|duties|qualifications|requirements|benefits|preferred|'
    r'about|experience|education|employment|location|salary|compensation|what\s+we|'
    r'nice[- ]?to[- ]?have|must\s+haves?|key\s+responsibilities|bonus\s+points?|'
    r'soft\s+skills?|candidate\s+profile)(?:\*\*)?\s*:?\s*$'
)
_PREF_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:preferred\s+(?:skills?|qualifications?)|nice[- ]?to[- ]?have(?:\s+skills?)?|'
    r'advanced\s+skills?|bonus\s+(?:points?|skills?)|good\s+to\s+have)(?:\*\*)?\s*:?\s*$'
)
_PREF_INLINE_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:preferred\s+(?:skills?|qualifications?)|nice[- ]?to[- ]?have(?:\s+skills?)?|'
    r'advanced\s+skills?|bonus\s+(?:points?|skills?)|good\s+to\s+have)(?:\*\*)?\s*[:\-][ \t]*(.+)$'
)
_QUAL_SKILL_NOISE_RE = re.compile(
    r'(?i)^(qualification|education|bachelor|master|degree|b\.?tech|b\.?e\.?|m\.?c\.?a|'
    r'b\.?c\.?a|b\.?sc|mba|phd|preferred\s*skills?|preferred\s*qualifications?|'
    r'required\s*skills?|mandatory\s*skills?|technical\s*skills?|primary\s*skills?|'
    r'educational\s*qualifications?|bonus\s*points?|experience\s*level|'
    r'soft\s*skills?(?:\s*&\s*competencies)?|preferred\s*candidate\s*profile|'
    r'nice[- ]?to[- ]?have|good\s*to\s*have|or\s+related\s+field)\b'
)
_SKILL_PROSE_NOISE_RE = re.compile(
    r'(?i)^(we\s|our\s|looking|seeking|join\s|the\s+candidate|you\s+will|'
    r'ability\s+to|responsible\s+for|must\s+be\s+able)\b'
)
_SKILL_GARBAGE_TOKENS = frozenset({
    'job', 'jd', 'role', 'position', 'title', 'location', 'experience', 'salary',
    'company', 'notice', 'period', 'education', 'qualification', 'requirements',
    'responsibilities', 'skills', 'none', 'n/a', 'na', 'tbd', 'etc',
})
_SOFT_SKILL_ONLY_RE = re.compile(
    r'(?i)^(excellent|strong|good|effective|outstanding)\s+'
    r'(communication|collaboration|interpersonal|problem[- ]solving|critical\s+thinking|'
    r'teamwork|leadership|analytical)\b|'
    r'^(communication|collaboration|interpersonal|problem[- ]solving|critical\s+thinking|'
    r'teamwork|leadership)\s+(skills?|abilities)\b'
)
_KNOWN_CITIES = (
    'mumbai', 'navi mumbai', 'pune', 'bengaluru', 'bangalore', 'chennai', 'hyderabad',
    'delhi', 'new delhi', 'noida', 'gurgaon', 'gurugram', 'kolkata', 'ahmedabad',
    'jaipur', 'chandigarh', 'kochi', 'thiruvananthapuram', 'indore', 'bhopal',
    'lucknow', 'coimbatore', 'nagpur', 'vikhroli', 'andheri', 'airoli', 'powai',
    'whitefield', 'electronic city', 'remote', 'hybrid', 'wfh', 'work from home',
)
# Section headers / filler that must never become skills (ATS matching safety)
_JD_SKILL_DENYLIST = frozenset({
    'preferred qualifications', 'preferred qualification', 'preferred skills',
    'preferred skill', 'required skills', 'required skill', 'mandatory skills',
    'technical skills', 'primary skills', 'core skills', 'key skills',
    'bonus points', 'bonus point', 'experience level', 'soft skills',
    'soft skills & competencies', 'preferred candidate profile', 'candidate profile',
    'qualifications', 'requirements', 'responsibilities', 'nice to have',
    'nice-to-have', 'good to have', 'or related field', 'related field',
    'plus', 'and', 'for', 'the', 'with', 'from', 'into', 'onto', 'over',
    'under', 'management', 'leadership', 'communication', 'teamwork',
    'public', 'job', 'jobs', 'role', 'roles', 'etc', 'etc.', 'n/a', 'na',
    'none', 'other', 'others', 'various', 'including', 'such as',
    'years of experience', 'years experience', 'work experience',
    'information technology', 'computer science',
})
_BANNER_ACRONYMS = frozenset({
    'PUBLIC', 'JOB', 'JOBS', 'ROLE', 'ROLES', 'TEAM', 'OPEN', 'APPLY',
    'HIRING', 'CAREER', 'CAREERS', 'EQUAL', 'EOE',
})
_CONNECTOR_WORDS = frozenset({
    'plus', 'and', 'or', 'for', 'the', 'with', 'from', 'into', 'onto',
    'over', 'under', 'a', 'an', 'to', 'of', 'in', 'on', 'at', 'by',
    'is', 'as', 'also', 'well',
})


def _split_skill_list_preserving_parens(text: str) -> list[str]:
    """Split comma/pipe lists without breaking 'AWS (EC2, EKS, VPC)'."""
    parts: list[str] = []
    buf: list[str] = []
    depth = 0
    for ch in text or '':
        if ch == '(':
            depth += 1
            buf.append(ch)
        elif ch == ')':
            depth = max(0, depth - 1)
            buf.append(ch)
        elif ch in ',|•·' and depth == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)
    tail = ''.join(buf).strip()
    if tail:
        parts.append(tail)
    return parts or ([text.strip()] if (text or '').strip() else [])


def _expand_parenthetical_skill(tok: str) -> list[str]:
    """'AWS (EC2, EKS, VPC)' → ['AWS', 'EC2', 'EKS', 'VPC']."""
    raw = (tok or '').strip()
    match = re.match(r'^(.{1,40}?)\s*\(([^()]{2,80})\)\s*$', raw)
    if not match:
        return [raw] if raw else []
    outer, inner = match.group(1).strip(), match.group(2).strip()
    if not outer or len(outer.split()) > 3:
        return [raw]
    inner_parts = [p.strip() for p in re.split(r'[,/|]', inner) if p.strip()]
    if len(inner_parts) < 2:
        return [raw]
    return [outer, *inner_parts]


def _looks_like_skill_token_list(line: str) -> bool:
    """True when a comma/pipe line is a short skill list, not prose."""
    text = (line or '').strip()
    if not text or len(text) > 100:
        return False
    if re.search(r'(?i)\b(?:is|are|was|were|have|has|will|should|must|looking|seeking)\b', text):
        if len(text.split()) >= 5:
            return False
    parts = _split_skill_list_preserving_parens(text)
    if len(parts) < 2:
        return False
    short = sum(1 for p in parts if len(p.split()) <= 4 and len(p) <= 40)
    return short >= max(2, int(0.7 * len(parts)))


def _is_skill_section_phrase(tok: str, *, from_skill_section: bool) -> bool:
    """Allow short skill phrases from a skills block; reject prose elsewhere."""
    if not tok:
        return False
    words = tok.split()
    lower = tok.lower().strip()
    if lower in _JD_SKILL_DENYLIST or lower in _CONNECTOR_WORDS:
        return False
    if tok.upper() in _BANNER_ACRONYMS:
        return False
    if words and words[-1].lower() in {'for', 'with', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by'}:
        return False
    if from_skill_section:
        if len(tok) > 80 or len(words) > 8:
            return False
        if _SKILL_PROSE_NOISE_RE.match(tok):
            return False
        if _QUAL_SKILL_NOISE_RE.match(tok):
            return False
        return True
    return is_plausible_keyword(tok)


def normalize_skill_tokens(
    items: list[str] | None,
    *,
    max_items: int = 40,
    from_skill_section: bool = False,
) -> list[str]:
    """Keep short skill/tech tokens; keep skill-section phrases up to ~8 words.

    Long skill-section sentences yield embedded tech tokens instead of being dropped.
    """
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _add(tok: str) -> bool:
        t = (tok or '').strip().strip('.,;:|')
        t = re.sub(r'^[\s•·▪▫●○\-\*]+', '', t).strip()
        t = re.sub(r'^[oO]\s+(?=[A-Z])', '', t).strip()
        t = re.sub(r'(?i)\s*(?:is\s+)?(?:a\s+)?plus\.?$', '', t).strip()
        t = re.sub(r'^[\(\)\[\]]+|[\(\)\[\]]+$', '', t).strip()
        if not t:
            return False
        key = t.lower()
        if key in seen:
            return False
        if key in _SKILL_GARBAGE_TOKENS or key in _JD_SKILL_DENYLIST or key in _CONNECTOR_WORDS:
            return False
        if t.upper() in _BANNER_ACRONYMS:
            return False
        if len(key) <= 2 and key.isalpha():
            return False
        if not _is_skill_section_phrase(t, from_skill_section=from_skill_section):
            return False
        if _QUAL_SKILL_NOISE_RE.match(t) or t.lower().startswith('qualification'):
            return False
        seen.add(key)
        out.append(t[:80])
        return len(out) >= max_items

    for raw in items:
        if not raw or not str(raw).strip():
            continue
        item = _strip_list_marker(str(raw))
        item = re.sub(r'^[\s•·▪▫●○\-\*]+', '', item).strip()
        if not item:
            continue
        if item.lower() in _SKILL_GARBAGE_TOKENS:
            continue
        if _QUAL_SKILL_NOISE_RE.match(item) or item.lower().startswith('qualification'):
            continue
        if _SKILL_PROSE_NOISE_RE.match(item):
            # Still try to salvage tech tokens from the sentence
            for tok in extract_tech_keywords_from_text(item, max_items=8):
                if _add(tok):
                    return out
            continue

        parts = [item]
        if (',' in item or '|' in item or '•' in item) and _looks_like_skill_token_list(item):
            parts = _split_skill_list_preserving_parens(item)
        elif ',' in item and len(item) < 160 and from_skill_section:
            # Skill-section comma lists — only split when parts stay short
            maybe = _split_skill_list_preserving_parens(item)
            if maybe and all(len(p.split()) <= 4 for p in maybe):
                parts = maybe

        for part in parts:
            tok = _strip_list_marker(part).strip().rstrip('.,;:|')[:80]
            tok = re.sub(r'^[\s•·▪▫●○\-\*]+', '', tok).strip()
            if not tok:
                continue
            # "Proficiency in Figma…" / "Experience with Terraform" → pull the tool
            prof = re.match(
                r'(?i)^(?:(?:strong|solid|good|excellent|proven|hands[- ]?on)\s+)?'
                r'(?:proficiency\s+in|experience\s+(?:with|in)|knowledge\s+of|'
                r'hands[- ]?on\s+(?:with\s+)?)\s*(.+)$',
                tok,
            )
            if prof:
                rest = prof.group(1).strip()
                for piece in _expand_parenthetical_skill(rest):
                    head = re.split(r'(?i)\s+(?:and|or|with)\s+', piece, maxsplit=1)[0].strip()
                    if head and len(head.split()) <= 4:
                        if _add(head):
                            return out
                for embedded in extract_tech_keywords_from_text(tok, max_items=6):
                    if _add(embedded):
                        return out
                continue
            expanded = _expand_parenthetical_skill(tok)
            if len(expanded) > 1:
                for piece in expanded:
                    if _add(piece):
                        return out
                continue
            # Soft-skill-only phrases: keep only if no tech can be salvaged
            if _SOFT_SKILL_ONLY_RE.match(tok):
                embedded = extract_tech_keywords_from_text(tok, max_items=4)
                if embedded:
                    for e in embedded:
                        if _add(e):
                            return out
                elif from_skill_section:
                    # Defer soft skills — prefer tech; add later only if empty
                    continue
                continue
            # Long skill-section line: keep if phrase-sized, else extract tech
            if from_skill_section and (len(tok.split()) > 8 or len(tok) > 80):
                for embedded in extract_tech_keywords_from_text(tok, max_items=10):
                    if _add(embedded):
                        return out
                continue
            before = len(out)
            if _add(tok):
                return out
            if len(out) > before:
                continue
            # Failed plausibility as a phrase — try embedded tech
            if from_skill_section:
                for embedded in extract_tech_keywords_from_text(tok, max_items=6):
                    if _add(embedded):
                        return out
    return out


def _collect_skill_section_items(desc: str, *, preferred: bool = False) -> list[str]:
    """Walk JD lines and collect items under Required/Preferred Skills headings."""
    raw_lines: list[str] = []
    in_section = False
    header_re = _PREF_HEADER_RE if preferred else _SKILL_HEADER_RE
    inline_re = _PREF_INLINE_HEADER_RE if preferred else _SKILL_INLINE_HEADER_RE
    stop_re = _SKILL_STOP_HEADER_RE
    extra_stop = _PREF_HEADER_RE if not preferred else _SKILL_HEADER_RE

    for line in desc.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        inline = inline_re.match(stripped)
        if inline:
            in_section = True
            rest = inline.group(1).strip()
            if rest:
                raw_lines.append(rest)
            continue
        if header_re.match(stripped):
            in_section = True
            continue
        if in_section:
            if stop_re.match(stripped) or extra_stop.match(stripped):
                break
            if preferred and _SKILL_HEADER_RE.match(stripped):
                break
            if not preferred and _PREF_HEADER_RE.match(stripped):
                break
            raw_lines.append(stripped)
            if len(raw_lines) >= 50:
                break

    if not raw_lines:
        return []
    merged = _merge_softwrapped_lines(raw_lines)
    return [_strip_list_marker(x) for x in merged if _strip_list_marker(x)]


def extract_skills_from_text(desc: str) -> tuple[list[str], list[str], list[str]]:
    """Return (mandatory_skills, preferred_skills, combined skills) from prose."""
    if not desc:
        return [], [], []
    mandatory_skills: list[str] = []
    preferred_skills: list[str] = []

    # Prefer full section walk (multi-line skill blocks)
    mandatory_raw = _collect_skill_section_items(desc, preferred=False)
    preferred_raw = _collect_skill_section_items(desc, preferred=True)

    # Primary / Secondary Technology lines (common in IT ops JDs)
    tech_raw: list[str] = []
    for m in re.finditer(
        r'(?i)(?:primary|secondary)\s*technolog(?:y|ies)\s*[-–—:]\s*([^\n]+)',
        desc,
    ):
        chunk = m.group(1).strip()
        # Split "Weblogic, Secondary Technology-OHS" leftovers already handled by separate matches
        for part in re.split(r'[,;|/]', chunk):
            p = part.strip()
            p = re.sub(r'(?i)^(?:primary|secondary)\s*technolog(?:y|ies)\s*[-–—:]?\s*', '', p).strip()
            if p:
                tech_raw.append(p)

    # Fallback: single-line labeled captures when section walk found nothing
    if not mandatory_raw:
        req_block = re.search(
            r'(?:\*\*)?(?:Required|Core|Mandatory|Primary|Technical|Key|Must[- ]?Have)\s*Skills?(?:\*\*)?\s*[:\-]\s*([^\n*]+)',
            desc,
            re.I,
        )
        primary_block = re.search(
            r'(?:\*\*)?Primary\s*skills?(?:\*\*)?\s*[:\-]\s*([^\n*]+)',
            desc,
            re.I,
        )
        if req_block:
            mandatory_raw = [s.strip() for s in re.split(r'[,•·|]', req_block.group(1)) if s.strip()]
        elif primary_block:
            mandatory_raw = [s.strip() for s in re.split(r'[,•·|]', primary_block.group(1)) if s.strip()]
        if not mandatory_raw:
            block = re.search(
                r'(?:\*\*)?(?:Required\s+|Primary\s+|Technical\s+|Key\s+)?Skills(?:\*\*)?\s*[:\-]\s*([^\n*]+)',
                desc,
                re.I,
            )
            if block:
                mandatory_raw = [s.strip() for s in re.split(r'[,•·|]', block.group(1)) if s.strip()]

    if tech_raw:
        # Prefer primary tech ahead of incidental section noise
        mandatory_raw = list(dict.fromkeys([*tech_raw, *mandatory_raw]))

    if not preferred_raw:
        pref_block = re.search(
            r'(?:\*\*)?(?:Preferred|Nice[- ]?to[- ]?have|Advanced)\s*(?:Skills?|Qualifications?)(?:\*\*)?\s*[:\-][ \t]*([^\n*]+)',
            desc,
            re.I,
        )
        if pref_block and pref_block.group(1).strip():
            preferred_raw = [s.strip() for s in re.split(r'[,•·|]', pref_block.group(1)) if s.strip()]
        if not preferred_raw:
            preferred_raw = _collect_skill_section_items(desc, preferred=True)

    mandatory_skills = normalize_skill_tokens(
        mandatory_raw, max_items=40, from_skill_section=bool(mandatory_raw)
    )
    preferred_skills = normalize_skill_tokens(
        preferred_raw, max_items=20, from_skill_section=bool(preferred_raw)
    )
    # Prefer not to double-count preferred tokens as mandatory
    pref_keys = {s.lower() for s in preferred_skills}
    mandatory_skills = [s for s in mandatory_skills if s.lower() not in pref_keys]

    # Tech-keyword backfill when labeled skills are missing/weak.
    # Do not promote preferred-section keywords into mandatory.
    if len(mandatory_skills) < 3:
        backfill_text = desc
        cut = re.search(
            r'(?i)(?:preferred\s+(?:skills?|qualifications?)|nice[- ]?to[- ]?have|bonus\s+points?)',
            desc,
        )
        if cut and cut.start() > 40:
            backfill_text = desc[: cut.start()]
        tech = extract_tech_keywords_from_text(backfill_text, max_items=20)
        seen = {s.lower() for s in mandatory_skills} | pref_keys
        for tok in tech:
            if tok.lower() in seen or tok.lower() in _SKILL_GARBAGE_TOKENS:
                continue
            if tok.upper() in _BANNER_ACRONYMS:
                continue
            mandatory_skills.append(tok)
            seen.add(tok.lower())
            if len(mandatory_skills) >= 20:
                break

    # Keep only tokens that actually appear in the JD (no invented skills).
    # Do NOT scrape the whole document for extra tech when a skills section exists —
    # Required Skills must mirror what the JD lists — except the thin-backfill above.
    src_l = desc.lower()

    def _grounded(items: list[str]) -> list[str]:
        out: list[str] = []
        seen: set[str] = set()
        for tok in items:
            t = (tok or '').strip()
            if not t:
                continue
            key = t.lower()
            if key in seen or key in _SKILL_GARBAGE_TOKENS:
                continue
            if key not in src_l and not all(
                part.lower() in src_l for part in re.findall(r'[a-z0-9+#.]{2,}', key) if len(part) >= 3
            ):
                # Allow if a significant token from the skill appears in source
                parts = [p for p in re.findall(r'[a-z0-9+#.]{2,}', key) if len(p) >= 3]
                if not parts or not any(p in src_l for p in parts):
                    continue
            seen.add(key)
            out.append(t)
        return out

    mandatory_skills = _grounded(mandatory_skills)
    preferred_skills = _grounded(preferred_skills)

    # Drop soft-skill-only rows when we also have tech skills
    techish = [s for s in mandatory_skills if not _SOFT_SKILL_ONLY_RE.match(s)]
    if techish:
        mandatory_skills = techish

    combined = list(dict.fromkeys(mandatory_skills + preferred_skills))[:40]
    return mandatory_skills[:40], preferred_skills[:20], combined


def skills_look_skill_like(skills: list[str] | None) -> bool:
    """True when skills look like a clean, usable skill list (not junk-heavy)."""
    raw = [str(s).strip() for s in (skills or []) if s and str(s).strip()]
    if not raw:
        return False
    toks = normalize_skill_tokens(raw, max_items=30, from_skill_section=False)
    toks = [t for t in toks if t.lower() not in _SKILL_GARBAGE_TOKENS]
    toks = [t for t in toks if not _SOFT_SKILL_ONLY_RE.match(t)]
    if len(toks) < 2:
        # Single strong tech token is still usable
        if len(toks) == 1 and is_plausible_keyword(toks[0]):
            return True
        return False
    if len(raw) >= 3 and len(toks) / len(raw) < 0.5:
        return False
    return True


def skills_look_polluted(skills: list[str] | None) -> bool:
    """True when a skill list has headers/filler or fails the clean-list check."""
    raw = [str(s).strip() for s in (skills or []) if s and str(s).strip()]
    if not raw:
        return True
    return not skills_look_skill_like(raw)


def extract_jd_keywords_from_text(
    text: str,
    *,
    max_items: int = 20,
    preferred_skills: list[str] | None = None,
    mandatory_skills: list[str] | None = None,
) -> list[str]:
    """Keywords from the overall JD — tech/domain terms across the document.

    Not a copy of Required Skills. Order of preference:
      1) grounded tech/domain tokens from full JD text
      2) preferred / nice-to-have skills present in the JD
      3) mandatory skills only as fill when slots remain (never sole source)
    """
    if not text or not str(text).strip():
        return []
    src = str(text)
    src_l = src.lower()
    out: list[str] = []
    seen: set[str] = set()

    def _add(tok: str) -> bool:
        t = (tok or '').strip().strip('.,;:|')
        if not t or t.lower() in _SKILL_GARBAGE_TOKENS:
            return False
        if not is_plausible_keyword(t) and len(t.split()) > 4:
            return False
        key = t.lower()
        if key in seen:
            return False
        if key not in src_l and not any(
            p in src_l for p in re.findall(r'[a-z0-9+#.]{2,}', key) if len(p) >= 3
        ):
            return False
        if _SOFT_SKILL_ONLY_RE.match(t):
            return False
        seen.add(key)
        out.append(t[:80])
        return len(out) >= max_items

    for tok in extract_tech_keywords_from_text(src, max_items=max_items):
        if _add(tok):
            return out

    for tok in preferred_skills or []:
        if _add(tok):
            return out

    # Fill remaining from mandatory only after overall/preferred coverage
    for tok in mandatory_skills or []:
        if _add(tok):
            return out

    return out


def extract_tech_keywords_from_text(text: str, max_items: int = 20) -> list[str]:
    """Pull short tech/domain keywords that actually appear in the JD text.

    Skips generic/title acronyms (AI, IT, QA, …) — those are not useful keywords.
    """
    if not text:
        return []
    found: list[str] = []
    seen: set[str] = set()
    skip_acronyms = {
        'JD', 'CEO', 'HR', 'USA', 'PDF', 'DOC', 'AI', 'IT', 'QA', 'PM', 'UI', 'UX',
        'CV', 'LLC', 'INC', 'LTD', 'PTE', 'PVT', 'OKR', 'KPI', 'SLA', 'NDA',
        'LPA', 'CTC', 'INR', 'USD', 'EUR', 'GBP', 'WFH', 'JOB', 'GUI',
        *_BANNER_ACRONYMS,
    }

    # Acronyms / product tokens: RAG, GenAI, NLP, AWS, LLM, etc.
    for m in re.finditer(r'\b([A-Z][A-Z0-9+]{1,9})\b', text):
        tok = m.group(1)
        # Prefer .NET over bare NET when present in source
        if tok == 'NET' and re.search(r'(?i)\.NET\b', text):
            tok = '.NET'
        key = tok.lower()
        if key in seen or tok in skip_acronyms:
            continue
        # Require length >= 3 for bare acronyms (RAG, AWS) — drop 2-letter noise
        if len(tok.lstrip('.')) < 3:
            continue
        if is_plausible_keyword(tok):
            seen.add(key)
            found.append(tok)
            if len(found) >= max_items:
                return found

    # Common tech phrases (only if present in text)
    phrases = [
        'machine learning', 'deep learning', 'natural language processing',
        'computer vision', 'large language model', 'large language models',
        'retrieval augmented generation', 'prompt engineering', 'vector database',
        'microservices', 'data pipeline', 'data pipelines',
        'langchain', 'llamaindex', 'pytorch', 'tensorflow', 'kubernetes',
        'docker', 'postgresql', 'mongodb', 'fastapi', 'flask', 'django',
        'react', 'node.js', 'typescript', 'python', 'java', 'golang',
        'aws', 'azure', 'gcp', 'genai', 'rag', 'llm', 'nlp', 'mlops',
        'vmware', 'windows', 'linux', 'virtualization', 'active directory',
        'netapp', 'palo alto', 'firewall', '.net', 'asp.net',
        'figma', 'wireframing', 'prototyping', 'adobe premiere', 'premiere pro',
        'final cut', 'after effects', 'photoshop', 'illustrator', 'sketch',
        'weblogic', 'websphere', 'terraform', 'cloudformation',
    ]
    def _phrase_in_text(phrase: str) -> bool:
        """Whole-token match so 'java' does not fire inside 'JavaScript'."""
        if phrase.startswith('.'):
            return phrase in lower
        return re.search(rf'(?i)(?<![A-Za-z0-9_]){re.escape(phrase)}(?![A-Za-z0-9_])', text) is not None

    lower = text.lower()
    for phrase in phrases:
        if _phrase_in_text(phrase) and phrase not in seen and is_plausible_keyword(phrase):
            display = phrase.upper() if len(phrase) <= 5 and ' ' not in phrase else phrase.title() if ' ' in phrase else phrase.capitalize()
            if phrase in {'rag', 'llm', 'nlp', 'aws', 'gcp', 'genai', 'mlops'}:
                display = phrase.upper() if phrase != 'genai' else 'GenAI'
            elif phrase == '.net':
                display = '.NET'
            elif phrase == 'asp.net':
                display = 'ASP.NET'
            elif phrase in {
                'langchain', 'llamaindex', 'pytorch', 'tensorflow', 'fastapi', 'django',
                'flask', 'postgresql', 'mongodb', 'kubernetes', 'docker', 'python', 'java', 'react',
                'vmware', 'windows', 'linux', 'virtualization', 'active directory', 'netapp',
                'palo alto', 'firewall',
            }:
                display = {
                    'langchain': 'LangChain', 'llamaindex': 'LlamaIndex', 'pytorch': 'PyTorch',
                    'tensorflow': 'TensorFlow', 'fastapi': 'FastAPI', 'django': 'Django',
                    'flask': 'Flask', 'postgresql': 'PostgreSQL', 'mongodb': 'MongoDB',
                    'kubernetes': 'Kubernetes', 'docker': 'Docker', 'python': 'Python',
                    'java': 'Java', 'react': 'React', 'vmware': 'VMware', 'windows': 'Windows',
                    'linux': 'Linux', 'virtualization': 'Virtualization',
                    'active directory': 'Active Directory', 'netapp': 'NetApp',
                    'palo alto': 'Palo Alto', 'firewall': 'Firewall',
                }.get(phrase, display)
            seen.add(phrase)
            found.append(display)
            if len(found) >= max_items:
                break
    return found


def strip_foreign_form_sections_from_description(text: str, title: str = '') -> str:
    """Remove skills/salary/employment/etc. — those belong in other form fields.

    Preserves overview prose and responsibility bullets already in the text.
    """
    if not text or not str(text).strip():
        return ''
    title_norm = re.sub(r'\s+', ' ', (title or '').strip()).lower() if is_plausible_job_title(title or '') else ''
    kept: list[str] = []
    for raw in str(text).replace('\r\n', '\n').split('\n'):
        line = raw.strip()
        if not line:
            if kept and kept[-1] != '':
                kept.append('')
            continue
        # Drop metadata / duplicate title lines only
        if re.match(
            r'(?i)^(?:job\s*title|title|role|position|company|employer|location|salary|ctc|'
            r'compensation|experience|employment\s*type|job\s*type|department|jd|job\s*description)\s*:{1,2}\s*',
            line,
        ):
            continue
        if re.match(r'(?i)^(?:jd|job\s*description|role|position)\s*$', line):
            continue
        line_norm = re.sub(r'\s+', ' ', line).lower().strip('.:- ')
        if title_norm and line_norm == title_norm:
            continue
        kept.append(line)

    cleaned = re.sub(r'\n{3,}', '\n\n', '\n'.join(kept)).strip()
    foreign = (
        r'Employment\s*Type|Job\s*Type|Required\s*Skills?|Preferred\s*Skills?|'
        r'Nice[- ]?to[- ]?have(?:\s*Skills?)?|Mandatory\s*Skills?|Core\s*Skills?|'
        r'Technical\s*Skills?|(?<![A-Za-z])Skills|Qualifications|Requirements|Must\s*Haves?|'
        r'Minimum\s*Qualifications|Benefits|What\s*We\s*Offer|Compensation|Salary|CTC'
    )
    cut = re.search(rf'(?im)(?:^|\n)\s*(?:\*\*)?(?:{foreign})(?:\*\*)?\s*:', cleaned)
    if cut:
        cleaned = cleaned[: cut.start()].strip()
    lines: list[str] = []
    for line in cleaned.split('\n'):
        if re.match(rf'(?i)^\s*(?:\*\*)?(?:{foreign})(?:\*\*)?\s*:?\s*$', line):
            continue
        lines.append(line)
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def detect_responsibility_heading(text: str) -> str:
    """Use the JD's own responsibilities heading when present."""
    if not text:
        return 'Responsibilities'
    m = re.search(
        rf'(?im)^(?:\*\*)?\s*({RESPONSIBILITY_HEADING_RE})\s*(?:\*\*)?\s*:?\s*$',
        text,
    )
    if m:
        raw = re.sub(r'\s+', ' ', m.group(1)).strip(' :*')
        return raw.title() if raw.islower() or raw.isupper() else raw
    m2 = re.search(rf'(?i)({RESPONSIBILITY_HEADING_RE})\s*:', text)
    if m2:
        raw = re.sub(r'\s+', ' ', m2.group(1)).strip(' :*')
        return raw.title() if raw.islower() or raw.isupper() else raw
    return 'Responsibilities'


def compose_jd_description(
    overview: str,
    responsibilities: list[str] | None = None,
    *,
    title: str = '',
    include_responsibilities: bool | None = None,
    source_text: str = '',
    responsibilities_heading: str | None = None,
) -> str:
    """Build Description = overview [+ responsibilities from the JD only].

    Skills/salary/employment stay out. Heading follows the JD when available.
    """
    title_for_clean = title if is_plausible_job_title(title) else ''
    overview_clean = strip_foreign_form_sections_from_description(overview or '', title=title_for_clean)
    overview_clean = re.sub(
        rf'\n*\s*(?:\*\*)?(?:{RESPONSIBILITY_HEADING_RE}):?\*?\*?\s*[\s\S]*$',
        '',
        overview_clean,
        flags=re.I,
    ).strip()

    resp_items = [
        _strip_list_marker(str(r))
        for r in (responsibilities or [])
        if r and _strip_list_marker(str(r))
    ]
    if include_responsibilities is False:
        resp_items = []

    if overview_clean and resp_items:
        ov_lower = overview_clean.lower()
        resp_items = [r for r in resp_items if r.lower()[:48] not in ov_lower]

    parts: list[str] = []
    if overview_clean:
        parts.append(overview_clean)
    if resp_items:
        heading = (
            responsibilities_heading
            or detect_responsibility_heading(source_text or overview or '')
        )
        bullets = "\n".join(f"• {r}" for r in resp_items)
        parts.append(f"**{heading}:**\n{bullets}")
    return "\n\n".join(parts).strip()


def extract_responsibilities_from_text(desc: str, max_items: int = 20) -> list[str]:
    """Parse responsibilities / key duties section from JD prose."""
    if not desc:
        return []
    if not has_responsibilities_section(desc):
        return []
    stop_heads = (
        r'qualifications|requirements|required\s+skills|mandatory\s+skills|'
        r'preferred\s+skills|skills|benefits|what\s+we|must\s+haves?|about|experience|'
        r'compensation|salary|employment|education|educational\s+qualifications?|'
        r'certifications?(?:\s*\([^)]*\))?|notice\s+period'
    )
    responsibilities: list[str] = []
    heading_re = RESPONSIBILITY_HEADING_RE
    if re.search(rf'(?i){heading_re}\s*:', desc) or re.search(
        rf'(?i)^\s*(?:\*\*)?(?:{heading_re})(?:\*\*)?\s*$', desc, re.M
    ):
        block = re.search(
            rf'(?:\*\*)?(?:{heading_re}):?(?:\*\*)?\s*([\s\S]*?)'
            rf'(?=\n\s*(?:\*\*)?(?:{stop_heads})\b|\n\s*\*\*[A-Z]|\Z)',
            desc,
            re.I,
        )
        if block:
            responsibilities = _split_list_items(block.group(1))
    if not responsibilities:
        in_section = False
        section_lines: list[str] = []
        for line in desc.split('\n'):
            stripped = line.strip()
            if re.match(rf'(?i)^(?:\*\*)?(?:{heading_re})(?:\*\*)?\s*:?\s*$', stripped):
                in_section = True
                continue
            # Inline "Responsibilities: sentence..."
            inline = re.match(
                rf'(?i)^(?:\*\*)?(?:{heading_re})(?:\*\*)?\s*:\s*(.+)$',
                stripped,
            )
            if inline and not in_section:
                section_lines.append(inline.group(1))
                in_section = True
                continue
            if in_section:
                if re.match(
                    rf'(?i)^(?:\*\*)?(?:{stop_heads})(?:\*\*)?\s*:?\s*$',
                    stripped,
                ):
                    break
                # Bare section word used as a bullet (e.g. "Education")
                if re.match(
                    r'(?i)^(?:education|qualifications?|requirements?|skills?|'
                    r'certifications?|benefits?|experience)\s*:?\s*$',
                    stripped,
                ):
                    break
                if stripped:
                    section_lines.append(stripped)
        responsibilities = _split_list_items('\n'.join(section_lines))
    # Drop heading-only leftovers
    cleaned: list[str] = []
    for item in responsibilities:
        s = (item or '').strip()
        if not s:
            continue
        if re.match(
            rf'(?i)^(?:{RESPONSIBILITY_HEADING_RE}|education|qualifications?|requirements?)\s*:?\s*$',
            s,
        ):
            continue
        cleaned.append(s)
    return cleaned[:max_items]


def extract_qualifications_from_text(desc: str, max_items: int = 15) -> list[str]:
    if not desc:
        return []
    qualifications: list[str] = []
    for heading in (
        r'(?:\*\*)?Qualifications:?(?:\*\*)?',
        r'(?:\*\*)?Requirements:?(?:\*\*)?',
        r'(?:\*\*)?Must\s+haves?:?(?:\*\*)?',
        r'(?:\*\*)?Minimum\s+qualifications:?(?:\*\*)?',
    ):
        if re.search(heading, desc, re.I):
            block = re.search(
                heading + r'\s*([\s\S]*?)(?=\n\s*\*\*[A-Z]|\n\s*[A-Z][a-z]+\s*:|\Z)',
                desc,
                re.I,
            )
            if block:
                qualifications = _split_list_items(block.group(1))
                if qualifications:
                    break
    if not qualifications:
        in_section = False
        for line in desc.split('\n'):
            stripped = line.strip()
            if re.match(r'(?i)^(?:qualifications|requirements|must\s+haves?)\s*:?\s*$', stripped):
                in_section = True
                continue
            if in_section:
                if re.match(r'(?i)^(?:responsibilities|skills|benefits|about)\s*:?\s*$', stripped):
                    break
                item = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if item and len(item) > 3:
                    qualifications.append(item[:500])
                    if len(qualifications) >= max_items:
                        break
    return qualifications[:max_items]


def extract_experience_years(experience_str: str) -> tuple[Any, Any]:
    """Parse min/max years. Requires years/yrs (or Fresher); ignores 24x7 windows."""
    if not experience_str:
        return None, None
    text = str(experience_str)
    # Mask on-call / availability windows so they never become experience
    text = re.sub(r'\b\d+\s*[xX/]\s*\d+\b', ' ', text)
    text = re.sub(r'\b24\s*[-–—]\s*7\b', ' ', text)

    fresher = re.search(r'(?i)\bfresher\b(?:\s*[–—\-to]+\s*(\d+(?:\.\d+)?)\s*(?:years?|yrs?))?', text)
    if fresher:
        if fresher.group(1):
            return 0.0, float(fresher.group(1))
        return 0.0, None

    # Require explicit years/yrs on ranges and singles
    range_m = re.search(
        r'(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)\b',
        text,
        re.I,
    )
    if range_m:
        return float(range_m.group(1)), float(range_m.group(2))

    plus_m = re.search(r'(\d+(?:\.\d+)?)\s*\+\s*(?:years?|yrs?)\b', text, re.I)
    if plus_m:
        return float(plus_m.group(1)), None

    # Labeled experience without needing the word twice: Experience: 3-5
    labeled = re.search(
        r'(?i)(?:experience|work\s*experience|exp\.?)\s*[:\-–—]\s*'
        r'(\d+(?:\.\d+)?)\s*(?:[-–—]|to)\s*(\d+(?:\.\d+)?)(?:\s*(?:years?|yrs?))?',
        text,
    )
    if labeled:
        return float(labeled.group(1)), float(labeled.group(2))

    single_labeled = re.search(
        r'(?i)(?:experience|work\s*experience|exp\.?)\s*[:\-–—]\s*'
        r'(\d+(?:\.\d+)?)\s*\+?\s*(?:years?|yrs?)?\b',
        text,
    )
    if single_labeled:
        return float(single_labeled.group(1)), None

    single = re.search(r'(\d+(?:\.\d+)?)\s*(?:years?|yrs?)\b', text, re.I)
    if single:
        return float(single.group(1)), None

    return None, None


def extract_location_from_text(text: str) -> str:
    if not text:
        return ''

    def _clean_loc(raw: str) -> str:
        loc = (raw or '').strip().strip('.,;:')
        if not loc:
            return ''
        # Drop interview / process notes in parentheses
        if re.search(
            r'(?i)\((?:final\s+round|face[- ]to[- ]face|interview|onsite\s+interview|'
            r'telephonic|video\s+call|looking\s+for)[^)]*\)',
            loc,
        ):
            loc = re.sub(r'\s*\([^)]*\)\s*', ' ', loc).strip(' ,;-')
        # Also strip trailing parenthetical hiring notes after city
        loc = re.sub(
            r'(?i)\s*\((?:looking\s+for|candidates?\s+from)[^)]*\)\s*',
            ' ',
            loc,
        ).strip(' ,;-')
        # Trim trailing process clauses after em-dash / hyphen notes
        loc = re.split(r'\s*[–—]\s*(?:Final|Face|Interview)', loc, maxsplit=1, flags=re.I)[0]
        loc = re.sub(r'\s{2,}', ' ', loc).strip(' .,;:-')
        if 2 <= len(loc) <= 80:
            return loc
        return ''

    # Labeled with optional separator: "Location: Mumbai", "Location Mumbai", "Location - Pune"
    patterns = [
        r'(?:location|work\s*location|job\s*location)\s*[:\-–—]+\s*([^\n]+)',
        r'(?:location|work\s*location|job\s*location)\s+([A-Za-z][A-Za-z0-9\s,\.\-/()]{1,70})',
        r'(?:based\s+in|office\s+location)\s+([A-Za-z][A-Za-z\s,\.\-]{2,60})',
        r'\b(Remote|Hybrid|Work\s+from\s+home|WFH)\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m and m.group(1):
            loc = _clean_loc(m.group(1))
            if loc:
                return loc

    # City after role title dash: "Cloud Engineer (AWS) – Mumbai"
    title_city = re.search(
        r'(?i)(?:job\s*description|title|role|position)\s*[:\-–—].{0,80}?[–—,\-]\s*'
        r'(' + '|'.join(re.escape(c) for c in sorted(_KNOWN_CITIES, key=len, reverse=True)) + r')\b',
        text,
    )
    if title_city:
        return _clean_loc(title_city.group(1)) or title_city.group(1).title()

    # City / mode fallback when labeled extract missed but evidence exists
    lower = text.lower()
    # Prefer longer city names first (navi mumbai before mumbai)
    cities = sorted(_KNOWN_CITIES, key=len, reverse=True)
    for city in cities:
        if city not in lower:
            continue
        # Prefer cities near a location cue
        near = re.search(
            rf'(?i)(?:location|based\s+in|office|work\s+from|hiring\s+(?:in|at)|'
            rf'candidates?\s+from)[^\n]{{0,40}}\b({re.escape(city)})\b'
            rf'|\b({re.escape(city)})\b[^\n]{{0,30}}(?:location|office|based)',
            text,
        )
        if near:
            span = near.group(1) or near.group(2) or city
            # Preserve original casing from source when possible
            m2 = re.search(re.escape(span), text, re.I)
            return (m2.group(0) if m2 else span.title())[:80]
    # Bare known city on its own line or early header
    for line in text.splitlines()[:25]:
        s = line.strip()
        if not s or len(s) > 80:
            continue
        sl = s.lower()
        for city in cities:
            if sl == city or sl.startswith(city + ',') or sl.startswith(city + ' /'):
                return s[:80]
            if re.match(rf'(?i)^{re.escape(city)}\b', s):
                return _clean_loc(s) or s[:80]
            # Trailing city on a short header line
            if re.search(rf'(?i)[–—,\-]\s*{re.escape(city)}\b\s*$', s):
                m2 = re.search(rf'(?i)({re.escape(city)})\b\s*$', s)
                if m2:
                    return m2.group(1)[:80]
    return ''


# Shared with clean_jd_description — labels that must never become job titles
_NON_TITLE_LABELS = frozenset({
    'role overview', 'job summary', 'overview', 'summary', 'public', 'confidential',
    'jd', 'job description', 'description', 'about the role', 'about the job',
    'about the position', 'position summary', "we're hiring", 'were hiring', 'hiring',
    'notice period', 'employment type', 'job type', 'work experience', 'experience',
    'location', 'company', 'salary', 'compensation', 'responsibilities', 'requirements',
    'qualifications', 'skills', 'benefits', 'role', 'position', 'designation',
    'key responsibilities', 'job requirements', 'role category', 'role summary',
    'certifications', 'certification', 'qualification', 'qualifications',
    'good to have', 'nice to have',
})

_TITLE_ABBREV_DOT_RE = re.compile(
    r'\b(?:Jr|Sr|Mgr|Mr|Mrs|Ms|Dr|Inc|Ltd|Pvt|Co|Corp)\.',
    re.I,
)
_DUTY_VERB_START_RE = re.compile(
    r'(?i)^(participate|design|develop|manage|lead|build|create|ensure|support|'
    r'collaborate|work|implement|maintain|provide|handle|perform|conduct|define|'
    r'demonstrate|architect|optimize|automate|test|deploy|upgrade|tune|respond|'
    r'fine[\s-]?tun)\b'
)
_TITLE_ROLE_NOUN_RE = re.compile(
    r'(?i)\b(engineer|developer|manager|analyst|admin|administrator|architect|'
    r'specialist|officer|associate|executive|consultant|coordinator|trainer|'
    r'lead|scientist|designer|editor|recruiter|generalist|sme|dba|ciso)\b'
)
_TITLE_META_PREFIX_RE = re.compile(
    r'(?i)^(notice\s*period|employment\s*type|job\s*type|experience|location|'
    r'salary|ctc|compensation|department|reports?\s*to|certifications?|'
    r'qualifications?|key\s+responsibilities|job\s+requirements|role\s+category|'
    r'role\s+summary|good\s+to\s+have|nice\s+to\s+have)\b'
)
_TITLE_MARKETING_ADJ_RE = re.compile(
    r'(?i)^(?:motivated|results[\s-]?driven|passionate|dynamic|experienced|skilled|'
    r'hands[\s-]?on|highly\s+skilled|innovative|talented|proven|senior-level|'
    r'self[\s-]?motivated|dedicated|enthusiastic)\s+'
)
_TITLE_LEADING_LABEL_RE = re.compile(
    r'(?i)^(?:jd|job\s*description|role\s*category|designation|position(?:\s*title)?|'
    r'job\s*title|title|role)\s*[:\-–—]\s*'
)
_TITLE_TRAILING_JD_RE = re.compile(
    r'(?i)\s*[–—\-]\s*(?:job\s*description|jd)\s*$'
)

_KV_LABEL_MAP = {
    'job title': 'title',
    'title': 'title',
    'position': 'title',
    'position title': 'title',
    'designation': 'title',
    'role': 'title',
    'location': 'location',
    'work location': 'location',
    'job location': 'location',
    'experience': 'experience',
    'work experience': 'experience',
    'exp': 'experience',
    'salary': 'salary',
    'ctc': 'salary',
    'compensation': 'salary',
    'employment type': 'employment_type',
    'job type': 'employment_type',
    'company': 'company',
    'employer': 'company',
    'organization': 'company',
    'organisation': 'company',
    'skills': 'skills',
    'required skills': 'skills',
    'primary skills': 'skills',
    'technical skills': 'skills',
    'key skills': 'skills',
}


def extract_kv_fields_from_text(text: str) -> dict[str, str]:
    """Parse Label: Value / Label | Value lines (tables + key-value JDs)."""
    if not text:
        return {}
    out: dict[str, str] = {}
    for raw in str(text).splitlines():
        line = raw.strip().strip('|').strip()
        if not line or len(line) > 240:
            continue
        m = re.match(
            r'^([A-Za-z][A-Za-z0-9 /&\-]{1,40}?)\s*[:\-–—|]\s*(.+)$',
            line,
        )
        if not m:
            # Two-column pipe without colon: Location | Mumbai
            parts = [p.strip() for p in line.split('|') if p.strip()]
            if len(parts) == 2 and len(parts[0].split()) <= 4:
                label, value = parts[0], parts[1]
            else:
                continue
        else:
            label, value = m.group(1).strip(), m.group(2).strip()
        key = _KV_LABEL_MAP.get(re.sub(r'\s+', ' ', label.lower()).strip(':'))
        if not key or not value or key in out:
            continue
        # Don't treat section headers as values
        if is_non_title_label(value) and key == 'title':
            continue
        out[key] = value.strip().strip('.,;:')[:200]
    return out


def normalize_title_candidate(title: str) -> str:
    """Strip bullets, label prefixes, marketing adjectives, and trailing JD noise."""
    t = re.sub(r'\s+', ' ', (title or '').strip())
    if not t:
        return ''
    t = re.sub(r'^[\s•·▪▫●○\-\*]+', '', t).strip()
    # Repeatedly peel known label prefixes (Role Category: / JD: / Job Description:)
    for _ in range(3):
        nxt = _TITLE_LEADING_LABEL_RE.sub('', t).strip()
        if nxt == t:
            break
        t = nxt
    t = _TITLE_TRAILING_JD_RE.sub('', t).strip()
    # Peel marketing adjectives (motivated Storage Engineer → Storage Engineer)
    for _ in range(3):
        nxt = _TITLE_MARKETING_ADJ_RE.sub('', t).strip()
        if nxt == t:
            break
        t = nxt
    # Drop trailing employment-context parentheticals when a clean role remains
    # e.g. "IT Sales Executive (Inside Sales)" → keep both if short; strip only
    # noisy "Good to Have" style parentheticals handled by plausibility rejects.
    t = re.sub(r'\s{2,}', ' ', t).strip()
    t = t.strip(' ,;')  # do not strip '.' — preserves .NET / C# edge tokens
    t = re.sub(r'\.+$', '', t).strip() if not re.match(r'(?i)^\.', t) else t
    # Normalize pipes inside paren fragments from wrapped PDF lines
    t = re.sub(r'\s*\|\s*', ' ', t).strip()
    return t[:120]


def is_non_title_label(title: str) -> bool:
    """True for section/meta headings that must not be used as job titles."""
    raw = (title or '').strip()
    t = re.sub(r'\s+', ' ', raw).strip('.:*-–— ').lower()
    if not t:
        return True
    if t in _NON_TITLE_LABELS:
        return True
    if re.match(
        r'(?i)^(?:\*\*)?(?:about(?:\s+the)?\s+(?:role|job|position)|job\s+summary|overview|'
        r'role\s+overview|position\s+summary|summary|description|key\s+responsibilities|'
        r'job\s+requirements|role\s+category|certifications?|qualifications?|'
        r'good\s+to\s+have|nice\s+to\s+have)(?:\*\*)?\s*:?\s*$',
        raw,
    ):
        return True
    return False


def is_plausible_job_title(title: str) -> bool:
    """Reject overview sentences and section labels wrongly used as titles."""
    t = normalize_title_candidate(title)
    if not t or len(t) < 2 or len(t) > 80:
        return False
    if is_non_title_label(t):
        return False
    # Bare section headers still ending with colon
    if t.endswith(':'):
        return False
    words = t.split()
    if len(words) > 10:
        return False
    # Allow Jr./Sr./.NET abbreviations; reject real sentence punctuation
    t_no_abbrev = _TITLE_ABBREV_DOT_RE.sub('JR', t)
    t_no_abbrev = re.sub(r'(?i)\.NET\b', 'NET', t_no_abbrev)
    if re.search(r'[!?]', t_no_abbrev) or re.search(r'\.(?:\s|$)', t_no_abbrev):
        return False
    lower = t.lower()
    if _TITLE_META_PREFIX_RE.match(t):
        return False
    if lower.startswith((
        'we ', 'our ', 'looking', 'seeking', 'join ', 'the ', 'a ', 'an ',
        'about ', 'this ', 'you ', 'your ', "we're ", 'were ',
    )):
        return False
    if re.match(
        r'(?i)^(about|responsibilit|duties|requirements?|qualifications?|skills?|'
        r'benefits?|what you|employment|location|company|salary|compensation|'
        r'notice\s*period|primary\s*skills?|certifications?|key\s+responsibilities|'
        r'job\s+requirements|role\s+category|good\s+to\s+have)\b',
        t,
    ):
        return False
    # Meta "Label: value" lines that are not job titles
    if re.match(
        r'(?i)^(certifications?|qualifications?|key\s+responsibilities|'
        r'job\s+requirements|experience|location|salary|notice\s*period)\s*:',
        t,
    ):
        return False
    if _DUTY_VERB_START_RE.match(t):
        # Allow short role titles ("Design Engineer") but reject duty sentences
        if not (_TITLE_ROLE_NOUN_RE.search(t) and len(words) <= 5):
            return False
    # Reject industry-only parentheticals or truncated fragments
    if t.startswith('(') and t.endswith(')'):
        return False
    if t.endswith(')') and '(' not in t:
        return False
    if t.endswith('(') or (t.count('(') != t.count(')')):
        return False
    if re.match(r'(?i)^(?:we[\'’]?re\s+hiring)\b', t):
        # "We're Hiring: Open Source DBA (L2)" — strip prefix later; raw form is weak
        if ':' in t:
            after = normalize_title_candidate(t.split(':', 1)[1])
            return is_plausible_job_title(after) if after != t else False
        return False
    return True


def _extend_wrapped_title_capture(text: str, start: int, first_line_value: str) -> str:
    """Continue a labeled title across the next line when PDF wraps mid-paren."""
    cand = first_line_value.strip()
    if cand.count('(') <= cand.count(')') and not cand.rstrip().endswith('|'):
        return cand
    rest = text[start:]
    lines = rest.splitlines()
    # lines[0] is the matched line; peek at following non-empty lines
    for nxt in lines[1:4]:
        piece = nxt.strip()
        if not piece:
            continue
        if is_non_title_label(piece) or re.match(
            r'(?i)^(experience|location|qualification|certifications?|role\s+summary|'
            r'responsibilit|requirements?|skills?)\b',
            piece,
        ):
            break
        cand = f'{cand} {piece}'.strip()
        if cand.count('(') <= cand.count(')') and not cand.rstrip().endswith('|'):
            break
        if len(cand) > 120:
            break
    return cand


def _title_from_labeled_line(text: str) -> str:
    """Extract title from common JD label patterns."""
    patterns = [
        r'(?im)^(?:job\s*title|position\s*title|position|title)\s*[:\-–—]\s*(.+)$',
        r'(?im)^(?:designation)\s*[:\-–—]\s*(.+)$',
        r'(?im)^role\s*category\s*[:\-–—]\s*(.+)$',
        r'(?im)^role\s*[–—\-:]\s*(.+)$',
        # Job Description: Role  OR  Job Description – Role (en-dash / hyphen)
        r'(?im)^job\s*description\s*[:\-–—]\s*(.+)$',
        r'(?im)^(?:we[\'’]?re\s+hiring)\s*:\s*(.+)$',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        cand = _extend_wrapped_title_capture(text, m.start(), m.group(1))
        cand = normalize_title_candidate(cand)
        # "Cloud Engineer (AWS) – Mumbai" → keep role, drop trailing city after dash
        cand = re.sub(
            r'\s+[–—\-]\s+(?:Mumbai|Navi\s+Mumbai|Pune|Bangalore|Bengaluru|Chennai|'
            r'Hyderabad|Delhi|Noida|Gurgaon|Gurugram|Remote|India)\b.*$',
            '',
            cand,
            flags=re.I,
        ).strip()
        # Drop trailing employment-context parenthetical when long
        cand = re.sub(
            r'(?i)\s*\((?:inside\s+sales|outside\s+sales|full[\s-]?time|part[\s-]?time|'
            r'contract|permanent|on[\s-]?site|remote)\)\s*$',
            '',
            cand,
        ).strip()
        if cand.lower().startswith('designation'):
            continue
        if is_plausible_job_title(cand):
            return normalize_title_candidate(cand)[:120]
    return ''


def extract_title_from_text(text: str) -> str:
    if not text:
        return ''
    kv = extract_kv_fields_from_text(text)
    if kv.get('title'):
        cand = normalize_title_candidate(kv['title'])
        if is_plausible_job_title(cand):
            return cand[:120]
    labeled = _title_from_labeled_line(text)
    if labeled:
        return labeled

    # Prose: "Looking for a motivated Storage Engineer to join…"
    # Allow .NET / C++ style tech tokens at the start of the role.
    prose = re.search(
        r'(?i)(?:looking\s+for|seeking|hiring)\s+(?:a|an)\s+'
        r'(?:(?:motivated|results[\s-]?driven|passionate|dynamic|experienced|skilled|'
        r'hands[\s-]?on|highly\s+skilled|innovative|talented|proven|dedicated|'
        r'enthusiastic|self[\s-]?motivated)\s+)*'
        r'((?:\.NET|C\+\+|C#|[A-Z])[A-Za-z0-9+#.]*(?:[\s/&\-][A-Za-z0-9+#.]+){0,8})'
        r'\s+to\s+(?:join|lead|work|support|drive|contribute)',
        text,
    )
    if prose:
        cand = normalize_title_candidate(prose.group(1))
        if is_plausible_job_title(cand):
            return cand[:120]

    skip_prefix = re.compile(
        r'(?i)^(company|employer|location|salary|ctc|compensation|experience|'
        r'employment|about|responsibilit|requirements?|skills?|'
        r'qualifications?|benefits?|what you|preferred|mandatory|notice\s*period|'
        r'primary\s*skills?|work\s*experience|employment\s*type|job\s*type|'
        r'role\s+overview|job\s+summary|overview|summary|public|confidential|'
        r'certifications?|key\s+responsibilities|job\s+requirements)\b'
    )
    # Scan deeper for multi-column / table-serialized preambles
    for line in text.split('\n')[:40]:
        stripped = line.strip()
        if not stripped or len(stripped) < 3:
            continue
        # Prefer Job Description – Role as a labeled source (do not skip wholesale)
        jd_inline = re.match(
            r'(?i)^job\s*description\s*[:\-–—]\s*(.+)$',
            stripped,
        )
        if jd_inline:
            cand = normalize_title_candidate(
                _extend_wrapped_title_capture(text, text.find(stripped), jd_inline.group(1))
            )
            if is_plausible_job_title(cand):
                return cand[:120]
            continue
        stripped = re.sub(r'^[\s#*•\-–—]+', '', stripped).strip()
        if not stripped:
            continue
        if skip_prefix.match(stripped) or is_non_title_label(stripped):
            continue
        stripped = normalize_title_candidate(stripped)
        stripped = re.sub(
            r'(?i)^(?:job\s*title|position\s*title|position|title|designation|role)\s*[:\-–—]\s*',
            '',
            stripped,
        ).strip()
        stripped = normalize_title_candidate(stripped)
        if is_plausible_job_title(stripped):
            return stripped[:120]
    return ''


def extract_salary_from_text(text: str) -> str:
    if not text:
        return ''
    patterns = [
        r'(?i)(?:salary|compensation|ctc|pay)\s*[:\-]\s*([^\n]+)',
        r'(?i)(?:₹|rs\.?|inr)\s*[\d,]+(?:\s*[-–—]\s*(?:₹|rs\.?|inr)?\s*[\d,]+)?(?:\s*(?:lpa|lakhs?|lakh|per\s+annum|p\.?a\.?)?)?',
        r'(?i)\d+(?:\.\d+)?\s*[-–—]\s*\d+(?:\.\d+)?\s*(?:lpa|lakhs?)',
        r'(?i)\$\s*[\d,]+(?:k)?(?:\s*[-–—]\s*\$?\s*[\d,]+(?:k)?)?',
        r'(?i)[\d,]+\s*[-–—]\s*[\d,]+\s*(?:usd|eur|gbp)',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if m:
            val = (m.group(1) if m.lastindex else m.group(0)).strip().strip('.,;:')
            # Reject currency-only noise ("rs", "₹", "INR") without an amount
            if re.fullmatch(r'(?i)(?:rs\.?|inr|₹|usd|eur|gbp|\$)', val):
                continue
            if not re.search(r'\d', val) and not re.search(r'(?i)lpa|lakh|negotiable', val):
                continue
            if 2 <= len(val) <= 80:
                return val
    return ''


def extract_employment_type_from_text(text: str) -> str:
    if not text:
        return ''
    labeled = re.search(
        r'(?i)(?:employment\s*type|job\s*type|type)\s*[:\-]\s*([^\n]+)',
        text,
    )
    if labeled and labeled.group(1):
        return labeled.group(1).strip().strip('.,;:')[:60]
    for token in (
        'Full-time', 'Full time', 'Part-time', 'Part time',
        'Contract', 'Internship', 'Temporary', 'Freelance', 'Remote',
    ):
        if re.search(rf'(?i)\b{re.escape(token)}\b', text):
            return token.replace(' ', '-') if 'time' in token.lower() else token
    return ''


def extract_company_from_text(text: str) -> str:
    if not text:
        return ''
    labeled = re.search(
        r'(?i)(?:company|employer|organization|organisation)\s*[:\-]\s*([^\n]+)',
        text,
    )
    if labeled and labeled.group(1):
        company = labeled.group(1).strip().strip('.,;:')
        if 2 <= len(company) <= 120:
            return company
    return ''


def extract_overview_from_text(text: str, max_chars: int = 2500) -> str:
    """Extract the job overview / about section for the Description form field.

    Returns empty when the JD has no real narrative (only title/location/skills metadata).
    """
    if not text or not str(text).strip():
        return ''
    desc = str(text).strip()

    about = re.search(
        r'(?i)(?:about(?:\s+the)?\s+(?:role|job|position)|job\s+summary|overview|role\s+overview|'
        r'position\s+summary|job\s+description|summary)\s*:?\s*\n+([\s\S]+?)'
        r'(?=\n\s*(?:\*\*)?(?:key\s+)?(?:responsibilities|duties|requirements|qualifications|'
        r'required\s+skills|skills|benefits|what\s+we|what\s+you|employment|experience)\b|\Z)',
        desc,
    )
    if about and len(about.group(1).strip()) >= 20:
        cleaned_about = clean_jd_description(about.group(1).strip()[:max_chars])
        if cleaned_about and len(cleaned_about) >= 20:
            return cleaned_about

    cut = re.search(
        rf'\n\s*(?:\*\*)?(?:{RESPONSIBILITY_HEADING_RE}|requirements|qualifications|'
        r'required\s+skills|mandatory\s+skills|skills|benefits|what\s+you|what\s+we|'
        r'must\s+haves?|qualifications)\b',
        desc,
        re.I,
    )
    head = desc[: cut.start()] if cut else desc
    lines: list[str] = []
    for line in head.split('\n'):
        stripped = line.strip()
        if not stripped:
            if lines and lines[-1] != '':
                lines.append('')
            continue
        if re.match(
            r'(?i)^(?:job\s*title|title|company|employer|location|salary|ctc|compensation|experience|employment\s*type|job\s*type|role)\s*:',
            stripped,
        ):
            continue
        if re.match(
            rf'(?i)^(?:\*\*)?(?:{RESPONSIBILITY_HEADING_RE}|requirements|qualifications|skills)\s*:?(?:\*\*)?\s*$',
            stripped,
        ):
            break
        if re.match(r'(?i)^(remote|hybrid|onsite|work\s+from\s+home|wfh)[\s,.-]*$', stripped):
            continue
        lines.append(_strip_list_marker(stripped) or stripped)
    overview = '\n'.join(ln for ln in lines if ln).strip()
    overview = re.sub(r'\n{3,}', '\n\n', overview)
    cleaned = clean_jd_description(overview)
    # Reject title/location-only leftovers — need real narrative
    if not cleaned or len(cleaned) < 40:
        return ''
    if is_plausible_job_title(cleaned):
        return ''
    if '.' not in cleaned and len(cleaned.split()) < 12:
        return ''
    return cleaned[:max_chars]


def build_description_from_available(
    *,
    overview: str = '',
    responsibilities: list[str] | None = None,
    mandatory_skills: list[str] | None = None,
    preferred_skills: list[str] | None = None,
    qualifications: list[str] | None = None,
    title: str = '',
    source_text: str = '',
    include_responsibilities: bool = False,
    responsibilities_heading: str | None = None,
) -> str:
    """Fill Description from whatever the JD actually has — never invent content.

    Priority:
      1) overview (+ responsibilities if present in JD)
      2) responsibilities only
      3) qualifications bullets
      4) required / preferred skills
    """
    resp = [
        _strip_list_marker(str(r))
        for r in (responsibilities or [])
        if r and _strip_list_marker(str(r))
    ]
    composed = compose_jd_description(
        overview or '',
        resp if include_responsibilities else [],
        title=title if is_plausible_job_title(title) else '',
        include_responsibilities=include_responsibilities,
        source_text=source_text,
        responsibilities_heading=responsibilities_heading,
    )
    if composed and len(composed.strip()) >= 10:
        return composed.strip()

    if include_responsibilities and resp:
        heading = responsibilities_heading or detect_responsibility_heading(source_text)
        return f"**{heading}:**\n" + "\n".join(f"• {r}" for r in resp)

    quals = [
        _strip_list_marker(str(q))
        for q in (qualifications or [])
        if q and _strip_list_marker(str(q))
    ]
    if quals:
        return "**Qualifications:**\n" + "\n".join(f"• {q}" for q in quals[:12])

    required = [str(s).strip() for s in (mandatory_skills or []) if s and str(s).strip()]
    if not required:
        required = [str(s).strip() for s in (preferred_skills or []) if s and str(s).strip()]
    if required:
        return f"**Required Skills:**\n{', '.join(required)}"
    return ''


def clean_jd_description(text: str, title: str = '') -> str:
    """Keep only the real job narrative — strip titles, Role:/JD labels, and junk lines."""
    if not text or not str(text).strip():
        return ''
    title_norm = re.sub(r'\s+', ' ', (title or '').strip()).lower()
    cleaned_lines: list[str] = []
    for raw_line in str(text).replace('\r\n', '\n').split('\n'):
        line = raw_line.strip()
        if not line:
            if cleaned_lines and cleaned_lines[-1] != '':
                cleaned_lines.append('')
            continue
        # Drop metadata / duplicate title lines
        if re.match(
            r'(?i)^(?:job\s*title|title|role|position|company|employer|location|salary|ctc|'
            r'compensation|experience|employment\s*type|job\s*type|department|jd|job\s*description)\s*:{1,2}\s*',
            line,
        ):
            continue
        if re.match(r'(?i)^(?:jd|job\s*description|role|position)\s*$', line):
            continue
        # Drop standalone section headings that aren't content
        if re.match(
            r'(?i)^(?:\*\*)?(?:about(?:\s+the)?\s+(?:role|job|position)|job\s+summary|overview|'
            r'role\s+overview|position\s+summary|summary|description)(?:\*\*)?\s*:?\s*$',
            line,
        ):
            continue
        # Strip trailing "About the role:" style label if glued to content start
        line = re.sub(
            r'(?i)^(?:\*\*)?(?:about(?:\s+the)?\s+(?:role|job|position)|job\s+summary|overview)\s*:\s*',
            '',
            line,
        ).strip()
        if not line:
            continue
        # Strip source bullet markers — Description overview is plain prose
        line = _strip_list_marker(line)
        if not line:
            continue
        line_norm = re.sub(r'\s+', ' ', line).lower().strip('.:- ')
        if title_norm and (line_norm == title_norm or line_norm == f'role {title_norm}'):
            continue
        # Drop ultra-short heading leftovers
        if len(line) <= 3 and line.isalpha():
            continue
        cleaned_lines.append(line)

    overview = '\n'.join(cleaned_lines).strip()
    overview = re.sub(r'\n{3,}', '\n\n', overview)
    # Fix common OCR / join artifacts per line (do not collapse newlines)
    fixed_lines: list[str] = []
    for ln in overview.split('\n'):
        ln = re.sub(r'\.\s*,\s*', ', ', ln)
        ln = re.sub(r',\s*,+', ', ', ln)
        ln = re.sub(r'[ \t]{2,}', ' ', ln).strip()
        fixed_lines.append(ln)
    overview = '\n'.join(fixed_lines).strip()
    overview = re.sub(r'\n{3,}', '\n\n', overview)
    # If still starts with title on first line of a longer block, drop that line
    parts = overview.split('\n', 1)
    if title_norm and parts:
        first = re.sub(r'\s+', ' ', parts[0]).lower().strip('.:- ')
        if first == title_norm and len(parts) > 1:
            overview = parts[1].strip()
    return overview.strip()


def is_plausible_keyword(token: str) -> bool:
    """Keywords must be short JD terms (skills/tech), never sentence fragments."""
    if not token or not str(token).strip():
        return False
    kw = str(token).strip().strip(',;:|')
    # Keep internal dots for tech tokens (Node.js, Vue.js); only strip trailing punctuation
    kw = kw.rstrip('.,;:|!?')
    kw = re.sub(r'^[\(\)\[\]]+|[\(\)\[\]]+$', '', kw).strip()
    if len(kw) < 2 or len(kw) > 48:
        return False
    # Reject sentence-like punctuation, but allow dotted product names (Node.js)
    if re.search(r'[!?]', kw):
        return False
    if '.' in kw and not re.match(
        r'^[A-Za-z0-9+#]+(?:\.[A-Za-z0-9+#]+)+$',
        kw,
    ):
        return False
    words = kw.split()
    if len(words) > 4:
        return False
    lower = kw.lower()
    if lower in _JD_SKILL_DENYLIST or lower in _CONNECTOR_WORDS:
        return False
    if kw.upper() in _BANNER_ACRONYMS:
        return False
    if lower.startswith((
        'we ', 'our ', 'the ', 'a ', 'an ', 'to ', 'looking', 'seeking',
        'join ', 'lead ', 'highly', 'innovative', 'must ', 'should ',
        'responsible', 'ability ', 'hands-on experience', 'preferred ',
        'required ', 'mandatory ', 'bonus ', 'nice ', 'good to ',
    )):
        return False
    # Reject duty / meta fragments
    if re.match(
        r'(?i)^(test|deploy|participate|provide|ensure|manage|develop|implement|'
        r'collaborate|maintain|perform|conduct|location|salary|experience|'
        r'remote|hybrid|onsite|full[\s-]?time|part[\s-]?time)\b',
        kw,
    ):
        return False
    # Reject prose-y fragments
    if any(w in lower.split() for w in ('seeking', 'looking', 'join', 'team', 'lead', 'highly', 'years', 'plus')):
        if len(words) >= 2:
            return False
    # Reject dangling preposition phrases ("Azure Database for")
    if words and words[-1].lower() in {'for', 'with', 'and', 'or', 'of', 'to', 'in', 'on', 'at', 'by'}:
        return False
    if re.search(r'(?i)\bis\s+a\s+plus\b', lower) or lower.endswith(' a plus'):
        return False
    return True


def infer_jd_fields_from_text(text: str) -> dict[str, Any]:
    """Infer TOON-relevant fields from raw JD text when LLM output is incomplete."""
    desc = (text or '').strip()
    mandatory, preferred, skills = extract_skills_from_text(desc)
    min_y, max_y = extract_experience_years(desc)
    return {
        'skills': skills,
        'mandatory_skills': mandatory,
        'preferred_skills': preferred,
        'responsibilities': extract_responsibilities_from_text(desc),
        'qualifications': extract_qualifications_from_text(desc),
        'location': extract_location_from_text(desc),
        'title': extract_title_from_text(desc),
        'company': extract_company_from_text(desc),
        'salary_range': extract_salary_from_text(desc),
        'employment_type': extract_employment_type_from_text(desc),
        'min_experience_years': min_y,
        'max_experience_years': max_y,
        'description': extract_overview_from_text(desc),
    }
