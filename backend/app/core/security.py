from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.settings import settings
from app.models.profile import Profile


@dataclass(frozen=True)
class CurrentUser:
    id: str
    email: str
    role: str


def _normalize_email(value: str) -> str:
    return str(value or "").strip().lower()


def _is_admin_email(email: str) -> bool:
    normalized = _normalize_email(email)
    if not normalized:
        return False
    return normalized in (settings.admin_emails or set())

PERSONAL_EMAIL_DOMAINS: set[str] = {
    "gmail.com",
    "googlemail.com",
    "yahoo.com",
    "yahoo.co.uk",
    "hotmail.com",
    "outlook.com",
    "live.com",
    "msn.com",
    "icloud.com",
    "me.com",
    "mac.com",
    "aol.com",
    "proton.me",
    "protonmail.com",
    "pm.me",
    "gmx.com",
    "gmx.net",
    "mail.com",
    "zoho.com",
    "yandex.com",
    "yandex.ru",
}

DISPOSABLE_EMAIL_DOMAINS: set[str] = {
    "mailinator.com",
    "guerrillamail.com",
    "guerrillamail.net",
    "guerrillamail.org",
    "sharklasers.com",
    "grr.la",
    "10minutemail.com",
    "10minutemail.net",
    "temp-mail.org",
    "tempmailo.com",
    "dispostable.com",
    "trashmail.com",
    "getnada.com",
    "yopmail.com",
    "yopmail.fr",
    "yopmail.net",
    "mohmal.com",
}


def _email_domain(email: str) -> str:
    e = _normalize_email(email)
    at = e.rfind("@")
    if at <= 0:
        return ""
    return e[at + 1 :].strip()


def _validate_signup_email(email: str) -> str | None:
    domain = _email_domain(email)
    if not domain:
        return "Invalid email"
    if domain in DISPOSABLE_EMAIL_DOMAINS:
        return "Temporary/disposable emails are not allowed"
    if domain in PERSONAL_EMAIL_DOMAINS:
        return "Personal emails are not allowed"
    return None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_request_ip(request: Request) -> str | None:
    xff = (request.headers.get("x-forwarded-for") or "").strip()
    if xff:
        first = xff.split(",")[0].strip()
        if first:
            return first
    xri = (request.headers.get("x-real-ip") or "").strip()
    if xri:
        return xri
    client = getattr(request, "client", None)
    host = getattr(client, "host", None) if client else None
    if host:
        return str(host).strip()
    return None


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    import jwt

    supabase_url = (settings.supabase_url or "").rstrip("/")
    if not supabase_url:
        raise HTTPException(status_code=500, detail="SUPABASE_URL is not configured")
    jwks_url = f"{supabase_url}/auth/v1/.well-known/jwks.json"
    issuer = settings.supabase_jwt_issuer or f"{supabase_url}/auth/v1"
    audience = settings.supabase_jwt_audience or "authenticated"

    try:
        jwks_client = jwt.PyJWKClient(jwks_url)
        signing_key = jwks_client.get_signing_key_from_jwt(token).key
        payload = jwt.decode(
            token,
            signing_key,
            algorithms=["ES256", "RS256"],
            audience=audience,
            issuer=issuer,
            options={"require": ["exp", "sub"]},
        )
        return dict(payload)
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid bearer token")
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid bearer token")


def _resolve_role(*, email_is_admin: bool, db_role: str | None) -> str:
    """Two sources only: ADMIN_EMAILS env var (always wins) and local DB profile role."""
    if email_is_admin:
        return "admin"
    dbr = str(db_role or "").strip().lower()
    return dbr if dbr else "user"


def _get_bearer_token(request: Request) -> str:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return token


def diagnose_current_user(request: Request, db: Session) -> dict[str, Any]:
    token = _get_bearer_token(request)
    claims = _decode_supabase_jwt(token)
    user_id = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip()

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    db_role = str((getattr(profile, "role", None) if profile else None) or "").strip().lower() or None
    email_is_admin = _is_admin_email(email)
    decided_role = _resolve_role(email_is_admin=email_is_admin, db_role=db_role)

    return {
        "user_id": user_id,
        "email": email,
        "email_is_admin": email_is_admin,
        "db_profile": {
            "exists": bool(profile),
            "role": db_role,
        },
        "decision": {
            "role": decided_role,
            "reason": "admin_emails" if email_is_admin else ("db_profile" if db_role else "default"),
        },
    }


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    token = _get_bearer_token(request)

    claims = _decode_supabase_jwt(token)
    user_id = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    user_meta = claims.get("user_metadata") or {}
    if not isinstance(user_meta, dict):
        user_meta = {}
    first_name = str(user_meta.get("first_name") or "").strip()
    last_name = str(user_meta.get("last_name") or "").strip()
    company_name = str(user_meta.get("company_name") or user_meta.get("company") or "").strip()
    work_email = str(user_meta.get("work_email") or "").strip() or email

    email_is_admin = _is_admin_email(email)
    profile = db.query(Profile).filter(Profile.id == user_id).first()
    request_ip = _get_request_ip(request)
    seen_at = _utcnow()

    if profile is None:
        if not email_is_admin:
            detail = _validate_signup_email(email)
            if detail:
                raise HTTPException(status_code=400, detail=detail)
        initial_role = _resolve_role(email_is_admin=email_is_admin, db_role=None)
        profile = Profile(
            id=user_id,
            email=email,
            work_email=work_email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            role=initial_role,
            signup_ip=request_ip,
            last_ip=request_ip,
            last_seen_at=seen_at,
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        changed = False
        # If email is in ADMIN_EMAILS, always ensure the DB reflects admin.
        if email_is_admin and (profile.role or "").strip().lower() != "admin":
            profile.role = "admin"
            changed = True
        if email and (profile.email or "") != email:
            profile.email = email
            changed = True
        if work_email and (getattr(profile, "work_email", "") or "") != work_email:
            profile.work_email = work_email
            changed = True
        if first_name and (getattr(profile, "first_name", "") or "") != first_name:
            profile.first_name = first_name
            changed = True
        if last_name and (getattr(profile, "last_name", "") or "") != last_name:
            profile.last_name = last_name
            changed = True
        if company_name and (getattr(profile, "company_name", "") or "") != company_name:
            profile.company_name = company_name
            changed = True
        if request_ip and (getattr(profile, "last_ip", "") or "") != request_ip:
            profile.last_ip = request_ip
            changed = True
        prev_seen = getattr(profile, "last_seen_at", None)
        if prev_seen is None:
            profile.last_seen_at = seen_at
            changed = True
        else:
            try:
                if (seen_at - prev_seen).total_seconds() >= 600:
                    profile.last_seen_at = seen_at
                    changed = True
            except Exception:
                profile.last_seen_at = seen_at
                changed = True
        if changed:
            try:
                db.commit()
            except Exception:
                db.rollback()

    resolved_role = _resolve_role(email_is_admin=email_is_admin, db_role=profile.role)
    return CurrentUser(id=profile.id, email=profile.email or "", role=resolved_role)


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
