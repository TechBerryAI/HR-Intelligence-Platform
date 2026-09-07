"""Trace bullet flattening, extra skills, and summary joining on the 24-resume corpus."""
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

from app.ai.document_intelligence.bullets import BULLET_PREFIX_RE, is_bullet_line
from app.ai.document_intelligence.pipeline import parse_resume_text_to_canonical
from app.ai.document_intelligence.sections import detect_sections, pick_section
from app.ai.parser.text_extraction import extract_text

CORPUS = Path(r'C:\Users\DELL\Downloads\resume testing')
SKIP = {'aadhar vishal c.pdf', '_organize_log.txt'}
DUTY_VERB = re.compile(
    r'(?i)^(?:managed|executed|developed|designed|created|built|led|drove|'
    r'implemented|optimized|improved|worked|assisted|supported|handled|'
    r'performed|conducted|analyzed|monitored|delivered|responsible\s+for)\b'
)


def files() -> list[Path]:
    return [
        p for p in sorted(CORPUS.iterdir(), key=lambda x: x.name.lower())
        if p.is_file()
        and p.name.lower() not in SKIP
        and p.suffix.lower() in {'.pdf', '.docx', '.doc'}
    ]


def count_bullets(text: str) -> int:
    n = 0
    for ln in (text or '').splitlines():
        s = ln.strip()
        if is_bullet_line(s) or DUTY_VERB.match(re.sub(r'^[\s•·\-\*●]+', '', s)):
            n += 1
    return n


def grounded_in(item: str, hay: str) -> bool:
    t = re.sub(r'\s+', ' ', (item or '').strip().lower())
    if len(t) < 2:
        return False
    blob = re.sub(r'\s+', ' ', (hay or '').lower())
    # token overlap: first 3 words must appear
    head = ' '.join(t.split()[:3])
    return head in blob


def main() -> None:
    rows = []
    for p in files():
        print('FILE', p.name[:70], flush=True)
        text = extract_text(p.read_bytes(), p.name) or ''
        spans = detect_sections(text, 'resume')
        profile, form, _ = parse_resume_text_to_canonical(
            text, max_workers=2, allow_semantic=False, source_filename=p.name
        )
        exp_src = pick_section(spans, 'Experience', 'Work Experience', 'Employment') or ''
        skills_src = pick_section(
            spans, 'Skills', 'Technical Skills', 'Key Skills', 'Skill Set', 'Skillset'
        ) or ''
        sum_src = pick_section(
            spans, 'Summary', 'Professional Summary', 'Career Objective', 'Objective', 'About Me'
        ) or ''
        src_bullets = count_bullets(exp_src)
        jobs = []
        desc_lines_total = 0
        desc_flat = 0
        for e in profile.experience:
            desc = e.description or ''
            nlines = len([ln for ln in desc.splitlines() if ln.strip()])
            desc_lines_total += nlines
            looks_para = nlines <= 1 and len(desc) > 80
            if looks_para:
                desc_flat += 1
            jobs.append(
                {
                    'c': e.company,
                    'r': e.role,
                    'desc_chars': len(desc),
                    'desc_lines': nlines,
                    'desc_has_bullet': bool(BULLET_PREFIX_RE.search(desc)),
                    'desc_head': desc[:160].replace('\n', ' \\n '),
                }
            )
        summary = profile.personal.summary or ''
        sum_lines = len([ln for ln in summary.splitlines() if ln.strip()])
        src_sum_bullets = count_bullets(sum_src)
        extra_skills = []
        duty_skills = []
        for s in profile.skills:
            name = s.name or ''
            if not grounded_in(name, skills_src) and not grounded_in(name, sum_src[:400]):
                # still ok if in skills_src after stripping labels
                extra_skills.append(name)
            if DUTY_VERB.match(name) or len(name.split()) >= 8 or re.search(r'[.=]', name) and len(name) > 40:
                duty_skills.append(name)
        rec = {
            'file': p.name,
            'src_exp_bullets': src_bullets,
            'n_exp': len(profile.experience),
            'jobs_desc_flat': desc_flat,
            'jobs_desc_lines': desc_lines_total,
            'jobs': jobs,
            'src_sum_bullets': src_sum_bullets,
            'sum_chars': len(summary),
            'sum_lines': sum_lines,
            'sum_flat': bool(summary) and sum_lines <= 1 and src_sum_bullets >= 2,
            'sum_head': summary[:180].replace('\n', ' \\n '),
            'n_skills': len(profile.skills),
            'skills': [s.name for s in profile.skills[:20]],
            'extra_or_ungrounded': extra_skills[:12],
            'duty_like_skills': duty_skills[:8],
            'skills_src_chars': len(skills_src),
            'skills_src_head': skills_src[:120].replace('\n', ' | '),
        }
        rows.append(rec)
        print(
            f"  exp_src_bul={src_bullets} jobs={len(jobs)} desc_flat={desc_flat} "
            f"sum_flat={rec['sum_flat']} sk={len(profile.skills)} "
            f"ungrounded={len(extra_skills)} duty_sk={len(duty_skills)}",
            flush=True,
        )
    dest = ROOT / '_forensic_tmp' / 'trace_desc_skills_summary.json'
    dest.write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding='utf-8')
    print('wrote', dest)
    print('SUMMARY files', len(rows))
    print('desc_flat_jobs', sum(r['jobs_desc_flat'] for r in rows))
    print('sum_flat', sum(1 for r in rows if r['sum_flat']))
    print('files_with_ungrounded_skills', sum(1 for r in rows if r['extra_or_ungrounded']))
    print('files_with_duty_skills', sum(1 for r in rows if r['duty_like_skills']))


if __name__ == '__main__':
    main()
