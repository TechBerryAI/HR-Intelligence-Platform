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


def _split_list_items(text: str) -> list[str]:
    """Split bullet/pipe/newline-separated prose into items. Never split on commas.

    Strips source bullet markers so callers can rebuild clean • bullets.
    Commas belong inside sentences (e.g. "Design, build, and ship APIs").
    """
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    parts: list[str] = []
    if '|' in raw:
        parts = [p.strip() for p in raw.split('|')]
    else:
        parts = [p.strip() for p in re.split(r'\n+', raw)]
    result: list[str] = []
    for part in parts:
        cleaned = _strip_list_marker(part)
        if cleaned and len(cleaned) > 2:
            result.append(cleaned[:500])
    return result


_SKILL_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:required\s+|core\s+|mandatory\s+|technical\s+|primary\s+|key\s+|must[- ]?have\s+)?'
    r'(?:skills?|tech\s*stack)(?:\*\*)?\s*:?\s*$'
)
_SKILL_STOP_HEADER_RE = re.compile(
    r'(?i)^(?:\*\*)?(?:responsibilities|qualifications|requirements|benefits|preferred|'
    r'about|experience|education|employment|location|salary)(?:\*\*)?\s*:?\s*$'
)
_QUAL_SKILL_NOISE_RE = re.compile(
    r'(?i)^(qualification|education|bachelor|master|degree|b\.?tech|b\.?e\.?|m\.?c\.?a|'
    r'b\.?c\.?a|b\.?sc|mba|phd|preferred\s*skills?|required\s*skills?|mandatory\s*skills?|'
    r'technical\s*skills?|primary\s*skills?|educational\s*qualifications?)\b'
)


def normalize_skill_tokens(items: list[str] | None, *, max_items: int = 30) -> list[str]:
    """Keep short skill/tech tokens; drop sentence fragments and qualification lines."""
    if not items:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for raw in items:
        if not raw or not str(raw).strip():
            continue
        item = _strip_list_marker(str(raw))
        # Extra bullet/encoding leftovers
        item = re.sub(r'^[\s•·▪▫●○\-\*]+', '', item).strip()
        if not item:
            continue
        if _QUAL_SKILL_NOISE_RE.match(item) or item.lower().startswith('qualification'):
            continue
        parts = [item]
        if ',' in item and len(item) < 120:
            parts = [p.strip() for p in item.split(',') if p.strip()]
        for part in parts:
            tok = _strip_list_marker(part).strip().strip('.,;:|')[:80]
            tok = re.sub(r'^[\s•·▪▫●○\-\*]+', '', tok).strip()
            if not tok or not is_plausible_keyword(tok):
                continue
            key = tok.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(tok)
            if len(out) >= max_items:
                return out
    return out


def extract_skills_from_text(desc: str) -> tuple[list[str], list[str], list[str]]:
    """Return (mandatory_skills, preferred_skills, combined skills) from prose."""
    if not desc:
        return [], [], []
    mandatory_skills: list[str] = []
    preferred_skills: list[str] = []
    skills: list[str] = []

    pref_block = re.search(
        r'(?:\*\*)?(?:Preferred|Nice-to-have|Advanced)\s*Skills?(?:\*\*)?\s*[:\-]\s*([^\n*]+)',
        desc,
        re.I,
    )
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
        mandatory_skills = [s.strip() for s in re.split(r'[,•·|]', req_block.group(1)) if s.strip()]
    elif primary_block:
        mandatory_skills = [s.strip() for s in re.split(r'[,•·|]', primary_block.group(1)) if s.strip()]
    if pref_block:
        preferred_skills = [s.strip() for s in re.split(r'[,•·|]', pref_block.group(1)) if s.strip()]
    if not mandatory_skills:
        block = re.search(
            r'(?:\*\*)?(?:Required\s+|Primary\s+|Technical\s+|Key\s+)?Skills(?:\*\*)?\s*[:\-]\s*([^\n*]+)',
            desc,
            re.I,
        )
        if block:
            skills = [s.strip() for s in re.split(r'[,•·|]', block.group(1)) if s.strip()]
            mandatory_skills = skills

    # Multi-line bullet skill sections (common in JDs)
    if not mandatory_skills:
        in_skills = False
        for line in desc.split('\n'):
            stripped = line.strip()
            if _SKILL_HEADER_RE.match(stripped):
                in_skills = True
                continue
            if in_skills:
                if _SKILL_STOP_HEADER_RE.match(stripped):
                    break
                item = _strip_list_marker(stripped)
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if item and 1 < len(item) <= 80:
                    if ',' in item and len(item) < 120:
                        mandatory_skills.extend([p.strip() for p in item.split(',') if p.strip()][:12])
                    else:
                        mandatory_skills.append(item[:80])
                    if len(mandatory_skills) >= 25:
                        break

    if not skills and mandatory_skills:
        skills = list(mandatory_skills)
    if not skills and desc:
        for line in desc.split('\n'):
            if 'skill' in line.lower():
                if re.match(r'(?i)^(?:\*\*)?(?:required\s+|preferred\s+|primary\s+)?skills?(?:\*\*)?\s*:?\s*$', line.strip()):
                    continue
                parts = re.split(r'[,•·|]', re.sub(r'(?i)^.*skills?\s*[:\-]\s*', '', line))
                skills.extend([p.strip().strip('*') for p in parts if len(p.strip()) > 1][:15])
                if skills:
                    break
        if skills and not mandatory_skills:
            mandatory_skills = skills

    # Tech-keyword backfill when labeled skills are missing/weak
    mandatory_skills = normalize_skill_tokens(mandatory_skills, max_items=30)
    preferred_skills = normalize_skill_tokens(preferred_skills, max_items=20)
    if len(mandatory_skills) < 3:
        tech = extract_tech_keywords_from_text(desc, max_items=20)
        for tok in tech:
            key = tok.lower()
            if key not in {s.lower() for s in mandatory_skills}:
                mandatory_skills.append(tok)
            if len(mandatory_skills) >= 20:
                break

    combined = (mandatory_skills or skills)[:30]
    combined = normalize_skill_tokens(combined, max_items=30) or mandatory_skills
    return mandatory_skills[:30], preferred_skills[:20], combined[:30]


