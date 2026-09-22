"""
Support Routes - Handle help and support requests
"""
import os
from flask import Blueprint, request, jsonify
from app.api.middleware.auth import authenticate_token, require_head_hr, optional_authenticate_token
from app.core.errors import log_unexpected
from app.database.connection.db import db_run, db_get, db_all, BACKEND, NOW_SQL
from app.domains.identity.services.organizations import require_organization_id
from app.integrations.email.utils import send_notification_email
from app.integrations.email.templates import support_request_html

support_bp = Blueprint('support', __name__)
SUPPORT_TABLE = "support_requests" if BACKEND == "postgresql" else "dbo.support_requests"

# Tenant boundary: a support request only belongs to an organization when it
# was raised by an authenticated hr/candidate user of that org (resolved via
# hr_signup/candidates.organization_id, never a client-supplied value).
# 'guest' requests (or missing/stale user_id) are not attributable to any
# tenant and are intentionally excluded from every org's Head HR view — they
# are still delivered to SUPPORT_NOTIFICATION_EMAIL for manual handling.
_ORG_SCOPE_CLAUSE = """(
    (user_type = 'hr' AND user_id IN (SELECT hrid FROM hr_signup WHERE organization_id = ?))
    OR (user_type = 'candidate' AND user_id IN (SELECT cid FROM candidates WHERE organization_id = ?))
)"""

# Email where Contact Us and internal feedback notifications are sent (can override via env)
SUPPORT_NOTIFICATION_EMAIL = os.getenv('SUPPORT_NOTIFICATION_EMAIL', 'techberryaiteam@gmail.com')


def _serialize_request_datetimes(req: dict) -> dict:
    for key in ('created_at', 'updated_at', 'resolved_at'):
        if req.get(key):
            req[key] = req[key].isoformat() if hasattr(req[key], 'isoformat') else str(req[key])
    return req


@support_bp.route('/submit', methods=['POST'])
@optional_authenticate_token
def submit_support_request():
    """
    Submit a new support request
    """
    try:
        data = request.get_json()

        # Validate required fields
        if not data:
            return jsonify({"error": "No data provided"}), 400

        name = data.get('name', '').strip()
        email = data.get('email', '').strip()
        subject = data.get('subject', '').strip()
        message = data.get('message', '').strip()

        if not name:
            return jsonify({"error": "Name is required"}), 400
        if not email:
            return jsonify({"error": "Email is required"}), 400
        if not subject:
            return jsonify({"error": "Subject is required"}), 400
        if not message:
            return jsonify({"error": "Message is required"}), 400

        # user_id/user_type are derived from the verified session, never from the
        # client body — otherwise anyone could claim user_type='hr' with an
        # arbitrary user_id and have a forged ticket appear in that org's
        # Head-HR queue attributed to a real employee.
        auth_user = request.user or {}
        if auth_user.get('user_id'):
            user_id = str(auth_user['user_id'])
            user_type = 'hr'
        else:
            user_id = None
            user_type = 'guest'
        priority = data.get('priority', 'medium')

        # Validate email format
        if '@' not in email or '.' not in email:
            return jsonify({"error": "Invalid email format"}), 400

        # Validate priority
        if priority not in ['low', 'medium', 'high', 'urgent']:
            priority = 'medium'
        
        # Insert support request (PG: RETURNING id; MSSQL: SCOPE_IDENTITY in second statement)
        if BACKEND == "postgresql":
            query = """
                INSERT INTO """ + SUPPORT_TABLE + """
                (name, email, user_id, user_type, subject, message, status, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, """ + NOW_SQL + """, """ + NOW_SQL + """)
                RETURNING id
            """
        else:
            query = """
                INSERT INTO """ + SUPPORT_TABLE + """
                (name, email, user_id, user_type, subject, message, status, priority, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 'open', ?, SYSUTCDATETIME(), SYSUTCDATETIME());
                SELECT CAST(SCOPE_IDENTITY() AS INT) as lastID;
            """
        result = db_run(query, (name, email, user_id, user_type, subject, message, priority))
        request_id = result.get('lastID')

        # Notify AI Team / support inbox (do not fail request if email fails)
        try:
            email_subject = f"[Support Request] {subject}"
            email_body = (
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"User type: {user_type}\n"
                f"Priority: {priority}\n"
                f"Request ID: #{request_id}\n\n"
                f"Message:\n{message}"
            )
            html = support_request_html(name, email, user_type, priority, request_id, message)
            ok = send_notification_email(
                SUPPORT_NOTIFICATION_EMAIL, email_subject, email_body, html=html
            )
            if not ok:
                log_unexpected('support_notify_email', Exception('notification send returned false'))
        except Exception as mail_err:
            log_unexpected('support_notify_email', mail_err)

        return jsonify({
            "success": True,
            "message": "Support request submitted successfully",
            "request_id": request_id
        }), 201
        
    except Exception as e:
        log_unexpected('support_request', e)
        return jsonify({"error": "Failed to submit support request"}), 500


