"""Production autofill correctness checks (parity + apply contract + grounding)."""
from __future__ import annotations

import re
from typing import Any

MAPPED_KEYS = (
    'fullName',
    'email',
    'phone',
    'linkedinUrl',
    'portfolioUrl',
    'githubUrl',
    'currentLocation',
    'preferredLocation',
    'experienceLevel',
    'skills',
    'summary',
    'education',
    'experiences',
    'certifications',
)

FAILURE_CATEGORIES = (
    'OCR/Text extraction',
    'Parser',
    'Canonical model',
    'Mapping',
    'Autofill',
    'Frontend',
    'Validation',
    'Unsupported document',
    'Timeout',
    'Other',
)


def _norm(v: Any) -> str:
    if v is None:
        return ''
    return str(v).strip()


def _norm_phone(v: str) -> str:
    return re.sub(r'\D+', '', v or '')


def _norm_url(v: str) -> str:
    s = (v or '').strip().lower()
    s = re.sub(r'^https?://', '', s)
    s = s.rstrip('/')
    return s


def _text_haystack(raw_text: str) -> str:
    return (raw_text or '').lower()


def _tokens(value: str, min_len: int = 3) -> list[str]:
    parts = re.findall(r"[A-Za-z0-9][A-Za-z0-9+.#/-]{%d,}" % max(0, min_len - 1), value or '')
    return [p.lower() for p in parts]


def validate_ai_owned_fields(form: dict) -> dict[str, str]:
    """Mirror ApplyJobModal / harness AI-owned validate()."""
    errors: dict[str, str] = {}
    if not _norm(form.get('fullName')):
        errors['fullName'] = 'Required'
    email = _norm(form.get('email'))
    if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
        errors['email'] = 'Valid email required'
    if not _norm(form.get('phone')):
        errors['phone'] = 'Required'
    if not _norm(form.get('currentLocation')):
        errors['currentLocation'] = 'Required'
    if not _norm(form.get('preferredLocation')):
        errors['preferredLocation'] = 'Required'
    if not _norm(form.get('experienceLevel')):
        errors['experienceLevel'] = 'Required'
    if not form.get('resumeFile') and not _norm(form.get('resumeFileName')):
        errors['resume'] = 'Resume required'
    if not form.get('_parsedId'):
        errors['resume'] = errors.get('resume') or 'Please wait for resume AI parsing to finish'
    edu_ok = any(
        _norm(e.get('degree')) and _norm(e.get('institution'))
        for e in (form.get('education') or [])
        if isinstance(e, dict)
    )
    if not edu_ok:
        errors['education'] = 'At least one education entry with degree and institution is required'
    return errors


def check_frontend_parity(form_dto: dict, fe_form: dict) -> list[dict]:
    """Form DTO vs post-autofill FE state for mapped keys (handleAutofill rules)."""
    issues = []
    for key in MAPPED_KEYS:
        dto_val = form_dto.get(key)
        fe_val = fe_form.get(key)
        if key in ('education', 'experiences', 'certifications'):
            dto_list = dto_val if isinstance(dto_val, list) and dto_val else None
            # handleAutofill keeps prev when DTO list empty
            if not dto_list:
                continue
            if not isinstance(fe_val, list) or _norm(fe_val) != _norm(dto_list):
                issues.append({
                    'field': key,
                    'expected': dto_list,
                    'actual': fe_val,
                    'reason': 'array_mismatch',
                })
            continue
        # scalar: mapped.x ?? prev — if DTO has value, FE must match
        if dto_val is None or dto_val == '':
            continue
        if _norm(fe_val) != _norm(dto_val):
            issues.append({
                'field': key,
                'expected': dto_val,
                'actual': fe_val,
                'reason': 'scalar_mismatch',
            })
    if form_dto and fe_form.get('_parsedId') is None and form_dto:
        # _parsedId comes from result.parsed_id via onAutofill wrapper
        pass
    return issues


