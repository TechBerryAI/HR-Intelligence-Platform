from typing import Optional, List, Dict
from db import db_run, db_get, db_all, BACKEND


def deactivate_session(token: str) -> Dict:
    # Sessions are now tracked in login history tables, no active session table to deactivate
    return {"success": True}


def deactivate_all_user_sessions(user_id, user_type: str) -> Dict:
    # Sessions are now tracked in login history tables, no active session table to deactivate
    return {"success": True}


def get_user_sessions(user_id, user_type: str) -> List[Dict]:
    if user_type == 'HR':
        return db_all("SELECT hrid, email, logged_in_at FROM hr_login WHERE hrid = ? ORDER BY logged_in_at DESC", (user_id,))
    if user_type == 'candidate':
        return db_all(
            "SELECT cid, email, logged_in_at FROM candidate_login WHERE cid = ? ORDER BY logged_in_at DESC",
            (user_id,)
        )
    return []


def record_login_attempt(email: str, user_type: str, status: str, ip_address: Optional[str] = None,
                         user_agent: Optional[str] = None, failure_reason: Optional[str] = None) -> Dict:
    db_run(
        """
        INSERT INTO login_history (email, user_type, ip_address, user_agent, status, failure_reason)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (email, user_type, ip_address, user_agent, status, failure_reason)
    )
    return {"success": True}


def get_login_history(email: str, user_type: str, limit: int = 50) -> List[Dict]:
    if BACKEND == "postgresql":
        return db_all(
            """
            SELECT * FROM login_history
            WHERE email = ? AND user_type = ?
            ORDER BY attempted_at DESC
            LIMIT ?
            """,
            (email, user_type, limit)
        )
    return db_all(
        """
        SELECT TOP (?) * FROM login_history
        WHERE email = ? AND user_type = ?
        ORDER BY attempted_at DESC
        """,
        (limit, email, user_type)
    )


def get_recent_failed_attempts(email: str, user_type: str, minutes: int = 15) -> int:
    if BACKEND == "postgresql":
        row = db_get(
            """
            SELECT COUNT(*) AS cnt FROM login_history
            WHERE email = ? AND user_type = ? AND status = 'failed'
              AND (EXTRACT(EPOCH FROM (NOW() - attempted_at)) / 60) < ?
            """,
            (email, user_type, minutes)
        )
    else:
        row = db_get(
            """
            SELECT COUNT(*) AS cnt FROM login_history
            WHERE email = ? AND user_type = ? AND status = 'failed'
              AND DATEDIFF(MINUTE, attempted_at, SYSUTCDATETIME()) < ?
            """,
            (email, user_type, minutes)
        )
    return int(row["cnt"]) if row else 0


def has_previous_login_from_same_device(email: str, user_type: str, ip_address: Optional[str] = None,
                                        user_agent: Optional[str] = None) -> bool:
    """
    Check if there's been a previous successful login from the same IP address and device.
    Returns True if this IP/device combination has been used before for successful logins.
    """
    if not ip_address and not user_agent:
        return False
    
    # Build query to check for previous successful logins with same IP and device
    conditions = ["email = ?", "user_type = ?", "status = 'success'"]
    params = [email, user_type]
    
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
    
    # Return True if there's at least one previous successful login from this IP/device
    return count > 0