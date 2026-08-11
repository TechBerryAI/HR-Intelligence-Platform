"""Interview scheduling after Shortlisted — Google Calendar FreeBusy + booking."""
from __future__ import annotations

import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.common.application_status import STATUS_INTERVIEW, STATUS_SHORTLISTED, normalize_status
from app.domains.integrations.provider.calendar_factory import get_calendar_provider
from app.domains.integrations.repository.oauth_tokens import PROVIDER_GOOGLE_CALENDAR
from app.domains.integrations.service import calendar_oauth_service as oauth_svc
from app.domains.recruitment.repository import interview_repository as repo
from app.domains.recruitment.services import interview_reminder_hooks as reminder_hooks
from app.integrations.email.templates import interview_confirmation_html, interview_invite_html
from app.integrations.email.utils import send_notification_email

logger = logging.getLogger(__name__)


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _duration_minutes() -> int:
    return max(15, _env_int('INTERVIEW_DURATION_MINUTES', 30))


def _lookahead_days() -> int:
    return max(1, _env_int('INTERVIEW_LOOKAHEAD_DAYS', 5))


def _invite_ttl_hours() -> int:
    return max(1, _env_int('INTERVIEW_INVITE_TTL_HOURS', 72))


def _interview_tz() -> ZoneInfo:
    name = (os.getenv('INTERVIEW_TZ') or 'Asia/Kolkata').strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo('Asia/Kolkata')


def _frontend_base() -> str:
    return (os.getenv('FRONTEND_URL') or 'http://localhost:5173').rstrip('/')


def _send_booking_invite_email(ctx: dict, invite_token: str, *, application_id: int) -> str:
    """Email the candidate the booking link. Returns booking_url."""
    booking_url = f'{_frontend_base()}/book/{invite_token}'
    candidate_name = ctx.get('candidate_name') or 'there'
    candidate_email = (ctx.get('candidate_email') or '').strip()
    job_title = ctx.get('job_title') or 'the position'
    company_name = ctx.get('company_name') or 'the company'
    assigned = (ctx.get('job_posted_by') or '').strip()
    recruiter_row = repo.get_hr_row(assigned) or {} if assigned else {}
    recruiter_name = recruiter_row.get('full_name') or ctx.get('recruiter_name') or 'the recruiter'

    if not candidate_email:
        logger.warning('[interview_scheduling] no candidate email for app=%s', application_id)
        return booking_url

    subject = f'Schedule your interview — {job_title}'
    body = (
        f'Hi {candidate_name},\n\n'
        f'You have been shortlisted for {job_title} at {company_name}.\n'
        f'Please book an interview slot with {recruiter_name}:\n\n'
        f'{booking_url}\n\n'
        f'This link expires in {_invite_ttl_hours()} hours.\n\n'
        f'— HR Intelligence Team'
    )
    html = interview_invite_html(
        candidate_name=candidate_name,
        job_title=job_title,
        company_name=company_name,
        recruiter_name=recruiter_name,
        booking_url=booking_url,
        ttl_hours=_invite_ttl_hours(),
    )
    try:
        ok = send_notification_email(candidate_email, subject, body, html=html)
        try:
            from app.domains.recruitment.repository import email_event_repository as email_events

            email_events.log_email_event(
                application_id=application_id,
                email_kind=email_events.KIND_INTERVIEW_INVITE,
                recipient=candidate_email,
                subject=subject,
                status=email_events.STATUS_SENT if ok else email_events.STATUS_FAILED,
            )
        except Exception as log_err:
            logger.warning('[interview_scheduling] email event log failed: %s', log_err)
    except Exception:
        logger.exception('[interview_scheduling] invite email failed app=%s', application_id)
    return booking_url


def _overlaps(start: datetime, end: datetime, busy: list) -> bool:
    for b in busy:
        if start < b.end and end > b.start:
            return True
    return False


