from typing import Optional, List, Dict

from app.database.connection.db import db_run, db_get, db_all
from app.domains.identity.authorization.rbac import ROLE_CANDIDATE, STAFF_ROLES


def audit_user_type(role: str) -> str:
    """Map JWT role to login_history.user_type ('HR' | 'candidate')."""
    if role == ROLE_CANDIDATE or (role or '').lower() == 'candidate':
        return 'candidate'
    if role in STAFF_ROLES or (role or '').upper() == 'HR':
        return 'HR'
    return role


def deactivate_session(token: str) -> Dict:
    # Sessions are tracked in login history; no active session table to deactivate
    return {"success": True}


def deactivate_all_user_sessions(user_id, user_type: str) -> Dict:
    # Sessions are tracked in login history; no active session table to deactivate
    return {"success": True}


def get_user_sessions(user_id, user_type: str) -> List[Dict]:
    audit_type = audit_user_type(user_type)
    if audit_type == 'HR':
        return db_all(
            "SELECT hrid, email, logged_in_at FROM hr_login WHERE hrid = ? ORDER BY logged_in_at DESC",
            (user_id,),
        )
    if audit_type == 'candidate':
        return db_all(
            "SELECT cid, email, logged_in_at FROM candidate_login WHERE cid = ? ORDER BY logged_in_at DESC",
            (user_id,),
        )
    return []


def record_login_attempt(
    email: str,
    user_type: str,
    status: str,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
    failure_reason: Optional[str] = None,
) -> Dict:
    db_run(
        """
        INSERT INTO login_history (email, user_type, ip_address, user_agent, status, failure_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, audit_user_type(user_type), ip_address, user_agent, status, failure_reason),
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
