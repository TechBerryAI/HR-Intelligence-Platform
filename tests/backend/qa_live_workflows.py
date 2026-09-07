"""Live-stack workflow smoke (HTTP) — run against node start.js."""
from __future__ import annotations

import json
import os
import sys
from io import BytesIO

import httpx

BASE = os.getenv('QA_BASE_URL', 'http://localhost:3000')
FE = os.getenv('QA_FE_URL', 'http://localhost:5173')
HEAD_HR = (
    os.getenv('SMOKE_HEAD_HR_EMAIL', 'chetan.gore@techberryinfotech.com'),
    os.getenv('SMOKE_HEAD_HR_PASSWORD', 'P@ssw0rd'),
)
CEO = (
    os.getenv('SMOKE_CEO_EMAIL', 'unmesh.tari@techberryinfotech.com'),
    os.getenv('SMOKE_CEO_PASSWORD', 'P@ssw0rd'),
)

results: list[tuple[str, str, str]] = []


def record(name: str, ok: bool, detail: str = '') -> None:
    results.append((name, 'PASS' if ok else 'FAIL', detail))


def login(client: httpx.Client, email: str, password: str) -> str | None:
    r = client.post(f'{BASE}/api/login', json={'email': email, 'password': password})
    if r.status_code != 200:
        return None
    return (r.json() or {}).get('token')


def main() -> int:
    fails = 0
    with httpx.Client(timeout=30.0) as client:
        # 1 Landing / health
        h = client.get(f'{BASE}/health')
        record('health', h.status_code == 200, str(h.status_code))
        rdy = client.get(f'{BASE}/ready')
        record('ready', rdy.status_code == 200, (rdy.json() or {}).get('status', ''))
        fe = client.get(FE)
        record('frontend_home', fe.status_code == 200, str(fe.status_code))

        # 2 Public jobs
        jobs = client.get(f'{BASE}/api/jobs/')
        record('public_jobs', jobs.status_code == 200, f'count={len(jobs.json() if isinstance(jobs.json(), list) else (jobs.json() or {}).get("jobs") or [])}')

        # 3 Hero video
        hv = client.get(f'{BASE}/api/media/public/hero-video')
        record('hero_video', hv.status_code in (200, 206, 302), str(hv.status_code))

        # 4 Staff logins + role redirects (API only)
        hr_tok = login(client, *HEAD_HR)
        record('head_hr_login', bool(hr_tok))
        ceo_tok = login(client, *CEO)
        record('ceo_login', bool(ceo_tok))

        if hr_tok:
            stats = client.get(f'{BASE}/api/head-hr/stats', headers={'Authorization': f'Bearer {hr_tok}'})
            record('head_hr_stats', stats.status_code == 200)
            cands = client.get(f'{BASE}/api/head-hr/candidates', headers={'Authorization': f'Bearer {hr_tok}'})
            record('head_hr_candidates', cands.status_code == 200)
            bulk_jobs = client.post(
                f'{BASE}/api/admin/bulk-parse/jobs',
                headers={'Authorization': f'Bearer {hr_tok}'},
                json={'label': 'QA smoke'},
            )
            record('bulk_parse_create_job', bulk_jobs.status_code in (200, 201), str(bulk_jobs.status_code))

        if ceo_tok:
            ceo_stats = client.get(f'{BASE}/api/head-hr/stats', headers={'Authorization': f'Bearer {ceo_tok}'})
            record('ceo_read_stats', ceo_stats.status_code == 200)
            blocked = client.post(
                f'{BASE}/api/jobs/',
                headers={'Authorization': f'Bearer {ceo_tok}'},
                json={'title': 'QA', 'company': 'X', 'location': 'Remote'},
            )
            record('ceo_create_blocked', blocked.status_code == 403, str(blocked.status_code))

        # 5 Public parse (minimal PDF)
        pdf = b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n2 0 obj<</Type/Pages/Kids[]/Count 0>>endobj\nxref\n0 3\ntrailer<</Root 1 0 R>>\nstartxref\n0\n%%EOF'
        parse = client.post(
            f'{BASE}/api/parse/resume/public',
            files={'file': ('smoke.pdf', BytesIO(pdf), 'application/pdf')},
        )
        record('public_parse', parse.status_code in (200, 400, 422, 500), str(parse.status_code))

        # 6 Support form validation
        sup = client.post(f'{BASE}/api/support/submit', json={})
        record('support_validation', sup.status_code in (400, 422), str(sup.status_code))

        # 7 Interview invalid token
        book = client.get(f'{BASE}/api/interviews/book/invalid-qa-token')
        record('interview_invalid_token', book.status_code in (400, 404), str(book.status_code))

    for name, status, detail in results:
        print(f'{status:4} {name:30} {detail}')
        if status == 'FAIL':
            fails += 1
    print(f'\nWorkflow checks: {len(results) - fails}/{len(results)} passed')
    return 1 if fails else 0


if __name__ == '__main__':
    sys.exit(main())
