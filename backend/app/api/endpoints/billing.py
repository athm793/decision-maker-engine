from __future__ import annotations

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user
from app.core.settings import settings
from app.models.subscription import Subscription
from app.models.credit_ledger import CreditLedger
from app.services.credits_engine import grant_business_topup, grant_monthly_credits


router = APIRouter()


class CheckoutSessionRequest(BaseModel):
    plan_key: str


class TopupRequest(BaseModel):
    credits: int


def _require_lemonsqueezy() -> None:
    if not settings.lemonsqueezy_api_key:
        raise HTTPException(status_code=500, detail="Lemon Squeezy is not configured")
    if not settings.lemonsqueezy_store_id:
        raise HTTPException(status_code=500, detail="LEMONSQUEEZY_STORE_ID is not configured")


def _lemonsqueezy_variant_for_plan(plan_key: str) -> str:
    k = (plan_key or "").strip().lower()
    if k == "trial" and settings.lemonsqueezy_variant_trial:
        return settings.lemonsqueezy_variant_trial
    if k == "entry" and settings.lemonsqueezy_variant_entry:
        return settings.lemonsqueezy_variant_entry
    if k == "pro" and settings.lemonsqueezy_variant_pro:
        return settings.lemonsqueezy_variant_pro
    if k == "business" and settings.lemonsqueezy_variant_business:
        return settings.lemonsqueezy_variant_business
    if k == "agency" and settings.lemonsqueezy_variant_agency:
        return settings.lemonsqueezy_variant_agency
    raise HTTPException(status_code=400, detail="Invalid plan_key")


def _parse_iso8601(raw: str | None) -> datetime | None:
    if not raw:
        return None
    v = str(raw).strip()
    if not v:
        return None
    try:
        if v.endswith("Z"):
            v = v[:-1] + "+00:00"
        dt = datetime.fromisoformat(v)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def _plan_key_from_variant_id(variant_id: object) -> str | None:
    vid = str(variant_id or "").strip()
    if not vid:
        return None
    if settings.lemonsqueezy_variant_trial and vid == str(settings.lemonsqueezy_variant_trial):
        return "trial"
    if settings.lemonsqueezy_variant_entry and vid == str(settings.lemonsqueezy_variant_entry):
        return "entry"
    if settings.lemonsqueezy_variant_pro and vid == str(settings.lemonsqueezy_variant_pro):
        return "pro"
    if settings.lemonsqueezy_variant_business and vid == str(settings.lemonsqueezy_variant_business):
        return "business"
    if settings.lemonsqueezy_variant_agency and vid == str(settings.lemonsqueezy_variant_agency):
        return "agency"
    return None


