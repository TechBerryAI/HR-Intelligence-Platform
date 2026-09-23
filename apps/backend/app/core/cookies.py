"""httpOnly-cookie auth for the web client.

Cookies carry the access/refresh JWTs for browser sessions so an XSS can no
longer read them out of localStorage. The Electron desktop client can't rely
on these (its production build loads via ``file://`` and calls the API
cross-origin, so a SameSite cookie from the API's origin never attaches) and
keeps using an ``Authorization: Bearer`` header instead; see
``extract_access_token`` for the dual-mode read that supports both.

Moving auth off a Bearer header and onto a cookie re-introduces CSRF risk that
a header-only scheme never had (browsers don't auto-attach custom headers
cross-site, but they do auto-attach cookies). ``csrf_token`` is a plain
(non-HttpOnly) double-submit cookie: the frontend JS reads it and echoes it
back as the ``X-CSRF-Token`` header on state-changing requests, and
``csrf_ok`` checks the two match. This is defense in depth on top of
``SameSite=Lax``, which already blocks the cookie from attaching to a
cross-site fetch/XHR in the first place.

``csrf_ok`` is enforced by ``authenticate_token``/``optional_authenticate_token``
(``app/api/middleware/auth.py``) for every route that uses them. ``/api/refresh``
and ``/api/logout`` read ``REFRESH_COOKIE_NAME`` directly instead of going
through those decorators, so they are *not* CSRF-checked — deliberately: both
rely on ``SameSite=Lax`` alone, since their worst-case CSRF outcome has no
attacker-exploitable impact (the response — new tokens, or a logout — only
ever reaches the victim's own browser, never the attacker's page).
"""
from __future__ import annotations

import hmac
import os
import secrets

from flask import Request, Response

from app.core.auth import JWT_ACCESS_EXPIRY_SECONDS, JWT_REFRESH_EXPIRY_SECONDS

ACCESS_COOKIE_NAME = "access_token"
REFRESH_COOKIE_NAME = "refresh_token"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "X-CSRF-Token"

# Every authenticated route lives under /api, so this is the narrowest Path
# that still covers all of them (Flask/browsers can't target two disjoint
# paths with one Set-Cookie).
_COOKIE_PATH = "/api"

COOKIE_SECURE = os.getenv(
    "COOKIE_SECURE", str(os.getenv("FLASK_DEBUG", "false").lower() != "true")
).lower() in ("1", "true", "yes", "on")


def _set(response: Response, name: str, value: str, *, max_age: int, http_only: bool) -> None:
    response.set_cookie(
        name,
        value,
        max_age=max_age,
        path=_COOKIE_PATH,
        secure=COOKIE_SECURE,
        httponly=http_only,
        samesite="Lax",
    )


def set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    """Set access/refresh/csrf cookies on a response. Called alongside (not
    instead of) returning the tokens in the JSON body, which the Electron
    client still needs since it can't use these cookies in production."""
    _set(response, ACCESS_COOKIE_NAME, access_token, max_age=JWT_ACCESS_EXPIRY_SECONDS, http_only=True)
    _set(response, REFRESH_COOKIE_NAME, refresh_token, max_age=JWT_REFRESH_EXPIRY_SECONDS, http_only=True)
    _set(
        response,
        CSRF_COOKIE_NAME,
        secrets.token_urlsafe(32),
        max_age=JWT_REFRESH_EXPIRY_SECONDS,
        http_only=False,
    )


def clear_auth_cookies(response: Response) -> None:
    """Expire all three cookies (e.g. on logout). Harmless no-op for a caller
    that never had them (Electron)."""
    for name in (ACCESS_COOKIE_NAME, REFRESH_COOKIE_NAME, CSRF_COOKIE_NAME):
        _set(response, name, "", max_age=0, http_only=(name != CSRF_COOKIE_NAME))


def extract_access_token(request: Request) -> tuple[str | None, str]:
    """Return (token, source). Cookie takes precedence over the Authorization
    header; source is 'cookie' or 'header' so callers can decide whether a
    CSRF check applies (a Bearer header is never auto-attached cross-site by
    a browser, so it needs no CSRF check — only the cookie path does).

    Cookie wins when both are present. Do not flip this to "header wins": the
    web frontend's own api.js still attaches its in-memory token as a Bearer
    header alongside the cookie (a harmless fallback for Electron's sake), so
    header-first precedence would classify the web client's own requests as
    source='header' and silently skip the CSRF check meant to protect it."""
    cookie_token = request.cookies.get(ACCESS_COOKIE_NAME)
    if cookie_token:
        return cookie_token, "cookie"
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1], "header"
    return None, "header"


def csrf_ok(request: Request) -> bool:
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME) or ""
    header_value = request.headers.get(CSRF_HEADER_NAME) or ""
    if not cookie_value or not header_value:
        return False
    return hmac.compare_digest(cookie_value, header_value)