def _generate_candidate_slots(
    busy: list,
    *,
    duration: timedelta,
    tz: ZoneInfo,
    lookahead_days: int,
) -> list[tuple[datetime, datetime]]:
    """Mon–Fri 10:00–17:00 in tz, excluding FreeBusy overlaps."""
    now = datetime.now(tz)
    work_start_h, work_end_h = 10, 17
    slots: list[tuple[datetime, datetime]] = []
    business_days = 0
    day = now.date()

    while business_days < lookahead_days and len(slots) < 40:
        if day.weekday() >= 5:
            day = day + timedelta(days=1)
            continue

        day_start = datetime(day.year, day.month, day.day, work_start_h, 0, tzinfo=tz)
        day_end = datetime(day.year, day.month, day.day, work_end_h, 0, tzinfo=tz)
        cursor = day_start
        if day == now.date():
            # Next aligned slot after now
            cursor = max(day_start, now.replace(second=0, microsecond=0) + timedelta(minutes=1))
            # Snap up to duration grid from day_start
            elapsed = cursor - day_start
            steps = int(elapsed.total_seconds() // duration.total_seconds())
            if elapsed.total_seconds() % duration.total_seconds() != 0:
                steps += 1
            cursor = day_start + steps * duration

        while cursor + duration <= day_end:
            slot_end = cursor + duration
            if cursor > now and not _overlaps(cursor, slot_end, busy):
                slots.append((cursor, slot_end))
            cursor = slot_end

        business_days += 1
        day = day + timedelta(days=1)

    return slots[:40]


def on_shortlisted(application_id: int, recruiter_hrid: str | None = None) -> dict:
    """
    Trigger after application reaches Shortlisted.
    Skips gracefully when calendar is not connected.
    Idempotent for existing Invited interviews with remaining slots.
    """
    ctx = repo.get_application_context(application_id)
    if not ctx:
        logger.warning('[interview_scheduling] application %s not found', application_id)
        return {'ok': False, 'reason': 'application_not_found'}

    status = normalize_status(ctx.get('application_status'))
    if status != STATUS_SHORTLISTED and not ctx.get('shortlisted'):
        logger.info(
            '[interview_scheduling] skip app=%s status=%s not shortlisted',
            application_id,
            status,
        )
        return {'ok': False, 'reason': 'not_shortlisted'}

    assigned = (recruiter_hrid or ctx.get('job_posted_by') or '').strip()
    if not assigned:
        logger.warning('[interview_scheduling] no recruiter for app=%s', application_id)
        return {'ok': False, 'reason': 'no_recruiter'}

    tokens = oauth_svc.load_valid_tokens(assigned)
    if not tokens:
        logger.info(
            '[interview_scheduling] recruiter %s has no Google Calendar; skip app=%s',
            assigned,
            application_id,
        )
        return {'ok': True, 'skipped': True, 'reason': 'calendar_not_connected'}

    provider = get_calendar_provider(PROVIDER_GOOGLE_CALENDAR)
    if not provider:
        return {'ok': False, 'reason': 'provider_unavailable'}

    existing = repo.get_open_interview_for_application(application_id)
    if existing and existing.get('status') == repo.STATUS_SCHEDULED:
        return {'ok': True, 'skipped': True, 'reason': 'already_scheduled'}

    if existing and existing.get('status') == repo.STATUS_INVITED:
        remaining = repo.list_available_slots(str(existing['id']))
        if remaining:
            # Resend booking email (e.g. first send was suppressed / failed).
            token = (existing.get('invite_token') or '').strip()
            booking_url = None
            if token:
                booking_url = _send_booking_invite_email(
                    ctx, token, application_id=application_id
                )
            logger.info(
                '[interview_scheduling] invite already open for app=%s (email resent)',
                application_id,
            )
            return {
                'ok': True,
                'skipped': True,
                'reason': 'invite_exists',
                'interviewId': str(existing['id']),
                'bookingUrl': booking_url,
            }

    tz = _interview_tz()
    duration_min = _duration_minutes()
    duration = timedelta(minutes=duration_min)
    lookahead = _lookahead_days()
    time_min = datetime.now(timezone.utc)
    time_max = time_min + timedelta(days=lookahead * 2 + 7)

    try:
        busy = provider.get_free_busy(tokens, time_min, time_max)
    except Exception:
        logger.exception('[interview_scheduling] FreeBusy failed for %s', assigned)
        return {'ok': False, 'reason': 'freebusy_failed'}

    # Normalize busy to aware datetimes
    normalized_busy = []
    for b in busy:
        s, e = b.start, b.end
        if s.tzinfo is None:
            s = s.replace(tzinfo=timezone.utc)
        if e.tzinfo is None:
            e = e.replace(tzinfo=timezone.utc)
        normalized_busy.append(type(b)(start=s, end=e))

    slot_pairs = _generate_candidate_slots(
        normalized_busy,
        duration=duration,
        tz=tz,
        lookahead_days=lookahead,
    )
    if not slot_pairs:
        logger.info('[interview_scheduling] no slots for app=%s', application_id)
        return {'ok': True, 'skipped': True, 'reason': 'no_slots'}

    invite_token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=_invite_ttl_hours())

    if existing and existing.get('status') == repo.STATUS_INVITED:
        interview_id = str(existing['id'])
        repo.update_interview_invite(
            interview_id,
            invite_token=invite_token,
            invite_expires_at=expires_at,
            assigned_to=assigned,
            duration_minutes=duration_min,
        )
        repo.delete_slots_for_interview(interview_id)
    else:
        row = repo.create_invited_interview(
            application_id=application_id,
            assigned_to=assigned,
            invite_token=invite_token,
            invite_expires_at=expires_at,
            duration_minutes=duration_min,
        )
        if not row:
            return {'ok': False, 'reason': 'interview_create_failed'}
        interview_id = str(row['id'])

    repo.insert_slots(interview_id, assigned, slot_pairs)

    booking_url = _send_booking_invite_email(
        ctx, invite_token, application_id=application_id
    )

    reminder_hooks.on_invite_sent(interview_id)
    return {
        'ok': True,
        'interviewId': interview_id,
        'slotCount': len(slot_pairs),
        'bookingUrl': booking_url,
    }


