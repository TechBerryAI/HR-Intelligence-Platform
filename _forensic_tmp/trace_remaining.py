"""Stage tracer for remaining failing resumes. Diagnosis only."""
from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'apps' / 'backend'))
os.environ.setdefault('RESUME_SKIP_LLM_WHEN_DETERMINISTIC', 'true')
os.environ.setdefault('DOCUMENT_INTELLIGENCE_SEMANTIC_AI', 'false')

from app.ai.document_intelligence.bullets import restore_inferred_list_markers, split_inline_bullets
from app.ai.document_intelligence.coverage import recover_resume_profile_gaps
from app.ai.document_intelligence.knowledge import apply_knowledge_to_candidate
from app.ai.document_intelligence.layout_doc import normalize_extracted_resume_text
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form
from app.ai.document_intelligence.parsers.resume import parse_resume_from_sections
from app.ai.document_intelligence.pipeline import _apply_resume_repair
from app.ai.document_intelligence.sections import detect_sections
from app.ai.document_intelligence.validation.engine import sanitize_candidate_profile
from app.ai.parser.text_extraction import extract_text, last_pdf_extractor, last_pdf_fallback_reason

CORPUS = Path(r'C:\Users\DELL\Downloads\resume testing')
FILES = [
    '#1_Vishal_Waghmode_Resume.pdf',
    '45_MMS_Marketing_Akshay     Pujari -1.jpg (1) (1) (1).docx',
    '1.docx',
    '2025_UMAR_SHARIEF_RESUME postgresql dba.pdf',
    '13_Ms.-Saloni-Dhuru.pdf',
    'Padmini Mongo dba Expertia AI.pdf',
    '1-Ashish_Chandel.docx',
    '26160_1726557418Abhi-Resume.docx',
    '1658748886885_RAHUL SURESH SURVASE Updated (1).docx',
    '3.1_YRS_PUNE_VIPUL  PATIL (1).pdf',
    'Ajinkya K MYSQL DBA.pdf',
    '1vinay(2)Ea3JB.pdf',
    '_Trupti Kokate Resume will inform by 14 feb if comfortable for vikhroli location.docx',
    '01 Furqan Khan - HR - 9 Years Experience.pdf',
    '3 Years of Exp MySQL Database Administrator.docx',
]


def snap(p):
    return {
        'name': p.personal.full_name,
        'email': p.contact.email,
        'phone': p.contact.phone,
        'loc': p.contact.location,
        'edu': [
            {'d': e.degree, 'i': e.institution, 'f': e.field, 'g': e.gpa, 's': e.start, 'e': e.end}
            for e in p.education
        ],
        'exp': [
            {'c': e.company, 'r': e.role, 's': e.start, 'e': e.end, 'dl': len((e.description or '').splitlines())}
            for e in p.experience
        ],
        'skills': [s.name for s in p.skills][:20],
        'n_skills': len(p.skills),
        'n_proj': len(p.projects),
        'n_lang': len(p.languages),
    }


def main():
    out = []
    for name in FILES:
        path = CORPUS / name
        if not path.is_file():
            print('MISSING', name)
            continue
        print('TRACE', name[:60], flush=True)
        data = path.read_bytes()
        raw = extract_text(data, name)
        working = restore_inferred_list_markers(split_inline_bullets(normalize_extracted_resume_text(raw)))
        sections = detect_sections(working, 'resume')
        parsed = parse_resume_from_sections(sections, working, max_workers=2, source_filename=name)
        after_cov, cov = recover_resume_profile_gaps(parsed, working)
        after_kn = apply_knowledge_to_candidate(after_cov)
        after_rep, _ = _apply_resume_repair(after_kn, working)
        after_san = sanitize_candidate_profile(after_rep, source_text=working)
        final, cov2 = recover_resume_profile_gaps(after_san, working)
        form = map_candidate_to_form(final, coverage=cov2.as_dicts())
        rec = {
            'file': name,
            'engine': last_pdf_extractor(),
            'fallback': last_pdf_fallback_reason(),
            'raw_chars': len(raw or ''),
            'raw_head': (raw or '')[:350],
            'sections': [(s.label, len(s.text or '')) for s in sections],
            'parsed': snap(parsed),
            'coverage': snap(after_cov),
            'repair': snap(after_rep),
            'final': snap(final),
            'form': {
                'name': form.fullName,
                'email': form.email,
                'loc': form.currentLocation,
                'n_edu': len(form.education),
                'n_exp': len(form.experiences),
                'n_cert': len(form.certifications),
                'skills': (form.skills or '')[:180],
            },
            'coverage_status': cov2.as_dicts(),
        }
        out.append(rec)
        f = rec['final']
        print(
            f"  name={f['name']!r} edu={len(f['edu'])} exp={len(f['exp'])} skills={f['n_skills']} "
            f"secs={[s[0] for s in rec['sections']]}",
            flush=True,
        )
    dest = ROOT / '_forensic_tmp' / 'remaining_trace_after.json'
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding='utf-8')
    print('wrote', dest)


if __name__ == '__main__':
    main()
