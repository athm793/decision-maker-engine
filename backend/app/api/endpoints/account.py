from __future__ import annotations

from datetime import timedelta
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import CurrentUser, get_current_user, diagnose_current_user
from app.models.coupon import CouponAssignment, CouponCode
from app.models.credit_account import CreditAccount
from app.models.credit_ledger import CreditLedger
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.services.credits_engine import recalculate_effective_balance, utcnow


router = APIRouter(dependencies=[Depends(get_current_user)])


class SubscriptionOut(BaseModel):
    plan_key: str | None = None
    status: str | None = None
    current_period_end: str | None = None


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    work_email: str | None = None
    first_name: str | None = None
    last_name: str | None = None
    company_name: str | None = None
    credits_balance: int
    subscription: SubscriptionOut | None = None


class RedeemCouponRequest(BaseModel):
    code: str


@router.get("/me", response_model=MeResponse)
async def me(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    try:
        balance = recalculate_effective_balance(db, current_user.id)
    except Exception:
        db.rollback()
        balance = 0
    try:
        sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    except Exception:
        db.rollback()
        sub = None
    try:
        profile = db.query(Profile).filter(Profile.id == current_user.id).first()
    except Exception:
        db.rollback()
        profile = None
    sub_out = None
    if sub is not None:
        sub_out = SubscriptionOut(
            plan_key=sub.plan_key,
            status=sub.status,
            current_period_end=(sub.current_period_end.isoformat() if sub.current_period_end else None),
        )
    return MeResponse(
        id=current_user.id,
        email=current_user.email,
        role=current_user.role,
        work_email=(getattr(profile, "work_email", None) if profile else None),
        first_name=(getattr(profile, "first_name", None) if profile else None),
        last_name=(getattr(profile, "last_name", None) if profile else None),
        company_name=(getattr(profile, "company_name", None) if profile else None),
        credits_balance=int(balance),
        subscription=sub_out,
    )


@router.get("/me/diagnostics")
async def me_diagnostics(request: Request, db: Session = Depends(get_db)) -> dict:
    return diagnose_current_user(request, db)


@router.post("/coupons/redeem")
async def redeem_coupon(
    body: RedeemCouponRequest,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
) -> dict:
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Invalid code")

    coupon = db.query(CouponCode).filter(CouponCode.code == code, CouponCode.active == 1).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")

    assignment = (
        db.query(CouponAssignment)
        .filter(CouponAssignment.coupon_code_id == coupon.id, CouponAssignment.user_id == current_user.id)
        .first()
    )
    if assignment is None:
        raise HTTPException(status_code=403, detail="Coupon is not assigned to this account")
    if assignment.redeemed_at is not None:
        raise HTTPException(status_code=400, detail="Coupon already redeemed")

    if (coupon.coupon_type or "").lower() != "credit_grant":
        raise HTTPException(status_code=400, detail="Unsupported coupon type")

    meta = coupon.coupon_metadata or {}
    credits = int(meta.get("credits") or 0)
    if credits <= 0:
        raise HTTPException(status_code=400, detail="Invalid coupon metadata")

    now = utcnow()
    sub = db.query(Subscription).filter(Subscription.user_id == current_user.id).first()
    expires_at = None
    if sub and (sub.plan_key or "").lower() == "business":
        expires_at = now + timedelta(days=90)
    elif sub and sub.current_period_end:
        expires_at = sub.current_period_end
    else:
        expires_at = now + timedelta(days=30)

    lot_id = str(uuid4())
    source = f"coupon:{code}"
    existing = db.query(CreditLedger).filter(CreditLedger.source == source, CreditLedger.user_id == current_user.id).first()
    if existing is not None:
        raise HTTPException(status_code=400, detail="Coupon already applied")

    entry = CreditLedger(
        user_id=current_user.id,
        lot_id=lot_id,
        event_type="coupon",
        delta=credits,
        source=source,
        job_id=None,
        expires_at=expires_at,
        event_metadata={"coupon_code": code},
    )
    db.add(entry)
    acct = db.query(CreditAccount).filter(CreditAccount.user_id == current_user.id).first()
    if acct is None:
        acct = CreditAccount(user_id=current_user.id, balance=0)
        db.add(acct)
        db.commit()
        db.refresh(acct)
    acct.balance = int(acct.balance or 0) + credits

    assignment.redeemed_at = now
    db.commit()
    return {"ok": True, "credits_granted": credits}
