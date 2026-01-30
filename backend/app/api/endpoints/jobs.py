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
import logging
import sys

router = APIRouter()
logger = logging.getLogger(__name__)

def _is_url_like(raw: object) -> bool:
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

def _text(raw: object) -> str:
    return str(raw or "").strip()

def _non_empty(raw: object, default: str) -> str:
    v = _text(raw)
    return v if v else default

def _split_location_to_city_country(raw: object) -> tuple[str, str]:
    v = _text(raw)
    if not v:
        return ("", "")
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if len(parts) >= 2:
        city = parts[0]
        country = parts[-1]
        if len(country) == 2 and country.isupper():
            country = ""
        if re.search(r"\d", country):
            country = ""
        return (city, country)
    return ("", "")


class CreditResponse(BaseModel):
    balance: int

class DecisionMakerResponse(BaseModel):
    id: int
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
    reasoning: str

def _dm_to_response(dm: DecisionMaker) -> DecisionMakerResponse:
    return DecisionMakerResponse(
        id=int(dm.id),
        company_name=_non_empty(getattr(dm, "company_name", ""), "Unknown"),
        company_type=_non_empty(getattr(dm, "company_type", ""), "Unknown"),
        company_city=_non_empty(getattr(dm, "company_city", ""), "Unknown"),
        company_country=_non_empty(getattr(dm, "company_country", ""), "Unknown"),
        company_website=_non_empty(getattr(dm, "company_website", ""), "N/A"),
        name=_non_empty(getattr(dm, "name", ""), "Unknown"),
        title=_non_empty(getattr(dm, "title", ""), "Unknown"),
        platform=_non_empty(getattr(dm, "platform", ""), "Unknown"),
        profile_url=_text(getattr(dm, "profile_url", "")),
        confidence_score=_non_empty(getattr(dm, "confidence_score", ""), "UNKNOWN"),
        reasoning=_non_empty(getattr(dm, "reasoning", ""), "N/A"),
    )


class DecisionMakerListResponse(BaseModel):
    items: List[DecisionMakerResponse]
    total: int
    limit: int
    offset: int

async def _process_job_task(job_id: int):
    logger.info("process_job_task.start job_id=%s", job_id)
    # Need to create a new DB session for the background task
    db = SessionLocal()
    scraper = ScraperService()
    
    try:
        job = db.query(Job).filter(Job.id == job_id).first()
        if not job:
            logger.warning("process_job_task.job_not_found job_id=%s", job_id)
            return

        if job.status == JobStatus.CANCELLED:
            logger.info("process_job_task.cancelled_before_start job_id=%s", job_id)
            return
            
        job.status = JobStatus.PROCESSING
        db.commit()
        logger.info(
            "process_job_task.processing job_id=%s total_companies=%s",
            job_id,
            job.total_companies,
        )
        
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
        city_col = mappings.get("city", "")
        country_col = mappings.get("country", "")
        
        logger.info(
            "process_job_task.options job_id=%s selected_platforms=%s max_total=%s max_per_company=%s credits_per_contact=%s",
            job_id,
            selected_platforms,
            max_contacts_total,
            max_contacts_per_company,
            platforms_multiplier,
        )

        for idx, company in enumerate(companies or []):
            # Check if job was cancelled
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                logger.info("process_job_task.cancelled_during_run job_id=%s processed_companies=%s", job_id, job.processed_companies)
                break

            if max_contacts_total and found_total >= max_contacts_total:
                logger.info("process_job_task.hit_overall_limit job_id=%s found_total=%s", job_id, found_total)
                break
                
            company_name = company.get(company_col) if company_col else ""
            location = company.get(location_col) if location_col else ""
            google_maps_url = company.get(gmaps_col) if gmaps_col else None
            website = company.get(website_col) if website_col else None
            company_type = company.get(company_type_col) if company_type_col else None
            company_city = company.get(city_col) if city_col else None
            company_country = company.get(country_col) if country_col else None

            if not website and _is_url_like(company_name):
                website = company_name
                company_name = ""

            if not company_city or not company_country:
                inferred_city, inferred_country = _split_location_to_city_country(location)
                if not company_city and inferred_city:
                    company_city = inferred_city
                if not company_country and inferred_country:
                    company_country = inferred_country

            logger.info(
                "process_job_task.company_start job_id=%s idx=%s raw_company_name=%s location=%s",
                job_id,
                idx,
                (str(company_name)[:200] if company_name is not None else ""),
                (str(location)[:200] if location is not None else ""),
            )

            location_hint = _text(location) or ", ".join([p for p in [_text(company_city), _text(company_country)] if p])
            enriched = await scraper.enrich_company(
                company_name=company_name,
                location=location_hint,
                google_maps_url=google_maps_url,
                website=website,
            )
            company_name = (enriched.get("company_name") or company_name or "").strip()
            company_type = (company_type or enriched.get("company_type") or "").strip() or None
            website = (website or enriched.get("company_website") or "").strip() or None
            company_city = (company_city or enriched.get("company_city") or "").strip() or None
            company_country = (company_country or enriched.get("company_country") or "").strip() or None

            logger.info(
                "process_job_task.company_enriched job_id=%s idx=%s company_name=%s website=%s company_type=%s city=%s country=%s",
                job_id,
                idx,
                (company_name[:200] if company_name else ""),
                ((website or "")[:200]),
                ((company_type or "")[:200]),
                ((company_city or "")[:200]),
                ((company_country or "")[:200]),
            )
            
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

            logger.info(
                "process_job_task.company_results job_id=%s idx=%s results=%s remaining_total=%s remaining_per_company=%s",
                job_id,
                idx,
                len(results or []),
                remaining_total,
                remaining_per_company,
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
                    logger.info(
                        "process_job_task.credits_exhausted job_id=%s balance=%s needed=%s",
                        job_id,
                        credit_state.balance,
                        platforms_multiplier,
                    )
                    break

                credit_state.balance -= platforms_multiplier

                company_name_out = _non_empty(company_name, "Unknown")
                company_type_out = _non_empty(company_type, "Unknown")
                company_city_out = _non_empty(company_city, "Unknown")
                company_country_out = _non_empty(company_country, "Unknown")
                website_out = _non_empty(website, "N/A")
                name_out = _non_empty(res.get("name"), "Unknown")
                title_out = _non_empty(res.get("title"), "Unknown")
                platform_out = _non_empty(res.get("platform", "LinkedIn"), "Unknown")

                dm = DecisionMaker(
                    job_id=job.id,
                    company_name=company_name_out,
                    company_type=company_type_out,
                    company_city=company_city_out,
                    company_country=company_country_out,
                    company_website=website_out,
                    name=name_out,
                    title=title_out,
                    platform=platform_out,
                    profile_url=_text(res.get("profile_url")),
                    confidence_score=res.get("confidence"),
                    reasoning=res.get("reasoning"),
                )
                db.add(dm)
                job.decision_makers_found += 1
                job.credits_spent = (job.credits_spent or 0) + platforms_multiplier
                found_total += 1
            
            job.processed_companies += 1
            db.commit()
            logger.info(
                "process_job_task.company_done job_id=%s idx=%s processed_companies=%s decision_makers_found=%s credits_spent=%s",
                job_id,
                idx,
                job.processed_companies,
                job.decision_makers_found,
                job.credits_spent,
            )
            
        if job.status != JobStatus.CANCELLED:
            job.status = JobStatus.COMPLETED
        
        db.commit()
        logger.info(
            "process_job_task.done job_id=%s status=%s processed_companies=%s decision_makers_found=%s credits_spent=%s stop_reason=%s",
            job_id,
            job.status,
            job.processed_companies,
            job.decision_makers_found,
            job.credits_spent,
            job.stop_reason,
        )
        
    except Exception as e:
        logger.exception("process_job_task.error job_id=%s", job_id)
        if job:
            job.status = JobStatus.FAILED
            db.commit()
    finally:
        await scraper.stop()
        db.close()

def _run_job_task_in_dedicated_loop(job_id: int) -> None:
    old_policy = None
    if sys.platform.startswith("win"):
        try:
            old_policy = asyncio.get_event_loop_policy()
        except Exception:
            old_policy = None
        try:
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        except Exception:
            pass

    loop = asyncio.new_event_loop()
    try:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_process_job_task(job_id))
        loop.run_until_complete(loop.shutdown_asyncgens())
    finally:
        try:
            asyncio.set_event_loop(None)
        except Exception:
            pass
        loop.close()
        if old_policy is not None:
            try:
                asyncio.set_event_loop_policy(old_policy)
            except Exception:
                pass

