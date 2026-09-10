"""Source-grounded scoring and A/B/C/D classification. Eval-only — not parser rules."""
from __future__ import annotations

import re
from typing import Any

from ai.eval.apply_public_eval.trace import (
    apply_coverage_gaps,
    cluster_issues,
    field_trace_verdicts,
    rank_training_backlog,
)

CLASS_A = 'A'  # extraction/layout
CLASS_B = 'B'  # parser
CLASS_C = 'C'  # source ambiguity
CLASS_D = 'D'  # API/UI

FIELD_KEYS = (
    'name',
    'email',
    'phone',
    'location',
    'linkedin',
    'experience',
    'company',
    'role',
    'start',
    'end',
    'isCurrent',
    'description',
    'education',
    'degree',
    'institution',
    'edu_start',
    'edu_end',
    'skills',
    'summary',
    'certifications',
)

_JOB_TITLE = re.compile(
    r'(?i)\b(?:engineer|developer|administrator|associate|analyst|manager|'
    r'intern|consultant|officer|executive|specialist|architect)\b',
)
_DATE_HINT = re.compile(
    r'(?i)\b(?:20\d{2}|19\d{2}|jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|'
    r'may|jun(?:e)?|jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|'
    r'nov(?:ember)?|dec(?:ember)?|present|till\s*date|current)\b',
)
_COMPANY_CUE = re.compile(
    r'(?i)(?:company(?:\s+name)?|organization|organisation|client|employer)\s*:|'
    r'\b(?:pvt\.?\s*ltd|llc|inc\.?|llp|limited)\b|'
    r'\bat\s+[A-Z][A-Za-z0-9&.\' -]{2,40}',
)
# Do not match bare "me"/"be"/"ma"/"ba" (prose pronouns / words).
# Require dotted abbreviations (B.E., M.A.) or full degree words / B-Tech forms.
_DEGREE_CUE = re.compile(
    r'(?i)(?:'
    r'\b(?:bachelors?|masters?|doctorate|diploma|degree|phd|mba|hsc|ssc)\b|'
    r'\bb\.?\s*-?\s*tech\b|\bm\.?\s*-?\s*tech\b|\bbtech\b|\bmtech\b|'
    r'\bb\.?\s*com\b|\bm\.?\s*com\b|\bb\.?\s*sc\b|\bm\.?\s*sc\b|'
    r'\bb\.\s*e\.?\b|\bm\.\s*e\.?\b|\bb\.\s*a\.?\b|\bm\.\s*a\.?\b|'
    r'\bb\.e\b|\bm\.e\b|\bb\.a\b|\bm\.a\b'
    r')',
)
_INST_CUE = re.compile(
    r'(?i)\b(?:university|college|institute|school|board)\b',
)
_SKILLS_HEAD = re.compile(r'(?im)^.{0,40}\bskills?\b',)
_SUMMARY_HEAD = re.compile(r'(?im)^.{0,40}\b(?:summary|objective|profile|synopsis)\b')
_EMAIL = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.I)
_PHONE = re.compile(r'(?:\+91[\s-]?)?[6-9]\d{9}|\b\d{10}\b')
_LINKEDIN = re.compile(r'(?i)linkedin\.com')
# Legacy broad cue kept for diagnostics only — scoring uses
# extract_has_candidate_location_evidence() (candidate-owned evidence).
_LOC_CUE = re.compile(
    r'(?i)\b(?:location|address|city|mumbai|pune|bengaluru|bangalore|'
    r'hyderabad|delhi|chennai|noida|gurgaon|gurugram|kolkata|remote)\b',
)
_CANDIDATE_LOC_LABEL = re.compile(
    r'(?i)(?:'
    r'\b(?:(?:permanent|present|current|residential|correspondence|mailing)\s+address|'
    r'current\s+location|native\s+place|home\s*town)\b|'
    r'\b(?:location|address|city|residence|place)\s*[:\-–—]|'
    r'\bbased\s+in\b\s*[:\-–—]?|\bresiding\s+(?:in|at)\b|\blives?\s+in\b'
    r')'
)
_CONTACT_TRAILING_PLACE = re.compile(
    r'(?i)(?:'
    r'[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}'
    r'|(?:\+?\d[\d\s\-().]{7,}\d)'
    r'|linkedin'
    r')'
    r'[^\n|]*\|\s*'
    r'([A-Za-z][A-Za-z .]{1,35})\s*[–—\-?,/]\s*'
    r'([A-Za-z][A-Za-z .]{1,35})\s*$'
)
_STREET_ADDRESS_CUE = re.compile(
    r'(?i)\b(?:road|street|cross\s+road|nagar|colony|apartment|sector|'
    r'flat\s*no|plot\s*no|at\.?\s*post|tal\.?|dist\.?|district|pin(?:code)?)\b'
)
_CERT_HEAD = re.compile(r'(?im)^.{0,40}\b(?:certifications?|certificates?)\b')
_DUTY_CUE = re.compile(
    r'(?i)\b(?:responsible for|developed|managed|implemented|supported|built|'
    r'designed|configured|maintained|administered)\b',
)
_EMPLOYMENT_PROSE_LINE = re.compile(
    r'(?i)^(?:\d+(?:\.\d+)?\+?\s*(?:yrs?|years?)\.?\s+(?:of\s+)?)?'
    r'(?:currently\s+)?'
    r'(?:working|worked|work)\s+(?:as|for|with|at)\b'
)
_PROSE_SKILL = re.compile(
    r'(?i)\b(?:i am responsible|project description|secured a training|'
    r'developed and implemented|business critical processes)\b',
)
_YEAR_PHRASE = re.compile(r'(?i)\b(?:in the year|year of passing)\b')


