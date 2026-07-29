"""
Extract JD TOON fields from unstructured job description text.
Shared by the parse pipeline and synthetic TOON builders (ATS fallback).
"""
from __future__ import annotations

import re
from typing import Any


def _split_list_items(text: str) -> list[str]:
    """Split comma, pipe, or newline-separated prose into trimmed non-empty lines."""
    if not text or not str(text).strip():
        return []
    raw = str(text).strip()
    parts: list[str] = []
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
        if cleaned and len(cleaned) > 2:
            result.append(cleaned[:500])
    return result


def extract_skills_from_text(desc: str) -> tuple[list[str], list[str], list[str]]:
    """Return (mandatory_skills, preferred_skills, combined skills) from prose."""
    if not desc:
        return [], [], []
    mandatory_skills: list[str] = []
    preferred_skills: list[str] = []
    skills: list[str] = []

    pref_block = re.search(r'\*\*(?:Preferred|Nice-to-have|Advanced)\s*Skills?\*\*\s*([^\n*]+)', desc, re.I)
    req_block = re.search(r'\*\*(?:Required|Core|Mandatory)\s*Skills?\*\*\s*([^\n*]+)', desc, re.I)
    if req_block:
        mandatory_skills = [s.strip() for s in re.split(r'[,•·]', req_block.group(1)) if s.strip()]
    if pref_block:
        preferred_skills = [s.strip() for s in re.split(r'[,•·]', pref_block.group(1)) if s.strip()]
    if not mandatory_skills and ('**Required Skills:**' in desc or '**Skills:**' in desc):
        block = re.search(r'\*\*(?:Required )?Skills:\*\*\s*([^\n*]+)', desc, re.I)
        if block:
            skills = [s.strip() for s in re.split(r'[,•·]', block.group(1)) if s.strip()]
            mandatory_skills = skills
    if not skills and mandatory_skills:
        skills = list(mandatory_skills)
    if not skills and desc:
        for line in desc.split('\n')[:5]:
            if 'skill' in line.lower() or 'experience' in line.lower():
                parts = re.split(r'[,•·\-]', line)
                skills.extend([p.strip().strip('*') for p in parts if len(p.strip()) > 2][:15])
                break
        if skills and not mandatory_skills:
            mandatory_skills = skills
    combined = (mandatory_skills or skills)[:30]
    return mandatory_skills[:30], preferred_skills[:20], combined


def extract_responsibilities_from_text(desc: str, max_items: int = 20) -> list[str]:
    """Parse responsibilities section or fallback lines from JD prose."""
    if not desc:
        return []
    responsibilities: list[str] = []
    if '**Responsibilities:**' in desc or re.search(r'(?i)responsibilities\s*:', desc):
        block = re.search(
            r'(?:\*\*)?Responsibilities:?(?:\*\*)?\s*([\s\S]*?)(?=\n\s*(?:\*\*[A-Z]|\Z))',
            desc,
            re.I,
        )
        if block:
            raw = block.group(1)
            responsibilities = _split_list_items(raw)
    if not responsibilities:
        in_section = False
        for line in desc.split('\n'):
            stripped = line.strip()
            if re.match(r'(?i)^(?:key\s+)?responsibilities\s*:?\s*$', stripped):
                in_section = True
                continue
            if in_section:
                if re.match(r'(?i)^(?:qualifications|requirements|skills|benefits)\s*:?\s*$', stripped):
                    break
                item = re.sub(r'^[\s•·\-\*]+', '', stripped).strip()
                item = re.sub(r'^\d+[\.\)]\s*', '', item).strip()
                if item and len(item) > 3:
                    responsibilities.append(item[:500])
                    if len(responsibilities) >= max_items:
                        break
    if not responsibilities and desc:
        for line in desc.split('\n'):
            line = line.strip().strip('•').strip()
            if len(line) > 10 and not re.match(r'(?i)^(title|company|location|salary)\s*:', line):
                responsibilities.append(line[:500])
                if len(responsibilities) >= min(10, max_items):
                    break
    return responsibilities[:max_items]


def extract_qualifications_from_text(desc: str, max_items: int = 15) -> list[str]:
    if not desc:
        return []
    qualifications: list[str] = []
    if '**Qualifications:**' in desc or re.search(r'(?i)qualifications\s*:', desc):
        block = re.search(
            r'(?:\*\*)?Qualifications:?(?:\*\*)?\s*([\s\S]*?)(?=\n\s*(?:\*\*[A-Z]|\Z))',
            desc,
            re.I,
        )
        if block:
            qualifications = _split_list_items(block.group(1))
    return qualifications[:max_items]


def extract_experience_years(experience_str: str) -> tuple[Any, Any]:
    if not experience_str:
        return None, None
    nums = re.findall(r'(\d+(?:\.\d+)?)', str(experience_str))
    if len(nums) >= 2:
        return float(nums[0]), float(nums[1])
    if len(nums) == 1:
        return float(nums[0]), None
    return None, None


def extract_location_from_text(text: str) -> str:
    if not text:
        return ''
    patterns = [
        r'(?:location|work\s*location|job\s*location)\s*[:\-]\s*([^\n]+)',
        r'(?:based\s+in|office\s+location)\s+([A-Za-z][A-Za-z\s,\.\-]{2,60})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m and m.group(1):
            loc = m.group(1).strip().strip('.,;:')
            if 2 <= len(loc) <= 80:
                return loc
    return ''


def infer_jd_fields_from_text(text: str) -> dict[str, Any]:
    """Infer TOON-relevant fields from raw JD text when LLM output is incomplete."""
    desc = (text or '').strip()
    mandatory, preferred, skills = extract_skills_from_text(desc)
    return {
        'skills': skills,
        'mandatory_skills': mandatory,
        'preferred_skills': preferred,
        'responsibilities': extract_responsibilities_from_text(desc),
        'qualifications': extract_qualifications_from_text(desc),
        'location': extract_location_from_text(desc),
    }
