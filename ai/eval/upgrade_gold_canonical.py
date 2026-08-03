#!/usr/bin/env python3
"""
Upgrade gold lake with expected_canonical.json + expected_frontend_fields.json.

Derived from expected_toon.json via the Document Intelligence canonical boundary
(so gold stays aligned with the single canonical schema).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / 'apps' / 'backend'
sys.path.insert(0, str(BACKEND))

from app.ai.document_intelligence.canonical.from_toon import (  # noqa: E402
    candidate_profile_from_toon,
    job_profile_from_toon,
)
from app.ai.document_intelligence.mapping.jd_form import map_job_to_form  # noqa: E402
from app.ai.document_intelligence.mapping.resume_form import map_candidate_to_form  # noqa: E402

LAKE = ROOT / 'ai' / 'dataset' / 'lake' / 'benchmark' / 'parsing' / 'v1'


def _upgrade_resume(case_dir: Path) -> None:
    toon = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    profile = candidate_profile_from_toon(toon)
    form = map_candidate_to_form(profile)
    (case_dir / 'expected_canonical.json').write_text(
        json.dumps(profile.model_dump(), indent=2), encoding='utf-8'
    )
    frontend = form.to_autofill_dict()
    frontend.pop('trace', None)
    (case_dir / 'expected_frontend_fields.json').write_text(
        json.dumps(frontend, indent=2), encoding='utf-8'
    )
    # Expand expected_form with nested rows when missing
    exp_form_path = case_dir / 'expected_form.json'
    exp = json.loads(exp_form_path.read_text(encoding='utf-8'))
    for key in (
        'fullName', 'email', 'phone', 'linkedinUrl', 'githubUrl',
        'currentLocation', 'skills', 'experienceLevel', 'summary',
    ):
        if key not in exp and getattr(form, key, None):
            exp[key] = getattr(form, key)
    exp_form_path.write_text(json.dumps(exp, indent=2), encoding='utf-8')


def _upgrade_jd(case_dir: Path) -> None:
    toon = json.loads((case_dir / 'expected_toon.json').read_text(encoding='utf-8'))
    profile = job_profile_from_toon(toon)
    form = map_job_to_form(profile)
    (case_dir / 'expected_canonical.json').write_text(
        json.dumps(profile.model_dump(), indent=2), encoding='utf-8'
    )
    frontend = form.to_autofill_dict()
    frontend.pop('trace', None)
    (case_dir / 'expected_frontend_fields.json').write_text(
        json.dumps(frontend, indent=2), encoding='utf-8'
    )


def main() -> None:
    resumes = sorted((LAKE / 'resumes').iterdir()) if (LAKE / 'resumes').exists() else []
    jds = sorted((LAKE / 'jds').iterdir()) if (LAKE / 'jds').exists() else []
    n_r = n_j = 0
    for d in resumes:
        if d.is_dir() and (d / 'expected_toon.json').exists():
            _upgrade_resume(d)
            n_r += 1
    for d in jds:
        if d.is_dir() and (d / 'expected_toon.json').exists():
            _upgrade_jd(d)
            n_j += 1
    print(f'Upgraded {n_r} resumes + {n_j} JDs with expected_canonical + expected_frontend_fields')


if __name__ == '__main__':
    main()