def _verify_lemonsqueezy_webhook_signature(raw_body: bytes, signature: str | None) -> None:
    import hashlib
    import hmac

    if not settings.lemonsqueezy_webhook_secret:
        raise HTTPException(status_code=500, detail="LEMONSQUEEZY_WEBHOOK_SECRET is not configured")
    sig = (signature or "").strip()
    if not sig:
        raise HTTPException(status_code=400, detail="Missing X-Signature")
    digest = hmac.new(
        key=str(settings.lemonsqueezy_webhook_secret).encode("utf-8"),
        msg=raw_body,
        digestmod=hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(digest, sig):
        raise HTTPException(status_code=400, detail="Invalid signature")


def _lemonsqueezy_get_subscription(subscription_id: str) -> dict:
    import requests

    _require_lemonsqueezy()
    resp = requests.get(
        f"https://api.lemonsqueezy.com/v1/subscriptions/{subscription_id}",
        headers={
            "Accept": "application/vnd.api+json",
            "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
        },
        timeout=30,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Lemon Squeezy error ({resp.status_code})")
    return resp.json() or {}


def _create_checkout_url(
    variant_id: str,
    user_id: str,
    custom: dict,
    email: str | None = None,
    quantity: int | None = None,
) -> str:
    import requests

    _require_lemonsqueezy()
    store_id = str(settings.lemonsqueezy_store_id)
    variant_id = str(variant_id)

    payload: dict = {
        "data": {
            "type": "checkouts",
            "attributes": {
                "product_options": {
                    "enabled_variants": [int(variant_id)],
                    "redirect_url": f"{settings.frontend_url}/plans?checkout=success",
                },
                "checkout_data": {
                    "custom": {"user_id": user_id, **(custom or {})},
                },
            },
            "relationships": {
                "store": {"data": {"type": "stores", "id": str(store_id)}},
                "variant": {"data": {"type": "variants", "id": str(variant_id)}},
            },
        }
    }
    if quantity and int(quantity) > 1:
        payload["data"]["attributes"]["checkout_data"]["variant_quantities"] = [
            {"variant_id": int(variant_id), "quantity": int(quantity)}
        ]
    if email:
        payload["data"]["attributes"]["checkout_data"]["email"] = email

    resp = requests.post(
        "https://api.lemonsqueezy.com/v1/checkouts",
        headers={
            "Accept": "application/vnd.api+json",
            "Content-Type": "application/vnd.api+json",
            "Authorization": f"Bearer {settings.lemonsqueezy_api_key}",
        },
        json=payload,
        timeout=30,
    )
    if resp.status_code >= 400:
        raise HTTPException(status_code=502, detail=f"Lemon Squeezy error ({resp.status_code})")
    data = resp.json()
    url = (((data.get("data") or {}).get("attributes") or {}).get("url")) or ""
    if not url:
        raise HTTPException(status_code=502, detail="Failed to create checkout")
    return str(url)


@router.post("/billing/checkout/session")
async def create_checkout_session(
    body: CheckoutSessionRequest,
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    variant_id = _lemonsqueezy_variant_for_plan(body.plan_key)
    url = _create_checkout_url(
        variant_id=variant_id,
        user_id=current_user.id,
        custom={"plan_key": (body.plan_key or "").strip().lower()},
        email=(current_user.email or None),
    )
    return {"url": url}


@router.post("/billing/topup/session")
async def create_business_topup_session(
    body: TopupRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    plan_key = (sub.plan_key if sub else "") or ""
    if plan_key.lower() not in {"business", "agency"}:
        raise HTTPException(status_code=403, detail="Top-ups are only available on Business and Agency")
    if not settings.lemonsqueezy_variant_topup:
        raise HTTPException(status_code=500, detail="LEMONSQUEEZY_VARIANT_TOPUP is not configured")

    credits = int(body.credits or 0)
    if credits <= 0:
        raise HTTPException(status_code=400, detail="credits must be positive")
    url = _create_checkout_url(
        variant_id=settings.lemonsqueezy_variant_topup,
        user_id=current_user.id,
        custom={"topup_credits": str(credits)},
        email=(current_user.email or None),
        quantity=int(credits),
    )
    return {"url": url}


@router.post("/billing/webhook")
async def lemonsqueezy_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    raw_body = await request.body()
    _verify_lemonsqueezy_webhook_signature(raw_body, request.headers.get("x-signature"))
    payload = {}
    try:
        payload = (await request.json()) or {}
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    event_name = (request.headers.get("x-event-name") or "") or str((payload.get("meta") or {}).get("event_name") or "")
    event_name = event_name.strip()
    custom_data = (payload.get("meta") or {}).get("custom_data") or {}
    user_id = str(custom_data.get("user_id") or "").strip()
    if not user_id:
        return {"received": True}

    data = payload.get("data") or {}
    data_type = str(data.get("type") or "").strip()
    data_id = str(data.get("id") or "").strip()
    attrs = data.get("attributes") or {}

    if event_name in {"subscription_created", "subscription_updated", "subscription_cancelled", "subscription_expired"}:
        try:
            subscription_id = data_id
            variant_id = (attrs.get("variant_id") if isinstance(attrs, dict) else None)
            plan_key = str(custom_data.get("plan_key") or "").strip().lower() or (_plan_key_from_variant_id(variant_id) or "")
            status = str((attrs.get("status") if isinstance(attrs, dict) else "") or "")
            current_period_end = _parse_iso8601((attrs.get("renews_at") if isinstance(attrs, dict) else None))
            sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if sub is None:
                sub = Subscription(user_id=user_id, plan_key=plan_key or None, status=status or None)
                db.add(sub)
                db.commit()
                db.refresh(sub)

            sub.plan_key = plan_key or sub.plan_key
            sub.status = status or sub.status
            sub.current_period_end = current_period_end or sub.current_period_end
            sub.provider = "lemonsqueezy"
            sub.provider_subscription_id = subscription_id or sub.provider_subscription_id
            sub.provider_customer_id = str(attrs.get("customer_id") or "") if isinstance(attrs, dict) else sub.provider_customer_id
            sub.provider_order_id = str(attrs.get("order_id") or "") if isinstance(attrs, dict) else sub.provider_order_id
            db.commit()
        except Exception:
            db.rollback()
            raise

    if event_name == "subscription_payment_success":
        try:
            invoice_id = data_id
            sub_id = str((attrs.get("subscription_id") if isinstance(attrs, dict) else "") or "").strip()
            if sub_id:
                sub_data = _lemonsqueezy_get_subscription(sub_id)
                sub_attrs = ((sub_data.get("data") or {}).get("attributes") or {})
                renews_at = _parse_iso8601(sub_attrs.get("renews_at"))
                plan_key = str(custom_data.get("plan_key") or "").strip().lower() or (_plan_key_from_variant_id(sub_attrs.get("variant_id")) or "")
                source = f"lemonsqueezy_invoice:{invoice_id}"
                already = db.query(CreditLedger).filter(CreditLedger.source == source, CreditLedger.user_id == user_id).first()
                if already is None and renews_at and plan_key:
                    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
                    if sub is None:
                        sub = Subscription(user_id=user_id, plan_key=plan_key, status="active", current_period_end=renews_at)
                        db.add(sub)
                        db.commit()
                        db.refresh(sub)
                    sub.plan_key = plan_key
                    sub.status = sub.status or "active"
                    sub.current_period_end = renews_at
                    sub.provider = "lemonsqueezy"
                    sub.provider_subscription_id = sub_id
                    sub.provider_customer_id = str(sub_attrs.get("customer_id") or "")
                    sub.provider_order_id = str(sub_attrs.get("order_id") or "")
                    db.commit()

                    grant_monthly_credits(
                        db,
                        user_id=user_id,
                        plan_key=plan_key,
                        current_period_end=renews_at,
                        source=source,
                        metadata={"lemonsqueezy_invoice_id": invoice_id, "lemonsqueezy_subscription_id": sub_id},
                    )
        except Exception:
            db.rollback()
            raise

    if event_name == "order_created":
        try:
            topup = str(custom_data.get("topup_credits") or "").strip()
            if topup:
                topup_credits = int(topup or 0)
                if topup_credits > 0:
                    sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
                    if sub and (sub.plan_key or "").lower() in {"business", "agency"}:
                        order_id = data_id
                        source = f"lemonsqueezy_order:{order_id}"
                        already = db.query(CreditLedger).filter(CreditLedger.source == source, CreditLedger.user_id == user_id).first()
                        if already is None:
                            grant_business_topup(
                                db,
                                user_id=user_id,
                                credits=topup_credits,
                                source=source,
                                metadata={"lemonsqueezy_order_id": order_id},
                            )
        except Exception:
            db.rollback()
            raise

    return {"received": True}
