"""
Extract Resume TOON fields from unstructured resume text.
Used by the inference stage after repair, normalization, and enrichment.
"""
from __future__ import annotations

import re
from typing import Any


SKILL_SECTION_PATTERN = re.compile(
    r'(?i)(?:^|\n)\s*(?:\*\*)?(?:'
    r'technical\s+skills?|core\s+skills?|key\s+skills?|skills?|tools?|technologies?|'
    r'frameworks?|programming\s+languages?|competencies?|expertise'
    r')(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?[A-Z][^\n]{2,40}(?:\*\*)?\s*:|\Z)',
)

SUMMARY_SECTION_PATTERN = re.compile(
    r'(?i)(?:\*\*)?(?:professional\s+summary|summary|objective|profile)(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?[A-Z]|\Z)',
)


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
                r'^tools?\s*:?\s*$|^technologies?\s*:?\s*$|^competencies?\s*:?\s*$',
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


def extract_experience_from_text(text: str, max_items: int = 10) -> list[dict[str, Any]]:
    """Lightweight experience lines when structured experience is missing."""
    if not text:
        return []
    experiences: list[dict[str, Any]] = []
    block_match = re.search(
        r'(?i)(?:\*\*)?(?:work\s+experience|professional\s+experience|experience|employment)(?:\*\*)?\s*:?\s*([\s\S]*?)(?=\n\s*(?:\*\*)?(?:education|skills|projects)|\Z)',
        text,
    )
    if not block_match:
        return []
    raw = block_match.group(1) or ''
    for line in raw.split('\n'):
        stripped = re.sub(r'^[\s•·\-\*]+', '', line.strip())
        stripped = re.sub(r'^\d+[\.\)]\s*', '', stripped).strip()
        if not stripped or len(stripped) < 5:
            continue
        parts = re.split(r'\s+at\s+|\s+@\s+|,\s+', stripped, maxsplit=1)
        title = parts[0].strip() if parts else stripped
        company = parts[1].strip() if len(parts) > 1 else ''
        if title:
            experiences.append({
                'title': title[:200],
                'company': company[:200],
                'from': '',
                'to': '',
                'years': None,
                'description': '',
            })
        if len(experiences) >= max_items:
            break
    return experiences


def infer_resume_fields_from_text(text: str) -> dict[str, Any]:
    """Return partial canonical resume fragments inferable from raw text."""
    return {
        'skills': extract_skills_from_text(text),
        'summary': extract_summary_from_text(text),
        'person': {
            'email': extract_email_from_text(text),
            'phone': extract_phone_from_text(text),
        },
        'experience': extract_experience_from_text(text),
    }
