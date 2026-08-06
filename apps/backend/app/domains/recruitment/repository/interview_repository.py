"""Interview + interview_slots persistence."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.database.connection.db import db_all, db_get, db_run

STATUS_INVITED = 'Invited'
STATUS_SCHEDULED = 'Scheduled'
STATUS_COMPLETED = 'Completed'
STATUS_CANCELLED = 'Cancelled'


def get_open_interview_for_application(application_id: int) -> dict | None:
    return db_get(
        '''
        SELECT * FROM interviews
        WHERE application_id = ?
          AND status IN (?, ?)
        ORDER BY created_at DESC
        LIMIT 1
        ''',
        (application_id, STATUS_INVITED, STATUS_SCHEDULED),
    )


def get_interview_by_token(token: str) -> dict | None:
    return db_get(
        'SELECT * FROM interviews WHERE invite_token = ?',
        (token,),
    )


def get_interview_by_id(interview_id: str) -> dict | None:
    return db_get('SELECT * FROM interviews WHERE id = ?', (interview_id,))


def create_invited_interview(
    *,
    application_id: int,
    assigned_to: str,
    invite_token: str,
    invite_expires_at: datetime,
    duration_minutes: int,
    interviewer_hrid: str | None = None,
) -> dict | None:
    return db_get(
        '''
        INSERT INTO interviews (
            application_id, assigned_to, status, duration_minutes,
            invite_token, invite_expires_at, interviewer_type, interviewer_hrid,
            created_by, updated_by
        )
        VALUES (?, ?, ?, ?, ?, ?, 'human', ?, ?, ?)
        RETURNING *
        ''',
        (
            application_id,
            assigned_to,
            STATUS_INVITED,
            duration_minutes,
            invite_token,
            invite_expires_at,
            interviewer_hrid,
            assigned_to,
            assigned_to,
        ),
    )


def update_interview_invite(
    interview_id: str,
    *,
    invite_token: str,
    invite_expires_at: datetime,
    assigned_to: str,
    duration_minutes: int,
) -> None:
    db_run(
        '''
        UPDATE interviews
        SET invite_token = ?,
            invite_expires_at = ?,
            assigned_to = ?,
            duration_minutes = ?,
            status = ?,
            updated_at = NOW(),
            updated_by = ?
        WHERE id = ?
        ''',
        (
            invite_token,
            invite_expires_at,
            assigned_to,
            duration_minutes,
            STATUS_INVITED,
            assigned_to,
            interview_id,
        ),
    )


def delete_slots_for_interview(interview_id: str) -> None:
    db_run('DELETE FROM interview_slots WHERE interview_id = ? AND is_booked = FALSE', (interview_id,))


def insert_slots(interview_id: str, recruiter_hrid: str, slots: list[tuple[datetime, datetime]]) -> list[dict]:
    created: list[dict] = []
    for start, end in slots:
        row = db_get(
            '''
            INSERT INTO interview_slots (interview_id, recruiter_hrid, start_time, end_time, is_booked)
            VALUES (?, ?, ?, ?, FALSE)
            RETURNING *
            ''',
            (interview_id, recruiter_hrid, start, end),
        )
        if row:
            created.append(row)
    return created


def list_available_slots(interview_id: str) -> list[dict]:
    return db_all(
        '''
        SELECT * FROM interview_slots
        WHERE interview_id = ? AND is_booked = FALSE
        ORDER BY start_time ASC
        ''',
        (interview_id,),
    )


def get_slot(slot_id: str, interview_id: str) -> dict | None:
    return db_get(
        '''
        SELECT * FROM interview_slots
        WHERE id = ? AND interview_id = ?
        ''',
        (slot_id, interview_id),
    )


def mark_slot_booked(slot_id: str) -> None:
    db_run(
        'UPDATE interview_slots SET is_booked = TRUE WHERE id = ?',
        (slot_id,),
    )


def mark_slot_unavailable(slot_id: str) -> None:
    """Treat as booked so it is no longer offered (became unavailable)."""
    mark_slot_booked(slot_id)


def confirm_interview_scheduled(
    interview_id: str,
    *,
    scheduled_at: datetime,
    calendar_event_id: str | None,
    meeting_link: str | None,
    updated_by: str | None,
) -> None:
    db_run(
        '''
        UPDATE interviews
        SET status = ?,
            scheduled_at = ?,
            calendar_event_id = ?,
            meeting_link = ?,
            updated_at = NOW(),
            updated_by = ?
        WHERE id = ?
        ''',
        (
            STATUS_SCHEDULED,
            scheduled_at,
            calendar_event_id,
            meeting_link,
            updated_by,
            interview_id,
        ),
    )


def get_application_context(application_id: int) -> dict | None:
    """Application + job + candidate + recruiter emails for scheduling."""
    return db_get(
        '''
        SELECT
            a.id AS application_id,
            a.candidate_id,
            a.job_id,
            a.status AS application_status,
            a.shortlisted,
            j.title AS job_title,
            j.company AS company_name,
            j.posted_by AS job_posted_by,
            COALESCE(cp.full_name, '') AS candidate_name,
            COALESCE(cp.email, cs.email) AS candidate_email,
            hr.full_name AS recruiter_name,
            hr.email AS recruiter_email
        FROM applications a
        JOIN jobs j ON j.jdid = a.job_id
        LEFT JOIN candidate_profiles cp ON cp.candidate_id = a.candidate_id
        LEFT JOIN candidate_signup cs ON cs.cid = a.candidate_id
        LEFT JOIN hr_signup hr ON hr.hrid = j.posted_by
        WHERE a.id = ?
        ''',
        (application_id,),
    )


def get_hr_email(hrid: str) -> str | None:
    row = db_get('SELECT email, full_name FROM hr_signup WHERE hrid = ?', (hrid,))
    return (row or {}).get('email')


def get_hr_row(hrid: str) -> dict | None:
    return db_get('SELECT hrid, email, full_name FROM hr_signup WHERE hrid = ?', (hrid,))


def set_application_status(application_id: int, status: str) -> None:
    db_run(
        'UPDATE applications SET status = ? WHERE id = ?',
        (status, application_id),
    )


def serialize_slot(row: dict) -> dict[str, Any]:
    start = row.get('start_time')
    end = row.get('end_time')
    return {
        'id': str(row.get('id')),
        'startTime': start.isoformat() if getattr(start, 'isoformat', None) else start,
        'endTime': end.isoformat() if getattr(end, 'isoformat', None) else end,
        'isBooked': bool(row.get('is_booked')),
    }
