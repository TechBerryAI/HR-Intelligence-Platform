"""Experience-ownership evidence. Signals only — does not create job records."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.ai.document_intelligence.bullets import is_bullet_line, looks_like_list_item
from app.ai.document_intelligence.deterministic import extract_date_range
from app.ai.document_intelligence.parsers.resume import _DUTY_VERB_START, _has_job_title_cue
from app.ai.parser.layout.heuristic import normalize_section_header

_ENUM_PREFIX = re.compile(r'^(?:[A-Z]|[IVX]{1,4}|\d{1,2})[.)]\s+', re.I)
_ORG_CUE = re.compile(
    r'(?i)\b(?:ltd|inc|pvt|llc|llp|limited|gmbh|plc|corp|corporation|'
    r'solutions|technologies|consulting|consultancy|infotech|systems|'
    r'hotel|hotels|hospital|university|college)\b'
)
_CERT_CUE = re.compile(r'(?i)\b(?:certified|certificate|certification|licen[cs]e)\b')
_EDU_CUE = re.compile(
    r'(?i)\b(?:university|college|school|cgpa|gpa|ssc|hsc|10th|12th|'
    r'bachelor|master|b\.?\s*tech|b\.?\s*e\.?|m\.?\s*c\.?\s*a)\b'
)
_SUMMARY_PROSE = re.compile(
    r'(?i)\b(?:seeking|results?-driven|dedicated|motivated|aspiring|'
    r'professional\s+with|years?\s+of\s+experience|passionate|'
    r'self-driven|objective|proficient|skilled\s+in)\b'
)
_PROJECT_CUE = re.compile(
    r'(?i)^(?:projects?|academic\s+projects?|personal\s+projects?|'
    r'key\s+projects?)\s*:?\s*$'
)
_SKILL_LIST = re.compile(r'[,|/]')


@dataclass
class OwnershipScore:
    score: float = 0.0
    signals: list[str] = field(default_factory=list)

    def add(self, signal: str, weight: float) -> None:
        if signal not in self.signals:
            self.signals.append(signal)
        self.score += weight


def heading_label(line: str) -> str | None:
    """Canonical section label, including numbered 'A. Work Experience' headings."""
    raw = (line or '').strip().strip(':').strip()
    if not raw:
        return None
    stripped = _ENUM_PREFIX.sub('', raw, count=1).strip()
    return normalize_section_header(stripped) or normalize_section_header(raw)


def _lines(text: str) -> list[str]:
    return [ln.strip() for ln in (text or '').splitlines() if ln.strip()]


def score_experience_ownership(text: str) -> OwnershipScore:
    """How strongly a blob belongs to Experience (not a parser)."""
    lines = _lines(text)
    out = OwnershipScore()
    if not lines:
        return out
    n = len(lines)
    date_hits = 0
    title_hits = 0
    org_hits = 0
    duty_hits = 0
    nested_heading = False
    for ln in lines:
        if heading_label(ln) == 'Experience':
            nested_heading = True
        start, _end = extract_date_range(ln)
        if start:
            date_hits += 1
        if _has_job_title_cue(ln):
            title_hits += 1
        if _ORG_CUE.search(ln):
            org_hits += 1
        if (
            is_bullet_line(ln)
            or looks_like_list_item(ln)
            or _DUTY_VERB_START.match(ln)
        ):
            duty_hits += 1
    if nested_heading:
        out.add('experience_heading', 0.35)
    if date_hits >= 2:
        out.add('employment_date_density', 0.25)
    elif date_hits == 1:
        out.add('employment_date_density', 0.12)
    if title_hits >= 1:
        out.add('role_pattern_density', 0.15)
    if org_hits >= 1:
        out.add('employer_pattern_density', 0.12)
    if duty_hits >= 2 and duty_hits / n >= 0.2:
        out.add('duty_density', 0.12)
    if date_hits >= 1 and title_hits >= 1:
        out.add('paired_title_date', 0.18)
    if date_hits >= 1 and title_hits >= 1 and (org_hits >= 1 or duty_hits >= 2):
        out.add('record_structure', 0.08)
    if n >= 4 and date_hits >= 2 and title_hits >= 1:
        out.add('repeated_record_format', 0.08)

    cert_hits = sum(1 for ln in lines if _CERT_CUE.search(ln))
    edu_hits = sum(1 for ln in lines if _EDU_CUE.search(ln) and not start_on(ln))
    skillish = sum(
        1
        for ln in lines
        if _SKILL_LIST.search(ln) and len(ln.split()) <= 12 and not extract_date_range(ln)[0]
    )
    if cert_hits >= 2 and date_hits == 0 and title_hits == 0:
        out.score -= 0.28
        out.signals.append('certification_like')
    if edu_hits >= 3 and date_hits <= 1 and title_hits == 0:
        out.score -= 0.22
        out.signals.append('education_like')
    if skillish >= max(3, n // 2) and date_hits == 0:
        out.score -= 0.30
        out.signals.append('skill_list_like')
    out.score = max(0.0, min(1.0, out.score))
    return out


def start_on(line: str) -> bool:
    return bool(extract_date_range(line)[0])


def score_native_label(text: str, label: str) -> float:
    """How well the blob matches its current section label."""
    lines = _lines(text)
    if not lines:
        return 0.0
    n = len(lines)
    key = (label or '').strip().lower()
    if key == 'summary':
        prose = sum(1 for ln in lines if _SUMMARY_PROSE.search(ln))
        dates = sum(1 for ln in lines if extract_date_range(ln)[0])
        return min(1.0, prose / max(n, 1) * 1.4) - min(0.4, dates * 0.08)
    if key in {'projects', 'project'}:
        heads = sum(1 for ln in lines if _PROJECT_CUE.match(ln) or heading_label(ln) == 'Projects')
        dates = sum(1 for ln in lines if extract_date_range(ln)[0])
        titles = sum(1 for ln in lines if _has_job_title_cue(ln))
        if dates >= 2 and titles >= 1:
            return 0.15
        return min(1.0, 0.2 + heads * 0.2 + (0.3 if dates == 0 else 0.0))
    if key in {'certifications', 'certificates'}:
        certs = sum(1 for ln in lines if _CERT_CUE.search(ln))
        dates = sum(1 for ln in lines if extract_date_range(ln)[0])
        titles = sum(1 for ln in lines if _has_job_title_cue(ln))
        if dates >= 2 and titles >= 1:
            return 0.1
        return min(1.0, certs / max(n, 1) * 1.5)
    if key == 'languages':
        spoken = sum(
            1
            for ln in lines
            if re.search(
                r'(?i)\b(?:english|hindi|marathi|tamil|telugu|kannada|french|german)\b',
                ln,
            )
        )
        return spoken / max(n, 1)
    if key in {'skills', 'technical skills'}:
        skillish = sum(
            1
            for ln in lines
            if (',' in ln or '/' in ln)
            and len(ln.split()) <= 12
            and not extract_date_range(ln)[0]
            and not _has_job_title_cue(ln)
        )
        dates = sum(1 for ln in lines if extract_date_range(ln)[0])
        titles = sum(1 for ln in lines if _has_job_title_cue(ln))
        if dates >= 1 and titles >= 1:
            return 0.1
        return min(1.0, skillish / max(n, 1) * 1.4)
    return 0.0


def is_summary_prose_line(line: str) -> bool:
    s = (line or '').strip()
    if not s or extract_date_range(s)[0]:
        return False
    if heading_label(s):
        return False
    return bool(_SUMMARY_PROSE.search(s)) or (len(s.split()) >= 12 and s[0].isupper())


def is_employment_record_start(line: str, nxt: str = '') -> bool:
    s = (line or '').strip()
    if not s or heading_label(s) in {'Education', 'Skills', 'Summary', 'Projects', 'Certifications'}:
        return False
    if heading_label(s) == 'Experience':
        return True
    if extract_date_range(s)[0] and (
        _has_job_title_cue(s) or _ORG_CUE.search(s) or len(s.split()) <= 8
    ):
        return True
    if _has_job_title_cue(s) and not _DUTY_VERB_START.match(s) and len(s.split()) <= 10:
        return True
    if _ORG_CUE.search(s) and 1 <= len(s.split()) <= 10 and not _DUTY_VERB_START.match(s):
        return True
    follow = (nxt or '').strip()
    if (
        follow
        and 2 <= len(s.split()) <= 8
        and s[0].isupper()
        and not _DUTY_VERB_START.match(s)
        and not s.endswith('.')
        and (
            extract_date_range(follow)[0]
            or (
                _has_job_title_cue(follow)
                and not _DUTY_VERB_START.match(follow)
            )
        )
    ):
        return True
    return False


def is_duty_or_continuation(line: str) -> bool:
    s = (line or '').strip()
    if not s:
        return False
    if heading_label(s):
        return False
    if is_bullet_line(s) or looks_like_list_item(s) or _DUTY_VERB_START.match(s):
        return True
    if extract_date_range(s)[0] or _has_job_title_cue(s) or _ORG_CUE.search(s):
        return True
    if s[:1].islower() and len(s.split()) >= 4:
        return True
    return False
