"""
Read-only forensic tracer for the resume pipeline.

Does not persist to DB. Does not modify production modules.
Writes stage snapshots + field traces under _forensic_tmp/out/.
"""
from __future__ import annotations

import json
import os
import re
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / 'apps' / 'backend'
sys.path.insert(0, str(BACKEND))

os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.bullets import (  # noqa: E402
    is_bullet_line,
    restore_inferred_list_markers,
    split_inline_bullets,
)
from app.ai.document_intelligence.coverage import recover_resume_profile_gaps  # noqa: E402
from app.ai.document_intelligence.knowledge import apply_knowledge_to_candidate  # noqa: E402
from app.ai.document_intelligence.layout_doc import normalize_extracted_resume_text  # noqa: E402
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form  # noqa: E402
from app.ai.document_intelligence.parsers.resume import parse_resume_from_sections  # noqa: E402
from app.ai.document_intelligence.pipeline import (  # noqa: E402
    _apply_resume_repair,
    resume_deterministic_is_strong,
)
from app.ai.document_intelligence.sections import detect_sections  # noqa: E402
from app.ai.document_intelligence.serialize.toon import candidate_to_toon  # noqa: E402
from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile  # noqa: E402
from app.ai.parser.text_extraction import (  # noqa: E402
    extract_text,
    extract_text_from_docx,
    extract_text_from_pdf_pymupdf,
    last_pdf_extractor,
    last_pdf_fallback_reason,
)

EMAIL_RE = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
PHONE_RE = re.compile(r'(?:\+91[\s\-]?)?[6-9]\d{9}')
DEGREE_RE = re.compile(
    r'(?i)\b(?:b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|b\.?sc|m\.?sc|mba|mms|'
    r'bca|mca|b\.?com|m\.?com|phd|bba|llb|b\.?arch|'
    r'bachelor|master|diploma|hsc|ssc|12th|10th)\b'
)
SKILL_HINTS = re.compile(
    r'(?i)\b(?:python|sql|java(?:script)?|c#|\.net|react|node|html|css|'
    r'power\s*bi|excel|tableau|aws|azure|docker|kubernetes|linux|'
    r'mysql|postgresql|mongodb|oracle|hadoop|spark|git|jira|'
    r'canva|photoshop|seo|sem|ms[- ]?office|word|powerpoint|'
    r'ansible|terraform|jenkins|kafka|redis|graphql)\b'
)
CITY_RE = re.compile(
    r'(?i)\b(?:mumbai|pune|thane|navi mumbai|nashik|nagpur|delhi|'
    r'bengaluru|bangalore|hyderabad|chennai|kolkata|ahmedabad|'
    r'noida|gurgaon|gurugram|jaipur|indore|kochi|vellore)\b'
)

SKIP_NAMES = {
    'aadhar vishal c.pdf',
    '_organize_log.txt',
}


def _emails(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in EMAIL_RE.finditer(text or '')})


def _phones(text: str) -> list[str]:
    out = set()
    for m in PHONE_RE.finditer(text or ''):
        digits = re.sub(r'\D', '', m.group(0))[-10:]
        if len(digits) == 10:
            out.add(digits)
    return sorted(out)


def _degrees(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in DEGREE_RE.finditer(text or '')})


def _skills(text: str) -> list[str]:
    return sorted({re.sub(r'\s+', ' ', m.group(0).lower()) for m in SKILL_HINTS.finditer(text or '')})


def _cities(text: str) -> list[str]:
    return sorted({m.group(0).lower() for m in CITY_RE.finditer(text or '')})


def _dump_profile(profile) -> dict:
    return {
        'name': getattr(profile.personal, 'full_name', '') or '',
        'summary': (getattr(profile.personal, 'summary', '') or '')[:240],
        'email': getattr(profile.contact, 'email', '') or '',
        'phone': getattr(profile.contact, 'phone', '') or '',
        'location': getattr(profile.contact, 'location', '') or '',
        'linkedin': getattr(profile.contact, 'linkedin', '') or '',
        'education': [
            {
                'degree': e.degree,
                'field': e.field,
                'institution': e.institution,
                'gpa': e.gpa,
                'start': e.start,
                'end': e.end,
            }
            for e in (profile.education or [])
        ],
        'experience': [
            {
                'company': e.company,
                'role': e.role,
                'start': e.start,
                'end': e.end,
                'location': e.location,
                'desc_chars': len(e.description or ''),
                'desc_lines': len([ln for ln in (e.description or '').splitlines() if ln.strip()]),
                'description_preview': (e.description or '')[:300],
            }
            for e in (profile.experience or [])
        ],
        'projects': [
            {
                'name': p.name,
                'desc_chars': len(p.description or ''),
                'technologies': list(p.technologies or []),
            }
            for p in (profile.projects or [])
        ],
        'skills': [s.canonical or s.name for s in (profile.skills or [])],
        'certificates': [c.name for c in (profile.certificates or [])],
        'languages': [l.name for l in (profile.languages or [])],
        'years': profile.total_experience_years,
    }


