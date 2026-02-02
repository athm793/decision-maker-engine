from __future__ import annotations

from dataclasses import dataclass
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


def get_current_user(request: Request, db: Session = Depends(get_db)) -> CurrentUser:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = auth.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing bearer token")

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

    profile = db.query(Profile).filter(Profile.id == user_id).first()
    if profile is None:
        profile = Profile(
            id=user_id,
            email=email,
            work_email=work_email,
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            role="user",
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    else:
        changed = False
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
        if changed:
            db.commit()

    return CurrentUser(id=profile.id, email=profile.email or "", role=profile.role or "user")


def require_admin(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    if (user.role or "").lower() != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
