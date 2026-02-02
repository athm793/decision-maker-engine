from __future__ import annotations

from datetime import timedelta, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
import csv
import io

from app.core.database import get_db
from app.core.security import CurrentUser, require_admin
from app.models.coupon import CouponAssignment, CouponCode
from app.models.credit_account import CreditAccount
from app.models.credit_ledger import CreditLedger
from app.models.decision_maker import DecisionMaker
from app.models.job import Job
from app.models.profile import Profile
from app.models.subscription import Subscription
from app.schemas.job import JobResponse
from app.services.credits_engine import recalculate_effective_balance, utcnow


router = APIRouter(dependencies=[Depends(require_admin)])


class CreditAdjustRequest(BaseModel):
    delta: int
    reason: str | None = None
    expires_days: int | None = None


class CreditSetRequest(BaseModel):
    balance: int
    reason: str | None = None
    expires_days: int | None = None


class CouponCreateRequest(BaseModel):
    code: str
    coupon_type: str = "credit_grant"
    credits: int = 0
    active: bool = True


class CouponAssignRequest(BaseModel):
    user_id: str


@router.get("/admin/stats")
async def admin_stats(db: Session = Depends(get_db)) -> dict:
    users = int(db.query(func.count(Profile.id)).scalar() or 0)
    jobs = int(db.query(func.count(Job.id)).scalar() or 0)
    results = int(db.query(func.count(DecisionMaker.id)).scalar() or 0)
    credits_spent = int(db.query(func.coalesce(func.sum(Job.credits_spent), 0)).scalar() or 0)
    llm_calls_started = int(db.query(func.coalesce(func.sum(Job.llm_calls_started), 0)).scalar() or 0)
    llm_calls_succeeded = int(db.query(func.coalesce(func.sum(Job.llm_calls_succeeded), 0)).scalar() or 0)
    return {
        "users": users,
        "jobs": jobs,
        "results": results,
        "credits_spent": credits_spent,
        "llm_calls_started": llm_calls_started,
        "llm_calls_succeeded": llm_calls_succeeded,
    }


@router.get("/admin/users")
async def admin_list_users(limit: int = 50, offset: int = 0, db: Session = Depends(get_db)) -> list[dict]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    rows = db.query(Profile).order_by(Profile.created_at.desc()).offset(offset).limit(limit).all()
    user_ids = [p.id for p in rows if p and p.id]

    subs_map: dict[str, str] = {}
    if user_ids:
        subs = db.query(Subscription).filter(Subscription.user_id.in_(user_ids)).all()
        for s in subs:
            if s and s.user_id:
                subs_map[str(s.user_id)] = str(s.plan_key or "").strip() or "free"

    cost_map: dict[str, float] = {}
    if user_ids:
        cost_rows = (
            db.query(Job.user_id, func.coalesce(func.sum(Job.total_cost_usd), 0.0))
            .filter(Job.user_id.in_(user_ids))
            .group_by(Job.user_id)
            .all()
        )
        for uid, total in cost_rows:
            if uid:
                try:
                    cost_map[str(uid)] = float(total or 0.0)
                except Exception:
                    cost_map[str(uid)] = 0.0

    out: list[dict] = []
    for p in rows:
        balance = recalculate_effective_balance(db, p.id)
        out.append(
            {
                "id": p.id,
                "email": p.email or "",
                "role": p.role or "user",
                "credits_balance": int(balance),
                "subscription_plan": subs_map.get(str(p.id), "free"),
                "user_total_cost_usd": round(cost_map.get(str(p.id), 0.0), 6),
            }
        )
    return out


