"""Persist candidate email send status per application."""
from __future__ import annotations

from app.database.connection.db import db_all, db_run

KIND_SHORTLISTED = 'SHORTLISTED'
KIND_NOT_SHORTLISTED = 'NOT_SHORTLISTED'
KIND_PROFILE_VIEWED = 'PROFILE_VIEWED'
KIND_INTERVIEW_INVITE = 'INTERVIEW_INVITE'

STATUS_SENT = 'sent'
STATUS_FAILED = 'failed'


def log_email_event(
    *,
    application_id: int | None,
    email_kind: str,
    recipient: str | None,
    subject: str | None = None,
    status: str = STATUS_SENT,
) -> None:
    if not application_id or not email_kind:
        return
    try:
        db_run(
            '''
            INSERT INTO application_email_events
                (application_id, email_kind, recipient, subject, status)
            VALUES (?, ?, ?, ?, ?)
            ''',
            (
                int(application_id),
                (email_kind or '').strip().upper(),
                (recipient or '').strip() or None,
                (subject or '').strip() or None,
                (status or STATUS_SENT).strip().lower(),
            ),
        )
    except Exception as exc:
        print(f'[EMAIL_EVENT] failed to log app={application_id} kind={email_kind}: {exc}')


def list_email_status_for_job(jdid: str, organization_id) -> list[dict]:
    """One row per application with latest shortlist + interview-invite email status."""
    return db_all(
        '''
        SELECT
            a.id AS application_id,
            a.candidate_id,
            a.status AS application_status,
            a.shortlisted,
            a.applied_at,
            COALESCE(cp.full_name, cs.name, '') AS candidate_name,
            COALESCE(cp.email, cs.email) AS candidate_email,
            (
              SELECT e.status FROM application_email_events e
              WHERE e.application_id = a.id AND e.email_kind = 'SHORTLISTED'
              ORDER BY e.sent_at DESC LIMIT 1
            ) AS shortlist_email_status,
            (
              SELECT e.sent_at FROM application_email_events e
              WHERE e.application_id = a.id AND e.email_kind = 'SHORTLISTED'
              ORDER BY e.sent_at DESC LIMIT 1
            ) AS shortlist_email_sent_at,
            (
              SELECT e.status FROM application_email_events e
              WHERE e.application_id = a.id AND e.email_kind = 'INTERVIEW_INVITE'
              ORDER BY e.sent_at DESC LIMIT 1
            ) AS interview_email_status,
            (
              SELECT e.sent_at FROM application_email_events e
              WHERE e.application_id = a.id AND e.email_kind = 'INTERVIEW_INVITE'
              ORDER BY e.sent_at DESC LIMIT 1
            ) AS interview_email_sent_at,
            i.status AS interview_status,
            i.scheduled_at,
            i.created_at AS interview_created_at
        FROM applications a
        JOIN jobs j ON j.jdid = a.job_id AND j.organization_id = ?
        LEFT JOIN candidate_profiles cp ON cp.candidate_id = a.candidate_id
        LEFT JOIN candidates cs ON cs.cid = a.candidate_id
        LEFT JOIN LATERAL (
            SELECT ii.status, ii.scheduled_at, ii.created_at
            FROM interviews ii
            WHERE ii.application_id = a.id
              AND ii.status IN ('Invited', 'Scheduled')
            ORDER BY ii.created_at DESC
            LIMIT 1
        ) i ON TRUE
        WHERE a.job_id = ?
          AND (
            a.shortlisted IS TRUE
            OR a.status IN ('Shortlisted', 'Interview')
          )
        ORDER BY a.applied_at DESC
        ''',
        (organization_id, jdid),
    )