def _ground_scalar(field: str, value: str, hay: str, raw_text: str) -> tuple[bool, str]:
    if not value:
        return True, 'empty_ok'
    low = value.lower().strip()
    if field == 'email':
        return (low in hay, 'email_in_text' if low in hay else 'email_missing_in_text')
    if field == 'phone':
        digits = _norm_phone(value)
        raw_digits = _norm_phone(raw_text)
        ok = len(digits) >= 8 and digits in raw_digits
        return ok, 'phone_in_text' if ok else 'phone_missing_in_text'
    if field in ('linkedinUrl', 'portfolioUrl', 'githubUrl'):
        nu = _norm_url(value)
        if len(nu) < 5:
            return True, 'url_short_skip'
        ok = nu in _norm_url(raw_text) or nu in hay or any(t in hay for t in _tokens(nu, 4)[:3])
        return ok, 'url_in_text' if ok else 'url_missing_in_text'
    if field == 'fullName':
        toks = [t for t in _tokens(value, 2) if t not in {'mr', 'mrs', 'ms', 'dr'}]
        if not toks:
            return False, 'name_empty_tokens'
        hits = sum(1 for t in toks if t in hay)
        ok = hits >= max(1, (len(toks) + 1) // 2)
        return ok, 'name_grounded' if ok else 'name_not_in_text'
    if field in ('currentLocation', 'preferredLocation'):
        toks = _tokens(value, 3)
        if not toks:
            return True, 'location_short_ok'
        ok = any(t in hay for t in toks)
        return ok, 'location_grounded' if ok else 'location_not_in_text'
    if field == 'experienceLevel':
        return value in ('fresher', 'experienced'), 'experience_level_enum'
    if field == 'skills':
        skills = [s.strip() for s in value.split(',') if s.strip()]
        if not skills:
            return True, 'skills_empty_ok'
        hits = 0
        for sk in skills[:40]:
            toks = _tokens(sk, 2)
            if not toks or any(t in hay for t in toks):
                hits += 1
        ok = hits / max(1, min(len(skills), 40)) >= 0.5
        return ok, 'skills_grounded' if ok else 'skills_not_in_text'
    if field == 'summary':
        toks = _tokens(value, 4)
        if len(toks) < 3:
            return True, 'summary_short_ok'
        hits = sum(1 for t in toks[:20] if t in hay)
        ok = hits >= max(2, len(toks[:20]) // 4)
        return ok, 'summary_grounded' if ok else 'summary_not_in_text'
    toks = _tokens(value, 3)
    if not toks:
        return True, 'no_tokens'
    ok = any(t in hay for t in toks)
    return ok, 'token_grounded' if ok else 'token_not_in_text'


def check_grounding(form: dict, raw_text: str) -> tuple[list[dict], int, int]:
    """Return (issues, grounded_ok, grounded_total)."""
    hay = _text_haystack(raw_text)
    issues: list[dict] = []
    ok_n = total = 0

    scalar_fields = (
        'fullName', 'email', 'phone', 'linkedinUrl', 'portfolioUrl', 'githubUrl',
        'currentLocation', 'preferredLocation', 'experienceLevel', 'skills', 'summary',
    )
    for field in scalar_fields:
        val = _norm(form.get(field))
        if not val:
            # Required fields with source evidence still counted via evidence checks below
            continue
        total += 1
        good, reason = _ground_scalar(field, val, hay, raw_text)
        if good:
            ok_n += 1
        else:
            issues.append({'field': field, 'value': val, 'reason': reason, 'layer': 'grounding'})

    for i, edu in enumerate(form.get('education') or []):
        if not isinstance(edu, dict):
            continue
        for sub in ('degree', 'institution'):
            val = _norm(edu.get(sub))
            if not val:
                continue
            total += 1
            good, reason = _ground_scalar(sub, val, hay, raw_text)
            if good:
                ok_n += 1
            else:
                issues.append({'field': f'education[{i}].{sub}', 'value': val, 'reason': reason, 'layer': 'grounding'})

    for i, exp in enumerate(form.get('experiences') or []):
        if not isinstance(exp, dict):
            continue
        for sub in ('company', 'role'):
            val = _norm(exp.get(sub))
            if not val:
                continue
            total += 1
            good, reason = _ground_scalar(sub, val, hay, raw_text)
            if good:
                ok_n += 1
            else:
                issues.append({'field': f'experiences[{i}].{sub}', 'value': val, 'reason': reason, 'layer': 'grounding'})

    # Source evidence: if email clearly in text, form must have it
    email_m = re.search(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', raw_text or '', re.I)
    if email_m and not _norm(form.get('email')):
        total += 1
        issues.append({'field': 'email', 'value': '', 'reason': 'email_in_source_not_filled', 'layer': 'recall'})
    elif email_m:
        total += 1
        ok_n += 1

    phone_m = re.search(r'(?:\+?\d[\d\s().-]{8,}\d)', raw_text or '')
    if phone_m and not _norm(form.get('phone')):
        total += 1
        issues.append({'field': 'phone', 'value': '', 'reason': 'phone_in_source_not_filled', 'layer': 'recall'})
    elif phone_m:
        total += 1
        ok_n += 1

    return issues, ok_n, total


def classify_failure(
    *,
    status: str,
    parse_error: str | None,
    parse_payload: dict | None,
    parity_issues: list,
    validation_errors: dict,
    grounding_issues: list,
    raw_text: str,
    screenshot_ok: bool,
    timed_out: bool = False,
    frontend_error: str | None = None,
) -> tuple[str, str]:
    """Return (category, signature)."""
    if timed_out:
        return 'Timeout', 'timeout'
    if frontend_error:
        return 'Frontend', f'frontend:{frontend_error[:80]}'
    err = (parse_error or '').lower()
    if 'unsupported' in err or 'invalid file type' in err or 'legacy .doc' in err:
        return 'Unsupported document', 'unsupported'
    if status == 'error' or (parse_payload and parse_payload.get('status') != 'ok'):
        api_err = ''
        if parse_payload:
            api_err = str(parse_payload.get('error') or '')
        combined = f'{parse_error or ""} {api_err}'.lower()
        if any(x in combined for x in ('extract', 'ocr', 'empty text', 'no text', 'pymupdf', 'pdf')):
            return 'OCR/Text extraction', f'extract:{combined[:100]}'
        if 'timeout' in combined or 'timed out' in combined:
            return 'Timeout', 'api_timeout'
        return 'Parser', f'parse_error:{combined[:100]}'

    chars = len(raw_text or '')
    if chars < 40:
        return 'OCR/Text extraction', f'short_text:{chars}'

    if not parse_payload or not parse_payload.get('form'):
        return 'Mapping', 'missing_form_dto'
    if parse_payload.get('canonical') is None and parse_payload.get('status') == 'ok':
        # validation payload expected; missing canonical is mapping/response issue
        pass

    if parity_issues:
        return 'Autofill', f'parity:{parity_issues[0].get("field")}'

    # Canonical present but form empty for required → Mapping
    form = parse_payload.get('form') or {}
    canonical = parse_payload.get('canonical') or {}
    personal = (canonical.get('personal') or {}) if isinstance(canonical, dict) else {}
    contact = (canonical.get('contact') or {}) if isinstance(canonical, dict) else {}
    if (personal.get('full_name') or contact.get('email')) and not (
        form.get('fullName') or form.get('email')
    ):
        return 'Mapping', 'canonical_not_mapped'

    grounding_parser = [g for g in grounding_issues if g.get('layer') == 'recall']
    if grounding_parser:
        return 'Parser', f'recall:{grounding_parser[0].get("reason")}'

    halluc = [g for g in grounding_issues if g.get('layer') == 'grounding']
    if halluc:
        # Prefer Parser if identity fields wrong; else Canonical/Mapping
        field = halluc[0].get('field', '')
        if field in ('fullName', 'email', 'phone') or str(field).startswith('education'):
            return 'Parser', f'ungrounded:{field}'
        return 'Canonical model', f'ungrounded:{field}'

    if validation_errors:
        return 'Validation', f'apply:{",".join(sorted(validation_errors.keys()))}'

    if not screenshot_ok:
        return 'Frontend', 'screenshot_failed'

    return 'Other', 'unspecified'


def evaluate_case(case: dict) -> dict:
    """
    Evaluate one harness capture.
    case keys: status, form, parsePayload, parseError, errors, elapsedMs, timed_out, frontend_error, screenshot_ok
    """
    parse_payload = case.get('parsePayload') or case.get('parse_payload') or {}
    form_state = case.get('form') or {}
    parse_error = case.get('parseError') or case.get('parse_error')
    timed_out = bool(case.get('timed_out'))
    frontend_error = case.get('frontend_error')
    screenshot_ok = bool(case.get('screenshot_ok', False))
    raw_text = ''
    if isinstance(parse_payload, dict):
        raw_text = parse_payload.get('raw_text') or ''

    form_dto = (parse_payload.get('form') if isinstance(parse_payload, dict) else None) or {}
    parity_issues = []
    validation_errors = {}
    grounding_issues: list = []
    grounded_ok = grounded_total = 0

    status = case.get('status') or 'unknown'
    api_ok = (
        not timed_out
        and not frontend_error
        and status == 'complete'
        and isinstance(parse_payload, dict)
        and parse_payload.get('status') == 'ok'
        and bool(parse_payload.get('form'))
        and bool(parse_payload.get('parsed_id') or form_state.get('_parsedId'))
    )

    if api_ok:
        parity_issues = check_frontend_parity(form_dto, form_state)
        validation_errors = validate_ai_owned_fields(form_state)
        grounding_issues, grounded_ok, grounded_total = check_grounding(form_state, raw_text)

    passed = bool(
        api_ok
        and not parity_issues
        and not validation_errors
        and not grounding_issues
        and screenshot_ok
    )

    category = ''
    signature = ''
    if not passed:
        category, signature = classify_failure(
            status=status,
            parse_error=parse_error,
            parse_payload=parse_payload if isinstance(parse_payload, dict) else None,
            parity_issues=parity_issues,
            validation_errors=validation_errors,
            grounding_issues=grounding_issues,
            raw_text=raw_text,
            screenshot_ok=screenshot_ok,
            timed_out=timed_out,
            frontend_error=frontend_error,
        )

    confidence = None
    if isinstance(parse_payload, dict):
        confidence = parse_payload.get('confidence')

    return {
        'passed': passed,
        'category': category,
        'signature': signature,
        'parity_issues': parity_issues,
        'validation_errors': validation_errors,
        'grounding_issues': grounding_issues,
        'grounded_ok': grounded_ok,
        'grounded_total': grounded_total,
        'field_accuracy': (grounded_ok / grounded_total) if grounded_total else (1.0 if passed else 0.0),
        'confidence': confidence,
        'elapsed_ms': case.get('elapsedMs') or case.get('elapsed_ms'),
        'raw_text_chars': len(raw_text or ''),
        'parsed_id': (parse_payload or {}).get('parsed_id') if isinstance(parse_payload, dict) else None,
        'partial': (parse_payload or {}).get('partial') if isinstance(parse_payload, dict) else None,
    }
