"""Public interview booking + recruiter interview status APIs."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request

from app.api.middleware.auth import authenticate_token, require_recruiter
from app.domains.recruitment.services import interview_scheduling_service as scheduling

logger = logging.getLogger(__name__)

interview_bp = Blueprint('interviews', __name__)


@interview_bp.get('/book/<string:token>')
def get_booking(token: str):
    payload, err, status = scheduling.get_booking_payload(token)
    if err and payload is None:
        return jsonify({'error': err}), status
    if err and payload is not None:
        return jsonify({'error': err, **payload}), status
    return jsonify(payload), status


@interview_bp.post('/book/<string:token>')
def post_booking(token: str):
    data = request.get_json(force=True, silent=True) or {}
    slot_id = (data.get('slotId') or data.get('slot_id') or '').strip()
    if not slot_id:
        return jsonify({'error': 'slotId is required'}), 400
    payload, err, status = scheduling.book_slot(token, slot_id)
    if err and (payload is None or status >= 500):
        return jsonify({'error': err}), status
    if err:
        body = {'error': err}
        if payload:
            body.update(payload)
        return jsonify(body), status
    return jsonify(payload), status


@interview_bp.get('/by-application/<int:application_id>')
@authenticate_token
@require_recruiter
def interview_by_application(application_id: int):
    from app.database.connection.db import db_get
    from app.domains.identity.services.organizations import require_organization_id

    org_id, org_err = require_organization_id(request.user)
    if org_err:
        return org_err
    owned = db_get(
        '''
        SELECT 1 AS ok
        FROM applications a
        JOIN jobs j ON j.jdid = a.job_id
        WHERE a.id = ? AND j.organization_id = ?
        ''',
        (application_id, org_id),
    )
    if not owned:
        return jsonify({'error': 'Application not found'}), 404
    row = scheduling.get_interview_for_application(application_id)
    if not row:
        return jsonify({'interview': None}), 200
    return jsonify({'interview': row}), 200
