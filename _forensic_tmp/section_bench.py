"""Before/after section-detection benchmark on the 24-resume corpus."""
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

from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
from app.ai.document_intelligence.sections import detect_sections
from app.ai.parser.text_extraction import extract_text

CORPUS = Path(r'C:\Users\DELL\Downloads\resume testing')
SKIP = {'aadhar vishal c.pdf', '_organize_log.txt'}
DEGREE_RE = re.compile(
    r'(?i)\b(?:b\.?tech|m\.?tech|b\.?e\.?|m\.?e\.?|b\.?sc|m\.?sc|mba|mms|'
    r'bca|mca|b\.?com|phd|bachelor|master|diploma|hsc|ssc)\b'
)
SKILL_HINTS = re.compile(
    r'(?i)\b(?:python|sql|java(?:script)?|c#|\.net|react|linux|mysql|'
    r'postgresql|mongodb|oracle|aws|azure|ansible|excel|ms[- ]?office)\b'
)


def files() -> list[Path]:
    return [
        p for p in sorted(CORPUS.iterdir(), key=lambda x: x.name.lower())
        if p.is_file()
        and p.name.lower() not in SKIP
        and p.suffix.lower() in {'.pdf', '.docx', '.doc'}
    ]


def measure(tag: str) -> Path:
    rows = []
    for p in files():
        print(tag, p.name[:60], flush=True)
        text = extract_text(p.read_bytes(), p.name) or ''
        spans = detect_sections(text, 'resume')
        profile, form, _ = parse_resume_text_to_canonical(
            text, max_workers=2, allow_semantic=False, source_filename=p.name
        )
        blob = json.dumps(
            {
                'edu': [(e.degree, e.institution) for e in profile.education],
                'exp': [(e.company, e.role) for e in profile.experience],
                'skills': [s.name for s in profile.skills],
            },
            ensure_ascii=False,
        ).lower()
        src_deg = sorted({m.group(0).lower() for m in DEGREE_RE.finditer(text)})
        src_sk = sorted({re.sub(r'\s+', ' ', m.group(0).lower()) for m in SKILL_HINTS.finditer(text)})
        desc_lines = 0
        desc_flat = 0
        for e in profile.experience:
            desc = e.description or ''
            nlines = len([ln for ln in desc.splitlines() if ln.strip()])
            desc_lines += nlines
            if nlines <= 1 and len(desc) > 80:
                desc_flat += 1
        summary = profile.personal.summary or ''
        sum_lines = len([ln for ln in summary.splitlines() if ln.strip()])
        rows.append(
            {
                'file': p.name,
                'labels': [s.label for s in spans],
                'unclassified_chars': sum(
                    len(s.text or '') for s in spans if s.label == 'Unclassified'
                ),
                'name': profile.personal.full_name,
                'n_edu': len(profile.education),
                'n_exp': len(profile.experience),
                'n_skills': len(profile.skills),
                'desc_lines': desc_lines,
                'desc_flat': desc_flat,
                'sum_lines': sum_lines,
                'sum_flat': bool(summary) and sum_lines <= 1,
                'jobs': [
                    {'c': e.company, 'r': e.role}
                    for e in profile.experience
                ],
                'edu': [
                    {'d': e.degree, 'i': e.institution}
                    for e in profile.education
                ][:6],
                'skills_head': [s.name for s in profile.skills[:12]],
                'degree_hints_lost': [d for d in src_deg if d not in blob],
                'skill_hints_lost': [s for s in src_sk if s not in blob],
                'src_deg': src_deg,
                'src_sk': src_sk,
            }
        )
        print(
            f"  edu={len(profile.education)} exp={len(profile.experience)} "
            f"sk={len(profile.skills)} lost_sk={rows[-1]['skill_hints_lost'][:6]}",
            flush=True,
        )
    dest = ROOT / '_forensic_tmp' / f'section_bench_{tag}.json'
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
    print('wrote', dest)
    return dest


