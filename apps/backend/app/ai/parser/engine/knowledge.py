"""Knowledge resolution — canonicalize skills/titles/degrees/locations/companies."""
from __future__ import annotations

import json
import logging
import threading
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

_LOCK = threading.RLock()

# Built-in fallbacks when knowledge aliases.json is empty (common HR terms)
_BUILTIN_SKILLS = {
    'js': 'JavaScript',
    'javascript': 'JavaScript',
    'ts': 'TypeScript',
    'typescript': 'TypeScript',
    'py': 'Python',
    'python': 'Python',
    'react.js': 'React',
    'reactjs': 'React',
    'node': 'Node.js',
    'nodejs': 'Node.js',
    'node.js': 'Node.js',
    'k8s': 'Kubernetes',
    'postgres': 'PostgreSQL',
    'postgresql': 'PostgreSQL',
    'mongo': 'MongoDB',
    'mongodb': 'MongoDB',
    'aws': 'Amazon Web Services',
    'amazon web services': 'Amazon Web Services',
    'gcp': 'Google Cloud Platform',
    'google cloud platform': 'Google Cloud Platform',
    'ml': 'Machine Learning',
    'ai': 'Artificial Intelligence',
    'nlp': 'Natural Language Processing',
    'ci/cd': 'CI/CD',
    'rest api': 'REST API',
    'restful': 'REST API',
}

_BUILTIN_DEGREES = {
    'b.tech': 'Bachelor of Technology',
    'btech': 'Bachelor of Technology',
    'b.e': 'Bachelor of Engineering',
    'be': 'Bachelor of Engineering',
    'b.e.': 'Bachelor of Engineering',
    'm.tech': 'Master of Technology',
    'mtech': 'Master of Technology',
    'bsc': 'Bachelor of Science',
    'b.sc': 'Bachelor of Science',
    'msc': 'Master of Science',
    'm.sc': 'Master of Science',
    'mba': 'Master of Business Administration',
    'bca': 'Bachelor of Computer Applications',
    'mca': 'Master of Computer Applications',
}

_BUILTIN_TITLES = {
    'sde': 'Software Development Engineer',
    'sde1': 'Software Development Engineer I',
    'sde2': 'Software Development Engineer II',
    'swe': 'Software Engineer',
    'se': 'Software Engineer',
    'fullstack': 'Full Stack Developer',
    'full-stack': 'Full Stack Developer',
    'full stack': 'Full Stack Developer',
    'frontend': 'Frontend Developer',
    'front-end': 'Frontend Developer',
    'backend': 'Backend Developer',
    'back-end': 'Backend Developer',
    'devops': 'DevOps Engineer',
    'ml engineer': 'Machine Learning Engineer',
}


def _knowledge_root() -> Path:
    try:
        from packages.knowledge import KNOWLEDGE_DIR

        return Path(KNOWLEDGE_DIR)
    except Exception:
        # apps/backend/app/ai/parser/engine/knowledge.py → repo root
        return Path(__file__).resolve().parents[6] / 'ai' / 'knowledge'


def _load_alias_map(domain: str) -> dict[str, tuple[str, Optional[str]]]:
    """
    Return lowercase alias → (canonical_display, canonical_id).
    Supports aliases.json entries as:
      {"alias": "...", "canonical": "...", "id": "..."}
      or {"from": "...", "to": "..."}
    """
    path = _knowledge_root() / domain / 'aliases.json'
    mapping: dict[str, tuple[str, Optional[str]]] = {}
    if not path.is_file():
        return mapping
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
    except Exception as exc:
        logger.warning('Failed to load knowledge %s: %s', path, exc)
        return mapping

    entries = data.get('aliases') if isinstance(data, dict) else data
    if not isinstance(entries, list):
        return mapping

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        alias = entry.get('alias') or entry.get('from') or entry.get('name')
        canonical = (
            entry.get('canonical')
            or entry.get('to')
            or entry.get('canonical_name')
            or entry.get('display')
        )
        cid = entry.get('id') or entry.get('canonical_id')
        if not alias or not canonical:
            continue
        mapping[str(alias).strip().lower()] = (str(canonical).strip(), str(cid) if cid else None)
    return mapping


@lru_cache(maxsize=8)
def _domain_map(domain: str) -> dict[str, tuple[str, Optional[str]]]:
    with _LOCK:
        file_map = _load_alias_map(domain)
        builtins: dict[str, tuple[str, Optional[str]]] = {}
        if domain == 'skills':
            builtins = {k: (v, None) for k, v in _BUILTIN_SKILLS.items()}
        elif domain == 'degrees':
            builtins = {k: (v, None) for k, v in _BUILTIN_DEGREES.items()}
        elif domain == 'job_titles':
            builtins = {k: (v, None) for k, v in _BUILTIN_TITLES.items()}
        # File aliases override builtins; index canonical display for reverse lookup
        merged = {**builtins, **file_map}
        extra: dict[str, tuple[str, Optional[str]]] = {}
        for _alias, pair in merged.items():
            display = (pair[0] or '').strip().lower()
            if display and display not in merged:
                extra[display] = pair
        return {**merged, **extra}


