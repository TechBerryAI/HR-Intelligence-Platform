from typing import Optional, List, Dict

from app.database.connection.db import db_run, db_get, db_all
from app.domains.identity.authorization.rbac import STAFF_ROLES


def audit_user_type(role: str) -> str:
    """Map JWT role to login_history.user_type ('HR')."""
    if role in STAFF_ROLES or (role or '').upper() == 'HR':
        return 'HR'
    return role or 'HR'


def deactivate_session(token: str) -> Dict:
    return {"success": True}


def deactivate_all_user_sessions(user_id, user_type: str) -> Dict:
    return {"success": True}


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
