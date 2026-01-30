from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.models.job import Job, JobStatus
from app.models.decision_maker import DecisionMaker
from app.models.credit_state import CreditState
from app.schemas.job import JobCreate, JobResponse
from app.services.scraper import ScraperService
import json
import asyncio
from typing import List
from pydantic import BaseModel
import csv
import io
import os
import re

router = APIRouter()


class CreditResponse(BaseModel):
    balance: int

class DecisionMakerResponse(BaseModel):
    id: int
    company_name: str
    company_type: str | None = None
    company_website: str | None = None
    name: str | None
    title: str | None
    platform: str | None
    profile_url: str | None
    confidence_score: str | None
    reasoning: str | None
    
    class Config:
        from_attributes = True


class DecisionMakerListResponse(BaseModel):
    items: List[DecisionMakerResponse]
    total: int
    limit: int
    offset: int

async def process_job_task(job_id: int):
    # Need to create a new DB session for the background task
    db = SessionLocal()
    scraper = ScraperService()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return

        if job.status == JobStatus.CANCELLED:
            return
            
        job.status = JobStatus.PROCESSING
        db.commit()
        
        await scraper.start()
        
        mappings = job.column_mappings
        companies = job.companies_data

        selected_platforms = job.selected_platforms or []
        max_contacts_total = job.max_contacts_total or 0
        max_contacts_per_company = job.max_contacts_per_company or 0
        platforms_multiplier = max(1, len(selected_platforms))
        found_total = 0
        
        company_col = mappings.get("company_name")
        location_col = mappings.get("location", "")
        gmaps_col = mappings.get("google_maps_url", "")
        website_col = mappings.get("website", "")
        company_type_col = mappings.get("industry", "")
        
        for company in companies:
            # Check if job was cancelled
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                break

            if max_contacts_total and found_total >= max_contacts_total:
                break
                
            company_name = company.get(company_col) if company_col else ""
            location = company.get(location_col) if location_col else ""
            google_maps_url = company.get(gmaps_col) if gmaps_col else None
            website = company.get(website_col) if website_col else None
            company_type = company.get(company_type_col) if company_type_col else None

            enriched = await scraper.enrich_company(
                company_name=company_name,
                location=location,
                google_maps_url=google_maps_url,
                website=website,
            )
            company_name = (enriched.get("company_name") or company_name or "").strip()
            company_type = (company_type or enriched.get("company_type") or "").strip() or None
            website = (website or enriched.get("company_website") or "").strip() or None
            
            # Scrape
            remaining_total = (max_contacts_total - found_total) if max_contacts_total else None
            remaining_per_company = max_contacts_per_company if max_contacts_per_company else None
            results = await scraper.process_company(
                company_name,
                location,
                google_maps_url=google_maps_url,
                website=website,
                platforms=selected_platforms,
                max_people=remaining_per_company,
                remaining_total=remaining_total,
            )
            
            # Save Results
            for res in results:
                if max_contacts_total and found_total >= max_contacts_total:
                    break

                credit_state = db.query(CreditState).filter(CreditState.id == 1).first()
                if credit_state is None:
                    credit_state = CreditState(id=1, balance=int(os.getenv("CREDITS_INITIAL_BALANCE", "0") or "0"))
                    db.add(credit_state)
                    db.commit()

                if credit_state.balance < platforms_multiplier:
                    job.stop_reason = "credits_exhausted"
                    job.status = JobStatus.COMPLETED
                    db.commit()
                    break

                credit_state.balance -= platforms_multiplier

                dm = DecisionMaker(
                    job_id=job.id,
                    company_name=company_name,
                    company_type=company_type,
                    company_website=website,
                    name=res.get("name"),
                    title=res.get("title"),
                    platform=res.get("platform", "LinkedIn"),
                    profile_url=res.get("profile_url"),
                    confidence_score=res.get("confidence"),
                    reasoning=res.get("reasoning")
                )
                db.add(dm)
                job.decision_makers_found += 1
                job.credits_spent = (job.credits_spent or 0) + platforms_multiplier
                found_total += 1
            
            job.processed_companies += 1
            db.commit()
            
        if job.status != JobStatus.CANCELLED:
            job.status = JobStatus.COMPLETED
        
        db.commit()
        
    except Exception as e:
        print(f"Error processing job {job_id}: {e}")
        if job:
            job.status = JobStatus.FAILED
            db.commit()
    finally:
        await scraper.stop()
        db.close()

