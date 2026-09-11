"""Short-lived signed claims binding a public parse to a later apply."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import jwt

from app.core.auth import JWT_SECRET

PARSE_CLAIM_TYPE = 'parse_claim'
PARSE_CLAIM_TTL_SECONDS = int(os.getenv('PARSE_CLAIM_TTL_SECONDS', str(60 * 60)))


def issue_parse_claim(parsed_id: str) -> str:
    """Return a signed JWT authorizing apply with this parsed_id."""
    pid = (parsed_id or '').strip()
    if not pid:
        raise ValueError('parsed_id required')
    now = datetime.now(timezone.utc)
    payload = {
        'type': PARSE_CLAIM_TYPE,
        'parsed_id': pid,
        'iat': now,
        'exp': now + timedelta(seconds=PARSE_CLAIM_TTL_SECONDS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm='HS256')


def verify_parse_claim(claim: str | None, parsed_id: str) -> bool:
    """True when claim is a valid, unexpired parse_claim for parsed_id."""
    if not claim or not parsed_id:
        return False
    try:
        payload = jwt.decode(claim, JWT_SECRET, algorithms=['HS256'])
    except Exception:
        return False
    if payload.get('type') != PARSE_CLAIM_TYPE:
        return False
    return str(payload.get('parsed_id') or '') == str(parsed_id).strip()