async def process_job_task(job_id: int):
    if sys.platform.startswith("win"):
        await asyncio.to_thread(_run_job_task_in_dedicated_loop, job_id)
        return
    await _process_job_task(job_id)

@router.post("/jobs", response_model=JobResponse)
async def create_job(job_in: JobCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    logger.info(
        "create_job.request filename=%s rows=%s selected_platforms=%s max_total=%s max_per_company=%s",
        job_in.filename,
        len(job_in.file_content or []),
        job_in.selected_platforms,
        job_in.max_contacts_total,
        job_in.max_contacts_per_company,
    )

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
    logger.info("create_job.created job_id=%s status=%s", db_job.id, db_job.status)
    
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
    return [_dm_to_response(dm) for dm in results]


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
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
                DecisionMaker.reasoning.ilike(q_like),
            )
        )

    total = query.count()
    rows = query.order_by(DecisionMaker.id.desc()).offset(offset).limit(limit).all()
    items = [_dm_to_response(dm) for dm in rows]
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
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
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
            "Company City",
            "Company Country",
            "Company Website",
            "Contact Name",
            "Contact Job Title",
            "Platform",
            "Platform Source URL",
            "Confidence",
            "Reasoning",
        ]
    )
    for dm in rows:
        writer.writerow(
            [
                _non_empty(getattr(dm, "company_name", ""), "Unknown"),
                _non_empty(getattr(dm, "company_type", ""), "Unknown"),
                _non_empty(getattr(dm, "company_city", ""), "Unknown"),
                _non_empty(getattr(dm, "company_country", ""), "Unknown"),
                _non_empty(getattr(dm, "company_website", ""), "N/A"),
                _non_empty(getattr(dm, "name", ""), "Unknown"),
                _non_empty(getattr(dm, "title", ""), "Unknown"),
                _non_empty(getattr(dm, "platform", ""), "Unknown"),
                _text(getattr(dm, "profile_url", "")),
                _non_empty(getattr(dm, "confidence_score", ""), "UNKNOWN"),
                _non_empty(getattr(dm, "reasoning", ""), "N/A"),
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