@router.post("/jobs", response_model=JobResponse)
async def create_job(job_in: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    def is_url_like(raw: object) -> bool:
        v = str(raw or "").strip()
        if not v:
            return False
        if re.match(r"^https?://", v, flags=re.IGNORECASE):
            return True
        if re.match(r"^www\.", v, flags=re.IGNORECASE):
            return True
        if re.search(r"[a-z0-9-]+\.[a-z]{2,}", v, flags=re.IGNORECASE) and not re.search(r"\s", v):
            return True
        return False

    company_col = (job_in.mappings or {}).get("company_name")
    website_col = (job_in.mappings or {}).get("website")
    if company_col and any(bad in company_col.lower() for bad in ["url", "website", "domain", "http", "www", "link"]):
        raise HTTPException(status_code=400, detail="Company Name must be a name column, not a website/url column")
    if company_col and website_col and company_col == website_col:
        raise HTTPException(status_code=400, detail="Company Name and Company Website must be different columns")

    sample_rows = (job_in.file_content or [])[:3]
    if company_col and sample_rows:
        company_values = [str(r.get(company_col, "") or "").strip() for r in sample_rows]
        company_values = [v for v in company_values if v]
        if company_values:
            url_count = sum(1 for v in company_values if is_url_like(v))
            if (url_count / len(company_values)) > 0.1:
                raise HTTPException(status_code=400, detail="Company Name column contains website/url-like values. Map the website column to Company Website and keep Company Name as the business name only.")

    if website_col and sample_rows:
        website_values = [str(r.get(website_col, "") or "").strip() for r in sample_rows]
        website_values = [v for v in website_values if v]
        if website_values:
            url_count = sum(1 for v in website_values if is_url_like(v))
            if (url_count / len(website_values)) < 0.5:
                raise HTTPException(status_code=400, detail="Company Website column must contain website URLs/domains only.")

    # Create Job record
    db_job = Job(
        filename=job_in.filename,
        column_mappings=json.loads(json.dumps(job_in.mappings)),
        companies_data=json.loads(json.dumps(job_in.file_content)),
        total_companies=len(job_in.file_content),
        status=JobStatus.QUEUED,
        selected_platforms=json.loads(json.dumps(job_in.selected_platforms)),
        max_contacts_total=job_in.max_contacts_total,
        max_contacts_per_company=job_in.max_contacts_per_company,
        credits_spent=0,
        stop_reason=None,
    )
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # Trigger background task
    background_tasks.add_task(process_job_task, db_job.id)
    
    return db_job


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(limit: int = 25, offset: int = 0, db: Session = Depends(get_db)):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    jobs = (
        db.query(Job)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jobs

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
        return job

    job.status = JobStatus.CANCELLED
    db.commit()
    db.refresh(job)
    return job

@router.get("/jobs/{job_id}/results", response_model=List[DecisionMakerResponse])
async def get_job_results(job_id: int, db: Session = Depends(get_db)):
    results = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id).all()
    return results


@router.get("/jobs/{job_id}/results/paged", response_model=DecisionMakerListResponse)
async def get_job_results_paged(
    job_id: int,
    q: str | None = None,
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    query = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id)

    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
                DecisionMaker.reasoning.ilike(q_like),
            )
        )

    total = query.count()
    items = query.order_by(DecisionMaker.id.desc()).offset(offset).limit(limit).all()
    return DecisionMakerListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/results.csv")
async def download_job_results_csv(job_id: int, q: str | None = None, db: Session = Depends(get_db)):
    query = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id)

    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
                DecisionMaker.reasoning.ilike(q_like),
            )
        )

    rows = query.order_by(DecisionMaker.id.desc()).all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Company Name",
            "Company Type",
            "Company Website",
            "Name",
            "Title",
            "Platform",
            "Platform Source URL",
            "Confidence",
            "Reasoning",
        ]
    )
    for dm in rows:
        writer.writerow(
            [
                dm.company_name or "",
                getattr(dm, "company_type", "") or "",
                getattr(dm, "company_website", "") or "",
                dm.name or "",
                dm.title or "",
                dm.platform or "",
                dm.profile_url or "",
                dm.confidence_score or "",
                dm.reasoning or "",
            ]
        )

    filename = f"job-{job_id}-results.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/credits", response_model=CreditResponse)
async def get_credits(db: Session = Depends(get_db)):
    credit_state = db.query(CreditState).filter(CreditState.id == 1).first()
    return CreditResponse(balance=int(credit_state.balance if credit_state else 0))
