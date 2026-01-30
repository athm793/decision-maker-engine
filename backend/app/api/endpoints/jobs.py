from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy import or_
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.models.job import Job, JobStatus
from app.models.decision_maker import DecisionMaker
from app.schemas.job import JobCreate, JobResponse
from app.services.scraper import ScraperService
import json
import asyncio
from typing import List
from pydantic import BaseModel
import csv
import io

router = APIRouter()

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
                
            company_name = company.get(company_col)
            if not company_name:
                continue
                
            location = company.get(location_col) if location_col else ""
            google_maps_url = company.get(gmaps_col) if gmaps_col else None
            website = company.get(website_col) if website_col else None
            company_type = company.get(company_type_col) if company_type_col else None
            
            # Scrape
            results = await scraper.process_company(company_name, location, google_maps_url=google_maps_url, website=website)
            
            # Save Results
            for res in results:
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
    # Create Job record
    db_job = Job(
        filename=job_in.filename,
        column_mappings=json.loads(json.dumps(job_in.mappings)),
        companies_data=json.loads(json.dumps(job_in.file_content)),
        total_companies=len(job_in.file_content),
        status=JobStatus.QUEUED
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