def _norm(v: Any) -> str:
    return re.sub(r'\s+', ' ', str(v or '')).strip()


def _fold(v: Any) -> str:
    return _norm(v).casefold()


def _employment_date_haystack(extract: str) -> str:
    """Ignore education/certification timelines when scoring employment dates."""
    text = extract or ''
    return re.sub(
        r'(?is)(?:^|\n)\s*(?:education|academic(?:\s+details)?|qualifications?|'
        r'educational\s+(?:qualification|background)s?|'
        r'certifications?|certificates?|licenses?|'
        r'publications?|awards?|achievements?)\b.*?'
        r'(?=\n\s*(?:experience|employment|work\s+history|professional\s+experience|'
        r'skills|projects?|summary|objective)\b|\Z)',
        '\n',
        text,
    )


def slim_form(form: dict | None) -> dict[str, Any]:
    form = form or {}
    experiences = [
        {
            'company': _norm(e.get('company')),
            'role': _norm(e.get('role')),
            'start': _norm(e.get('startMonth') or e.get('start')),
            'end': _norm(e.get('endMonth') or e.get('end')),
            'isCurrent': bool(e.get('isCurrent') if 'isCurrent' in e else e.get('is_current')),
            'description': _norm(e.get('description')),
        }
        for e in (form.get('experiences') or form.get('experience') or [])
        if isinstance(e, dict)
    ]
    education = [
        {
            'degree': _norm(e.get('degree')),
            'institution': _norm(e.get('institution')),
            'start': _norm(e.get('startMonth') or e.get('start')),
            'end': _norm(e.get('endMonth') or e.get('end')),
        }
        for e in (form.get('education') or [])
        if isinstance(e, dict)
    ]
    skills = form.get('skills')
    if isinstance(skills, list):
        skills_s = ', '.join(_norm(s) for s in skills if _norm(s))
    else:
        skills_s = _norm(skills)
    certifications = [
        {
            'name': _norm(c.get('name')),
            'issuer': _norm(c.get('issuer')),
        }
        for c in (form.get('certifications') or [])
        if isinstance(c, dict) and (_norm(c.get('name')) or _norm(c.get('issuer')))
    ]
    return {
        'name': _norm(form.get('fullName') or form.get('name')),
        'email': _norm(form.get('email')),
        'phone': _norm(form.get('phone')),
        'location': _norm(form.get('currentLocation') or form.get('preferredLocation')),
        'preferredLocation': _norm(form.get('preferredLocation')),
        'linkedin': _norm(form.get('linkedinUrl') or form.get('linkedin')),
        'experiences': experiences,
        'education': education,
        'skills': skills_s,
        'summary': _norm(form.get('summary')),
        'certifications': certifications,
    }


