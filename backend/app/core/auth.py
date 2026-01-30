import secrets
import base64

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.security.utils import get_authorization_scheme_param

from app.core.settings import settings


security = HTTPBasic(auto_error=False)


def enforce_basic_auth_for_request(request: Request) -> None:
    if not settings.basic_auth_enabled:
        return

    if settings.basic_auth_username is None or settings.basic_auth_password is None:
        raise RuntimeError("Basic Auth enabled but credentials are not set")
        return

    auth_header = request.headers.get("authorization")
    scheme, param = get_authorization_scheme_param(auth_header)
    if scheme.lower() != "basic" or not param:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    try:
        decoded = base64.b64decode(param).decode("utf-8")
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    if ":" not in decoded:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )

    username, password = decoded.split(":", 1)
    username_ok = secrets.compare_digest(username, settings.basic_auth_username)
    password_ok = secrets.compare_digest(password, settings.basic_auth_password)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )


def require_basic_auth(credentials: HTTPBasicCredentials | None = Depends(security)) -> None:
    if not settings.basic_auth_enabled:
        return

    if settings.basic_auth_username is None or settings.basic_auth_password is None:
        raise RuntimeError("Basic Auth enabled but credentials are not set")
        return

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Basic"},
        )

    username_ok = secrets.compare_digest(credentials.username, settings.basic_auth_username)
    password_ok = secrets.compare_digest(credentials.password, settings.basic_auth_password)

    if not (username_ok and password_ok):
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
            headers={"WWW-Authenticate": "Basic"},
        )