def compare(before_path: Path | None = None, after_path: Path | None = None) -> Path:
    root = ROOT / '_forensic_tmp'
    before = json.loads((before_path or root / 'section_bench_before.json').read_text(encoding='utf-8'))
    after = json.loads((after_path or root / 'section_bench_after.json').read_text(encoding='utf-8'))
    by_before = {r['file']: r for r in before}
    rows = []
    invented = []
    lost_jobs = []
    lost_edu = []
    skill_fn = []
    skill_fp = []
    for rec in after:
        prev = by_before.get(rec['file']) or {}
        before_jobs = {(j.get('c'), j.get('r')) for j in prev.get('jobs') or []}
        after_jobs = {(j.get('c'), j.get('r')) for j in rec.get('jobs') or []}
        added_jobs = sorted(after_jobs - before_jobs)
        removed_jobs = sorted(before_jobs - after_jobs)
        before_edu = {(e.get('d'), e.get('i')) for e in prev.get('edu') or []}
        after_edu = {(e.get('d'), e.get('i')) for e in rec.get('edu') or []}
        delta = {
            'file': rec['file'],
            'n_edu': [prev.get('n_edu'), rec.get('n_edu')],
            'n_exp': [prev.get('n_exp'), rec.get('n_exp')],
            'n_skills': [prev.get('n_skills'), rec.get('n_skills')],
            'desc_lines': [prev.get('desc_lines'), rec.get('desc_lines')],
            'desc_flat': [prev.get('desc_flat'), rec.get('desc_flat')],
            'sum_lines': [prev.get('sum_lines'), rec.get('sum_lines')],
            'labels_before': prev.get('labels'),
            'labels_after': rec.get('labels'),
            'unclassified_chars': rec.get('unclassified_chars'),
            'added_jobs': added_jobs,
            'removed_jobs': removed_jobs,
            'skill_hints_lost_before': prev.get('skill_hints_lost') or [],
            'skill_hints_lost_after': rec.get('skill_hints_lost') or [],
            'degree_hints_lost_before': prev.get('degree_hints_lost') or [],
            'degree_hints_lost_after': rec.get('degree_hints_lost') or [],
            'recovered_skills': sorted(
                set(prev.get('skill_hints_lost') or []) - set(rec.get('skill_hints_lost') or [])
            ),
            'new_skill_losses': sorted(
                set(rec.get('skill_hints_lost') or []) - set(prev.get('skill_hints_lost') or [])
            ),
            'recovered_degrees': sorted(
                set(prev.get('degree_hints_lost') or []) - set(rec.get('degree_hints_lost') or [])
            ),
            'new_degree_losses': sorted(
                set(rec.get('degree_hints_lost') or []) - set(prev.get('degree_hints_lost') or [])
            ),
        }
        rows.append(delta)
        if added_jobs:
            invented.append({'file': rec['file'], 'added': added_jobs})
        if removed_jobs:
            lost_jobs.append({'file': rec['file'], 'removed': removed_jobs})
        if delta['new_degree_losses']:
            lost_edu.append({'file': rec['file'], 'lost': delta['new_degree_losses']})
        if delta['new_skill_losses']:
            skill_fn.append({'file': rec['file'], 'lost': delta['new_skill_losses']})
        if rec.get('n_skills', 0) > (prev.get('n_skills') or 0) + 8:
            skill_fp.append({
                'file': rec['file'],
                'n_skills': delta['n_skills'],
            })
    report = {
        'files': len(rows),
        'invented_jobs': invented,
        'jobs_removed': lost_jobs,
        'new_degree_losses': lost_edu,
        'new_skill_losses': skill_fn,
        'skill_count_spikes': skill_fp,
        'deltas': rows,
    }
    dest = root / 'section_bench_compare.json'
    dest.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
    print('invented_jobs', len(invented), invented)
    print('jobs_removed', len(lost_jobs), lost_jobs)
    print('new_skill_losses', skill_fn)
    print('new_degree_losses', lost_edu)
    print('wrote', dest)
    return dest


if __name__ == '__main__':
    tag = sys.argv[1] if len(sys.argv) > 1 else 'before'
    if tag == 'compare':
        before_p = Path(sys.argv[2]) if len(sys.argv) > 2 else None
        after_p = Path(sys.argv[3]) if len(sys.argv) > 3 else None
        compare(before_p, after_p)
    else:
        measure(tag)
