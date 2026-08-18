"""HR auth — single table ``hr_signup`` (pending OTP + active accounts)."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt
from flask import Blueprint, request, jsonify

from app.database.connection.db import db_get, db_run
from app.integrations.email.utils import send_notification_email
from app.integrations.email.templates import (
    welcome_hr_html,
    password_changed_html,
    login_alert_html,
)
from app.domains.identity.otp.otp_utils import (
    generate_otp,
    is_valid_email,
    parse_otp_expiry,
    send_email_otp,
    utc_now_aware,
    normalize_to_utc_aware,
)
from app.domains.identity.sessions.service import (
    record_login_attempt,
    register_refresh_token,
    rotate_refresh_token,
    is_refresh_token_active,
    is_login_rate_limited,
    hash_otp,
    verify_otp_hash,
    deactivate_session,
)
from app.core.auth import build_jwt_payload, JWT_SECRET, validate_password_strength
from app.core import shared_store
from app.core.errors import client_internal_error, log_unexpected
from app.api.middleware.auth import authenticate_token
from app.domains.identity.authorization.rbac import build_hr_identity, ROLE_RECRUITER, get_user_id

auth_bp = Blueprint('auth', __name__)

_OTP_RATE_LIMIT = int(os.getenv('OTP_RATE_LIMIT', '8'))
_OTP_RATE_WINDOW_SEC = int(os.getenv('OTP_RATE_WINDOW_SEC', '900'))


def _otp_rate_limited(email: str) -> bool:
    ip = request.remote_addr or 'unknown'
    return shared_store.rate_limit_hit(
        f'otp:{ip}:{email}',
        _OTP_RATE_LIMIT,
        _OTP_RATE_WINDOW_SEC,
    )

ALLOWED_PASSWORD_RESET_DOMAIN = (
    os.getenv('ALLOWED_PASSWORD_RESET_DOMAIN') or 'techberryinfotech.com'
).strip().lower()


def _is_allowed_password_reset_email(email: str) -> bool:
    if not email or '@' not in email:
        return False
    domain = email.rsplit('@', 1)[-1].strip().lower()
    return domain == ALLOWED_PASSWORD_RESET_DOMAIN


def _next_hrid() -> str:
    try:
        row = db_get(
            "SELECT MAX(CAST(SUBSTRING(hrid,5,10) AS INT)) AS maxn FROM hr_signup",
            (),
        )
        next_num = int(row['maxn']) + 1 if row and row.get('maxn') is not None else 1
    except (ValueError, TypeError, KeyError):
        count_row = db_get("SELECT COUNT(*) AS cnt FROM hr_signup", ())
        next_num = (count_row['cnt'] if count_row else 0) + 1
    return f"HRID{next_num:03d}"


def _otp_valid(stored_otp, otp_expiry_raw, input_otp: str, *, grace_seconds: int = 30) -> tuple[bool, str | None]:
    if not verify_otp_hash(stored_otp, input_otp):
        return False, 'Invalid OTP.'
    expiry = parse_otp_expiry(otp_expiry_raw)
    if not expiry:
        return False, 'OTP expired. Please request a new OTP.'
    expiry_utc = normalize_to_utc_aware(expiry)
    if expiry_utc and utc_now_aware() > (expiry_utc + timedelta(seconds=grace_seconds)):
        return False, 'OTP expired. Please request a new OTP.'
    return True, None


def _issue_token_pair(identity: dict) -> tuple[str, str]:
    access_token = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
    refresh_token = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')
    register_refresh_token(refresh_token, identity['user_id'])
    return access_token, refresh_token


def _attach_org(hrid: str, company: str | None) -> None:
    try:
        from app.domains.identity.services.organizations import (
            attach_organization_id,
            ensure_organization,
        )
        org_id = ensure_organization(company)
        attach_organization_id('hr_signup', 'hrid', hrid, org_id)
    except Exception as org_err:
        print(f"[HR AUTH] organization attach skipped: {org_err}")


@auth_bp.post('/signup')
def hr_signup():
    try:
        data = request.get_json(force=True)
        full_name = (data.get('fullName') or '').strip()
        email = (data.get('email') or '').strip().lower()
        password = data.get('password') or ''
        company = (data.get('company') or '').strip()

        if not full_name or not email or not password or not company:
            return jsonify({"error": "All fields are required"}), 400
        ok, err = validate_password_strength(password)
        if not ok:
            return jsonify({"error": err}), 400
        if not is_valid_email(email):
            return jsonify({"error": "Please provide a valid email address"}), 400

        from app.domains.identity.services.organizations import organization_exists_for_name

        if organization_exists_for_name(company):
            return jsonify({
                "error": "This company already exists. Ask your Head of HR to create your account.",
            }), 400
        return jsonify({
            "error": (
                "New companies must be provisioned by a platform administrator. "
                "Ask your Head of HR for an account."
            ),
        }), 400
    except Exception as e:
        log_unexpected('hr_signup', e)
        return client_internal_error()


@auth_bp.post('/verify-otp')
def verify_hr_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if _otp_rate_limited(email):
            return jsonify({'error': 'Too many OTP attempts. Please try again later.'}), 429

        row = db_get(
            """
            SELECT hrid, full_name, email, company, password, role, account_status, otp, otp_expiry
            FROM hr_signup WHERE LOWER(TRIM(email)) = ?
            """,
            (email,),
        )
        if not row:
            return jsonify({'error': 'HR not found. Please signup again.'}), 404
        if (row.get('account_status') or 'active') == 'active' and not row.get('otp'):
            return jsonify({"error": "Account already verified and registered"}), 400

        ok, err = _otp_valid(row.get('otp'), row.get('otp_expiry'), otp)
        if not ok:
            return jsonify({'error': err}), 400

        db_run(
            """
            UPDATE hr_signup SET
                account_status = 'active', otp = NULL, otp_expiry = NULL, updated_at = NOW()
            WHERE hrid = ?
            """,
            (row['hrid'],),
        )

        hrid = row['hrid']
        identity = build_hr_identity({**row, 'role': ROLE_RECRUITER})
        access_token, refresh_token = _issue_token_pair(identity)

        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')
        record_login_attempt(
            row['email'], 'HR', 'success', ip_address, user_agent, user_id=hrid
        )

        try:
            body = (
                f"Hi {row['full_name'] or 'there'},\n\n"
                "Welcome to HR Intelligence! Your account is verified and ready."
            )
            html = welcome_hr_html(row['full_name'] or 'there')
            send_notification_email(row['email'], "Welcome to HR Intelligence", body, html=html)
        except Exception:
            pass

        return jsonify({
            "message": "Account verified and created successfully",
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "hrId": hrid,
                "email": row['email'],
                "fullName": row['full_name'],
                "company": row['company'],
                "role": ROLE_RECRUITER,
            }
        }), 200
    except Exception as e:
        log_unexpected('verify_hr_otp', e)
        return client_internal_error()


@auth_bp.post('/resend-otp')
def resend_hr_otp():
    try:
        data = request.get_json(force=True)
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        if not is_valid_email(email):
            return jsonify({"error": "Please provide a valid email address"}), 400
        if _otp_rate_limited(email):
            return jsonify({'error': 'Too many OTP requests. Please try again later.'}), 429

        row = db_get(
            'SELECT hrid, account_status FROM hr_signup WHERE LOWER(TRIM(email)) = ?',
            (email,),
        )
        if not row:
            return jsonify({'error': 'No signup found. Please signup first.'}), 404
        if (row.get('account_status') or 'active') == 'active':
            return jsonify({'error': 'Account already verified. Please login.'}), 400

        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=5)
        db_run(
            'UPDATE hr_signup SET otp = ?, otp_expiry = ?, updated_at = NOW() WHERE hrid = ?',
            (hash_otp(otp), expiry, row['hrid']),
        )
        if not send_email_otp(email, otp, user_type="HR"):
            return jsonify({'error': 'Unable to send OTP. Please try again later.'}), 500
        return jsonify({'message': 'OTP resent successfully. Please check your email.'}), 200
    except Exception as e:
        log_unexpected('resend_hr_otp', e)
        return client_internal_error()


@auth_bp.post('/forgot-password')
def hr_forgot_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        if not email:
            return jsonify({'error': 'Email is required.'}), 400
        if not is_valid_email(email) or not _is_allowed_password_reset_email(email):
            return jsonify({'error': 'Invalid email'}), 400
        if _otp_rate_limited(email):
            return jsonify({'error': 'Too many OTP requests. Please try again later.'}), 429

        hr_row = db_get(
            """
            SELECT hrid, full_name FROM hr_signup
            WHERE LOWER(TRIM(email)) = ? AND COALESCE(account_status, 'active') = 'active'
            """,
            (email,),
        )
        if not hr_row:
            return jsonify({'error': 'Invalid email'}), 400

        otp = generate_otp()
        expiry = datetime.now(timezone.utc) + timedelta(minutes=10)
        db_run(
            'UPDATE hr_signup SET otp = ?, otp_expiry = ?, updated_at = NOW() WHERE hrid = ?',
            (hash_otp(otp), expiry, hr_row['hrid']),
        )
        if not send_email_otp(email, otp, user_type="HR", purpose="password_reset", minutes=10):
            return jsonify({'error': 'Failed to send OTP email. Please try again later.'}), 500
        return jsonify({'message': 'OTP sent successfully. Please check your email.'}), 200
    except Exception as e:
        log_unexpected('hr_forgot_password', e)
        return client_internal_error()


@auth_bp.post('/forgot-password/resend-otp')
def hr_forgot_password_resend():
    return hr_forgot_password()


@auth_bp.post('/forgot-password/verify-otp')
def hr_verify_reset_otp():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if not is_valid_email(email) or not _is_allowed_password_reset_email(email):
            return jsonify({'error': 'Invalid email'}), 400
        if _otp_rate_limited(email):
            return jsonify({'error': 'Too many OTP attempts. Please try again later.'}), 429

        row = db_get(
            'SELECT otp, otp_expiry FROM hr_signup WHERE LOWER(TRIM(email)) = ?',
            (email,),
        )
        if not row or not row.get('otp'):
            return jsonify({'error': 'Please request a new OTP.'}), 400
        ok, err = _otp_valid(row.get('otp'), row.get('otp_expiry'), otp)
        if not ok:
            return jsonify({'error': err}), 400
        return jsonify({'message': 'OTP verified. You may set a new password.'}), 200
    except Exception as e:
        log_unexpected('hr_verify_reset_otp', e)
        return client_internal_error()


@auth_bp.post('/reset-password')
def hr_reset_password():
    try:
        data = request.get_json(force=True) or {}
        email = (data.get('email') or '').strip().lower()
        otp = (data.get('otp') or '').strip()
        new_password = data.get('newPassword') or data.get('password') or ''
        confirm_password = data.get('confirmPassword') or data.get('confirm_password') or ''

        if not email or not otp:
            return jsonify({'error': 'Email and OTP are required.'}), 400
        if not is_valid_email(email) or not _is_allowed_password_reset_email(email):
            return jsonify({'error': 'Invalid email'}), 400
        ok, err = validate_password_strength(new_password)
        if not ok:
            return jsonify({'error': err}), 400
        if new_password != confirm_password:
            return jsonify({'error': 'Passwords do not match.'}), 400

        row = db_get(
            """
            SELECT hrid, full_name, otp, otp_expiry FROM hr_signup
            WHERE LOWER(TRIM(email)) = ?
              AND COALESCE(account_status, 'active') = 'active'
            """,
            (email,),
        )
        if not row:
            return jsonify({'error': 'Account not found for this email.'}), 404
        if not row.get('otp'):
            return jsonify({'error': 'Please request a new OTP.'}), 400
        valid, verr = _otp_valid(row.get('otp'), row.get('otp_expiry'), otp, grace_seconds=0)
        if not valid:
            return jsonify({'error': verr}), 400

        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_run(
            """
            UPDATE hr_signup SET password = ?, otp = NULL, otp_expiry = NULL, updated_at = NOW()
            WHERE hrid = ?
            """,
            (password_hash, row['hrid']),
        )

        html = password_changed_html(row.get('full_name') or 'there')
        send_notification_email(
            email,
            "Your HR Intelligence password was changed",
            "Your password was changed.",
            html=html,
        )
        return jsonify({'message': 'Password updated successfully. You can now login.'}), 200
    except Exception as e:
        log_unexpected('hr_reset_password', e)
        return client_internal_error()


@auth_bp.post('/login')
def hr_login():
    try:
        data = request.get_json(force=True)
        email = data.get('email')
        password = data.get('password')
        ip_address = request.remote_addr
        user_agent = request.headers.get('User-Agent')

        if not email or not password:
            return jsonify({"error": "Email and password are required"}), 400

        email_clean = email.strip().lower()
        if is_login_rate_limited(email_clean, 'HR'):
            return jsonify({
                "error": "Too many failed login attempts. Try again in 15 minutes.",
            }), 429

        signup_data = db_get(
            """
            SELECT hrid, email, password, full_name, company, role, account_status,
                   organization_id
            FROM hr_signup WHERE LOWER(TRIM(email)) = ?
            """,
            (email_clean,),
        )
        if not signup_data or (signup_data.get('account_status') or 'active') != 'active':
            record_login_attempt(email, 'HR', 'failed', ip_address, user_agent, 'User not found')
            return jsonify({"error": "Invalid email or password"}), 401

        user_id = signup_data['hrid']
        stored = signup_data.get('password') or ''
        if not stored:
            record_login_attempt(
                email, 'HR', 'failed', ip_address, user_agent, 'Invalid password', user_id=user_id
            )
            return jsonify({"error": "Invalid email or password"}), 401
        stored_b = stored.encode('utf-8') if isinstance(stored, str) else stored
        if not bcrypt.checkpw(password.encode('utf-8'), stored_b):
            record_login_attempt(
                email, 'HR', 'failed', ip_address, user_agent, 'Invalid password', user_id=user_id
            )
            return jsonify({"error": "Invalid email or password"}), 401

        identity = build_hr_identity(signup_data)
        role = identity['role']
        access_token, refresh_token = _issue_token_pair(identity)

        from app.domains.identity.sessions.service import has_previous_login_from_same_device
        is_new_device = not has_previous_login_from_same_device(email, 'HR', ip_address, user_agent)

        record_login_attempt(
            email, 'HR', 'success', ip_address, user_agent, user_id=user_id
        )

        if is_new_device:
            login_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            body = (
                f"Hi {signup_data['full_name'] or 'there'},\n\n"
                f"We noticed a login to your HR Intelligence account on {login_time}\n"
                f"IP Address: {ip_address or 'Unavailable'}\n"
                f"Device: {user_agent or 'Unavailable'}\n\n"
                "If this was you, no action is needed. If you did not sign in, please reset your password immediately."
            )
            html = login_alert_html(
                signup_data['full_name'] or 'there',
                ip_address or 'Unavailable',
                user_agent or 'Unavailable',
                login_time,
            )
            send_notification_email(
                signup_data['email'],
                "New login to your HR Intelligence account",
                body,
                html=html,
            )

        return jsonify({
            "token": access_token,
            "refresh_token": refresh_token,
            "user": {
                "hrId": user_id,
                "email": signup_data['email'],
                "fullName": signup_data['full_name'],
                "company": identity.get('org_name') or signup_data['company'],
                "role": role,
                "organizationId": identity.get('organization_id'),
                "orgSlug": identity.get('org_slug'),
            }
        })
    except Exception:
        return jsonify({"error": "Internal server error"}), 500


@auth_bp.post('/change-password')
@authenticate_token
def hr_change_password():
    try:
        user = getattr(request, 'user', None)
        if not user or not get_user_id(user):
            return jsonify({'error': 'Access denied'}), 403
        data = request.get_json(force=True) or {}
        current_password = (data.get('currentPassword') or data.get('current_password') or '').strip()
        new_password = (data.get('newPassword') or data.get('new_password') or '').strip()
        if not current_password:
            return jsonify({'error': 'Current password is required'}), 400
        ok, err = validate_password_strength(new_password)
        if not ok:
            return jsonify({'error': err}), 400
        hrid = get_user_id(user)
        signup_data = db_get(
            """
            SELECT hrid, email, password, full_name FROM hr_signup
            WHERE hrid = ? AND COALESCE(account_status, 'active') = 'active'
            """,
            (hrid,),
        )
        if not signup_data:
            return jsonify({'error': 'Account not found'}), 404
        stored = signup_data.get('password') or ''
        if not stored:
            return jsonify({'error': 'Invalid current password'}), 401
        stored_b = stored.encode('utf-8') if isinstance(stored, str) else stored
        if not bcrypt.checkpw(current_password.encode('utf-8'), stored_b):
            return jsonify({'error': 'Current password is incorrect'}), 401
        password_hash = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        db_run('UPDATE hr_signup SET password = ?, updated_at = NOW() WHERE hrid = ?', (password_hash, hrid))
        try:
            html = password_changed_html(signup_data.get('full_name') or 'there')
            send_notification_email(
                signup_data['email'],
                "Your HR Intelligence password was changed",
                "Your password was changed.",
                html=html,
            )
        except Exception:
            pass
        return jsonify({'message': 'Password updated successfully'}), 200
    except Exception as e:
        log_unexpected('hr_change_password', e)
        return client_internal_error()


@auth_bp.post('/refresh')
def refresh_tokens():
    try:
        data = request.get_json(silent=True) or {}
        refresh_token = (data.get('refresh_token') or '').strip()
        if not refresh_token:
            return jsonify({"error": "refresh_token required"}), 400
        payload = jwt.decode(refresh_token, JWT_SECRET, algorithms=["HS256"])
        if payload.get('type') != 'refresh':
            return jsonify({"error": "Invalid refresh token"}), 403
        if not is_refresh_token_active(refresh_token):
            return jsonify({"error": "Refresh token revoked"}), 403
        user_id = payload.get('user_id')
        if not user_id:
            return jsonify({"error": "Invalid refresh token"}), 403
        signup_data = db_get(
            """
            SELECT hrid, email, full_name, company, role, account_status, organization_id
            FROM hr_signup WHERE hrid = ?
            """,
            (user_id,),
        )
        if not signup_data or (signup_data.get('account_status') or 'active') != 'active':
            deactivate_session(refresh_token)
            return jsonify({"error": "Account inactive or not found"}), 403
        identity = build_hr_identity(signup_data)
        new_access = jwt.encode(build_jwt_payload(identity, refresh=False), JWT_SECRET, algorithm='HS256')
        new_refresh = jwt.encode(build_jwt_payload(identity, refresh=True), JWT_SECRET, algorithm='HS256')
        rotate_refresh_token(refresh_token, new_refresh, identity['user_id'])
        return jsonify({"token": new_access, "refresh_token": new_refresh})
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "Refresh token expired"}), 403
    except jwt.InvalidTokenError:
        return jsonify({"error": "Invalid refresh token"}), 403
    except Exception as e:
        log_unexpected('hr_refresh_token', e)
        return jsonify({"error": "Invalid refresh token"}), 403


@auth_bp.post('/logout')
def hr_logout():
    try:
        data = request.get_json(silent=True) or {}
        refresh_token = (data.get('refresh_token') or '').strip()
        auth_header = request.headers.get('Authorization', '')
        access_token = auth_header.split(' ')[1] if auth_header.startswith('Bearer ') else None
        if refresh_token:
            deactivate_session(refresh_token)
        elif access_token:
            deactivate_session(access_token)
        return jsonify({"message": "Logged out successfully"})
    except Exception:
        return jsonify({"message": "Logged out successfully"})
