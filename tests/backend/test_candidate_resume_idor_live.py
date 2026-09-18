"""Live-DB regression: Head HR candidate detail/resume endpoints are org-scoped.

The existing coverage for ``get_candidate`` / ``get_candidate_resume``
(test_media_resume_retrieval.py) only asserts that the word
``organization_id`` appears in the function's source text — it never issues
a real request, so it would keep passing even if the check were wired to the
wrong variable or a dead branch. This file exercises the actual HTTP
boundary against live PostgreSQL, including the BUG-004 worst case: two
organizations that share an identical display name.
"""
from __future__ import annotations

import uuid

from live_db_helpers import (
    app_client,  # noqa: F401
    auth_header,
    login,
    seed_candidate_with_application,
    seed_job,
    seed_org_with_staff_same_name,
)


def test_candidate_and_resume_denied_across_orgs_with_same_display_name(app_client):
    shared_name = f'Acme Technologies {uuid.uuid4().hex[:6]}'
    a = seed_org_with_staff_same_name(shared_name)
    b = seed_org_with_staff_same_name(shared_name)
    assert a['org_id'] != b['org_id']

    job_a = seed_job(a['org_id'], a['recruiter_hrid'])
    cid_a = seed_candidate_with_application(a['org_id'], job_a)

    token_b = login(app_client, b['head_email'])
    headers_b = auth_header(token_b)

    detail_b = app_client.get(f'/api/head-hr/candidates/{cid_a}', headers=headers_b)
    assert detail_b.status_code == 404

    resume_b = app_client.get(f'/api/head-hr/candidates/{cid_a}/resume', headers=headers_b)
    assert resume_b.status_code == 404
    assert resume_b.get_json()['error'] == 'Resume not found'

    # Org B cannot delete org A's candidate either.
    delete_b = app_client.delete(f'/api/head-hr/candidates/{cid_a}', headers=headers_b)
    assert delete_b.status_code == 404

    # Sanity: org A's own Head HR can see its candidate.
    token_a = login(app_client, a['head_email'])
    detail_a = app_client.get(f'/api/head-hr/candidates/{cid_a}', headers=auth_header(token_a))
    assert detail_a.status_code == 200
    assert detail_a.get_json()['candidate_id'] == cid_a

    from app.database.connection.db import db_get

    still_there = db_get('SELECT cid FROM candidates WHERE cid = ?', (cid_a,))
    assert still_there is not None