def get_booking_payload(token: str) -> tuple[dict | None, str | None, int]:
    """Return (payload, error, http_status)."""
    interview = repo.get_interview_by_token(token)
    if not interview:
        return None, 'Invalid booking link', 404
    expires = interview.get('invite_expires_at')
    if expires:
        if getattr(expires, 'tzinfo', None) is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return None, 'This booking link has expired', 410
    if interview.get('status') == repo.STATUS_SCHEDULED:
        return {
            'status': 'scheduled',
            'scheduledAt': interview.get('scheduled_at').isoformat()
            if getattr(interview.get('scheduled_at'), 'isoformat', None)
            else interview.get('scheduled_at'),
            'meetLink': interview.get('meeting_link'),
        }, None, 200
    if interview.get('status') != repo.STATUS_INVITED:
        return None, 'Interview is no longer available for booking', 409

    ctx = repo.get_application_context(int(interview['application_id']))
    slots = [repo.serialize_slot(s) for s in repo.list_available_slots(str(interview['id']))]
    return {
        'status': 'invited',
        'candidateName': (ctx or {}).get('candidate_name') or '',
        'jobTitle': (ctx or {}).get('job_title') or '',
        'companyName': (ctx or {}).get('company_name') or '',
        'recruiterName': (ctx or {}).get('recruiter_name') or '',
        'durationMinutes': interview.get('duration_minutes') or _duration_minutes(),
        'slots': slots,
    }, None, 200