@router.post("/admin/users/{user_id}/credits/adjust")
async def admin_adjust_credits(user_id: str, body: CreditAdjustRequest, db: Session = Depends(get_db)) -> dict:
    user_id = (user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    delta = int(body.delta or 0)
    if delta == 0:
        raise HTTPException(status_code=400, detail="delta must be non-zero")

    now = utcnow()
    expires_at = None
    if delta > 0:
        if body.expires_days and int(body.expires_days) > 0:
            expires_at = now + timedelta(days=int(body.expires_days))
        else:
            sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if sub and (sub.plan_key or "").lower() in {"business", "agency"}:
                expires_at = now + timedelta(days=90)
            elif sub and sub.current_period_end:
                expires_at = sub.current_period_end
            else:
                expires_at = now + timedelta(days=30)

    source = f"admin_adjust:{uuid4()}"
    entry = CreditLedger(
        user_id=user_id,
        lot_id=(str(uuid4()) if delta > 0 else None),
        event_type="admin_adjust",
        delta=delta,
        source=source,
        job_id=None,
        expires_at=expires_at,
        event_metadata={"reason": (body.reason or "").strip()},
    )
    db.add(entry)

    acct = db.query(CreditAccount).filter(CreditAccount.user_id == user_id).first()
    if acct is None:
        acct = CreditAccount(user_id=user_id, balance=0)
        db.add(acct)
        db.commit()
        db.refresh(acct)
    acct.balance = int(acct.balance or 0) + delta
    db.commit()
    balance = recalculate_effective_balance(db, user_id)
    return {"ok": True, "balance": int(balance)}


@router.post("/admin/users/{user_id}/credits/set")
async def admin_set_credits(user_id: str, body: CreditSetRequest, db: Session = Depends(get_db)) -> dict:
    user_id = (user_id or "").strip()
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user_id")

    target = int(body.balance or 0)
    if target < 0:
        raise HTTPException(status_code=400, detail="balance must be >= 0")

    acct = db.query(CreditAccount).filter(CreditAccount.user_id == user_id).first()
    if acct is None:
        acct = CreditAccount(user_id=user_id, balance=0)
        db.add(acct)
        db.commit()
        db.refresh(acct)

    current = int(acct.balance or 0)
    delta = target - current

    now = utcnow()
    expires_at = None
    if delta > 0:
        if body.expires_days and int(body.expires_days) > 0:
            expires_at = now + timedelta(days=int(body.expires_days))
        else:
            sub = db.query(Subscription).filter(Subscription.user_id == user_id).first()
            if sub and (sub.plan_key or "").lower() in {"business", "agency"}:
                expires_at = now + timedelta(days=90)
            elif sub and sub.current_period_end:
                expires_at = sub.current_period_end
            else:
                expires_at = now + timedelta(days=30)

    source = f"admin_set:{uuid4()}"
    entry = CreditLedger(
        user_id=user_id,
        lot_id=(str(uuid4()) if delta > 0 else None),
        event_type="admin_set",
        delta=delta,
        source=source,
        job_id=None,
        expires_at=expires_at,
        event_metadata={"reason": (body.reason or "").strip(), "target_balance": target},
    )
    db.add(entry)
    acct.balance = target
    db.commit()
    balance = recalculate_effective_balance(db, user_id)
    return {"ok": True, "balance": int(balance)}


@router.get("/admin/coupons")
async def admin_list_coupons(db: Session = Depends(get_db)) -> list[dict]:
    rows = db.query(CouponCode).order_by(CouponCode.created_at.desc()).all()
    out: list[dict] = []
    for c in rows:
        meta = c.coupon_metadata or {}
        out.append(
            {
                "id": c.id,
                "code": c.code,
                "coupon_type": c.coupon_type,
                "active": bool(c.active),
                "credits": int(meta.get("credits") or 0),
            }
        )
    return out


@router.post("/admin/coupons")
async def admin_create_coupon(body: CouponCreateRequest, db: Session = Depends(get_db)) -> dict:
    code = (body.code or "").strip()
    if not code:
        raise HTTPException(status_code=400, detail="Invalid code")
    if db.query(CouponCode).filter(CouponCode.code == code).first() is not None:
        raise HTTPException(status_code=400, detail="Coupon already exists")
    credits = int(body.credits or 0)
    coupon = CouponCode(
        code=code,
        coupon_type=(body.coupon_type or "credit_grant"),
        active=(1 if body.active else 0),
        coupon_metadata={"credits": credits},
    )
    db.add(coupon)
    db.commit()
    db.refresh(coupon)
    return {"id": coupon.id, "code": coupon.code}


@router.delete("/admin/coupons/{code}")
async def admin_delete_coupon(code: str, db: Session = Depends(get_db)) -> dict:
    code = (code or "").strip()
    coupon = db.query(CouponCode).filter(CouponCode.code == code).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.query(CouponAssignment).filter(CouponAssignment.coupon_code_id == coupon.id).delete()
    db.delete(coupon)
    db.commit()
    return {"ok": True}


@router.post("/admin/coupons/{code}/assign")
async def admin_assign_coupon(code: str, body: CouponAssignRequest, db: Session = Depends(get_db)) -> dict:
    code = (code or "").strip()
    user_id = (body.user_id or "").strip()
    coupon = db.query(CouponCode).filter(CouponCode.code == code).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    if db.query(Profile).filter(Profile.id == user_id).first() is None:
        raise HTTPException(status_code=404, detail="User not found")
    existing = (
        db.query(CouponAssignment)
        .filter(CouponAssignment.coupon_code_id == coupon.id, CouponAssignment.user_id == user_id)
        .first()
    )
    if existing is None:
        db.add(CouponAssignment(coupon_code_id=coupon.id, user_id=user_id))
        db.commit()
    return {"ok": True}


@router.post("/admin/coupons/{code}/unassign")
async def admin_unassign_coupon(code: str, body: CouponAssignRequest, db: Session = Depends(get_db)) -> dict:
    code = (code or "").strip()
    user_id = (body.user_id or "").strip()
    coupon = db.query(CouponCode).filter(CouponCode.code == code).first()
    if coupon is None:
        raise HTTPException(status_code=404, detail="Coupon not found")
    db.query(CouponAssignment).filter(CouponAssignment.coupon_code_id == coupon.id, CouponAssignment.user_id == user_id).delete()
    db.commit()
    return {"ok": True}


class AdminDecisionMakerResponse(BaseModel):
    id: int
    user_id: str
    job_id: int
    company_name: str
    company_type: str
    company_city: str
    company_country: str
    company_website: str
    name: str
    title: str
    platform: str
    profile_url: str
    confidence_score: str
    uploaded_company_data: str | None = None
    llm_input: str | None = None
    serper_queries: str | None = None
    llm_output: str | None = None
    llm_call_timestamp: datetime | None = None
    serper_call_timestamp: datetime | None = None

    class Config:
        from_attributes = True


class AdminDecisionMakerListResponse(BaseModel):
    items: list[AdminDecisionMakerResponse]
    total: int
    limit: int
    offset: int


@router.get("/admin/jobs", response_model=list[JobResponse])
async def admin_list_jobs(
    user_id: str | None = None,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> list[Job]:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    query = db.query(Job)
    if user_id:
        query = query.filter(Job.user_id == user_id)
    if q:
        q_like = f"%{q}%"
        query = query.filter(Job.filename.ilike(q_like))
    return query.order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit).all()


@router.get("/admin/jobs.csv")
async def admin_download_jobs_csv(
    user_id: str | None = None,
    q: str | None = None,
    limit: int = 5000,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit = max(1, min(int(limit or 5000), 5000))
    offset = max(0, int(offset or 0))
    query = db.query(Job)
    if user_id:
        query = query.filter(Job.user_id == user_id)
    if q:
        q_like = f"%{q}%"
        query = query.filter(Job.filename.ilike(q_like))
    rows = query.order_by(Job.created_at.desc(), Job.id.desc()).offset(offset).limit(limit).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Job ID",
            "Support ID",
            "User ID",
            "Filename",
            "Status",
            "LLM API Calls",
            "Serper API Calls",
            "LLM Prompt Tokens",
            "LLM Completion Tokens",
            "LLM Total Tokens",
            "LLM Cost USD",
            "Serper Cost USD",
            "Total Cost USD",
            "Cost Per Contact USD",
            "Contacts Found",
            "Credits Spent",
            "Created At",
        ]
    )
    for j in rows:
        writer.writerow(
            [
                int(j.id),
                getattr(j, "support_id", None) or "",
                getattr(j, "user_id", None) or "",
                getattr(j, "filename", None) or "",
                str(getattr(j, "status", "") or ""),
                int(getattr(j, "llm_calls_started", 0) or 0),
                int(getattr(j, "serper_calls", 0) or 0),
                int(getattr(j, "llm_prompt_tokens", 0) or 0),
                int(getattr(j, "llm_completion_tokens", 0) or 0),
                int(getattr(j, "llm_total_tokens", 0) or 0),
                float(getattr(j, "llm_cost_usd", 0.0) or 0.0),
                float(getattr(j, "serper_cost_usd", 0.0) or 0.0),
                float(getattr(j, "total_cost_usd", 0.0) or 0.0),
                float(getattr(j, "cost_per_contact_usd", 0.0) or 0.0),
                int(getattr(j, "decision_makers_found", 0) or 0),
                int(getattr(j, "credits_spent", 0) or 0),
                str(getattr(j, "created_at", "") or ""),
            ]
        )

    filename = "admin-jobs.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/admin/jobs/{job_id}", response_model=JobResponse)