def _form_dump(form) -> dict:
    d = form.to_autofill_dict() if hasattr(form, 'to_autofill_dict') else form
    return {
        'fullName': d.get('fullName', ''),
        'email': d.get('email', ''),
        'phone': d.get('phone', ''),
        'currentLocation': d.get('currentLocation', ''),
        'linkedinUrl': d.get('linkedinUrl', ''),
        'skills': d.get('skills', ''),
        'summary': (d.get('summary') or '')[:240],
        'education': d.get('education', []),
        'experiences': [
            {
                'company': e.get('company', ''),
                'role': e.get('role', ''),
                'startMonth': e.get('startMonth', ''),
                'endMonth': e.get('endMonth', ''),
                'desc_chars': len(e.get('description') or ''),
                'desc_lines': len([ln for ln in (e.get('description') or '').splitlines() if ln.strip()]),
            }
            for e in (d.get('experiences') or [])
        ],
        'certifications': d.get('certifications', []),
        'has_projects_key': 'projects' in d,
        'has_languages_key': 'languages' in d,
        'has_internships_key': 'internships' in d,
    }


def _wrong_assignment(profile, source: str) -> list[dict]:
    issues = []
    src_emails = set(_emails(source))
    src_phones = set(_phones(source))
    for i, e in enumerate(profile.experience or []):
        blob = f'{e.company} {e.role}'
        if any(p in re.sub(r'\D', '', blob) for p in src_phones if p):
            issues.append({'kind': 'PHONE_AS_EXPERIENCE', 'index': i, 'value': blob})
        if any(em in blob.lower() for em in src_emails):
            issues.append({'kind': 'EMAIL_AS_EXPERIENCE', 'index': i, 'value': blob})
        if re.search(r'(?i)\b(?:university|college|institute|school)\b', e.company or ''):
            issues.append({'kind': 'INSTITUTION_AS_COMPANY', 'index': i, 'value': e.company})
        if re.search(r'(?i)^(python|sql|java|skills?|education|summary)\b', e.company or ''):
            issues.append({'kind': 'SKILL_OR_HEADER_AS_COMPANY', 'index': i, 'value': e.company})
        if re.search(r'(?i)^(developed|designed|built|managed|worked)\b', e.role or e.company or ''):
            issues.append({'kind': 'DUTY_AS_ROLE_OR_COMPANY', 'index': i, 'value': blob})
        if re.search(r'(?i)\b(?:reference|referred|contact person)\b', blob):
            issues.append({'kind': 'REFERENCE_AS_EXPERIENCE', 'index': i, 'value': blob})
    loc = (profile.contact.location or '').lower()
    if any(tok in loc for tok in ('python', 'sql', 'java', 'summary', 'curriculum')):
        issues.append({'kind': 'SKILL_AS_LOCATION', 'value': profile.contact.location})
    if any(p in re.sub(r'\D', '', loc) for p in src_phones):
        issues.append({'kind': 'PHONE_AS_LOCATION', 'value': profile.contact.location})
    return issues


def _partial_records(profile, source: str) -> list[dict]:
    out = []
    src_has_dates = bool(re.search(r'(?i)(?:20\d{2}|present|current)', source or ''))
    for i, e in enumerate(profile.experience or []):
        missing = []
        if not (e.company or '').strip():
            missing.append('company')
        if not (e.role or '').strip():
            missing.append('role')
        if not (e.start or '').strip() and src_has_dates:
            missing.append('start')
        if not (e.end or '').strip() and src_has_dates:
            missing.append('end')
        if not (e.description or '').strip():
            missing.append('description')
        if missing:
            out.append({'kind': 'experience', 'index': i, 'company': e.company, 'role': e.role, 'missing': missing})
    for i, e in enumerate(profile.education or []):
        missing = []
        if not (e.degree or '').strip():
            missing.append('degree')
        if not (e.institution or '').strip():
            missing.append('institution')
        if missing:
            out.append({'kind': 'education', 'index': i, 'degree': e.degree, 'institution': e.institution, 'missing': missing})
    return out