def normalize_skill(value: str) -> tuple[str, Optional[str]]:
    """Return (display, canonical_id). Uses knowledge + builtins."""
    raw = (value or '').strip()
    if not raw:
        return '', None
    key = raw.lower()
    mapping = _domain_map('skills')
    if key in mapping:
        return mapping[key]
    # Soft match without punctuation
    compact = key.replace('.', '').replace(' ', '')
    for alias, pair in mapping.items():
        if alias.replace('.', '').replace(' ', '') == compact:
            return pair
    return raw, None


def canonical_skill_key(value: str) -> str:
    """Stable compare key so AWS and Amazon Web Services match."""
    display, _cid = normalize_skill(value)
    return (display or value or '').strip().lower()


def skill_values_equivalent(left: str, right: str) -> bool:
    """True when two skill labels are the same alias or the same canonical name."""
    a, b = (left or '').strip(), (right or '').strip()
    if not a or not b:
        return a.lower() == b.lower()
    if a.lower() == b.lower():
        return True
    return canonical_skill_key(a) == canonical_skill_key(b)


def skill_csv_equivalent(expected: str, actual: str) -> bool:
    """Compare comma-separated skill lists using alias-aware equality (order preserved)."""
    exp = [p.strip() for p in (expected or '').split(',') if p.strip()]
    act = [p.strip() for p in (actual or '').split(',') if p.strip()]
    if len(exp) != len(act):
        return False
    return all(skill_values_equivalent(e, a) for e, a in zip(exp, act))


def normalize_job_title(value: str) -> tuple[str, Optional[str]]:
    raw = (value or '').strip()
    if not raw:
        return '', None
    key = raw.lower()
    mapping = _domain_map('job_titles')
    if key in mapping:
        return mapping[key]
    return raw, None


def normalize_degree(value: str) -> tuple[str, Optional[str]]:
    raw = (value or '').strip()
    if not raw:
        return '', None
    key = raw.lower().replace(' ', '')
    mapping = _domain_map('degrees')
    # Try exact and compact keys
    for alias, pair in mapping.items():
        if alias.replace(' ', '') == key or alias == raw.lower():
            return pair
    return raw, None


def normalize_location(value: str) -> tuple[str, Optional[str]]:
    raw = (value or '').strip()
    if not raw:
        return '', None
    mapping = _domain_map('locations')
    key = raw.lower()
    if key in mapping:
        return mapping[key]
    return raw, None


def normalize_company(value: str) -> tuple[str, Optional[str]]:
    raw = (value or '').strip()
    if not raw:
        return '', None
    mapping = _domain_map('companies')
    key = raw.lower()
    if key in mapping:
        return mapping[key]
    return raw, None


def apply_knowledge_to_resume(toon: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize resume TOON fields in-place; attach optional _knowledge map."""
    if not isinstance(toon, dict):
        return toon
    knowledge: dict[str, Any] = {}

    skills = toon.get('skills')
    if isinstance(skills, list):
        new_skills: list[str] = []
        skill_ids: list[Optional[str]] = []
        for s in skills:
            name = s.get('name') if isinstance(s, dict) else str(s or '')
            display, cid = normalize_skill(str(name))
            if display:
                new_skills.append(display)
                skill_ids.append(cid)
        toon['skills'] = new_skills
        if any(skill_ids):
            knowledge['skill_ids'] = skill_ids

    experience = toon.get('experience')
    if isinstance(experience, list):
        for exp in experience:
            if not isinstance(exp, dict):
                continue
            title = str(exp.get('title') or exp.get('role') or '')
            if title:
                display, _ = normalize_job_title(title)
                if display:
                    exp['title'] = display
            company = str(exp.get('company') or '')
            if company:
                display, _ = normalize_company(company)
                if display:
                    exp['company'] = display

    education = toon.get('education')
    if isinstance(education, list):
        for edu in education:
            if not isinstance(edu, dict):
                continue
            degree = str(edu.get('degree') or '')
            if degree:
                display, _ = normalize_degree(degree)
                if display:
                    edu['degree'] = display

    person = toon.get('person') if isinstance(toon.get('person'), dict) else None
    if person:
        loc = str(person.get('location') or '')
        if loc:
            display, _ = normalize_location(loc)
            if display:
                person['location'] = display

    if knowledge:
        toon['_knowledge'] = knowledge
    return toon


def apply_knowledge_to_jd(toon: dict[str, Any]) -> dict[str, Any]:
    """Canonicalize JD skill lists and title/location/company."""
    if not isinstance(toon, dict):
        return toon

    for key in ('skills', 'mandatory_skills', 'preferred_skills'):
        vals = toon.get(key)
        if isinstance(vals, list):
            toon[key] = [normalize_skill(str(s))[0] for s in vals if str(s or '').strip()]

    title = str(toon.get('title') or '')
    if title:
        toon['title'] = normalize_job_title(title)[0]
    company = str(toon.get('company') or '')
    if company:
        toon['company'] = normalize_company(company)[0]
    location = str(toon.get('location') or '')
    if location:
        toon['location'] = normalize_location(location)[0]
    return toon


def clear_knowledge_cache() -> None:
    _domain_map.cache_clear()
