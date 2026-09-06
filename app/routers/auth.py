from fastapi import APIRouter, Request, Response, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.rate_limit import limiter
from app.services import auth as auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    password: str


@router.get("/status")
def status(request: Request):
    if not auth_service.gate_enabled():
        return {"gate_enabled": False, "authenticated": True}
    token = request.cookies.get(auth_service.COOKIE_NAME)
    return {"gate_enabled": True, "authenticated": auth_service.is_valid_session(token)}


@router.post("/login")
@limiter.limit("10/minute")
def login(request: Request, response: Response, payload: LoginRequest):
    if not auth_service.gate_enabled():
        return {"ok": True}
    if not auth_service.check_password(payload.password):
        raise HTTPException(status_code=401, detail="Incorrect password")
    token = auth_service.create_session_token()
    response.set_cookie(
        auth_service.COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=settings.environment == "production",
        max_age=auth_service._SESSION_MAX_AGE_SECONDS,
    )
    return {"ok": True}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(auth_service.COOKIE_NAME)
    return {"ok": True}