async def admin_get_job(job_id: int, db: Session = Depends(get_db)) -> Job:
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/admin/jobs/{job_id}/results/paged", response_model=AdminDecisionMakerListResponse)
async def admin_get_job_results_paged(
    job_id: int,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
) -> AdminDecisionMakerListResponse:
    limit = max(1, min(int(limit or 50), 200))
    offset = max(0, int(offset or 0))
    if db.query(Job.id).filter(Job.id == job_id).first() is None:
        raise HTTPException(status_code=404, detail="Job not found")
    query = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id)
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
            )
        )
    total = int(query.count() or 0)
    rows = query.order_by(DecisionMaker.id.asc()).offset(offset).limit(limit).all()
    items = [AdminDecisionMakerResponse.model_validate(r) for r in rows]
    return AdminDecisionMakerListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/admin/jobs/{job_id}/results.csv")
async def admin_download_job_results_csv(
    job_id: int,
    q: str | None = None,
    db: Session = Depends(get_db),
):
    job = db.query(Job).filter(Job.id == job_id).first()
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")

    query = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id)
    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
                DecisionMaker.llm_input.ilike(q_like),
                DecisionMaker.serper_queries.ilike(q_like),
                DecisionMaker.llm_output.ilike(q_like),
            )
        )

    rows = query.order_by(DecisionMaker.id.asc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Job ID",
            "Job Support ID",
            "User ID",
            "Company Name",
            "Company Type",
            "Company City",
            "Company Country",
            "Company Website",
            "Contact Name",
            "Contact Job Title",
            "Platform",
            "Profile URL",
            "Confidence",
            "LLM Input",
            "Serper Queries",
            "LLM Output",
        ]
    )
    for dm in rows:
        writer.writerow(
            [
                int(job.id),
                getattr(job, "support_id", None) or "",
                getattr(dm, "user_id", None) or "",
                getattr(dm, "company_name", "") or "",
                getattr(dm, "company_type", "") or "",
                getattr(dm, "company_city", "") or "",
                getattr(dm, "company_country", "") or "",
                getattr(dm, "company_website", "") or "",
                getattr(dm, "name", "") or "",
                getattr(dm, "title", "") or "",
                getattr(dm, "platform", "") or "",
                getattr(dm, "profile_url", "") or "",
                getattr(dm, "confidence_score", "") or "",
                getattr(dm, "llm_input", None) or "",
                getattr(dm, "serper_queries", None) or "",
                getattr(dm, "llm_output", None) or "",
            ]
        )

    filename = f"admin-job-{job_id}-results.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )
