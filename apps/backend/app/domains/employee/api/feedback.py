"""
Employee Feedback & Issue Reporting - Internal HRMS testing feedback.
Stores submissions in DB, optional screenshot upload, and notifies AI Team via email.
"""
import os
import re
import uuid
from flask import Blueprint, request, jsonify, current_app
from app.api.middleware.auth import require_recruiter
from app.core.errors import log_unexpected
from app.database.connection.db import db_run, db_get, db_all, BACKEND, NOW_SQL
from app.integrations.email.utils import send_notification_email
from app.integrations.email.templates import hrms_feedback_html

feedback_bp = Blueprint('feedback', __name__)
FEEDBACK_TABLE = "employee_feedback" if BACKEND == "postgresql" else "dbo.employee_feedback"

# Email where HRMS Testing Feedback notifications are sent (default: techberryaiteam@gmail.com)
def _feedback_recipient():
    return os.getenv('FEEDBACK_NOTIFICATION_EMAIL') or os.getenv('AI_TEAM_EMAIL') or 'techberryaiteam@gmail.com'

# Allowed feedback types and severities
FEEDBACK_TYPES = ('Bug Report', 'Feature Request', 'General Feedback', 'Appreciation')
SEVERITIES = ('Low', 'Medium', 'High', 'Critical')
MODULES = ('Leave Management', 'Payroll', 'Attendance', 'Dashboard', 'Other')
STATUSES = ('open', 'reviewed', 'resolved')

# File upload: allowed extensions and max size (5MB)
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
MAX_FILE_SIZE = 5 * 1024 * 1024


def _allowed_file(filename):
    if not filename or '.' not in filename:
        return False
    return filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def _sanitize_text(value, max_len=2000):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    # Remove null bytes and control chars
    s = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', s)
    return s[:max_len] if max_len else s


def _build_email_body(record):
    lines = [
        f"Employee Name: {record.get('employee_name') or 'N/A'}",
        f"Employee ID: {record.get('employee_id') or 'N/A'}",
        f"Department: {record.get('department') or 'N/A'}",
        f"Feedback Type: {record.get('feedback_type') or 'N/A'}",
        f"Module: {record.get('module') or 'N/A'}",
        f"Severity: {record.get('severity') or 'N/A'}",
        f"Timestamp: {record.get('created_at')}",
        "",
        "Description:",
        (record.get('description') or 'N/A'),
    ]
    if record.get('screenshot_path'):
        lines.append("")
        lines.append(f"Screenshot: {record.get('screenshot_path')}")
    return "\n".join(lines)


@feedback_bp.route('/submit', methods=['POST'])
def submit_feedback():
    """
    Submit internal HRMS testing feedback.
    Accepts multipart/form-data (with optional screenshot) or application/json.
    """
    try:
        # Prefer JSON for non-file fields; if form is used, take from form
        if request.is_json:
            data = request.get_json() or {}
            screenshot_file = None
        else:
            data = {k: request.form.get(k) for k in (
                'employee_name', 'employee_id', 'department', 'feedback_type',
                'module', 'severity', 'description'
            )}
            data = {k: (v.strip() if isinstance(v, str) else v) for k, v in data.items() if v is not None}
            screenshot_file = request.files.get('screenshot') if request.files else None

        # Required
        employee_name = _sanitize_text(data.get('employee_name'), 255)
        if not employee_name:
            return jsonify({"error": "Employee name is required"}), 400

        feedback_type = (data.get('feedback_type') or '').strip()
        if feedback_type not in FEEDBACK_TYPES:
            return jsonify({"error": "Invalid feedback type"}), 400

        description = _sanitize_text(data.get('description'), 5000)
        if not description:
            return jsonify({"error": "Description is required"}), 400

        # Optional
        employee_id = _sanitize_text(data.get('employee_id'), 50)
        department = _sanitize_text(data.get('department'), 255)
        module_raw = _sanitize_text(data.get('module'), 255)
        module = module_raw if module_raw in MODULES else (module_raw or 'Other')
        severity = (data.get('severity') or '').strip()
        # DB allows only Low/Medium/High/Critical or NULL; empty string violates check constraint
        if severity not in SEVERITIES:
            severity = None
        # Severity required for Bug Report
        if feedback_type == 'Bug Report' and not severity:
            severity = 'Medium'

        screenshot_path = None
        if screenshot_file and screenshot_file.filename:
            if not _allowed_file(screenshot_file.filename):
                return jsonify({"error": "Screenshot must be an image (png, jpg, jpeg, gif, webp)"}), 400
            blob = screenshot_file.read()
            if len(blob) > MAX_FILE_SIZE:
                return jsonify({"error": "Screenshot must be under 5MB"}), 400
            ext = screenshot_file.filename.rsplit('.', 1)[1].lower()
            safe_name = f"{uuid.uuid4().hex}.{ext}"
            from app.core import media_storage
            key = media_storage.put(f'feedback/{safe_name}', blob)
            # Store media key (portable across MEDIA_ROOT moves)
            screenshot_path = key

        # Insert
        if BACKEND == "postgresql":
            query = """
                INSERT INTO """ + FEEDBACK_TABLE + """
                (employee_name, employee_id, department, feedback_type, module, severity, description, screenshot_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', """ + NOW_SQL + """)
                RETURNING id
            """
        else:
            query = """
                INSERT INTO """ + FEEDBACK_TABLE + """
                (employee_name, employee_id, department, feedback_type, module, severity, description, screenshot_path, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'open', SYSUTCDATETIME());
                SELECT CAST(SCOPE_IDENTITY() AS INT) as lastID;
            """
        result = db_run(query, (
            employee_name, employee_id, department, feedback_type, module, severity, description, screenshot_path
        ))
        feedback_id = result.get('lastID')

        # Fetch created row for email (with created_at)
        row = db_get(
            "SELECT id, employee_name, employee_id, department, feedback_type, module, severity, description, screenshot_path, created_at FROM "
            + FEEDBACK_TABLE + " WHERE id = ?",
            (feedback_id,)
        )
        if row and row.get('created_at'):
            row['created_at'] = row['created_at'].isoformat() if hasattr(row['created_at'], 'isoformat') else str(row['created_at'])

        # Email notification to AI Team (default: techberryaiteam@gmail.com)
        recipient = _feedback_recipient()
        if row:
            subject = f"[HRMS FEEDBACK] {feedback_type} - {module or 'General'}"
            body = _build_email_body(row)
            html = hrms_feedback_html(
                row.get('employee_name'),
                row.get('employee_id'),
                row.get('department'),
                row.get('feedback_type'),
                row.get('module'),
                row.get('severity'),
                row.get('description') or '',
                row.get('created_at'),
                row.get('screenshot_path'),
            )
            send_notification_email(recipient, subject, body, html=html)

        return jsonify({
            "success": True,
            "message": "Thank you. Your feedback has been recorded and will help improve HRMS.",
            "feedback_id": feedback_id
        }), 201

    except Exception as e:
        current_app.logger.exception(e) if current_app else None
        log_unexpected('feedback', e)
        return jsonify({"error": "Failed to submit feedback"}), 500


