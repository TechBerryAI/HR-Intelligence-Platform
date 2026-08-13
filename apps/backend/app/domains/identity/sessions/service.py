from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timezone
from typing import Optional, List, Dict

import jwt

from app.core.auth import JWT_SECRET
from app.database.connection.db import db_run, db_get, db_all
from app.domains.identity.authorization.rbac import STAFF_ROLES

MAX_FAILED_LOGIN_ATTEMPTS = 8
LOGIN_LOCKOUT_MINUTES = 15


def audit_user_type(role: str) -> str:
    """Map JWT role to login_history.user_type ('HR')."""
    if role in STAFF_ROLES or (role or '').upper() == 'HR':
        return 'HR'
    return role or 'HR'


def _token_fingerprint(token: str) -> str:
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _ensure_refresh_table() -> None:
    """Idempotent create for environments that have not run the latest migration yet."""
    try:
        db_run(
            """
            CREATE TABLE IF NOT EXISTS auth_refresh_tokens (
                jti VARCHAR(64) PRIMARY KEY,
                user_id VARCHAR(50) NOT NULL,
                token_hash VARCHAR(64) NOT NULL,
                expires_at TIMESTAMPTZ NOT NULL,
                revoked_at TIMESTAMPTZ NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """,
            (),
        )
        db_run(
            """
            CREATE INDEX IF NOT EXISTS idx_auth_refresh_tokens_user
            ON auth_refresh_tokens (user_id)
            """,
            (),
        )
    except Exception as exc:
        print(f"[SESSIONS] refresh table ensure skipped: {exc}")


def register_refresh_token(token: str, user_id: str, expires_at: datetime | None = None) -> Dict:
    _ensure_refresh_table()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
    except Exception:
        return {"success": False, "error": "invalid token"}
    jti = payload.get('jti')
    if not jti:
        return {"success": False, "error": "missing jti"}
    exp = expires_at
    if exp is None and payload.get('exp'):
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
    if exp is None:
        exp = datetime.now(timezone.utc)
    db_run(
        """
        INSERT INTO auth_refresh_tokens (jti, user_id, token_hash, expires_at)
        VALUES (?, ?, ?, ?)
        ON CONFLICT (jti) DO NOTHING
        """,
        (jti, str(user_id), _token_fingerprint(token), exp),
    )
    return {"success": True, "jti": jti}


def is_refresh_token_active(token: str) -> bool:
    _ensure_refresh_table()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
    except Exception:
        return False
    if payload.get('type') != 'refresh':
        return False
    jti = payload.get('jti')
    if not jti:
        return False
    row = db_get(
        """
        SELECT jti FROM auth_refresh_tokens
        WHERE jti = ? AND revoked_at IS NULL AND expires_at > NOW()
          AND token_hash = ?
        """,
        (jti, _token_fingerprint(token)),
    )
    if row:
        return True
    # Backward-compatible: accept first-use tokens issued before table existed,
    # then register them so logout can revoke thereafter.
    existing = db_get("SELECT jti FROM auth_refresh_tokens WHERE jti = ?", (jti,))
    if existing:
        return False
    register_refresh_token(token, str(payload.get('user_id') or ''))
    return True


def revoke_refresh_token(token: str) -> Dict:
    _ensure_refresh_table()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
        jti = payload.get('jti')
    except Exception:
        jti = None
    if jti:
        db_run(
            "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE jti = ? AND revoked_at IS NULL",
            (jti,),
        )
    else:
        db_run(
            "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE token_hash = ? AND revoked_at IS NULL",
            (_token_fingerprint(token),),
        )
    return {"success": True}


def deactivate_session(token: str) -> Dict:
    """Revoke a refresh token (or access token's sibling via body refresh)."""
    if not token:
        return {"success": False, "error": "Token is required"}
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], options={"verify_exp": False})
        if payload.get('type') == 'refresh':
            return revoke_refresh_token(token)
        # Access token logout: revoke all sessions for this user.
        user_id = payload.get('user_id')
        if user_id:
            return deactivate_all_user_sessions(user_id, payload.get('role') or 'HR')
        return {"success": False, "error": "Token is missing user identity"}
    except Exception:
        return {"success": False, "error": "Invalid token"}


