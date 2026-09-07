"""Diagnose section-detection issues on the resume-testing corpus."""
from __future__ import annotations

import json
import os
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'backend'))
os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.bullets import restore_inferred_list_markers, split_inline_bullets
from app.ai.document_intelligence.layout_doc import normalize_extracted_resume_text
from app.ai.document_intelligence.sections import detect_sections, pick_section
from app.ai.parser.text_extraction import extract_text

CORPUS = Path(r'C:\Users\DELL\Downloads\resume testing')
SKIP = {'aadhar vishal c.pdf', '_organize_log.txt'}
WEAK_BODY = 40
CONTENT = {'Skills', 'Education', 'Experience', 'Projects', 'Certifications', 'Languages', 'Summary'}


def files() -> list[Path]:
    out = []
    for p in sorted(CORPUS.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_file():
            continue
        if p.name.lower() in SKIP or p.suffix.lower() not in {'.pdf', '.docx', '.doc'}:
            continue
        out.append(p)
    return out


def body_len(span) -> int:
    lines = (span.text or '').splitlines()
    if not lines:
        return 0
    return len('\n'.join(lines[1:]).strip())


def diagnose(path: Path) -> dict:
    raw = extract_text(path.read_bytes(), path.name) or ''
    working = restore_inferred_list_markers(split_inline_bullets(normalize_extracted_resume_text(raw)))
    spans = detect_sections(working, 'resume')
    labels = [s.label for s in spans]
    counts = Counter(labels)
    short = [
        {'label': s.label, 'body': body_len(s), 'source': s.source, 'head': (s.text or '')[:60].replace('\n', ' | ')}
        for s in spans
        if s.label in CONTENT and body_len(s) < WEAK_BODY
    ]
    preamble = pick_section(spans, 'Preamble')
    return {
        'file': path.name,
        'n_spans': len(spans),
        'labels': labels,
        'dupes': {k: v for k, v in counts.items() if v > 1},
        'short_content': short,
        'has_experience': any(l == 'Experience' for l in labels),
        'has_skills': any(l == 'Skills' for l in labels),
        'has_education': any(l == 'Education' for l in labels),
        'preamble_chars': len(preamble or ''),
        'preamble_head': (preamble or '')[:180].replace('\n', ' | '),
        'uncertain': [s.label for s in spans if s.source == 'uncertain'],
    }


def main():
    rows = []
    for p in files():
        print('FILE', p.name[:70], flush=True)
        try:
            rec = diagnose(p)
        except Exception as exc:
            rec = {'file': p.name, 'error': str(exc)}
        rows.append(rec)
        print(
            ' ',
            'exp' if rec.get('has_experience') else 'NO-EXP',
            'sk' if rec.get('has_skills') else 'NO-SK',
            'edu' if rec.get('has_education') else 'NO-EDU',
            'dupes', rec.get('dupes'),
            'short', [(s['label'], s['body']) for s in rec.get('short_content') or []],
            flush=True,
        )
    dest = ROOT / '_forensic_tmp' / 'section_diagnosis.json'
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
    print('wrote', dest, 'n=', len(rows))


if __name__ == '__main__':
    main()
