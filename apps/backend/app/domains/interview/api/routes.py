"""Interview scheduling + AI interview session APIs."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app.api.middleware.auth import authenticate_token
from app.database.connection.db import db_run
from app.domains.identity.authorization.rbac import has_permission, is_read_only, require_analytics_read
from app.domains.interview.services.ai_interview import evaluate_answer, finalize_interview
from app.domains.interview.services.scheduling import (
    create_interview,
    get_interview_by_id,
    get_interview_by_token,
    list_interviews,
    list_interviews_for_application,
    serialize_interview,
)

interview_bp = Blueprint('interviews', __name__)


def _json_col(value):
    if value is None:
        return None
    if isinstance(value, str):
        return value
    return json.dumps(value)


def _parse_json(value, default=None):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return default


# ---------------------------------------------------------------------------
# Staff (Head HR / analytics) routes — mounted under /api/head-hr/interviews
# ---------------------------------------------------------------------------

@interview_bp.get('/interviews')
@require_analytics_read
def staff_list_interviews():
    return jsonify({'interviews': list_interviews()})


@interview_bp.post('/interviews')
@authenticate_token
def staff_create_interview():
    user = request.user
    if is_read_only(user):
        return jsonify({'error': 'Read-only access'}), 403
    if not (has_permission(user, 'analytics:read') or has_permission(user, 'jobs:write_own') or has_permission(user, 'jobs:write_any')):
        return jsonify({'error': 'Forbidden'}), 403

    data = request.get_json(force=True) or {}
    application_id = data.get('application_id') or data.get('applicationId')
    try:
        application_id = int(application_id)
    except (TypeError, ValueError):
        return jsonify({'error': 'application_id is required'}), 400

    hrid = user.get('hrid') or user.get('user_id') or user.get('id') or user.get('sub')
    try:
        interview = create_interview(
            application_id=application_id,
            created_by=hrid,
            interviewer_type=data.get('interviewer_type') or data.get('interviewerType') or 'ai',
            scheduled_at=data.get('scheduled_at') or data.get('scheduledAt'),
            duration_minutes=data.get('duration_minutes') or data.get('durationMinutes') or 30,
            notes=(data.get('notes') or '').strip(),
            assigned_to=data.get('assigned_to') or data.get('assignedTo'),
            meeting_link=(data.get('meeting_link') or data.get('meetingLink') or '').strip(),
        )
        return jsonify(interview), 201
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'Failed to schedule interview: {e}'}), 500


@interview_bp.get('/interviews/<interview_id>')
@require_analytics_read
def staff_get_interview(interview_id):
    row = get_interview_by_id(interview_id)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    return jsonify(serialize_interview(row, include_questions=True, include_answers=True))


@interview_bp.get('/applications/<int:app_id>/interviews')
@require_analytics_read
def staff_list_application_interviews(app_id):
    return jsonify({'interviews': list_interviews_for_application(app_id)})


@interview_bp.post('/interviews/<interview_id>/cancel')
@authenticate_token
def staff_cancel_interview(interview_id):
    user = request.user
    if is_read_only(user):
        return jsonify({'error': 'Read-only access'}), 403
    row = get_interview_by_id(interview_id)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    if row.get('status') == 'Completed':
        return jsonify({'error': 'Completed interviews cannot be cancelled'}), 400
    hrid = user.get('hrid') or user.get('id')
    db_run(
        "UPDATE interviews SET status = 'Cancelled', updated_by = ?, updated_at = NOW() WHERE id = ?::uuid",
        (hrid, interview_id),
    )
    row = get_interview_by_id(interview_id)
    return jsonify(serialize_interview(row))


# ---------------------------------------------------------------------------
# Public candidate session — mounted under /api/interviews
# ---------------------------------------------------------------------------

public_interview_bp = Blueprint('public_interviews', __name__)


@public_interview_bp.get('/session/<token>')
def public_get_session(token):
    row = get_interview_by_token(token)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    status = row.get('status')
    questions = _parse_json(row.get('questions_json'), [])
    answers = _parse_json(row.get('answers_json'), [])
    # Do not leak full feedback until complete for in-progress sessions
    payload = {
        'id': str(row.get('id')),
        'status': status,
        'interviewer_type': row.get('interviewer_type') or 'ai',
        'duration_minutes': row.get('duration_minutes') or 30,
        'job_title': row.get('job_title'),
        'job_company': row.get('job_company'),
        'candidate_name': row.get('candidate_name'),
        'scheduled_at': row.get('scheduled_at').isoformat() if hasattr(row.get('scheduled_at'), 'isoformat') else row.get('scheduled_at'),
        'question_count': len(questions),
        'answered_count': len(answers),
        'is_ai': (row.get('interviewer_type') or 'ai') == 'ai',
    }
    if status == 'Completed':
        payload['overall_score'] = float(row['overall_score']) if row.get('overall_score') is not None else None
        payload['score_summary'] = row.get('score_summary')
    if status in ('Scheduled', 'InProgress') and (row.get('interviewer_type') or 'ai') == 'ai':
        # Reveal only current unanswered question text (progressive)
        next_idx = len(answers)
        if next_idx < len(questions):
            q = questions[next_idx]
            payload['current_question'] = {
                'index': next_idx,
                'id': q.get('id'),
                'question': q.get('question'),
                'category': q.get('category'),
            }
        payload['done'] = next_idx >= len(questions)
    return jsonify(payload)


@public_interview_bp.post('/session/<token>/start')
def public_start_session(token):
    row = get_interview_by_token(token)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    if row.get('status') == 'Cancelled':
        return jsonify({'error': 'This interview was cancelled'}), 400
    if row.get('status') == 'Completed':
        return jsonify({'error': 'This interview is already completed'}), 400
    if (row.get('interviewer_type') or 'ai') != 'ai':
        return jsonify({'error': 'This interview is not an AI session'}), 400

    if row.get('status') == 'Scheduled':
        db_run(
            "UPDATE interviews SET status = 'InProgress', updated_at = NOW() WHERE id = ?::uuid",
            (str(row['id']),),
        )
        row = get_interview_by_token(token)

    questions = _parse_json(row.get('questions_json'), [])
    answers = _parse_json(row.get('answers_json'), [])
    next_idx = len(answers)
    current = None
    if next_idx < len(questions):
        q = questions[next_idx]
        current = {
            'index': next_idx,
            'id': q.get('id'),
            'question': q.get('question'),
            'category': q.get('category'),
        }
    return jsonify({
        'status': row.get('status'),
        'question_count': len(questions),
        'answered_count': len(answers),
        'current_question': current,
        'done': next_idx >= len(questions),
        'job_title': row.get('job_title'),
        'candidate_name': row.get('candidate_name'),
    })


@public_interview_bp.post('/session/<token>/answer')
def public_submit_answer(token):
    row = get_interview_by_token(token)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    if row.get('status') in ('Cancelled', 'Completed'):
        return jsonify({'error': f'Interview is {row.get("status")}'}), 400
    if (row.get('interviewer_type') or 'ai') != 'ai':
        return jsonify({'error': 'This interview is not an AI session'}), 400

    data = request.get_json(force=True) or {}
    answer_text = (data.get('answer') or '').strip()
    if not answer_text:
        return jsonify({'error': 'Answer is required'}), 400

    if row.get('status') == 'Scheduled':
        db_run(
            "UPDATE interviews SET status = 'InProgress', updated_at = NOW() WHERE id = ?::uuid",
            (str(row['id']),),
        )

    questions = _parse_json(row.get('questions_json'), [])
    answers = _parse_json(row.get('answers_json'), []) or []
    next_idx = len(answers)
    if next_idx >= len(questions):
        return jsonify({'error': 'All questions already answered'}), 400

    q = questions[next_idx]
    evaluation = evaluate_answer(
        q.get('question') or '',
        answer_text,
        job_title=row.get('job_title') or '',
    )
    answers.append({
        'question_id': q.get('id'),
        'question': q.get('question'),
        'category': q.get('category'),
        'answer': answer_text,
        'score': evaluation.get('score'),
        'feedback': evaluation.get('feedback'),
        'answered_at': datetime.now(timezone.utc).isoformat(),
    })

    db_run(
        'UPDATE interviews SET answers_json = ?::jsonb, updated_at = NOW() WHERE id = ?::uuid',
        (_json_col(answers), str(row['id'])),
    )

    done = len(answers) >= len(questions)
    next_question = None
    if not done:
        nq = questions[len(answers)]
        next_question = {
            'index': len(answers),
            'id': nq.get('id'),
            'question': nq.get('question'),
            'category': nq.get('category'),
        }

    return jsonify({
        'accepted': True,
        'answered_count': len(answers),
        'question_count': len(questions),
        'last_feedback': evaluation.get('feedback'),
        'done': done,
        'current_question': next_question,
    })


@public_interview_bp.post('/session/<token>/complete')
def public_complete_session(token):
    row = get_interview_by_token(token)
    if not row:
        return jsonify({'error': 'Interview not found'}), 404
    if row.get('status') == 'Cancelled':
        return jsonify({'error': 'Interview was cancelled'}), 400
    if row.get('status') == 'Completed':
        return jsonify({
            'status': 'Completed',
            'overall_score': float(row['overall_score']) if row.get('overall_score') is not None else None,
            'score_summary': row.get('score_summary'),
        })

    answers = _parse_json(row.get('answers_json'), []) or []
    questions = _parse_json(row.get('questions_json'), []) or []
    if len(answers) < len(questions):
        return jsonify({'error': 'Please answer all questions before completing'}), 400

    result = finalize_interview(answers, job_title=row.get('job_title') or '')
    db_run(
        '''UPDATE interviews
           SET status = 'Completed',
               completed_at = NOW(),
               overall_score = ?,
               score_summary = ?,
               feedback_toon = ?,
               updated_at = NOW()
           WHERE id = ?::uuid''',
        (
            result.get('overall_score'),
            result.get('score_summary'),
            _json_col(result),
            str(row['id']),
        ),
    )
    return jsonify({
        'status': 'Completed',
        'overall_score': result.get('overall_score'),
        'score_summary': result.get('score_summary'),
        'recommendation': result.get('recommendation'),
    })
