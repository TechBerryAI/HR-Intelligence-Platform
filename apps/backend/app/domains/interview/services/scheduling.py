"""Interview scheduling helpers: create sessions, notify candidates, serialize rows."""
from __future__ import annotations

import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.common.application_status import STATUS_INTERVIEW
from app.database.connection.db import db_all, db_get, db_run
from app.domains.interview.services.ai_interview import generate_interview_questions
from app.integrations.email.utils import send_notification_email


def _frontend_base() -> str:
    return (os.getenv('FRONTEND_URL') or os.getenv('FRONTEND_URLS', 'http://localhost:5173').split(',')[0]).strip().rstrip('/')


def _json_col(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _parse_json(value: Any, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


def serialize_interview(row: Dict[str, Any], *, include_questions: bool = False, include_answers: bool = False) -> Dict[str, Any]:
    if not row:
        return {}
    invite = row.get('invite_token')
    payload = {
        'id': str(row.get('id')),
        'application_id': row.get('application_id'),
        'status': row.get('status'),
        'interviewer_type': row.get('interviewer_type') or 'ai',
        'scheduled_at': row.get('scheduled_at').isoformat() if hasattr(row.get('scheduled_at'), 'isoformat') else row.get('scheduled_at'),
        'completed_at': row.get('completed_at').isoformat() if hasattr(row.get('completed_at'), 'isoformat') else row.get('completed_at'),
        'duration_minutes': row.get('duration_minutes') or 30,
        'interview_type': row.get('interview_type'),
        'location': row.get('location'),
        'notes': row.get('notes'),
        'meeting_link': row.get('meeting_link'),
        'invite_token': invite,
        'candidate_link': f'{_frontend_base()}/interview/{invite}' if invite else None,
        'overall_score': float(row['overall_score']) if row.get('overall_score') is not None else None,
        'score_summary': row.get('score_summary'),
        'assigned_to': row.get('assigned_to'),
        'created_by': row.get('created_by'),
        'candidate_name': row.get('candidate_name'),
        'candidate_email': row.get('candidate_email'),
        'job_title': row.get('job_title'),
        'job_company': row.get('job_company'),
        'created_at': row.get('created_at').isoformat() if hasattr(row.get('created_at'), 'isoformat') else row.get('created_at'),
    }
    if include_questions:
        payload['questions'] = _parse_json(row.get('questions_json'), [])
    if include_answers:
        payload['answers'] = _parse_json(row.get('answers_json'), [])
    return payload


def get_application_context(application_id: int) -> Optional[Dict[str, Any]]:
    return db_get(
        '''SELECT a.id, a.candidate_id, a.job_id, a.status, a.shortlisted,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company,
                  j.description AS job_description, j.location AS job_location
           FROM applications a
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           WHERE a.id = ?''',
        (application_id,),
    )


def create_interview(
    *,
    application_id: int,
    created_by: str,
    interviewer_type: str = 'ai',
    scheduled_at: Optional[str] = None,
    duration_minutes: int = 30,
    notes: str = '',
    assigned_to: Optional[str] = None,
    meeting_link: str = '',
) -> Dict[str, Any]:
    interviewer_type = (interviewer_type or 'ai').lower().strip()
    if interviewer_type not in ('ai', 'human'):
        raise ValueError('interviewer_type must be "ai" or "human"')

    app_row = get_application_context(application_id)
    if not app_row:
        raise ValueError('Application not found')

    duration_minutes = max(10, min(180, int(duration_minutes or 30)))
    interview_id = str(uuid.uuid4())
    invite_token = secrets.token_urlsafe(24)
    when = scheduled_at or datetime.now(timezone.utc).isoformat()

    questions: List[Dict[str, Any]] = []
    if interviewer_type == 'ai':
        candidate_summary = f"{app_row.get('candidate_name') or ''} ({app_row.get('candidate_email') or ''})"
        questions = generate_interview_questions(
            job_title=app_row.get('job_title') or '',
            company=app_row.get('job_company') or '',
            job_context=app_row.get('job_description') or '',
            candidate_summary=candidate_summary,
            count=5,
        )

    human_assignee = assigned_to or (created_by if interviewer_type == 'human' else None)

    db_run(
        '''INSERT INTO interviews (
            id, application_id, assigned_to, status, scheduled_at,
            interview_type, location, notes, created_by, updated_by,
            interviewer_type, duration_minutes, invite_token, meeting_link,
            questions_json, answers_json
        ) VALUES (
            ?::uuid, ?, ?, 'Scheduled', ?::timestamptz,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?,
            ?::jsonb, ?::jsonb
        )''',
        (
            interview_id,
            application_id,
            human_assignee,
            when,
            'AI Interview' if interviewer_type == 'ai' else 'Human Interview',
            meeting_link or None,
            notes or None,
            created_by,
            created_by,
            interviewer_type,
            duration_minutes,
            invite_token,
            meeting_link or None,
            _json_col(questions),
            _json_col([]),
        ),
    )

    # Move application toward interview stage
    try:
        db_run(
            "UPDATE applications SET status = ? WHERE id = ?",
            (STATUS_INTERVIEW, application_id),
        )
    except Exception as e:
        print(f'[interview] status update skipped: {e}')

    link = f'{_frontend_base()}/interview/{invite_token}'
    _send_invite_email(app_row, link, interviewer_type, when, duration_minutes)

    row = get_interview_by_id(interview_id)
    return serialize_interview(row, include_questions=True)


def _send_invite_email(app_row: Dict[str, Any], link: str, interviewer_type: str, when: str, duration: int) -> None:
    email = (app_row.get('candidate_email') or '').strip()
    if not email:
        return
    name = (app_row.get('candidate_name') or '').strip() or 'there'
    job = app_row.get('job_title') or 'the role'
    company = app_row.get('job_company') or 'our company'
    if interviewer_type == 'ai':
        subject = f'AI interview invitation — {job}'
        body = (
            f'Hi {name},\n\n'
            f'You have been invited to complete an AI-powered interview for {job} at {company}.\n\n'
            f'Scheduled: {when}\n'
            f'Duration: about {duration} minutes\n\n'
            f'Start your interview here (no login required):\n{link}\n\n'
            f'The interview is conducted by our AI interviewer — no human interviewer will join the session.\n\n'
            f'— HR Intelligence'
        )
    else:
        subject = f'Interview invitation — {job}'
        body = (
            f'Hi {name},\n\n'
            f'You have been invited to an interview for {job} at {company}.\n\n'
            f'Scheduled: {when}\n'
            f'Duration: about {duration} minutes\n\n'
            f'Details: {link}\n\n'
            f'— HR Intelligence'
        )
    try:
        send_notification_email(email, subject, body)
    except Exception as e:
        print(f'[interview] email failed: {e}')


def list_interviews(limit: int = 100) -> List[Dict[str, Any]]:
    rows = db_all(
        '''SELECT i.*,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           ORDER BY i.scheduled_at DESC NULLS LAST, i.created_at DESC
           LIMIT ?''',
        (limit,),
    )
    return [serialize_interview(r) for r in rows]


def list_interviews_for_application(application_id: int) -> List[Dict[str, Any]]:
    rows = db_all(
        '''SELECT i.*,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           WHERE i.application_id = ?
           ORDER BY i.created_at DESC''',
        (application_id,),
    )
    return [serialize_interview(r, include_questions=True, include_answers=True) for r in rows]


def get_interview_by_id(interview_id: str) -> Optional[Dict[str, Any]]:
    return db_get(
        '''SELECT i.*,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           WHERE i.id = ?::uuid''',
        (interview_id,),
    )


def get_interview_by_token(token: str) -> Optional[Dict[str, Any]]:
    return db_get(
        '''SELECT i.*,
                  cs.name AS candidate_name, cs.email AS candidate_email,
                  j.title AS job_title, j.company AS job_company
           FROM interviews i
           JOIN applications a ON a.id = i.application_id
           LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
           LEFT JOIN jobs j ON j.jdid = a.job_id
           WHERE i.invite_token = ?''',
        (token,),
    )
