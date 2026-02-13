from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.settings import settings
from app.models.profile import Profile
from app.services.cache import TTLCache


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


def _require_supabase_config() -> str:
    if not settings.supabase_url:
        raise HTTPException(status_code=500, detail="SUPABASE_URL is not configured")
    return settings.supabase_url


def _decode_supabase_jwt(token: str) -> dict[str, Any]:
    import jwt

    supabase_url = _require_supabase_config().rstrip("/")
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


_SUPABASE_PROFILE_ROLE_CACHE = TTLCache(max_items=20000, ttl_s=60)


def _supabase_rest_profiles_role(
    *,
    supabase_url: str,
    user_id: str,
    api_key: str,
    bearer: str,
    timeout_s: float = 8,
) -> tuple[int | None, str | None]:
    try:
        import requests

        resp = requests.get(
            f"{supabase_url}/rest/v1/profiles",
            params={"select": "role", "id": f"eq.{user_id}"},
            headers={
                "apikey": api_key,
                "authorization": f"Bearer {bearer}",
                "accept": "application/json",
            },
            timeout=timeout_s,
        )
        status = int(resp.status_code)
        if status != 200:
            return (status, None)
        rows = resp.json()
        if not isinstance(rows, list) or not rows:
            return (status, None)
        role = rows[0].get("role") if isinstance(rows[0], dict) else None
        role = str(role or "").strip().lower() or None
        return (status, role)
    except Exception:
        return (None, None)


def _fetch_profile_role_from_supabase_cached(*, user_id: str, user_token: str) -> str | None:
    supabase_url = (settings.supabase_url or "").strip().rstrip("/")
    if not supabase_url:
        return None
    api_key = (settings.supabase_service_role_key or settings.supabase_anon_key or "").strip()
    if not api_key:
        return None
    cache_key = f"supabase_profile_role:{user_id}"
    cached = _SUPABASE_PROFILE_ROLE_CACHE.get(cache_key)
    if isinstance(cached, str):
        return cached or None
    bearer = (settings.supabase_service_role_key or user_token or "").strip()
    if not bearer:
        return None
    _status, role = _supabase_rest_profiles_role(
        supabase_url=supabase_url,
        user_id=user_id,
        api_key=api_key,
        bearer=bearer,
        timeout_s=8,
    )
    if role:
        _SUPABASE_PROFILE_ROLE_CACHE.set(cache_key, role)
    return role or None


def _decide_role(
    *,
    email_is_admin: bool,
    claim_is_admin: bool,
    db_role: str | None,
    supabase_role: str | None,
) -> tuple[str, str]:
    dbr = str(db_role or "").strip().lower()
    if dbr == "admin":
        return ("admin", "db_profile")
    if email_is_admin:
        return ("admin", "admin_emails")
    if claim_is_admin:
        return ("admin", "jwt_claim")
    if str(supabase_role or "").strip().lower() == "admin":
        return ("admin", "supabase_profiles")
    if dbr:
        return (dbr, "db_profile")
    return ("user", "default")


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

    app_meta = claims.get("app_metadata") or {}
    if not isinstance(app_meta, dict):
        app_meta = {}
    claimed_role = str(app_meta.get("role") or "").strip().lower()
    top_level_role = str(claims.get("role") or "").strip().lower()
    claim_is_admin = claimed_role == "admin" or top_level_role == "admin"

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    db_role = str((getattr(profile, "role", None) if profile else None) or "").strip().lower() or None

    supabase_url = (settings.supabase_url or "").strip().rstrip("/")
    api_key = (settings.supabase_service_role_key or settings.supabase_anon_key or "").strip()
    bearer = (settings.supabase_service_role_key or token or "").strip()

    supabase_status = None
    supabase_role = None
    if supabase_url and api_key and bearer and user_id:
        supabase_status, supabase_role = _supabase_rest_profiles_role(
            supabase_url=supabase_url,
            user_id=user_id,
            api_key=api_key,
            bearer=bearer,
            timeout_s=8,
        )

    email_is_admin = _is_admin_email(email)
    decided_role, decided_reason = _decide_role(
        email_is_admin=email_is_admin,
        claim_is_admin=claim_is_admin,
        db_role=db_role,
        supabase_role=supabase_role,
    )

    return {
        "user_id": user_id,
        "email": email,
        "config": {
            "has_supabase_url": bool(supabase_url),
            "has_supabase_anon_key": bool(settings.supabase_anon_key),
            "has_supabase_service_role_key": bool(settings.supabase_service_role_key),
            "supabase_jwt_aud": settings.supabase_jwt_audience,
            "supabase_jwt_issuer": settings.supabase_jwt_issuer,
        },
        "jwt": {
            "role": top_level_role,
            "app_metadata_role": claimed_role,
        },
        "db_profile": {
            "exists": bool(profile),
            "role": db_role,
        },
        "supabase_profiles": {
            "attempted": bool(supabase_url and api_key and bearer and user_id),
            "status": supabase_status,
            "role": supabase_role,
            "used_service_role_key": bool(settings.supabase_service_role_key),
        },
        "decision": {
            "role": decided_role,
            "reason": decided_reason,
            "email_is_admin": email_is_admin,
            "claim_is_admin": claim_is_admin,
        },
    }


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    token = _get_bearer_token(request)

    claims = _decode_supabase_jwt(token)
    user_id = str(claims.get("sub") or "").strip()
    email = str(claims.get("email") or "").strip()
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    app_meta = claims.get("app_metadata") or {}
    if not isinstance(app_meta, dict):
        app_meta = {}
    claimed_role = str(app_meta.get("role") or "").strip().lower()
    top_level_role = str(claims.get("role") or "").strip().lower()
    claim_is_admin = claimed_role == "admin" or top_level_role == "admin"

    user_meta = claims.get("user_metadata") or {}
    if not isinstance(user_meta, dict):
        user_meta = {}
    first_name = str(user_meta.get("first_name") or "").strip()
    last_name = str(user_meta.get("last_name") or "").strip()
    company_name = str(user_meta.get("company_name") or user_meta.get("company") or "").strip()
    work_email = str(user_meta.get("work_email") or "").strip() or email

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    email_is_admin = _is_admin_email(email)
    remote_role: str | None = None
    local_role = str((profile.role if profile else "") or "").strip().lower()
    if local_role != "admin" and not (email_is_admin or claim_is_admin):
        remote_role = _fetch_profile_role_from_supabase_cached(user_id=user_id, user_token=token)
    request_ip = _get_request_ip(request)
    seen_at = _utcnow()
    if profile is None:
        if not (email_is_admin or claim_is_admin):
            detail = _validate_signup_email(email)
            if detail:
                raise HTTPException(status_code=400, detail=detail)
        initial_role, _reason = _decide_role(
            email_is_admin=email_is_admin,
            claim_is_admin=claim_is_admin,
            db_role=None,
            supabase_role=remote_role,
        )
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
        next_role, _reason = _decide_role(
            email_is_admin=email_is_admin,
            claim_is_admin=claim_is_admin,
            db_role=getattr(profile, "role", None),
            supabase_role=remote_role,
        )
        if next_role and (profile.role or "").strip().lower() != next_role:
            profile.role = next_role
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
                # Ignore presence update errors to keep API fast
                pass

    return CurrentUser(id=profile.id, email=profile.email or "", role=profile.role or "user")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