def _loss(source: str, profile, form) -> dict:
    src_emails = set(_emails(source))
    src_phones = set(_phones(source))
    src_degrees = set(_degrees(source))
    src_skills = set(_skills(source))
    src_cities = set(_cities(source))
    parsed_blob = json.dumps(_dump_profile(profile), ensure_ascii=False).lower()
    form_blob = json.dumps(_form_dump(form), ensure_ascii=False).lower()
    return {
        'source_emails': sorted(src_emails),
        'emails_lost_after_parse': sorted(e for e in src_emails if e not in parsed_blob),
        'emails_lost_after_form': sorted(e for e in src_emails if e not in form_blob),
        'source_phones': sorted(src_phones),
        'phones_lost_after_parse': sorted(p for p in src_phones if p not in re.sub(r'\D', '', parsed_blob)),
        'phones_lost_after_form': sorted(p for p in src_phones if p not in re.sub(r'\D', '', form_blob)),
        'source_degree_tokens': sorted(src_degrees),
        'degree_tokens_lost_after_parse': sorted(d for d in src_degrees if d not in parsed_blob),
        'source_skill_hints': sorted(src_skills),
        'skill_hints_lost_after_parse': sorted(s for s in src_skills if s not in parsed_blob),
        'skill_hints_lost_after_form': sorted(s for s in src_skills if s not in form_blob),
        'source_cities': sorted(src_cities),
        'city_in_parse_location': any(c in (profile.contact.location or '').lower() for c in src_cities),
    }


def _first_failures(trace: dict) -> list[dict]:
    """Identify first stage where a source signal disappeared or was misassigned."""
    failures = []
    src = trace['signals']['raw']
    stages = [
        ('raw_extract', trace['signals']['raw']),
        ('normalized', trace['signals']['normalized']),
        ('parsed', trace['signals']['parsed']),
        ('validated', trace['signals']['validated']),
        ('form', trace['signals']['form']),
    ]
    for kind in ('emails', 'phones', 'degrees', 'skills'):
        present = set(src[kind])
        last_ok = 'source'
        last_set = present
        for name, sig in stages:
            cur = set(sig[kind])
            lost = last_set - cur
            if lost:
                failures.append({
                    'field_group': kind,
                    'first_correct_stage': last_ok,
                    'first_incorrect_stage': name,
                    'lost': sorted(lost),
                    'category': {
                        'raw_extract': 'EXTRACTION',
                        'normalized': 'LAYOUT',
                        'parsed': 'PARSER',
                        'validated': 'VALIDATION',
                        'form': 'DTO_MAPPING',
                    }.get(name, 'UNKNOWN'),
                })
                break
            last_ok = name
            last_set = cur
    for issue in trace.get('wrong_assignment') or []:
        failures.append({
            'field_group': issue.get('kind'),
            'first_correct_stage': 'source',
            'first_incorrect_stage': 'parsed',
            'lost': [issue.get('value')],
            'category': 'PARSER' if 'AS_' in issue.get('kind', '') else 'RECORD_BOUNDARY',
        })
    return failures


def _signals(text: str) -> dict:
    return {
        'emails': _emails(text),
        'phones': _phones(text),
        'degrees': _degrees(text),
        'skills': _skills(text),
        'cities': _cities(text),
        'chars': len(text or ''),
        'lines': len([ln for ln in (text or '').splitlines() if ln.strip()]),
        'bullet_lines': sum(1 for ln in (text or '').splitlines() if is_bullet_line(ln)),
    }


def _signals_from_profile(profile) -> dict:
    blob = json.dumps(_dump_profile(profile), ensure_ascii=False)
    return _signals(blob)


def _signals_from_form(form) -> dict:
    blob = json.dumps(_form_dump(form), ensure_ascii=False)
    return _signals(blob)