def extract_has_candidate_location_evidence(extract: str) -> bool:
    """True only for candidate-owned location/address evidence.

    Employer / job / education / project cities and bare tech ``remote``
    (e.g. ``Server Remote Utilities``) do not count. Empty Location with
    only those cues → scorer ``n/a``, not a parser failure.
    """
    text = extract or ''
    if not text.strip():
        return False
    # Labeled rows must carry a non-empty value (ignore bare "Place:" / "Location:")
    for m in re.finditer(
        r'(?im)^(?:\*\*)?(?:(?:permanent|present|current|residential|correspondence|mailing)\s+)?'
        r'(?:location|address|city|residence|place)\s*[:\-–—]\s*(.*?)\s*$',
        text,
    ):
        val = (m.group(1) or '').strip().strip('.,;')
        if len(val) >= 2 and not re.match(r'(?i)^(date|name|signature)\b', val):
            return True
    if re.search(
        r'(?i)\b(?:(?:permanent|present|current|residential|correspondence|mailing)\s+address|'
        r'current\s+location|native\s+place|home\s*town)\b\s*[:\-–—]\s*\S',
        text,
    ):
        return True
    if re.search(
        r'(?i)(?:location|based\s+in|work\s+(?:mode|location)|preferred\s+location)'
        r'\s*[:\-–—]\s*(?:remote|hybrid|wfh|work\s+from\s+home)\b',
        text,
    ):
        return True
    if re.search(
        r'(?i)\bbased\s+in\b\s*[:\-–—]?\s*[A-Za-z]|\bresiding\s+(?:in|at)\b\s+[A-Za-z]|'
        r'\blives?\s+in\b\s+[A-Za-z]',
        text,
    ):
        return True
    header = '\n'.join(text.splitlines()[:30])
    if _CONTACT_TRAILING_PLACE.search(header):
        return True
    for ln in header.splitlines():
        s = ln.strip()
        if not s or len(s) > 120:
            continue
        if re.search(r'(?i)\b(?:worked|working|company|employer|client|project|'
                     r'university|college|institute|organization|organisation)\b', s):
            continue
        if _STREET_ADDRESS_CUE.search(s) and re.search(
            r'(?i)\b[A-Z][a-zA-Z]{2,}(?:\s*,\s*[A-Z][a-zA-Z .]+)?\b',
            s,
        ):
            return True
    return False


def source_support(extract: str) -> dict[str, bool]:
    text = extract or ''
    return {
        'name': bool(_EMAIL.search(text) or re.search(r'(?m)^[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+){1,3}\s*$', text[:800])),
        'email': bool(_EMAIL.search(text)),
        'phone': bool(_PHONE.search(text)),
        'location': extract_has_candidate_location_evidence(text),
        'linkedin': bool(_LINKEDIN.search(text)),
        'experience': bool(_JOB_TITLE.search(text) and _DATE_HINT.search(text)),
        'company': bool(_COMPANY_CUE.search(text)),
        'role': bool(_JOB_TITLE.search(text)),
        'dates': bool(_DATE_HINT.search(text)),
        'education': bool(_DEGREE_CUE.search(text) or _INST_CUE.search(text)),
        'degree': bool(_DEGREE_CUE.search(text)),
        'institution': bool(_INST_CUE.search(text)),
        'skills': bool(_SKILLS_HEAD.search(text)),
        'summary': bool(_SUMMARY_HEAD.search(text)),
        'certifications': bool(_CERT_HEAD.search(text)),
        # Global cue kept for diagnostics; description scoring uses
        # experience_has_duty_evidence() (Experience-section scoped).
        'description': experience_has_duty_evidence(text),
    }


def experience_section_text(extract: str) -> str:
    """Return the Experience / Employment body from a resume extract, if any."""
    text = extract or ''
    lines = text.splitlines()
    start = None
    for i, ln in enumerate(lines):
        probe = ln.strip().rstrip(':').strip()
        if not probe:
            continue
        if re.match(
            r'(?i)^(?:professional\s+)?(?:work\s+)?experiences?$|'
            r'^employment(?:\s+history)?$|^work\s+history$|^career\s+history$|'
            r'^internship(?:\s+experience)?$',
            probe,
        ):
            start = i + 1
            break
    if start is None:
        return ''
    out: list[str] = []
    for ln in lines[start:]:
        probe = ln.strip().rstrip(':').strip()
        if probe and re.match(
            r'(?i)^(?:education|academic|skills?|certifications?|'
            r'certificates?|summary|objective|declaration|hobbies|languages?|'
            r'achievements?|awards|personal\s+details|'
            r'technical\s+(?:skills?|proficiency))\b',
            probe,
        ):
            break
        # Bare Projects section only — not nested "Project 1 | Title" under Experience.
        if re.match(r'(?i)^(?:key\s+)?projects?\s*:?\s*$', probe):
            break
        out.append(ln)
    return '\n'.join(out)


def experience_has_duty_evidence(extract: str) -> bool:
    """True when the Experience section itself contains duty bullets/prose.

    Employment sentences (``Working as ROLE for COMPANY``) and Project-only
    sections elsewhere do not count. Header-only Experience → False → n/a.
    """
    exp = experience_section_text(extract)
    if not exp.strip():
        # No labeled Experience span — fall back carefully: only bullet lines
        # that look like duties near job titles (avoid Project/Skills dumps).
        return False
    for ln in exp.splitlines():
        s = ln.strip()
        if not s or len(s) < 8:
            continue
        if _EMPLOYMENT_PROSE_LINE.match(s):
            continue
        if re.match(r'(?i)^(?:role|title|designation|position|company|employer|duration|period)\s*:', s):
            continue
        if re.match(r'(?i)^(?:key\s+)?projects?\s*(?:#|no\.?\s*)?\d*\b', s):
            continue
        if s[:1] in '•·*-●▪▸►' or re.match(r'^\d{1,2}[.)]\s+\S', s):
            body = re.sub(r'^[\s•·\-\*●▪▸►\d.)]+', '', s).strip()
            if len(body) >= 8 and not _EMPLOYMENT_PROSE_LINE.match(body):
                return True
        if _DUTY_CUE.search(s) and not _EMPLOYMENT_PROSE_LINE.match(s):
            return True
    return False


