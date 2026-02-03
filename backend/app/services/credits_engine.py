from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.credit_account import CreditAccount
from app.models.credit_ledger import CreditLedger
from app.models.subscription import Subscription


PLAN_MONTHLY_CREDITS: dict[str, int] = {
    "trial": 20,
    "entry": 7250,
    "pro": 26000,
    "business": 80000,
    "agency": 249000,
}


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def get_or_create_credit_account(db: Session, user_id: str) -> CreditAccount:
    acct = db.query(CreditAccount).filter(CreditAccount.user_id == user_id).first()
    if acct is None:
        acct = CreditAccount(user_id=user_id, balance=0)
        db.add(acct)
        db.commit()
        db.refresh(acct)
    return acct


def get_subscription(db: Session, user_id: str) -> Subscription | None:
    return db.query(Subscription).filter(Subscription.user_id == user_id).first()


def recalculate_effective_balance(db: Session, user_id: str, now: datetime | None = None) -> int:
    now = now or utcnow()
    total = (
        db.query(func.coalesce(func.sum(CreditLedger.delta), 0))
        .filter(CreditLedger.user_id == user_id)
        .filter((CreditLedger.expires_at.is_(None)) | (CreditLedger.expires_at > now))
        .scalar()
    )
    acct = get_or_create_credit_account(db, user_id)
    acct.balance = int(total or 0)
    db.commit()
    return acct.balance


def grant_monthly_credits(
    db: Session,
    user_id: str,
    plan_key: str,
    current_period_end: datetime,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> CreditLedger:
    credits = int(PLAN_MONTHLY_CREDITS.get(plan_key, 0))
    lot_id = str(uuid4())
    entry = CreditLedger(
        user_id=user_id,
        lot_id=lot_id,
        event_type="grant_monthly",
        delta=credits,
        source=source,
        job_id=None,
        expires_at=current_period_end,
        event_metadata=(metadata or None),
    )
    db.add(entry)
    acct = get_or_create_credit_account(db, user_id)
    acct.balance = int(acct.balance or 0) + credits
    db.commit()
    db.refresh(entry)
    return entry


def grant_business_topup(
    db: Session,
    user_id: str,
    credits: int,
    source: str,
    metadata: dict[str, Any] | None = None,
) -> CreditLedger:
    lot_id = str(uuid4())
    expires_at = utcnow() + timedelta(days=90)
    entry = CreditLedger(
        user_id=user_id,
        lot_id=lot_id,
        event_type="topup",
        delta=int(credits),
        source=source,
        job_id=None,
        expires_at=expires_at,
        event_metadata=(metadata or None),
    )
    db.add(entry)
    acct = get_or_create_credit_account(db, user_id)
    acct.balance = int(acct.balance or 0) + int(credits)
    db.commit()
    db.refresh(entry)
    return entry


def spend_credits_for_job(
    db: Session,
    user_id: str,
    amount: int,
    job_id: int,
    source: str = "job",
    now: datetime | None = None,
) -> None:
    now = now or utcnow()
    amount = int(amount)
    if amount <= 0:
        return

    acct = get_or_create_credit_account(db, user_id)
    effective = recalculate_effective_balance(db, user_id, now=now)
    if effective < amount:
        raise ValueError("insufficient_credits")

    lots = (
        db.query(CreditLedger)
        .filter(CreditLedger.user_id == user_id, CreditLedger.delta > 0)
        .filter((CreditLedger.expires_at.is_(None)) | (CreditLedger.expires_at > now))
        .order_by(CreditLedger.expires_at.asc(), CreditLedger.created_at.asc(), CreditLedger.id.asc())
        .all()
    )

    remaining = amount
    for lot in lots:
        if remaining <= 0:
            break
        lot_id = lot.lot_id
        if not lot_id:
            continue
        lot_total = (
            db.query(func.coalesce(func.sum(CreditLedger.delta), 0))
            .filter(CreditLedger.user_id == user_id, CreditLedger.lot_id == lot_id)
            .scalar()
        )
        lot_remaining = int(lot_total or 0)
        if lot_remaining <= 0:
            continue
        use = min(lot_remaining, remaining)
        spend = CreditLedger(
            user_id=user_id,
            lot_id=lot_id,
            event_type="spend",
            delta=-use,
            source=source,
            job_id=int(job_id),
            expires_at=lot.expires_at,
            event_metadata=None,
        )
        db.add(spend)
        remaining -= use

    if remaining != 0:
        raise ValueError("insufficient_credits")

    acct.balance = int(acct.balance or 0) - amount
    db.commit()