def deactivate_all_user_sessions(user_id, user_type: str) -> Dict:
    _ensure_refresh_table()
    if user_id:
        db_run(
            "UPDATE auth_refresh_tokens SET revoked_at = NOW() WHERE user_id = ? AND revoked_at IS NULL",
            (str(user_id),),
        )
    return {"success": True}


def rotate_refresh_token(old_token: str, new_token: str, user_id: str) -> Dict:
    revoke_refresh_token(old_token)
    return register_refresh_token(new_token, user_id)


def is_login_rate_limited(email: str, user_type: str = 'HR') -> bool:
    return get_recent_failed_attempts(email, user_type, LOGIN_LOCKOUT_MINUTES) >= MAX_FAILED_LOGIN_ATTEMPTS


def hash_otp(otp: str) -> str:
    pepper = (JWT_SECRET or 'otp-pepper').encode('utf-8')
    return hmac.new(pepper, str(otp).strip().encode('utf-8'), hashlib.sha256).hexdigest()


def verify_otp_hash(stored: str | None, input_otp: str) -> bool:
    if not stored:
        return False
    stored = str(stored).strip()
    candidate = str(input_otp).strip()
    # Legacy plaintext OTP support during migration
    if len(stored) != 64:
        return secrets.compare_digest(stored, candidate)
    return secrets.compare_digest(stored, hash_otp(candidate))


def get_user_sessions(user_id, user_type: str) -> List[Dict]:
    """Successful logins for this user (from login_history — hr_login merged away)."""
    audit_type = audit_user_type(user_type)
    if audit_type != 'HR' or not user_id:
        return []
    return db_all(
        """
        SELECT user_id AS hrid, email, attempted_at AS logged_in_at,
               ip_address, user_agent
        FROM login_history
        WHERE user_id = ? AND user_type = 'HR' AND status = 'success'
        ORDER BY attempted_at DESC
        LIMIT 100
        """,
        (user_id,),
    )


def record_login_attempt(
    email: str,
    user_type: str,
    status: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None,
    user_id: Optional[str] = None,
) -> Dict:
    db_run(
        """
        INSERT INTO login_history (
            email, user_type, ip_address, user_agent, status, failure_reason, user_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            email,
            audit_user_type(user_type),
            ip_address,
            user_agent,
            status,
            failure_reason,
            user_id,
        ),
    )
    return {"success": True}


def get_login_history(email: str, user_type: str, limit: int = 50) -> List[Dict]:
    return db_all(
        """
        SELECT * FROM login_history
        WHERE email = ? AND user_type = ?
        ORDER BY attempted_at DESC
        LIMIT ?
        """,
        (email, audit_user_type(user_type), limit),
    )


def get_recent_failed_attempts(email: str, user_type: str, minutes: int = 15) -> int:
    row = db_get(
        """
        SELECT COUNT(*) AS cnt FROM login_history
        WHERE email = ? AND user_type = ? AND status = 'failed'
          AND attempted_at > NOW() - (? * INTERVAL '1 minute')
        """,
        (email, audit_user_type(user_type), minutes),
    )
    return int(row["cnt"]) if row else 0


def has_previous_login_from_same_device(
    email: str,
    user_type: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> bool:
    """
    Return True if a previous successful login used the same IP/device combination.
    """
    if not ip_address and not user_agent:
        return False

    conditions = ["email = ?", "user_type = ?", "status = 'success'"]
    params = [email, audit_user_type(user_type)]

    if ip_address:
        conditions.append("ip_address = ?")
        params.append(ip_address)

    if user_agent:
        conditions.append("user_agent = ?")
        params.append(user_agent)

    query = f"""
        SELECT COUNT(*) AS cnt FROM login_history
        WHERE {' AND '.join(conditions)}
    """

    row = db_get(query, tuple(params))
    count = int(row["cnt"]) if row else 0
    return count > 0
