"""
Admin-only Developer Mode performance APIs.

Gated by DEVELOPER_MODE env flag + HEAD_HR (Administrator) authorization.
When Developer Mode is off, all routes return 404.
"""
from __future__ import annotations

import csv
import io
from functools import wraps

from flask import Blueprint, Response, jsonify, request

from app.api.middleware.auth import authenticate_token, require_head_hr
from app.core.developer_mode import is_developer_mode_enabled
from app.core.timing_collector import timing_collector
from app.domains.identity.authorization.rbac import has_permission

developer_bp = Blueprint("developer", __name__)


def require_developer_mode(f):
    """404 when Developer Mode is disabled so the surface is invisible."""

    @wraps(f)
    def wrapper(*args, **kwargs):
        if not is_developer_mode_enabled():
            return jsonify({"error": "Not found"}), 404
        return f(*args, **kwargs)

    return wrapper


def require_developer_admin(f):
    """HEAD_HR + developer:performance permission + Developer Mode enabled."""

    @wraps(f)
    @require_developer_mode
    @require_head_hr
    def wrapper(*args, **kwargs):
        user = getattr(request, "user", None)
        if not has_permission(user, "developer:performance"):
            return jsonify({"error": "Access denied"}), 403
        return f(*args, **kwargs)

    return wrapper


def _filter_kwargs_from_request() -> dict:
    args = request.args
    return {
        "candidate_id": (args.get("candidate_id") or args.get("candidate") or "").strip() or None,
        "job_id": (args.get("job_id") or args.get("job") or "").strip() or None,
        "function_name": (args.get("function_name") or args.get("function") or "").strip() or None,
        "status": (args.get("status") or "").strip() or None,
        "request_id": (args.get("request_id") or "").strip() or None,
        "date_from": (args.get("date_from") or args.get("from") or "").strip() or None,
        "date_to": (args.get("date_to") or args.get("to") or "").strip() or None,
        "kind": (args.get("kind") or "").strip() or None,
    }


@developer_bp.route("/status", methods=["GET"])
@authenticate_token
def developer_status():
    """
    Lightweight flag for the SPA.

    Any authenticated staff can call this; only returns enabled=true for HEAD_HR
    when Developer Mode is on (Recruiters never see the UI).
    """
    from app.domains.identity.authorization.rbac import is_head_hr

    user = getattr(request, "user", None)
    enabled = bool(is_developer_mode_enabled() and user and is_head_hr(user))
    return jsonify({"enabled": enabled, "developer_mode": is_developer_mode_enabled()})


@developer_bp.route("/performance/recent", methods=["GET"])
@require_developer_admin
def performance_recent():
    try:
        limit = min(200, max(1, int(request.args.get("limit", 50))))
    except (TypeError, ValueError):
        limit = 50
    filters = _filter_kwargs_from_request()
    sessions = timing_collector.list_recent(limit=limit, **filters)
    return jsonify(
        {
            "sessions": [s.to_summary() for s in sessions],
            "count": len(sessions),
        }
    )


@developer_bp.route("/performance/request/<request_id>", methods=["GET"])
@require_developer_admin
def performance_request(request_id: str):
    session = timing_collector.get_session(request_id)
    if session is None:
        return jsonify({"error": "Request not found"}), 404
    return jsonify(session.to_detail())


@developer_bp.route("/performance/stats", methods=["GET"])
@require_developer_admin
def performance_stats():
    try:
        hours = float(request.args.get("hours", 24))
    except (TypeError, ValueError):
        hours = 24.0
    hours = max(0.1, min(hours, 168.0))
    return jsonify(timing_collector.compute_stats(hours=hours))


@developer_bp.route("/performance/export", methods=["GET"])
@require_developer_admin
def performance_export():
    """CSV export of recent timing events (filterable)."""
    try:
        limit = min(1000, max(1, int(request.args.get("limit", 500))))
    except (TypeError, ValueError):
        limit = 500
    filters = _filter_kwargs_from_request()
    sessions = timing_collector.list_recent(limit=limit, **filters)

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "request_id",
            "started_at",
            "kind",
            "status",
            "total_duration_ms",
            "candidate_id",
            "job_id",
            "user_id",
            "path",
            "function",
            "module",
            "stage",
            "duration_ms",
            "success",
            "exception_name",
            "timestamp",
        ]
    )
    for s in sessions:
        if not s.events:
            writer.writerow(
                [
                    s.request_id,
                    s.started_at,
                    s.kind,
                    s.status,
                    s.total_duration_ms,
                    s.candidate_id or "",
                    s.job_id or "",
                    s.user_id or "",
                    s.path,
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                    "",
                ]
            )
            continue
        for e in s.events:
            writer.writerow(
                [
                    s.request_id,
                    s.started_at,
                    s.kind,
                    s.status,
                    s.total_duration_ms,
                    e.candidate_id or s.candidate_id or "",
                    e.job_id or s.job_id or "",
                    e.user_id or s.user_id or "",
                    s.path,
                    e.function,
                    e.module,
                    e.stage,
                    e.duration_ms,
                    e.success,
                    e.exception_name or "",
                    e.timestamp,
                ]
            )

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=performance-timings.csv",
        },
    )