def _values_close(a: str, b: str) -> bool:
    fa, fb = _fold(a), _fold(b)
    if fa == fb:
        return True
    if not fa or not fb:
        return not fa and not fb
    if fa in fb or fb in fa:
        return min(len(fa), len(fb)) >= 4
    at, bt = set(re.findall(r'[a-z0-9]{3,}', fa)), set(re.findall(r'[a-z0-9]{3,}', fb))
    if at and bt:
        return len(at & bt) / max(1, min(len(at), len(bt))) >= 0.6
    return False


def json_expected_blob(ref: dict, key: str) -> str:
    if key == 'name':
        return ref.get('name') or ''
    if key in ('email', 'phone', 'location', 'linkedin'):
        return ref.get(key) or ''
    if key in ('company', 'role', 'start', 'end'):
        rows = ref.get('experiences') or []
        return (rows[0].get(key) if rows else '') or ''
    if key == 'isCurrent':
        return ''
    if key in ('degree', 'institution'):
        rows = ref.get('education') or []
        return (rows[0].get(key) if rows else '') or ''
    if key == 'edu_start':
        rows = ref.get('education') or []
        return (rows[0].get('start') if rows else '') or ''
    if key == 'edu_end':
        rows = ref.get('education') or []
        return (rows[0].get('end') if rows else '') or ''
    if key == 'skills':
        return ref.get('skills') or ''
    if key == 'summary':
        return (ref.get('summary') or '')[:80]
    return ''


def _skill_tokens(s: str) -> list[str]:
    return [p.strip().casefold() for p in re.split(r'[,|;]', s or '') if p.strip()]


def compare_forms(actual: dict, expected: dict) -> dict[str, bool]:
    a, e = slim_form(actual), slim_form(expected)
    out: dict[str, bool] = {}
    out['name'] = _values_close(a['name'], e['name'])
    for k in ('email', 'phone', 'location', 'linkedin'):
        out[k] = True if not e.get(k) else _values_close(a.get(k, ''), e.get(k, ''))
    out['experience'] = bool(a['experiences']) == bool(e['experiences']) or (
        len(a['experiences']) >= 1 and len(e['experiences']) >= 1
    )
    ae = a['experiences'][:1]
    ee = e['experiences'][:1]
    if ee:
        row_a = ae[0] if ae else {}
        row_e = ee[0]
        out['company'] = _values_close(row_a.get('company', ''), row_e.get('company', '')) or (
            not row_e.get('company') and not row_a.get('company')
        )
        out['role'] = _values_close(row_a.get('role', ''), row_e.get('role', ''))
        out['start'] = _values_close(row_a.get('start', ''), row_e.get('start', '')) or (
            (row_a.get('start') or '')[:4] == (row_e.get('start') or '')[:4]
            and bool((row_e.get('start') or '')[:4])
        )
        out['end'] = _values_close(row_a.get('end', ''), row_e.get('end', '')) or (
            bool(row_a.get('isCurrent')) and _fold(row_e.get('end')) in ('', 'present')
        )
        out['isCurrent'] = bool(row_a.get('isCurrent')) == bool(row_e.get('isCurrent')) or (
            bool(row_a.get('isCurrent')) and _fold(row_e.get('end')) in ('present', 'current', '')
        )
    else:
        for k in ('company', 'role', 'start', 'end', 'isCurrent'):
            out[k] = True
    out['education'] = bool(a['education']) == bool(e['education']) or (
        len(a['education']) >= 1 and len(e['education']) >= 1
    )
    ad = a['education'][:1]
    ed = e['education'][:1]
    if ed:
        row_a = ad[0] if ad else {}
        row_e = ed[0]
        out['degree'] = _values_close(row_a.get('degree', ''), row_e.get('degree', '')) or (
            not row_e.get('degree') and not row_a.get('degree')
        )
        out['institution'] = _values_close(row_a.get('institution', ''), row_e.get('institution', ''))
        out['edu_start'] = True if not row_e.get('start') else _values_close(
            row_a.get('start', ''), row_e.get('start', ''),
        )
        out['edu_end'] = True if not row_e.get('end') else (
            _values_close(row_a.get('end', ''), row_e.get('end', ''))
            or (row_a.get('end') or '')[:4] == (row_e.get('end') or '')[:4]
        )
    else:
        for k in ('degree', 'institution', 'edu_start', 'edu_end'):
            out[k] = True
    a_sk, e_sk = set(_skill_tokens(a['skills'])), set(_skill_tokens(e['skills']))
    if e_sk:
        out['skills'] = len(a_sk & e_sk) / max(1, len(e_sk)) >= 0.5
    else:
        out['skills'] = True
    out['summary'] = (not e['summary']) or _values_close(a['summary'][:80], e['summary'][:80])
    if e.get('certifications'):
        out['certifications'] = bool(a.get('certifications'))
    else:
        out['certifications'] = True
    return out


