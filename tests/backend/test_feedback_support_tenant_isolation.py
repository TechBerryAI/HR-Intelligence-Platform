"""Cross-tenant isolation for employee feedback and support-request inboxes.

``employee_feedback`` and ``support_requests`` have no organization_id column
of their own — they are attributed to a tenant only via the submitter
(``submitted_by`` -> hr_signup.organization_id, or ``user_id``/``user_type``
-> hr_signup/candidates.organization_id). Before this fix, GET/PATCH on
these endpoints had no tenant scoping at all: any authenticated recruiter or
Head HR from *any* organization could read and modify *every* other
organization's feedback and support tickets. Runs against live PostgreSQL —
no DB mocks for the tenant-boundary checks.
"""
from __future__ import annotations

from live_db_helpers import app_client, auth_header, login, seed_org_with_staff  # noqa: F401


def test_feedback_isolated_by_submitters_organization(app_client):
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    token_a = login(app_client, a['head_email'])
    token_b = login(app_client, b['head_email'])

    submit = app_client.post(
        '/api/feedback/submit',
        headers=auth_header(token_a),
        json={
            'employee_name': 'Org A Employee',
            'feedback_type': 'Bug Report',
            'severity': 'High',
            'description': 'Something only org A should ever see.',
        },
    )
    assert submit.status_code == 201, submit.get_json()
    feedback_id = submit.get_json()['feedback_id']

    # Org B must not see org A's feedback in the list.
    listing_b = app_client.get('/api/feedback/list', headers=auth_header(token_b))
    assert listing_b.status_code == 200
    ids_b = {row['id'] for row in listing_b.get_json()['feedback']}
    assert feedback_id not in ids_b

    # Org B cannot mutate org A's feedback by guessing/enumerating its id.
    patch_b = app_client.patch(
        f'/api/feedback/{feedback_id}/status',
        headers=auth_header(token_b),
        json={'status': 'resolved'},
    )
    assert patch_b.status_code == 404

    # Org A still sees and can manage its own feedback.
    listing_a = app_client.get('/api/feedback/list', headers=auth_header(token_a))
    ids_a = {row['id'] for row in listing_a.get_json()['feedback']}
    assert feedback_id in ids_a

    patch_a = app_client.patch(
        f'/api/feedback/{feedback_id}/status',
        headers=auth_header(token_a),
        json={'status': 'resolved'},
    )
    assert patch_a.status_code == 200

    from app.database.connection.db import db_get

    row = db_get('SELECT status FROM employee_feedback WHERE id = ?', (feedback_id,))
    assert row['status'] == 'resolved'


def test_support_request_isolated_by_submitters_organization(app_client):
    a = seed_org_with_staff()
    b = seed_org_with_staff()
    token_a_head = login(app_client, a['head_email'])
    token_b_head = login(app_client, b['head_email'])

    submit = app_client.post(
        '/api/support/submit',
        headers=auth_header(token_a_head),
        json={
            'name': 'Org A Head HR',
            'email': a['head_email'],
            'subject': 'Only org A should see this',
            'message': 'Confidential org A support message.',
        },
    )
    assert submit.status_code == 201, submit.get_json()
    request_id = submit.get_json()['request_id']

    # Org B's Head HR must not see org A's ticket at all.
    listing_b = app_client.get('/api/support/all', headers=auth_header(token_b_head))
    assert listing_b.status_code == 200
    ids_b = {row['id'] for row in listing_b.get_json()['requests']}
    assert request_id not in ids_b

    detail_b = app_client.get(f'/api/support/{request_id}', headers=auth_header(token_b_head))
    assert detail_b.status_code == 404

    patch_b = app_client.patch(
        f'/api/support/{request_id}/status',
        headers=auth_header(token_b_head),
        json={'status': 'closed', 'admin_notes': 'org B should never write this'},
    )
    assert patch_b.status_code == 404

    # Org A's own Head HR can see and manage its own ticket.
    listing_a = app_client.get('/api/support/all', headers=auth_header(token_a_head))
    ids_a = {row['id'] for row in listing_a.get_json()['requests']}
    assert request_id in ids_a

    detail_a = app_client.get(f'/api/support/{request_id}', headers=auth_header(token_a_head))
    assert detail_a.status_code == 200

    patch_a = app_client.patch(
        f'/api/support/{request_id}/status',
        headers=auth_header(token_a_head),
        json={'status': 'resolved', 'admin_notes': 'handled internally'},
    )
    assert patch_a.status_code == 200

    from app.database.connection.db import db_get

    row = db_get('SELECT status, admin_notes FROM support_requests WHERE id = ?', (request_id,))
    assert row['status'] == 'resolved'
    assert row['admin_notes'] == 'handled internally'


def test_guest_support_request_not_visible_to_any_tenant(app_client):
    """A guest (unauthenticated, no org) ticket belongs to no tenant and must
    not leak into any organization's Head HR inbox."""
    a = seed_org_with_staff()
    token_a_head = login(app_client, a['head_email'])

    submit = app_client.post(
        '/api/support/submit',
        json={
            'name': 'Random Visitor',
            'email': 'visitor@example.com',
            'subject': 'Pre-signup question',
            'message': 'Not tied to any company.',
        },
    )
    assert submit.status_code == 201, submit.get_json()
    request_id = submit.get_json()['request_id']

    listing_a = app_client.get('/api/support/all', headers=auth_header(token_a_head))
    ids_a = {row['id'] for row in listing_a.get_json()['requests']}
    assert request_id not in ids_a

    detail_a = app_client.get(f'/api/support/{request_id}', headers=auth_header(token_a_head))
    assert detail_a.status_code == 404