def _compare_extractors(file_data: bytes, filename: str) -> dict:
    ext = filename.lower().rsplit('.', 1)[-1]
    out = {'production_engine': None, 'fallback_reason': '', 'engines': {}}
    if ext != 'pdf':
        return out
    try:
        pymu = extract_text_from_pdf_pymupdf(file_data)
        out['engines']['pymupdf'] = {
            'chars': len(pymu or ''),
            'emails': _emails(pymu),
            'phones': _phones(pymu),
            'skills': _skills(pymu),
            'degrees': _degrees(pymu),
            'bullet_lines': sum(1 for ln in (pymu or '').splitlines() if is_bullet_line(ln)),
            'preview': (pymu or '')[:400],
        }
    except Exception as exc:
        out['engines']['pymupdf'] = {'error': str(exc)}
        pymu = ''
    plumber_default = ''
    plumber_col = ''
    try:
        import pdfplumber

        with pdfplumber.open(__import__('io').BytesIO(file_data)) as pdf:
            parts_def = []
            parts_col = []
            for page in pdf.pages:
                parts_def.append(page.extract_text() or '')
                from app.ai.parser.pdfplumber_extractor import _extract_page_column_aware

                col = _extract_page_column_aware(page)
                parts_col.append(col if col else (page.extract_text() or ''))
            plumber_default = '\n\n'.join(parts_def).strip()
            plumber_col = '\n\n'.join(parts_col).strip()
        out['engines']['pdfplumber_default'] = {
            'chars': len(plumber_default),
            'emails': _emails(plumber_default),
            'phones': _phones(plumber_default),
            'skills': _skills(plumber_default),
            'degrees': _degrees(plumber_default),
            'bullet_lines': sum(1 for ln in plumber_default.splitlines() if is_bullet_line(ln)),
            'preview': plumber_default[:400],
        }
        out['engines']['pdfplumber_column_aware'] = {
            'chars': len(plumber_col),
            'emails': _emails(plumber_col),
            'phones': _phones(plumber_col),
            'skills': _skills(plumber_col),
            'degrees': _degrees(plumber_col),
            'bullet_lines': sum(1 for ln in plumber_col.splitlines() if is_bullet_line(ln)),
            'same_as_default': plumber_col == plumber_default,
            'preview': plumber_col[:400],
        }
    except Exception as exc:
        out['engines']['pdfplumber'] = {'error': str(exc)}
    # Quality: who keeps more identity + section tokens, not just chars
    scores = {}
    for name, eng in out['engines'].items():
        if 'error' in eng:
            continue
        scores[name] = (
            3 * len(eng.get('emails') or [])
            + 3 * len(eng.get('phones') or [])
            + 2 * len(eng.get('degrees') or [])
            + 2 * len(eng.get('skills') or [])
            + min(int(eng.get('chars') or 0), 8000) / 8000
        )
    out['quality_scores'] = scores
    if scores:
        best = max(scores, key=scores.get)
        out['better_engine_by_signal'] = best
        out['pymupdf_already_best_or_tied'] = scores.get('pymupdf', -1) >= max(
            (v for k, v in scores.items() if k != 'pymupdf'), default=-1
        )
    return out