def skills_look_skill_like(skills: list[str] | None) -> bool:
    """True when at least one token looks like a real skill/tech keyword."""
    toks = normalize_skill_tokens(skills or [], max_items=10)
    return len(toks) >= 1


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
        'LPA', 'CTC', 'INR', 'USD', 'EUR', 'GBP', 'WFH',
    }

    # Acronyms / product tokens: RAG, GenAI, NLP, AWS, LLM, etc.
    for m in re.finditer(r'\b([A-Z][A-Z0-9+]{1,9})\b', text):
        tok = m.group(1)
        key = tok.lower()
        if key in seen or tok in skip_acronyms:
            continue
        # Require length >= 3 for bare acronyms (RAG, AWS) — drop 2-letter noise
        if len(tok) < 3:
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
    ]
    lower = text.lower()
    for phrase in phrases:
        if phrase in lower and phrase not in seen and is_plausible_keyword(phrase):
            display = phrase.upper() if len(phrase) <= 5 and ' ' not in phrase else phrase.title() if ' ' in phrase else phrase.capitalize()
            if phrase in {'rag', 'llm', 'nlp', 'aws', 'gcp', 'genai', 'mlops'}:
                display = phrase.upper() if phrase != 'genai' else 'GenAI'
            elif phrase in {
                'langchain', 'llamaindex', 'pytorch', 'tensorflow', 'fastapi', 'django',
                'flask', 'postgresql', 'mongodb', 'kubernetes', 'docker', 'python', 'java', 'react',
            }:
                display = {
                    'langchain': 'LangChain', 'llamaindex': 'LlamaIndex', 'pytorch': 'PyTorch',
                    'tensorflow': 'TensorFlow', 'fastapi': 'FastAPI', 'django': 'Django',
                    'flask': 'Flask', 'postgresql': 'PostgreSQL', 'mongodb': 'MongoDB',
                    'kubernetes': 'Kubernetes', 'docker': 'Docker', 'python': 'Python',
                    'java': 'Java', 'react': 'React',
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
    responsibilities: list[str] = []
    heading_re = RESPONSIBILITY_HEADING_RE
    if re.search(rf'(?i){heading_re}\s*:', desc) or re.search(
        rf'(?i)^\s*(?:\*\*)?(?:{heading_re})(?:\*\*)?\s*$', desc, re.M
    ):
        block = re.search(
            rf'(?:\*\*)?(?:{heading_re}):?(?:\*\*)?\s*([\s\S]*?)'
            rf'(?=\n\s*(?:\*\*)?(?:qualifications|requirements|required\s+skills|mandatory\s+skills|'
            rf'preferred\s+skills|skills|benefits|what\s+we|must\s+haves?|about|experience|'
            rf'compensation|salary|employment)\b|\n\s*\*\*[A-Z]|\Z)',
            desc,
            re.I,
        )
        if block:
            responsibilities = _split_list_items(block.group(1))
    if not responsibilities:
        in_section = False
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
                item = _strip_list_marker(inline.group(1))
                if item and len(item) > 3:
                    responsibilities.append(item[:500])
                in_section = True
                continue
            if in_section:
                if re.match(
                    r'(?i)^(?:\*\*)?(?:qualifications|requirements|skills|benefits|about|'
                    r'what\s+we\s+offer|must\s+haves?|experience|compensation|salary)(?:\*\*)?\s*:?\s*$',
                    stripped,
                ):
                    break
                item = _strip_list_marker(stripped)
                if item and len(item) > 3:
                    responsibilities.append(item[:500])
                    if len(responsibilities) >= max_items:
                        break
    return responsibilities[:max_items]


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
    patterns = [
        r'(?:location|work\s*location|job\s*location)\s*[:\-–—]+\s*([^\n]+)',
        r'(?:based\s+in|office\s+location)\s+([A-Za-z][A-Za-z\s,\.\-]{2,60})',
        r'\b(Remote|Hybrid|Work\s+from\s+home|WFH)\b',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m and m.group(1):
            loc = m.group(1).strip().strip('.,;:')
            # Drop interview / process notes in parentheses
            if re.search(
                r'(?i)\((?:final\s+round|face[- ]to[- ]face|interview|onsite\s+interview|'
                r'telephonic|video\s+call)[^)]*\)',
                loc,
            ):
                loc = re.sub(r'\s*\([^)]*\)\s*', ' ', loc).strip(' ,;-')
            # Trim trailing process clauses after em-dash / hyphen notes
            loc = re.split(r'\s*[–—]\s*(?:Final|Face|Interview)', loc, maxsplit=1, flags=re.I)[0]
            loc = re.sub(r'\s{2,}', ' ', loc).strip(' .,;:-')
            if 2 <= len(loc) <= 80:
                return loc
    return ''


# Shared with clean_jd_description — labels that must never become job titles
_NON_TITLE_LABELS = frozenset({
    'role overview', 'job summary', 'overview', 'summary', 'public', 'confidential',
    'jd', 'job description', 'description', 'about the role', 'about the job',
    'about the position', 'position summary', "we're hiring", 'were hiring', 'hiring',
    'notice period', 'employment type', 'job type', 'work experience', 'experience',
    'location', 'company', 'salary', 'compensation', 'responsibilities', 'requirements',
    'qualifications', 'skills', 'benefits', 'role', 'position', 'designation',
})

_TITLE_ABBREV_DOT_RE = re.compile(
    r'\b(?:Jr|Sr|Mgr|Mr|Mrs|Ms|Dr|Inc|Ltd|Pvt|Co|Corp)\.',
    re.I,
)
_DUTY_VERB_START_RE = re.compile(
    r'(?i)^(participate|design|develop|manage|lead|build|create|ensure|support|'
    r'collaborate|work|implement|maintain|provide|handle|perform|conduct|define|'
    r'demonstrate|architect|optimize|automate)\b'
)
_TITLE_ROLE_NOUN_RE = re.compile(
    r'(?i)\b(engineer|developer|manager|analyst|admin|administrator|architect|'
    r'specialist|officer|associate|executive|consultant|coordinator|trainer|'
    r'lead|scientist|designer|editor|recruiter|generalist|sme|dba|ciso)\b'
)
_TITLE_META_PREFIX_RE = re.compile(
    r'(?i)^(notice\s*period|employment\s*type|job\s*type|experience|location|'
    r'salary|ctc|compensation|department|reports?\s*to)\b'
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


def is_non_title_label(title: str) -> bool:
    """True for section/meta headings that must not be used as job titles."""
    t = re.sub(r'\s+', ' ', (title or '').strip()).strip('.:*-–— ').lower()
    if not t:
        return True
    if t in _NON_TITLE_LABELS:
        return True
    if re.match(
        r'(?i)^(?:\*\*)?(?:about(?:\s+the)?\s+(?:role|job|position)|job\s+summary|overview|'
        r'role\s+overview|position\s+summary|summary|description)(?:\*\*)?\s*:?\s*$',
        title or '',
    ):
        return True
    return False


def is_plausible_job_title(title: str) -> bool:
    """Reject overview sentences and section labels wrongly used as titles."""
    t = re.sub(r'\s+', ' ', (title or '').strip())
    t = re.sub(r'^[\s•·▪▫●○\-\*]+', '', t).strip()
    if not t or len(t) < 2 or len(t) > 80:
        return False
    if is_non_title_label(t):
        return False
    words = t.split()
    if len(words) > 10:
        return False
    # Allow Jr./Sr. abbreviations; reject real sentence punctuation
    t_no_abbrev = _TITLE_ABBREV_DOT_RE.sub('JR', t)
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
        r'notice\s*period|primary\s*skills?)\b',
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
            after = t.split(':', 1)[1].strip()
            return is_plausible_job_title(after) if after != t else False
        return False
    return True


def _title_from_labeled_line(text: str) -> str:
    """Extract title from common JD label patterns."""
    patterns = [
        r'(?im)^(?:job\s*title|position\s*title|position|title)\s*[:\-–—]\s*(.+)$',
        r'(?im)^(?:designation)\s*[:\-–—]\s*(.+)$',
        r'(?im)^role\s*[–—\-:]\s*(.+)$',
        r'(?im)^job\s*description\s*:\s*(.+)$',
        r'(?im)^(?:we[\'’]?re\s+hiring)\s*:\s*(.+)$',
    ]
    for pat in patterns:
        m = re.search(pat, text)
        if not m:
            continue
        cand = m.group(1).strip().strip('.,;:')
        cand = re.sub(r'(?i)^(?:jd|job\s*description)\s*:\s*', '', cand).strip()
        # "Cloud Engineer (AWS) – Mumbai" → keep role, drop trailing city after dash
        cand = re.sub(
            r'\s+[–—\-]\s+(?:Mumbai|Navi\s+Mumbai|Pune|Bangalore|Bengaluru|Chennai|'
            r'Hyderabad|Delhi|Noida|Gurgaon|Gurugram|Remote|India)\b.*$',
            '',
            cand,
            flags=re.I,
        ).strip()
        if cand.lower().startswith('designation'):
            continue
        if is_plausible_job_title(cand):
            return cand[:120]
    return ''


def extract_title_from_text(text: str) -> str:
    if not text:
        return ''
    kv = extract_kv_fields_from_text(text)
    if kv.get('title') and is_plausible_job_title(kv['title']):
        return kv['title'][:120]
    labeled = _title_from_labeled_line(text)
    if labeled:
        return labeled

    # Prose: "Looking for a hands-on Platform Reliability Associate to join…"
    prose = re.search(
        r'(?i)(?:looking\s+for|seeking|hiring)\s+(?:a|an)\s+'
        r'(?:hands-?on\s+|skilled\s+|experienced\s+)?'
        r'([A-Z][A-Za-z0-9][A-Za-z0-9 /&\-]{3,70}?)'
        r'\s+to\s+(?:join|lead|work|support|drive)',
        text,
    )
    if prose:
        cand = prose.group(1).strip().strip('.,;:')
        if is_plausible_job_title(cand):
            return cand[:120]

    skip_prefix = re.compile(
        r'(?i)^(company|employer|location|salary|ctc|compensation|experience|'
        r'employment|about|job\s+description|responsibilit|requirements?|skills?|'
        r'qualifications?|benefits?|what you|preferred|mandatory|notice\s*period|'
        r'primary\s*skills?|work\s*experience|employment\s*type|job\s*type|'
        r'role\s+overview|job\s+summary|overview|summary|public|confidential)\b'
    )
    # Scan deeper for multi-column / table-serialized preambles
    for line in text.split('\n')[:40]:
        stripped = re.sub(r'^[\s#*•\-–—]+', '', line.strip())
        if not stripped or len(stripped) < 3:
            continue
        if skip_prefix.match(stripped) or is_non_title_label(stripped):
            continue
        stripped = re.sub(
            r'(?i)^(?:job\s*title|position\s*title|position|title|designation|role)\s*[:\-–—]\s*',
            '',
            stripped,
        ).strip()
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
    kw = str(token).strip().strip('.,;:|')
    if len(kw) < 2 or len(kw) > 48:
        return False
    if re.search(r'[.!?]', kw):
        return False
    words = kw.split()
    if len(words) > 4:
        return False
    lower = kw.lower()
    if lower.startswith((
        'we ', 'our ', 'the ', 'a ', 'an ', 'to ', 'looking', 'seeking',
        'join ', 'lead ', 'highly', 'innovative',
    )):
        return False
    # Reject prose-y fragments
    if any(w in lower.split() for w in ('seeking', 'looking', 'join', 'team', 'lead', 'highly')):
        if len(words) >= 3:
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
