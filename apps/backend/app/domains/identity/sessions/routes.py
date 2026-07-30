from flask import Blueprint, request, jsonify

from app.api.middleware.auth import authenticate_token
from app.domains.identity.authorization.rbac import get_user_id, get_role
from app.domains.identity.sessions.service import (
    get_user_sessions,
    get_login_history,
    deactivate_session,
    deactivate_all_user_sessions,
)

sessions_bp = Blueprint('sessions', __name__)


@sessions_bp.get('/my-sessions')
@authenticate_token
def my_sessions():
    try:
        user = request.user
        user_id = get_user_id(user)
        role = get_role(user) or user.get('role')
        sessions = get_user_sessions(user_id, role)
        return jsonify(sessions)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@sessions_bp.get('/my-history')
@authenticate_token
def my_history():
    try:
        user = request.user
        role = get_role(user) or user.get('role')
        limit = int(request.args.get('limit', '50'))
        history = get_login_history(user.get('email', ''), role, limit)
        return jsonify(history)
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@sessions_bp.post('/logout-session')
@authenticate_token
def logout_session():
    try:
        data = request.get_json(force=True)
        token = data.get('token')
        if not token:
            return jsonify({'error': 'Token is required'}), 400
        deactivate_session(token)
        return jsonify({'message': 'Session deactivated successfully'})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500


@sessions_bp.post('/logout-all')
@authenticate_token
def logout_all():
    try:
        user = request.user
        user_id = get_user_id(user)
        role = get_role(user) or user.get('role')
        deactivate_all_user_sessions(user_id, role)
        return jsonify({'message': 'All sessions deactivated successfully'})
    except Exception:
        return jsonify({'error': 'Internal server error'}), 500