@support_bp.route('/my-requests', methods=['GET'])
@authenticate_token
def get_my_requests():
    """Get support requests for the authenticated user only."""
    try:
        user = request.user or {}
        email = (user.get('email') or '').strip()
        user_id = str(user.get('user_id') or '').strip()
        if not email and not user_id:
            return jsonify({"error": "Authenticated identity required"}), 401

        if email:
            query = """
                SELECT id, name, email, user_id, user_type, subject, message, 
                       status, priority, created_at, updated_at, resolved_at
                FROM """ + SUPPORT_TABLE + """
                WHERE email = ?
                ORDER BY created_at DESC
            """
            requests = db_all(query, (email,))
        else:
            query = """
                SELECT id, name, email, user_id, user_type, subject, message, 
                       status, priority, created_at, updated_at, resolved_at
                FROM """ + SUPPORT_TABLE + """
                WHERE user_id = ?
                ORDER BY created_at DESC
            """
            requests = db_all(query, (user_id,))

        for req in requests:
            _serialize_request_datetimes(req)

        return jsonify({
            "success": True,
            "requests": requests
        }), 200
        
    except Exception as e:
        log_unexpected('support_request', e)
        return jsonify({"error": "Failed to fetch support requests"}), 500


@support_bp.route('/all', methods=['GET'])
@require_head_hr
def get_all_requests():
    """Get all support requests for the caller's own organization (Head HR only)."""
    try:
        org_id, err = require_organization_id(request.user)
        if err:
            return err

        status = request.args.get('status', '').strip()

        if status:
            query = """
                SELECT id, name, email, user_id, user_type, subject, message,
                       status, priority, created_at, updated_at, resolved_at
                FROM """ + SUPPORT_TABLE + """
                WHERE status = ? AND """ + _ORG_SCOPE_CLAUSE + """
                ORDER BY created_at DESC
            """
            requests = db_all(query, (status, org_id, org_id))
        else:
            query = """
                SELECT id, name, email, user_id, user_type, subject, message,
                       status, priority, created_at, updated_at, resolved_at
                FROM """ + SUPPORT_TABLE + """
                WHERE """ + _ORG_SCOPE_CLAUSE + """
                ORDER BY created_at DESC
            """
            requests = db_all(query, (org_id, org_id))

        for req in requests:
            _serialize_request_datetimes(req)

        return jsonify({
            "success": True,
            "requests": requests
        }), 200
        
    except Exception as e:
        log_unexpected('support_request', e)
        return jsonify({"error": "Failed to fetch support requests"}), 500


@support_bp.route('/<int:request_id>', methods=['GET'])
@require_head_hr
def get_request_by_id(request_id):
    """Get a specific support request by ID, scoped to the caller's own organization (Head HR only)."""
    try:
        org_id, err = require_organization_id(request.user)
        if err:
            return err

        query = """
            SELECT id, name, email, user_id, user_type, subject, message,
                   status, priority, created_at, updated_at, resolved_at, admin_notes
            FROM """ + SUPPORT_TABLE + """
            WHERE id = ? AND """ + _ORG_SCOPE_CLAUSE + """
        """
        support_request = db_get(query, (request_id, org_id, org_id))
        
        if not support_request:
            return jsonify({"error": "Support request not found"}), 404

        _serialize_request_datetimes(support_request)

        return jsonify({
            "success": True,
            "request": support_request
        }), 200
        
    except Exception as e:
        log_unexpected('support_request', e)
        return jsonify({"error": "Failed to fetch support request"}), 500


@support_bp.route('/<int:request_id>/status', methods=['PATCH'])
@require_head_hr
def update_request_status(request_id):
    """Update the status of a support request, scoped to the caller's own organization (Head HR only)."""
    try:
        org_id, err = require_organization_id(request.user)
        if err:
            return err

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data provided"}), 400

        status = data.get('status', '').strip()
        admin_notes = data.get('admin_notes', '').strip()

        if not status:
            return jsonify({"error": "Status is required"}), 400

        if status not in ['open', 'in_progress', 'resolved', 'closed']:
            return jsonify({"error": "Invalid status"}), 400

        # Check the request exists AND belongs to the caller's own organization.
        check_query = "SELECT id FROM " + SUPPORT_TABLE + " WHERE id = ? AND " + _ORG_SCOPE_CLAUSE
        existing = db_get(check_query, (request_id, org_id, org_id))
        if not existing:
            return jsonify({"error": "Support request not found"}), 404
        
        # Update status
        if status in ['resolved', 'closed']:
            query = """
                UPDATE """ + SUPPORT_TABLE + """
                SET status = ?, updated_at = """ + NOW_SQL + """,
                    resolved_at = """ + NOW_SQL + """, admin_notes = ?
                WHERE id = ?
            """
            db_run(query, (status, admin_notes, request_id))
        else:
            query = """
                UPDATE """ + SUPPORT_TABLE + """
                SET status = ?, updated_at = """ + NOW_SQL + """, admin_notes = ?
                WHERE id = ?
            """
            db_run(query, (status, admin_notes, request_id))
        
        return jsonify({
            "success": True,
            "message": "Support request status updated successfully"
        }), 200
        
    except Exception as e:
        log_unexpected('support_request', e)
        return jsonify({"error": "Failed to update support request"}), 500

