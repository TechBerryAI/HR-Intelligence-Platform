"""Real-resume corpus diagnostics — artifacts only, never production rules.

Captures each pipeline stage so a failure can be attributed to extract,
prepare, sections, parse, recover, sanitize, or the Form DTO.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

BACKEND = Path(__file__).resolve().parents[3] / 'apps' / 'backend'
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

DEFAULT_CORPUS_DIR = Path(os.environ.get(
    'RESUME_CORPUS_DIR',
    r'C:\Users\DELL\Downloads\resume testing',
))
DEFAULT_ARTIFACT_DIR = Path(__file__).resolve().parents[3] / '_forensic_tmp' / 'corpus_harness'
# Previously failing layout classes — file stems for validation only.
_FOCUS_STEMS = (
    'Adil Rashid Khan RESUME',
    'Naukri_Rakeshdilipkarpe',
    'Naukri_RajendraNimbalkar',
    'Naukri_RakshaJaiswal',
)


def corpus_files(corpus_dir: Path | None = None) -> list[Path]:
    root = Path(corpus_dir or DEFAULT_CORPUS_DIR)
    if not root.is_dir():
        return []
    run_all = os.environ.get('RESUME_CORPUS_ALL', '').lower() in ('1', 'true', 'yes')
    out: list[Path] = []
    for p in sorted(root.iterdir()):
        if p.suffix.lower() not in {'.pdf', '.docx'} or not p.is_file():
            continue
        if run_all or any(p.name.startswith(stem) for stem in _FOCUS_STEMS):
            out.append(p)
    return out


def _safe(obj: Any) -> Any:
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if is_dataclass(obj):
        return asdict(obj)
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if hasattr(obj, 'to_autofill_dict'):
        return obj.to_autofill_dict()
    if isinstance(obj, list):
        return [_safe(x) for x in obj]
    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}
    return str(obj)


def _profile_summary(profile: Any) -> dict[str, Any]:
    if profile is None:
        return {}
    exp = getattr(profile, 'experience', None) or []
    edu = getattr(profile, 'education', None) or []
    skills = getattr(profile, 'skills', None) or []
    personal = getattr(profile, 'personal', None)
    contact = getattr(profile, 'contact', None)
    return {
        'full_name': getattr(personal, 'full_name', '') if personal else '',
        'email': getattr(contact, 'email', '') if contact else '',
        'phone': getattr(contact, 'phone', '') if contact else '',
        'location': getattr(contact, 'location', '') if contact else '',
        'experience': [
            {
                'company': getattr(e, 'company', ''),
                'role': getattr(e, 'role', ''),
                'start': getattr(e, 'start', ''),
                'end': getattr(e, 'end', ''),
                'is_current': getattr(e, 'is_current', False),
            }
            for e in exp
        ],
        'education': [
            {
                'degree': getattr(e, 'degree', ''),
                'institution': getattr(e, 'institution', ''),
                'end': getattr(e, 'end', ''),
            }
            for e in edu
        ],
        'skills': [getattr(s, 'name', s) for s in skills],
        'summary': getattr(personal, 'summary', '') if personal else '',
    }


def run_corpus_file(path: Path, artifact_dir: Path | None = None) -> dict[str, Any]:
    """Run the Apply parse tail and write per-stage artifacts."""
    from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
    from app.ai.document_intelligence.pipeline import parse_resume_from_working_text
    from app.ai.document_intelligence.response import build_resume_client_payload
    from app.ai.document_intelligence.resume_preprocess import prepare_resume_working_text
    from app.ai.document_intelligence.sections import detect_sections

    data = path.read_bytes()
    try:
        from app.ai.parser.text_extraction import extract_text_from_docx, extract_text_from_pdf

        if path.suffix.lower() == '.docx':
            raw = extract_text_from_docx(data) or ''
        else:
            raw = extract_text_from_pdf(data) or ''
    except Exception:
        raw = ''
    working = prepare_resume_working_text(
        raw,
        file_data=data if path.suffix.lower() == '.pdf' else data,
    )
    sections = detect_sections(working, 'resume')
    profile, coverage, _spans, used_llm, _toon = parse_resume_from_working_text(
        working,
        allow_semantic=False,
        source_filename=path.name,
    )
    form = map_candidate_to_form(profile, coverage=coverage.as_dicts())
    payload = build_resume_client_payload({
        'status': 'ok',
        'form': form.to_autofill_dict(),
        'canonical': profile.model_dump(),
    })
    report = {
        'file': path.name,
        'suffix': path.suffix.lower(),
        'raw_len': len(raw),
        'working_len': len(working),
        'source_unavailable': len(raw.strip()) < 40,
        'sections': [
            {
                'label': s.label,
                'source': s.source,
                'chars': len(s.text or ''),
            }
            for s in sections
        ],
        'final_profile': _profile_summary(profile),
        'form': _safe(payload.get('form')),
        'used_llm': used_llm,
        'extract_has_email': '@' in raw,
        'extract_has_labeled_job': bool(
            __import__('re').search(
                r'(?im)^(?:company(?:\s+name)?|client|organization)\s*:',
                working,
            )
        ),
        'extract_has_pipe_job': '|' in working and bool(
            __import__('re').search(r'(?i)\b(?:till\s*date|present|20\d{2})\b', working)
        ),
        'extract_has_degree': bool(
            __import__('re').search(r'(?i)\b(?:bachelor|b\.?\s*e|degree|university)\b', working)
        ),
    }
    dest = Path(artifact_dir or DEFAULT_ARTIFACT_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    stem = ''.join(ch if ch.isalnum() or ch in '-_.' else '_' for ch in path.stem)[:60]
    (dest / f'{stem}_raw.txt').write_text(raw, encoding='utf-8')
    (dest / f'{stem}_working.txt').write_text(working, encoding='utf-8')
    (dest / f'{stem}_report.json').write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding='utf-8',
    )
    return report


def run_corpus(corpus_dir: Path | None = None, artifact_dir: Path | None = None) -> list[dict[str, Any]]:
    reports = []
    for path in corpus_files(corpus_dir):
        reports.append(run_corpus_file(path, artifact_dir=artifact_dir))
    dest = Path(artifact_dir or DEFAULT_ARTIFACT_DIR)
    dest.mkdir(parents=True, exist_ok=True)
    (dest / 'index.json').write_text(json.dumps(reports, indent=2, ensure_ascii=False), encoding='utf-8')
    return reports