@feedback_bp.route('/list', methods=['GET'])
@require_recruiter
def list_feedback():
    """
    List feedback entries with optional filters (staff recruiters).
    Query params: feedback_type, module, severity, status, date_from, date_to.
    """
    try:
        feedback_type = request.args.get('feedback_type', '').strip()
        module = request.args.get('module', '').strip()
        severity = request.args.get('severity', '').strip()
        status = request.args.get('status', '').strip()
        date_from = request.args.get('date_from', '').strip()
        date_to = request.args.get('date_to', '').strip()

        conditions = []
        params = []
        if feedback_type and feedback_type in FEEDBACK_TYPES:
            conditions.append("feedback_type = ?")
            params.append(feedback_type)
        if module:
            conditions.append("module = ?")
            params.append(module)
        if severity and severity in SEVERITIES:
            conditions.append("severity = ?")
            params.append(severity)
        if status and status in STATUSES:
            conditions.append("status = ?")
            params.append(status)
        if date_from:
            conditions.append("created_at >= ?")
            params.append(date_from)
        if date_to:
            conditions.append("created_at <= ?")
            params.append(date_to)

        where_clause = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        query = """
            SELECT id, employee_name, employee_id, department, feedback_type, module, severity, description, screenshot_path, status, created_at
            FROM """ + FEEDBACK_TABLE + """
            """ + where_clause + """
            ORDER BY created_at DESC
        """
        if not conditions:
            rows = db_all(query)
        else:
            rows = db_all(query, tuple(params))

        for r in rows:
            if r.get('created_at'):
                r['created_at'] = r['created_at'].isoformat() if hasattr(r['created_at'], 'isoformat') else str(r['created_at'])

        return jsonify({"success": True, "feedback": rows}), 200

    except Exception as e:
        log_unexpected('feedback', e)
        return jsonify({"error": "Failed to list feedback"}), 500


@feedback_bp.route('/<int:feedback_id>/status', methods=['PATCH'])
@require_recruiter
def update_feedback_status(feedback_id):
    """Update feedback status (open / reviewed / resolved). Staff recruiters."""
    try:
        data = request.get_json() or {}
        status = (data.get('status') or '').strip()
        if status not in STATUSES:
            return jsonify({"error": "Invalid status"}), 400
        existing = db_get("SELECT id FROM " + FEEDBACK_TABLE + " WHERE id = ?", (feedback_id,))
        if not existing:
            return jsonify({"error": "Feedback not found"}), 404
        db_run(
            "UPDATE " + FEEDBACK_TABLE + " SET status = ? WHERE id = ?",
            (status, feedback_id)
        )
        return jsonify({"success": True, "message": "Status updated"}), 200
    except Exception as e:
        log_unexpected('feedback', e)
        return jsonify({"error": "Failed to update status"}), 500