def audit_file(path: Path) -> dict:
    file_data = path.read_bytes()
    filename = path.name
    report: dict = {
        'file': filename,
        'bytes': len(file_data),
        'ext': filename.rsplit('.', 1)[-1].lower() if '.' in filename else '',
        'error': None,
    }
    try:
        raw = extract_text(file_data, filename)
    except Exception as exc:
        report['error'] = f'extract_text: {exc}'
        report['traceback'] = traceback.format_exc()
        return report
    if raw is None:
        report['error'] = 'extract_text returned None'
        return report
    report['production_extractor'] = last_pdf_extractor() or ('docx' if filename.lower().endswith('.docx') else '')
    report['pdfplumber_fallback_reason'] = last_pdf_fallback_reason()
    report['extractor_compare'] = _compare_extractors(file_data, filename)

    from app.ai.parser.layout.detector import enhance_resume_text, is_layout_enabled

    layout_text = raw
    layout_changed = False
    if is_layout_enabled():
        structured = enhance_resume_text(raw)
        if structured and len(structured.strip()) >= 30 and structured != raw:
            layout_text = structured
            layout_changed = True
    normalized = normalize_extracted_resume_text(layout_text)
    working = restore_inferred_list_markers(split_inline_bullets(normalized))
    sections = detect_sections(working, 'resume')
    profile = parse_resume_from_sections(sections, working, max_workers=2, source_filename=filename)
    parsed_snap = _dump_profile(profile)
    profile, coverage = recover_resume_profile_gaps(profile, working)
    after_cov = _dump_profile(profile)
    profile = apply_knowledge_to_candidate(profile)
    strong = resume_deterministic_is_strong(profile, coverage, source_text=working)
    profile, _toon = _apply_resume_repair(profile, working)
    profile = sanitize_candidate_profile(profile, source_text=working)
    profile, coverage = recover_resume_profile_gaps(profile, working)
    validated = _dump_profile(profile)
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    form_snap = _form_dump(form)

    signals = {
        'raw': _signals(raw),
        'normalized': _signals(working),
        'parsed': _signals_from_profile(profile),  # after full det path
        'validated': _signals_from_profile(profile),
        'form': _signals_from_form(form),
    }
    # overwrite parsed with pre-sanitize snapshot for first-failure
    signals['parsed'] = _signals(json.dumps(parsed_snap, ensure_ascii=False))
    signals['validated'] = _signals(json.dumps(validated, ensure_ascii=False))

    report.update({
        'layout_changed': layout_changed,
        'section_labels': [s.label for s in sections],
        'section_sizes': {s.label: len(s.text or '') for s in sections},
        'deterministic_strong': strong,
        'coverage': coverage.as_dicts() if hasattr(coverage, 'as_dicts') else [],
        'parsed': parsed_snap,
        'after_coverage': after_cov,
        'validated': validated,
        'form': form_snap,
        'signals': signals,
        'wrong_assignment': _wrong_assignment(profile, working),
        'partial_records': _partial_records(profile, working),
        'information_loss': _loss(working, profile, form),
        'canonical_vs_form': {
            'name_match': (parsed_snap.get('name') or '') == (form_snap.get('fullName') or '')
            or (validated.get('name') or '') == (form_snap.get('fullName') or ''),
            'email_match': (validated.get('email') or '').lower() == (form_snap.get('email') or '').lower(),
            'phone_digits_match': re.sub(r'\D', '', validated.get('phone') or '')[-10:]
            == re.sub(r'\D', '', form_snap.get('phone') or '')[-10:],
            'exp_count_canonical': len(validated.get('experience') or []),
            'exp_count_form': len(form_snap.get('experiences') or []),
            'edu_count_canonical': len(validated.get('education') or []),
            'edu_count_form': len(form_snap.get('education') or []),
            'skills_canonical': len(validated.get('skills') or []),
            'projects_canonical': len(validated.get('projects') or []),
            'projects_in_form': form_snap.get('has_projects_key'),
            'languages_canonical': len(validated.get('languages') or []),
            'languages_in_form': form_snap.get('has_languages_key'),
        },
    })
    report['first_failures'] = _first_failures(report)
    report['raw_preview'] = (working or '')[:800]
    return report


def main() -> None:
    src = Path(r'C:\Users\DELL\Downloads\resume testing')
    out_dir = ROOT / '_forensic_tmp' / 'out'
    out_dir.mkdir(parents=True, exist_ok=True)
    files = sorted(
        p for p in src.iterdir()
        if p.is_file() and p.name.lower() not in SKIP_NAMES
        and p.suffix.lower() in {'.pdf', '.docx'}
    )
    summary = []
    for path in files:
        print(f'AUDITING {path.name} ...', flush=True)
        try:
            report = audit_file(path)
        except Exception as exc:
            report = {'file': path.name, 'error': str(exc), 'traceback': traceback.format_exc()}
        safe = re.sub(r'[^\w.\-]+', '_', path.name)[:80]
        (out_dir / f'{safe}.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        summary.append({
            'file': path.name,
            'error': report.get('error'),
            'engine': report.get('production_extractor'),
            'sections': report.get('section_labels'),
            'name': (report.get('validated') or {}).get('name'),
            'email': (report.get('validated') or {}).get('email'),
            'phone': (report.get('validated') or {}).get('phone'),
            'location': (report.get('validated') or {}).get('location'),
            'edu': len((report.get('validated') or {}).get('education') or []),
            'exp': len((report.get('validated') or {}).get('experience') or []),
            'skills': len((report.get('validated') or {}).get('skills') or []),
            'projects': len((report.get('validated') or {}).get('projects') or []),
            'wrong': [w.get('kind') for w in (report.get('wrong_assignment') or [])],
            'partial': len(report.get('partial_records') or []),
            'first_failures': report.get('first_failures') or [],
            'skill_loss': (report.get('information_loss') or {}).get('skill_hints_lost_after_parse'),
            'degree_loss': (report.get('information_loss') or {}).get('degree_tokens_lost_after_parse'),
            'dto': report.get('canonical_vs_form'),
            'strong': report.get('deterministic_strong'),
        })
        print(f"  name={summary[-1]['name']!r} email={summary[-1]['email']!r} exp={summary[-1]['exp']} edu={summary[-1]['edu']} skills={summary[-1]['skills']} fail={len(summary[-1]['first_failures'])}", flush=True)
    (out_dir / '_summary.json').write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
    print(f'Wrote {len(summary)} reports to {out_dir}', flush=True)


if __name__ == '__main__':
    main()
