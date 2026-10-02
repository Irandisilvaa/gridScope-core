from __future__ import annotations

import hmac

from fastapi import HTTPException, Request, Response, status

try:
    from src.config import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_SESSION_TTL_SECONDS
except ModuleNotFoundError:
    from config import AUTH_COOKIE_NAME, AUTH_COOKIE_SECURE, AUTH_SESSION_TTL_SECONDS

from .security import new_csrf_token
from .store import UserRecord, get_user_by_session_token


CSRF_COOKIE_NAME = "gridscope_csrf"


def request_identity(request: Request) -> str:
    return request.headers.get("x-real-ip") or (request.client.host if request.client else "unknown")


def current_user(request: Request) -> UserRecord:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    try:
        user = get_user_by_session_token(token or "")
    except Exception as error:
        raise HTTPException(status_code=503, detail="Autenticação indisponível") from error
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Autenticação necessária")
    return user


def admin_user(request: Request) -> UserRecord:
    user = current_user(request)
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso administrativo necessário")
    return user


def require_csrf(request: Request) -> None:
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME, "")
    header_token = request.headers.get("x-csrf-token", "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Token CSRF inválido")


def set_auth_cookies(response: Response, session_token: str) -> None:
    csrf_token = new_csrf_token()
    cookie_kwargs = {
        "max_age": AUTH_SESSION_TTL_SECONDS,
        "secure": AUTH_COOKIE_SECURE,
        "httponly": True,
        "samesite": "lax",
        "path": "/",
    }
    response.set_cookie(AUTH_COOKIE_NAME, session_token, **cookie_kwargs)
    response.set_cookie(
        CSRF_COOKIE_NAME,
        csrf_token,
        max_age=AUTH_SESSION_TTL_SECONDS,
        secure=AUTH_COOKIE_SECURE,
        httponly=False,
        samesite="lax",
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME, path="/")
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")