def _form_vs_inproc_mismatch(http: dict, inproc: dict) -> bool:
    h, p = slim_form(http), slim_form(inproc)
    if _fold(h['name']) != _fold(p['name']):
        return True
    if [(x.get('company'), x.get('role'), x.get('start')) for x in h['experiences']] != [
        (x.get('company'), x.get('role'), x.get('start')) for x in p['experiences']
    ]:
        return True
    if [(x.get('degree'), x.get('institution'), x.get('end')) for x in h['education']] != [
        (x.get('degree'), x.get('institution'), x.get('end')) for x in p['education']
    ]:
        return True
    if _fold(h['skills']) != _fold(p['skills']):
        return True
    for k in ('email', 'phone', 'location', 'linkedin'):
        if _fold(h.get(k)) != _fold(p.get(k)):
            return True
    return False


def evaluate_case(
    *,
    form: dict,
    extract: str,
    http_status: int,
    inproc_form: dict | None = None,
    reference: dict | None = None,
    extract_short: bool | None = None,
    coverage: list[dict] | None = None,
) -> dict[str, Any]:
    """Score one Apply Form DTO. Missing source evidence is not a parser failure."""
    slim = slim_form(form)
    support = source_support(extract)
    issues: list[dict[str, str]] = []
    field_ok: dict[str, str] = {k: 'n/a' for k in FIELD_KEYS}
    short = bool(extract_short) or len((extract or '').strip()) < 40
    coverage_rows = coverage if coverage is not None else (
        form.get('coverage') if isinstance(form, dict) else None
    )

    if http_status == 429:
        issues.append({'class': CLASS_D, 'field': '*', 'reason': 'rate_limited'})
    elif http_status != 200 or not form:
        issues.append({'class': CLASS_D, 'field': '*', 'reason': f'http_{http_status}'})

    if inproc_form is not None and http_status == 200 and form and not short:
        if _form_vs_inproc_mismatch(form, inproc_form):
            issues.append({
                'class': CLASS_D,
                'field': '*',
                'reason': 'http_form_dto_mismatch_vs_inprocess',
            })

    if short and http_status == 200:
        issues.append({'class': CLASS_A, 'field': '*', 'reason': 'extract_too_short'})

    hay = (extract or '').casefold()

    def mark(field: str, status: str) -> None:
        field_ok[field] = status

    # --- Name ---
    if reference and _norm((reference.get('fullName') or reference.get('name'))):
        mark('name', 'pass' if _values_close(slim['name'], slim_form(reference)['name']) else 'fail')
        if field_ok['name'] == 'fail':
            expected = slim_form(reference)['name']
            cls = CLASS_A if expected.casefold() not in hay and not all(
                t in hay for t in expected.casefold().split()[:2]
            ) else CLASS_B
            issues.append({'class': cls, 'field': 'name', 'reason': 'name_mismatch_vs_reference'})
    elif support['name']:
        if slim['name']:
            tokens = [t for t in slim['name'].replace('.', '').split() if len(t) > 1]
            grounded = sum(1 for t in tokens if t.casefold() in hay) >= max(1, len(tokens) // 2)
            mark('name', 'pass' if grounded else 'fail')
            if not grounded:
                issues.append({'class': CLASS_B, 'field': 'name', 'reason': 'name_not_in_extract'})
        else:
            mark('name', 'fail')
            issues.append({
                'class': CLASS_A if short else CLASS_B,
                'field': 'name',
                'reason': 'name_supported_but_empty',
            })
    else:
        mark('name', 'n/a' if not slim['name'] else 'pass')

    def _score_contact(field: str, value: str, *, empty_reason: str, ungrounded_reason: str) -> None:
        if support.get(field):
            if value:
                grounded = value.casefold() in hay if field != 'phone' else (
                    re.sub(r'\D', '', value)[-10:] in re.sub(r'\D', '', extract or '')
                    if len(re.sub(r'\D', '', value)) >= 8 else False
                )
                if field == 'linkedin':
                    token = value.casefold().replace('https://', '').replace('http://', '').rstrip('/')
                    grounded = bool(token) and token[:24] in hay
                if field == 'location':
                    toks = [t for t in re.findall(r'[a-z]{3,}', value.casefold()) if t]
                    grounded = bool(toks) and sum(1 for t in toks if t in hay) >= max(1, len(toks) // 2)
                mark(field, 'pass' if grounded else 'fail')
                if not grounded:
                    issues.append({'class': CLASS_B, 'field': field, 'reason': ungrounded_reason})
            else:
                mark(field, 'fail')
                issues.append({
                    'class': CLASS_A if short else CLASS_B,
                    'field': field,
                    'reason': empty_reason,
                })
        else:
            mark(field, 'n/a' if not value else 'pass')

    _score_contact(
        'email', slim.get('email') or '',
        empty_reason='email_supported_but_empty',
        ungrounded_reason='email_not_in_extract',
    )
    _score_contact(
        'phone', slim.get('phone') or '',
        empty_reason='phone_supported_but_empty',
        ungrounded_reason='phone_not_in_extract',
    )
    _score_contact(
        'location', slim.get('location') or '',
        empty_reason='location_supported_but_empty',
        ungrounded_reason='location_not_in_extract',
    )
    _score_contact(
        'linkedin', slim.get('linkedin') or '',
        empty_reason='linkedin_supported_but_empty',
        ungrounded_reason='linkedin_not_in_extract',
    )

    exp = slim['experiences']
    first = exp[0] if exp else {}

    # --- Experience row ---
    if support['experience']:
        if exp:
            mark('experience', 'pass')
        else:
            mark('experience', 'fail')
            issues.append({
                'class': CLASS_A if short else CLASS_B,
                'field': 'experience',
                'reason': 'job_cues_in_extract_but_no_rows',
            })
    else:
        mark('experience', 'n/a' if not exp else 'pass')

    # --- Company / role / dates ---
    if support['company']:
        if first.get('company'):
            mark('company', 'pass' if first['company'].casefold()[:8] in hay or any(
                t in hay for t in first['company'].casefold().split() if len(t) > 3
            ) else 'fail')
            if field_ok['company'] == 'fail':
                issues.append({'class': CLASS_B, 'field': 'company', 'reason': 'company_not_grounded'})
        else:
            mark('company', 'fail')
            issues.append({'class': CLASS_B, 'field': 'company', 'reason': 'company_cue_in_extract_empty_form'})
    else:
        if first.get('company'):
            mark('company', 'pass')
        else:
            mark('company', 'n/a')
            if exp and first.get('role') and not first.get('company'):
                issues.append({
                    'class': CLASS_C,
                    'field': 'company',
                    'reason': 'role_without_company_no_company_cue',
                })

    if support['role']:
        if first.get('role'):
            mark('role', 'pass')
        elif exp:
            mark('role', 'fail')
            issues.append({'class': CLASS_B, 'field': 'role', 'reason': 'experience_row_missing_role'})
        else:
            mark('role', field_ok['experience'])
    else:
        mark('role', 'n/a' if not first.get('role') else 'pass')

    range_hint = bool(re.search(
        r'(?i)(?:20\d{2}|jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)'
        r'.{0,48}(?:to|–|-|till|until).{0,24}'
        r'(?:20\d{2}|present|current|till\s*date)',
        _employment_date_haystack(extract or ''),
    ))
    if exp and range_hint:
        has_start = bool(first.get('start'))
        currentish = first.get('isCurrent') or _fold(first.get('end')) in ('present', 'current')
        has_end = bool(first.get('end')) or currentish
        mark('start', 'pass' if has_start else 'fail')
        if not has_start:
            issues.append({'class': CLASS_B, 'field': 'start', 'reason': 'date_range_in_extract_start_empty'})
        if has_end:
            mark('end', 'pass')
        elif has_start:
            mark('end', 'n/a')
            issues.append({
                'class': CLASS_C,
                'field': 'end',
                'reason': 'range_in_source_end_unspecified_or_current_unmarked',
            })
        else:
            mark('end', 'fail')
            issues.append({'class': CLASS_B, 'field': 'end', 'reason': 'date_range_in_extract_end_empty'})
        mark('isCurrent', 'pass')
    else:
        mark('start', 'n/a' if not first.get('start') else 'pass')
        mark('end', 'n/a' if not (first.get('end') or first.get('isCurrent')) else 'pass')
        mark('isCurrent', 'n/a' if not exp else 'pass')

    first_desc = (first.get('description') or '') if first else ''
    any_desc = any((j.get('description') or '').strip() for j in exp) if exp else False
    exp_duty_support = experience_has_duty_evidence(extract or '')
    if any_desc:
        # Duties present on at least one job. First-job-empty alone is not a
        # fail when another row owns the description (legitimate n/a on Job A).
        mark('description', 'pass')
        if first_desc and any(
            (j.get('description') or '').strip()
            and j is not first
            and _fold(first_desc) == _fold(j.get('description') or '')
            for j in exp[1:]
        ):
            # Same duty blob duplicated across jobs — soft signal only.
            pass
    elif exp and exp_duty_support:
        mark('description', 'fail')
        issues.append({
            'class': CLASS_B,
            'field': 'description',
            'reason': 'duty_cues_in_experience_empty_description',
        })
    else:
        # No Experience-section duty evidence (header-only jobs, or duties only
        # in Projects/Summary) → n/a, not a parser failure.
        mark('description', 'n/a')

    if first.get('company') and slim['name'] and _fold(first['company']) == _fold(slim['name']):
        issues.append({'class': CLASS_B, 'field': 'company', 'reason': 'person_name_used_as_company'})
        mark('company', 'fail')

    # --- Education ---
    edu = slim['education']
    erow = edu[0] if edu else {}
    if support['education']:
        if edu:
            mark('education', 'pass')
        else:
            mark('education', 'fail')
            issues.append({
                'class': CLASS_A if short else CLASS_B,
                'field': 'education',
                'reason': 'education_cues_in_extract_no_rows',
            })
    else:
        mark('education', 'n/a' if not edu else 'pass')

    if support['degree']:
        if erow.get('degree'):
            mark('degree', 'pass')
        elif edu:
            mark('degree', 'n/a')
            issues.append({
                'class': CLASS_C,
                'field': 'degree',
                'reason': 'institution_row_without_degree_token_kept',
            })
        else:
            mark('degree', field_ok['education'])
    else:
        if erow.get('degree'):
            mark('degree', 'pass')
        else:
            mark('degree', 'n/a')
            if edu and erow.get('institution') and not erow.get('degree'):
                issues.append({
                    'class': CLASS_C,
                    'field': 'degree',
                    'reason': 'source_has_institution_without_clear_degree',
                })

    if support['institution']:
        if erow.get('institution'):
            inst = erow['institution']
            if _YEAR_PHRASE.search(inst):
                mark('institution', 'fail')
                issues.append({
                    'class': CLASS_B,
                    'field': 'institution',
                    'reason': 'date_phrase_left_in_institution',
                })
            else:
                mark('institution', 'pass')
        elif edu:
            mark('institution', 'n/a')
            issues.append({
                'class': CLASS_C,
                'field': 'institution',
                'reason': 'degree_only_row_no_institution',
            })
        else:
            mark('institution', field_ok['education'])
    else:
        mark('institution', 'n/a' if not erow.get('institution') else 'pass')

    if erow.get('end'):
        mark('edu_end', 'pass')
    else:
        mark('edu_end', 'n/a')
        if edu and re.search(
            r'(?i)\b(?:in the year|year of passing|passed in)\s+20\d{2}\b',
            extract or '',
        ):
            mark('edu_end', 'fail')
            issues.append({
                'class': CLASS_B,
                'field': 'edu_end',
                'reason': 'explicit_passing_year_not_mapped',
            })
    mark('edu_start', 'n/a' if not erow.get('start') else 'pass')

    # --- Skills ---
    skills = slim['skills']
    if _PROSE_SKILL.search(skills):
        mark('skills', 'fail')
        issues.append({'class': CLASS_B, 'field': 'skills', 'reason': 'prose_in_skills'})
    elif support['skills']:
        mark('skills', 'pass' if skills else 'fail')
        if not skills:
            issues.append({'class': CLASS_B, 'field': 'skills', 'reason': 'skills_heading_in_extract_empty_form'})
    else:
        mark('skills', 'n/a' if not skills else 'pass')

    # --- Summary ---
    if support['summary']:
        mark('summary', 'pass' if slim['summary'] else 'n/a')
        if not slim['summary']:
            issues.append({
                'class': CLASS_C,
                'field': 'summary',
                'reason': 'summary_heading_present_body_may_be_ambiguous',
            })
    else:
        mark('summary', 'n/a' if not slim['summary'] else 'pass')

    certs = slim.get('certifications') or []
    if support.get('certifications'):
        mark('certifications', 'pass' if certs else 'fail')
        if not certs:
            issues.append({
                'class': CLASS_B,
                'field': 'certifications',
                'reason': 'cert_heading_in_extract_empty_form',
            })
    else:
        mark('certifications', 'n/a' if not certs else 'pass')

    apply_coverage_gaps(
        slim=slim,
        coverage=coverage_rows if isinstance(coverage_rows, list) else None,
        field_ok=field_ok,
        issues=issues,
        mark=mark,
    )

    if reference:
        ref_cmp = compare_forms(form, reference)
        ref_slim = slim_form(reference)
        for key, ok in ref_cmp.items():
            if key not in field_ok:
                continue
            if ok:
                field_ok[key] = 'pass'
                continue
            field_ok[key] = 'fail'
            expected_blob = json_expected_blob(ref_slim, key)
            in_extract = bool(expected_blob) and expected_blob.casefold()[:12] in hay
            cls = CLASS_A if expected_blob and not in_extract and key in {
                'name', 'company', 'role', 'degree', 'institution',
            } else CLASS_B
            issues.append({
                'class': cls,
                'field': key,
                'reason': 'mismatch_vs_reference',
            })

    parser_fail = any(i['class'] == CLASS_B for i in issues)
    api_fail = any(i['class'] == CLASS_D for i in issues)
    acceptable = (not parser_fail) and (not api_fail) and http_status == 200
    classes = sorted({i['class'] for i in issues})
    traces = field_trace_verdicts(
        slim=slim,
        extract=extract or '',
        coverage=coverage_rows if isinstance(coverage_rows, list) else None,
        support=support,
    )
    empty = {
        'name': not slim.get('name'),
        'email': not slim.get('email'),
        'phone': not slim.get('phone'),
        'location': not slim.get('location'),
        'linkedin': not slim.get('linkedin'),
        'experience': not slim.get('experiences'),
        'education': not slim.get('education'),
        'skills': not slim.get('skills'),
        'summary': not slim.get('summary'),
        'certifications': not slim.get('certifications'),
    }
    return {
        'form': slim,
        'support': support,
        'fields': field_ok,
        'issues': issues,
        'classes': classes,
        'acceptable': acceptable,
        'had_reference': bool(reference),
        'coverage': coverage_rows if isinstance(coverage_rows, list) else [],
        'field_trace': traces,
        'empty': empty,
    }


def aggregate(cases: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(cases)
    field_stats: dict[str, dict[str, int]] = {
        k: {'pass': 0, 'fail': 0, 'n/a': 0} for k in FIELD_KEYS
    }
    class_counts = {CLASS_A: 0, CLASS_B: 0, CLASS_C: 0, CLASS_D: 0}
    acceptable = 0
    failures = []
    for case in cases:
        ev = case.get('evaluation') or {}
        if ev.get('acceptable'):
            acceptable += 1
        else:
            failures.append({
                'file': case.get('file'),
                'classes': ev.get('classes') or [],
                'issues': ev.get('issues') or [],
            })
        for k in FIELD_KEYS:
            st = (ev.get('fields') or {}).get(k, 'n/a')
            if st not in field_stats[k]:
                st = 'n/a'
            field_stats[k][st] += 1
        for cls in set(ev.get('classes') or []):
            if cls in class_counts:
                class_counts[cls] += 1

    per_field = {}
    for k, st in field_stats.items():
        scored = st['pass'] + st['fail']
        per_field[k] = {
            **st,
            'accuracy': (st['pass'] / scored) if scored else None,
            'scored': scored,
        }

    empty_keys = (
        'name', 'email', 'phone', 'location', 'linkedin',
        'experience', 'education', 'skills', 'summary', 'certifications',
    )
    empty_rates: dict[str, dict[str, Any]] = {
        k: {'empty': 0, 'filled': 0, 'rate': None} for k in empty_keys
    }
    coverage_counts: dict[str, dict[str, int]] = {}
    verdict_counts: dict[str, dict[str, int]] = {}
    for case in cases:
        ev = case.get('evaluation') or {}
        for k in empty_keys:
            if (ev.get('empty') or {}).get(k):
                empty_rates[k]['empty'] += 1
            else:
                empty_rates[k]['filled'] += 1
        for row in ev.get('coverage') or []:
            if not isinstance(row, dict):
                continue
            field = str(row.get('field') or '')
            status = str(row.get('status') or '')
            if not field:
                continue
            bucket = coverage_counts.setdefault(
                field,
                {'filled': 0, 'recovered': 0, 'missing_with_evidence': 0, 'missing_no_evidence': 0, 'other': 0},
            )
            if status in bucket:
                bucket[status] += 1
            else:
                bucket['other'] += 1
        for field, tr in (ev.get('field_trace') or {}).items():
            if not isinstance(tr, dict):
                continue
            verdict = str(tr.get('verdict') or 'other')
            bucket = verdict_counts.setdefault(
                field,
                {'ok': 0, 'weak_missing': 0, 'weak_ungrounded': 0, 'absent': 0, 'fallback': 0, 'other': 0},
            )
            if verdict in bucket:
                bucket[verdict] += 1
            else:
                bucket['other'] += 1
    for k, st in empty_rates.items():
        total = st['empty'] + st['filled']
        st['rate'] = (st['empty'] / total) if total else None

    clusters = cluster_issues(cases)
    backlog = rank_training_backlog(cases)
    return {
        'total': n,
        'acceptable': acceptable,
        'failure_count': n - acceptable,
        'per_field': per_field,
        'empty_rates': empty_rates,
        'coverage_counts': coverage_counts,
        'verdict_counts': verdict_counts,
        'clusters': clusters,
        'training_backlog': backlog,
        'class_counts_resumes': class_counts,
        'failures': failures,
    }
