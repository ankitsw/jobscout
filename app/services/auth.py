"""Single shared-password gate for the whole app.

This is not a multi-user auth system - there's one password
(settings.site_access_key), handed out to whoever the owner wants to let
in. A successful login gets a signed, HttpOnly session cookie; there's no
per-user account or data ownership behind it. If site_access_key is unset
the gate is disabled outright, which is what local development expects.
"""
import time

import jwt
from fastapi import HTTPException, Request

from app.config import settings

COOKIE_NAME = "jobscout_session"
_ALGORITHM = "HS256"
_SESSION_MAX_AGE_SECONDS = 60 * 60 * 24 * 30  # 30 days


def gate_enabled() -> bool:
    return bool(settings.site_access_key)


def check_password(password: str) -> bool:
    return gate_enabled() and password == settings.site_access_key


def create_session_token() -> str:
    payload = {"authenticated": True, "exp": int(time.time()) + _SESSION_MAX_AGE_SECONDS}
    return jwt.encode(payload, settings.session_secret, algorithm=_ALGORITHM)


def is_valid_session(token: str | None) -> bool:
    if not token:
        return False
    try:
        jwt.decode(token, settings.session_secret, algorithms=[_ALGORITHM])
        return True
    except jwt.PyJWTError:
        return False


def require_access(request: Request) -> None:
    """FastAPI dependency gating the app's data/action routes. No-op when
    no access key is configured, so local dev never needs to log in."""
    if not gate_enabled():
        return
    if not is_valid_session(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status_code=401, detail="Not authenticated")
