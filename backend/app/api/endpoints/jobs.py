from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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

router = APIRouter()

class DecisionMakerResponse(BaseModel):
    id: int
    company_name: str
    name: str | None
    title: str | None
    platform: str | None
    profile_url: str | None
    confidence_score: str | None
    reasoning: str | None
    
    class Config:
        from_attributes = True

async def process_job_task(job_id: int):
    # Need to create a new DB session for the background task
    db = SessionLocal()
    scraper = ScraperService()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            return
            
        job.status = JobStatus.PROCESSING
        db.commit()
        
        await scraper.start()
        
        mappings = job.column_mappings
        companies = job.companies_data
        
        company_col = mappings.get("company_name")
        location_col = mappings.get("location", "")
        
        for company in companies:
            # Check if job was cancelled
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                break
                
            company_name = company.get(company_col)
            if not company_name:
                continue
                
            location = company.get(location_col) if location_col else ""
            
            # Scrape
            results = await scraper.process_company(company_name, location)
            
            # Save Results
            for res in results:
                dm = DecisionMaker(
                    job_id=job.id,
                    company_name=company_name,
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

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

@router.get("/jobs/{job_id}/results", response_model=List[DecisionMakerResponse])
async def get_job_results(job_id: int, db: Session = Depends(get_db)):
    results = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id).all()
    return results
