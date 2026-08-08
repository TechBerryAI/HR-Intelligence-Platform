"""Google Calendar OAuth routes under /api/integrations/calendar/google."""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, redirect, request

from app.api.middleware.auth import authenticate_token, require_recruiter
from app.domains.identity.authorization.rbac import get_user_id
from app.domains.integrations.service import calendar_oauth_service as oauth_svc

logger = logging.getLogger(__name__)

calendar_oauth_bp = Blueprint('calendar_oauth', __name__)


@calendar_oauth_bp.get('/calendar/google/connect')
@authenticate_token
@require_recruiter
def google_calendar_connect():
    # Prefer the page the recruiter started from so post-Google redirect keeps the same
    # browser origin (localhost vs LAN IP) and thus the same localStorage session.
    return_to = request.args.get('returnTo') or request.args.get('return_to')
    if not return_to:
        origin = (request.headers.get('Origin') or '').rstrip('/')
        if origin:
            return_to = f'{origin}/settings'
    url, err = oauth_svc.start_oauth(request.user, return_to=return_to)
    if err:
        return jsonify({'error': err}), 400
    return jsonify({'authUrl': url}), 200


@calendar_oauth_bp.get('/calendar/google/callback')
@calendar_oauth_bp.get('/google/callback')
def google_calendar_callback():
    code = request.args.get('code')
    state = request.args.get('state')
    redirect_url, err = oauth_svc.handle_oauth_callback(code, state)
    if err:
        logger.warning('[calendar_oauth] callback error: %s', err)
    return redirect(redirect_url)


@calendar_oauth_bp.get('/calendar/google/status')
@authenticate_token
@require_recruiter
def google_calendar_status():
    hrid = get_user_id(request.user)
    if not hrid:
        return jsonify({'error': 'User id required'}), 400
    return jsonify(oauth_svc.get_connection_status(hrid)), 200


@calendar_oauth_bp.delete('/calendar/google/disconnect')
@authenticate_token
@require_recruiter
def google_calendar_disconnect():
    hrid = get_user_id(request.user)
    if not hrid:
        return jsonify({'error': 'User id required'}), 400
    oauth_svc.disconnect(hrid)
    return jsonify({'status': 'ok', 'connected': False}), 200