def book_slot(token: str, slot_id: str) -> tuple[dict | None, str | None, int]:
    """Book a slot: recheck FreeBusy, create Meet event, set Interview status."""
    interview = repo.get_interview_by_token(token)
    if not interview:
        return None, 'Invalid booking link', 404
    expires = interview.get('invite_expires_at')
    if expires:
        if getattr(expires, 'tzinfo', None) is None:
            expires = expires.replace(tzinfo=timezone.utc)
        if datetime.now(timezone.utc) > expires:
            return None, 'This booking link has expired', 410
    if interview.get('status') != repo.STATUS_INVITED:
        return None, 'Interview is no longer available for booking', 409

    interview_id = str(interview['id'])
    slot = repo.get_slot(slot_id, interview_id)
    if not slot or slot.get('is_booked'):
        remaining = [repo.serialize_slot(s) for s in repo.list_available_slots(interview_id)]
        return {'slots': remaining, 'reason': 'slot_unavailable'}, 'Slot is no longer available', 409

    assigned = interview.get('assigned_to')
    tokens = oauth_svc.load_valid_tokens(assigned)
    if not tokens:
        return None, 'Recruiter calendar is not connected', 503

    provider = get_calendar_provider(PROVIDER_GOOGLE_CALENDAR)
    if not provider:
        return None, 'Calendar provider unavailable', 503

    start = slot['start_time']
    end = slot['end_time']
    if getattr(start, 'tzinfo', None) is None:
        start = start.replace(tzinfo=timezone.utc)
    if getattr(end, 'tzinfo', None) is None:
        end = end.replace(tzinfo=timezone.utc)

    try:
        busy = provider.get_free_busy(tokens, start - timedelta(minutes=1), end + timedelta(minutes=1))
    except Exception:
        logger.exception('[interview_scheduling] FreeBusy recheck failed')
        return None, 'Unable to verify calendar availability', 502

    for b in busy:
        bs, be = b.start, b.end
        if bs.tzinfo is None:
            bs = bs.replace(tzinfo=timezone.utc)
        if be.tzinfo is None:
            be = be.replace(tzinfo=timezone.utc)
        if start < be and end > bs:
            repo.mark_slot_unavailable(slot_id)
            remaining = [repo.serialize_slot(s) for s in repo.list_available_slots(interview_id)]
            return {
                'slots': remaining,
                'reason': 'slot_conflict',
            }, 'That time is no longer available. Please choose another slot.', 409

    ctx = repo.get_application_context(int(interview['application_id']))
    if not ctx:
        return None, 'Application not found', 404

    candidate_email = (ctx.get('candidate_email') or '').strip()
    recruiter_email = (repo.get_hr_email(assigned) or ctx.get('recruiter_email') or '').strip()
    attendees = [e for e in [candidate_email, recruiter_email] if e]
    interviewer_hrid = interview.get('interviewer_hrid')
    if interviewer_hrid:
        ie = repo.get_hr_email(interviewer_hrid)
        if ie and ie not in attendees:
            attendees.append(ie)

    job_title = ctx.get('job_title') or 'Interview'
    candidate_name = ctx.get('candidate_name') or 'Candidate'
    company_name = ctx.get('company_name') or ''
    tz_name = (os.getenv('INTERVIEW_TZ') or 'Asia/Kolkata').strip()

    # Claim slot before creating the calendar event to prevent double-booking races.
    if not repo.claim_slot(slot_id):
        remaining = [repo.serialize_slot(s) for s in repo.list_available_slots(interview_id)]
        return {'slots': remaining, 'reason': 'slot_unavailable'}, 'Slot is no longer available', 409

    result = provider.create_event(
        tokens,
        summary=f'Interview: {candidate_name} — {job_title}',
        description=f'Interview for {job_title} at {company_name}',
        start=start,
        end=end,
        attendee_emails=attendees,
        timezone=tz_name,
        create_meet=True,
    )
    if not result.success:
        repo.release_slot_claim(slot_id)
        return None, result.error or 'Failed to create calendar event', 502

    repo.confirm_interview_scheduled(
        interview_id,
        scheduled_at=start,
        calendar_event_id=result.event_id,
        meeting_link=result.meet_link,
        updated_by=assigned,
    )
    repo.set_application_status(int(interview['application_id']), STATUS_INTERVIEW)

    when_str = start.astimezone(_interview_tz()).strftime('%a %d %b %Y, %I:%M %p %Z')
    meet = result.meet_link or ''
    if candidate_email:
        subject = f'Interview confirmed — {job_title}'
        body = (
            f'Hi {candidate_name},\n\n'
            f'Your interview for {job_title} is confirmed.\n'
            f'When: {when_str}\n'
            f'Meet: {meet or "See calendar invite"}\n\n'
            f'— HR Intelligence Team'
        )
        html = interview_confirmation_html(
            candidate_name=candidate_name,
            job_title=job_title,
            company_name=company_name,
            when_str=when_str,
            meet_link=meet,
            for_recruiter=False,
        )
        try:
            send_notification_email(candidate_email, subject, body, html=html)
        except Exception:
            logger.exception('[interview_scheduling] confirmation email failed')

    if recruiter_email:
        subject = f'Interview booked — {candidate_name} / {job_title}'
        body = (
            f'Hi,\n\n'
            f'{candidate_name} booked an interview for {job_title}.\n'
            f'When: {when_str}\n'
            f'Meet: {meet or "See calendar invite"}\n'
        )
        html = interview_confirmation_html(
            candidate_name=candidate_name,
            job_title=job_title,
            company_name=company_name,
            when_str=when_str,
            meet_link=meet,
            for_recruiter=True,
        )
        try:
            send_notification_email(recruiter_email, subject, body, html=html)
        except Exception:
            logger.exception('[interview_scheduling] recruiter confirmation failed')

    reminder_hooks.on_interview_scheduled(interview_id)
    return {
        'status': 'scheduled',
        'scheduledAt': start.isoformat(),
        'meetLink': meet,
        'calendarEventId': result.event_id,
    }, None, 200


def get_interview_for_application(application_id: int) -> dict | None:
    row = repo.get_open_interview_for_application(application_id)
    if not row:
        return None
    return {
        'id': str(row['id']),
        'status': row.get('status'),
        'scheduledAt': row.get('scheduled_at').isoformat()
        if getattr(row.get('scheduled_at'), 'isoformat', None)
        else row.get('scheduled_at'),
        'meetLink': row.get('meeting_link'),
        'inviteExpiresAt': row.get('invite_expires_at').isoformat()
        if getattr(row.get('invite_expires_at'), 'isoformat', None)
        else row.get('invite_expires_at'),
        'assignedTo': row.get('assigned_to'),
        'durationMinutes': row.get('duration_minutes'),
    }
