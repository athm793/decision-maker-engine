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

def _looks_like_postal_code(raw: object) -> bool:
    v = _text(raw)
    if not v:
        return False
    if re.match(r"^\d{4,6}(-\d{4})?$", v):
        return True
    if re.search(r"\b\d{4,6}\b", v) and len(v) <= 12 and not re.search(r"[a-zA-Z]", v):
        return True
    return False

def _looks_like_address(raw: object) -> bool:
    v = _text(raw)
    if len(v) < 6:
        return False
    if re.search(r"\b(po box|p\.?o\.?\s*box)\b", v, flags=re.IGNORECASE):
        return True
    if re.search(r"\b\d{5}(-\d{4})?\b", v) and "," in v:
        return True
    if re.search(r"\b\d{1,6}\s+\S+", v) and re.search(
        r"\b(st|street|ave|avenue|rd|road|blvd|boulevard|dr|drive|ln|lane|way|hwy|highway|suite|ste|apt|unit|pl|place|ct|court|cir|circle)\b",
        v,
        flags=re.IGNORECASE,
    ):
        return True
    return False

def _clean_company_type(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    if _is_url_like(v):
        return ""
    if _looks_like_address(v):
        return ""
    if _looks_like_postal_code(v):
        return ""
    return v

def _clean_company_name(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    if _is_url_like(v):
        return ""
    return v

def _clean_city(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    if _looks_like_postal_code(v):
        return ""
    if re.search(r"\d", v):
        return ""
    return v

def _clean_country(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    if _looks_like_postal_code(v):
        return ""
    if len(v) == 2 and v.isupper():
        return ""
    if re.search(r"\d", v):
        return ""
    return v

def _parse_uploaded_company_data(raw: object) -> dict:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        s = raw.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}

def _is_placeholder_value(raw: object) -> bool:
    v = _text(raw)
    if not v:
        return True
    v_lower = v.lower()
    return v_lower in {"unknown", "n/a", "na", "none", "null", "-", "—"}

def _infer_company_name_from_google_maps_url(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    m = re.search(r"/place/([^/]+)", v)
    if not m:
        return ""
    name = m.group(1)
    try:
        from urllib.parse import unquote

        name = unquote(name)
    except Exception:
        pass
    name = name.replace("+", " ").strip()
    name = re.sub(r"\s+", " ", name)
    return name

_US_STATE_NAMES = {
    "alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming",
}
_US_STATE_ABBRS = {
    "AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY",
}

def _infer_country_from_location_hint(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    parts = [p.strip() for p in v.split(",") if p.strip()]
    if len(parts) == 1:
        token = parts[0]
        if token.upper() in _US_STATE_ABBRS:
            return "United States"
        if token.lower() in _US_STATE_NAMES:
            return "United States"
        return ""
    last = parts[-1]
    if last.upper() in _US_STATE_ABBRS or last.lower() in _US_STATE_NAMES:
        return "United States"
    return ""

_TLD_COUNTRY = {
    "us": "United States",
    "uk": "United Kingdom",
    "gb": "United Kingdom",
    "ca": "Canada",
    "au": "Australia",
    "nz": "New Zealand",
    "ie": "Ireland",
    "de": "Germany",
    "fr": "France",
    "es": "Spain",
    "it": "Italy",
    "nl": "Netherlands",
    "se": "Sweden",
    "no": "Norway",
    "dk": "Denmark",
    "fi": "Finland",
    "ch": "Switzerland",
    "at": "Austria",
    "be": "Belgium",
    "pt": "Portugal",
    "br": "Brazil",
    "mx": "Mexico",
    "in": "India",
    "jp": "Japan",
    "sg": "Singapore",
}

def _infer_country_from_website(raw: object) -> str:
    v = _text(raw)
    if not v:
        return ""
    host = v
    if re.match(r"^https?://", host, flags=re.IGNORECASE):
        try:
            from urllib.parse import urlparse

            host = urlparse(host).netloc
        except Exception:
            host = v
    host = host.lower()
    host = host[4:] if host.startswith("www.") else host
    parts = [p for p in host.split(".") if p]
    if len(parts) < 2:
        return ""
    tld = parts[-1]
    return _TLD_COUNTRY.get(tld, "")

def _resolve_company_fields(dm: DecisionMaker, mappings: dict) -> dict[str, str]:
    payload = _parse_uploaded_company_data(getattr(dm, "uploaded_company_data", None))

    def uploaded(col_key: str) -> str:
        col = (mappings or {}).get(col_key)
        if not col:
            return ""
        return _text(payload.get(col, ""))

    raw_company_name = uploaded("company_name")
    raw_location = uploaded("location")
    raw_gmaps = uploaded("google_maps_url")
    raw_website = uploaded("website")
    raw_type = uploaded("industry")
    raw_city = uploaded("city")
    raw_country = uploaded("country")

    name = _text(getattr(dm, "company_name", ""))
    if _is_placeholder_value(name):
        name = ""
    if not name:
        name = _clean_company_name(raw_company_name) or ""
    if not name and raw_gmaps:
        name = _clean_company_name(_infer_company_name_from_google_maps_url(raw_gmaps)) or ""
    if not name and raw_website:
        try:
            name = _clean_company_name(ScraperService()._guess_company_name_from_website(raw_website)) or ""
        except Exception:
            name = ""

    site = _text(getattr(dm, "company_website", ""))
    if _is_placeholder_value(site):
        site = ""
    if not site:
        site = _text(raw_website)

    ctype = _text(getattr(dm, "company_type", ""))
    if _is_placeholder_value(ctype):
        ctype = ""
    if not ctype:
        ctype = _clean_company_type(raw_type) or ""

    city = _text(getattr(dm, "company_city", ""))
    if _is_placeholder_value(city):
        city = ""
    if not city:
        city = _clean_city(raw_city) or ""

    country = _text(getattr(dm, "company_country", ""))
    if _is_placeholder_value(country):
        country = ""
    if not country:
        country = _clean_country(raw_country) or ""
    if not country:
        inferred = _infer_country_from_location_hint(raw_location) or _infer_country_from_location_hint(city)
        country = _clean_country(inferred) or ""
    if not country and site:
        country = _clean_country(_infer_country_from_website(site)) or ""
    if not country:
        _, inferred_country = _split_location_to_city_country(raw_location)
        country = _clean_country(inferred_country) or ""

    if not city and raw_location:
        inferred_city, _ = _split_location_to_city_country(raw_location)
        city = _clean_city(inferred_city) or ""

    return {
        "company_name": name,
        "company_type": ctype,
        "company_city": city,
        "company_country": country,
        "company_website": site,
    }

def _resolve_company_fields_for_save(
    *,
    company_name: str | None,
    company_type: str | None,
    company_city: str | None,
    company_country: str | None,
    website: str | None,
    location_hint: str,
    company_row: dict,
    mappings: dict,
    scraper: ScraperService,
) -> dict[str, str]:
    def uploaded(col_key: str) -> str:
        col = (mappings or {}).get(col_key)
        if not col:
            return ""
        return _text(company_row.get(col, ""))

    raw_company_name = uploaded("company_name")
    raw_location = uploaded("location")
    raw_gmaps = uploaded("google_maps_url")
    raw_website = uploaded("website")
    raw_type = uploaded("industry")
    raw_city = uploaded("city")
    raw_country = uploaded("country")

    name = _clean_company_name(company_name) or ""
    if not name:
        name = _clean_company_name(raw_company_name) or ""
    if not name and raw_gmaps:
        name = _clean_company_name(_infer_company_name_from_google_maps_url(raw_gmaps)) or ""
    if not name and (website or raw_website):
        name = _clean_company_name(scraper._guess_company_name_from_website(website or raw_website)) or ""

    site = _text(website) or _text(raw_website)

    ctype = _clean_company_type(company_type) or ""
    if not ctype:
        ctype = _clean_company_type(raw_type) or ""

    city = _clean_city(company_city) or ""
    if not city:
        city = _clean_city(raw_city) or ""

    country = _clean_country(company_country) or ""
    if not country:
        country = _clean_country(raw_country) or ""
    if not country:
        inferred = _infer_country_from_location_hint(raw_location) or _infer_country_from_location_hint(location_hint) or _infer_country_from_location_hint(city)
        country = _clean_country(inferred) or ""
    if not country and site:
        country = _clean_country(_infer_country_from_website(site)) or ""
    if not country:
        _, inferred_country = _split_location_to_city_country(raw_location or location_hint)
        country = _clean_country(inferred_country) or ""

    if not city:
        inferred_city, _ = _split_location_to_city_country(raw_location or location_hint)
        city = _clean_city(inferred_city) or ""

    return {
        "company_name": name,
        "company_type": ctype,
        "company_city": city,
        "company_country": country,
        "company_website": site,
    }


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

def _dm_to_response(dm: DecisionMaker, mappings: dict | None = None) -> DecisionMakerResponse:
    resolved = _resolve_company_fields(dm, mappings or {})
    return DecisionMakerResponse(
        id=int(dm.id),
        company_name=resolved.get("company_name", ""),
        company_type=resolved.get("company_type", ""),
        company_city=resolved.get("company_city", ""),
        company_country=resolved.get("company_country", ""),
        company_website=resolved.get("company_website", ""),
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
        
        mappings = job.column_mappings or {}
        companies = job.companies_data or []

        selected_platforms = job.selected_platforms or []
        max_contacts_total = job.max_contacts_total or 0
        max_contacts_per_company = job.max_contacts_per_company or 0
        platforms_multiplier = max(1, len(selected_platforms))
        job_options = getattr(job, "options", None) or {}
        deep_search = bool(job_options.get("deep_search"))
        credits_per_contact = platforms_multiplier + (1 if deep_search else 0)
        found_total = 0
        
        company_col = mappings.get("company_name")
        location_col = mappings.get("location", "")
        gmaps_col = mappings.get("google_maps_url", "")
        website_col = mappings.get("website", "")
        company_type_col = mappings.get("industry", "")
        city_col = mappings.get("city", "")
        country_col = mappings.get("country", "")
        
        logger.info(
            "process_job_task.options job_id=%s selected_platforms=%s max_total=%s max_per_company=%s credits_per_contact=%s deep_search=%s",
            job_id,
            selected_platforms,
            max_contacts_total,
            max_contacts_per_company,
            credits_per_contact,
            deep_search,
        )

        concurrency = int(os.getenv("JOB_CONCURRENCY", "3") or "3")
        concurrency = max(1, min(concurrency, 8))
        search_limit = 3
        enrichment_search_limit = 5

        async def _scrape_one(idx: int, company: dict, remaining_total: int | None) -> dict:
            company_name = _text(company.get(company_col) if company_col else "")
            location = _text(company.get(location_col) if location_col else "")
            google_maps_url = company.get(gmaps_col) if gmaps_col else None
            website = _text(company.get(website_col) if website_col else "")
            company_type = _clean_company_type(company.get(company_type_col) if company_type_col else None) or None
            company_city = _clean_city(company.get(city_col) if city_col else None) or None
            company_country = _clean_country(company.get(country_col) if country_col else None) or None

            if _is_url_like(company_name):
                if not website:
                    website = company_name
                company_name = ""

            if not company_city or not company_country:
                inferred_city, inferred_country = _split_location_to_city_country(location)
                if not company_city and inferred_city:
                    company_city = _clean_city(inferred_city) or None
                if not company_country and inferred_country:
                    company_country = _clean_country(inferred_country) or None

            location_hint = _text(location) or ", ".join([p for p in [_text(company_city), _text(company_country)] if p])

            needs_enrichment = bool((not company_name) or (not company_country) or (not company_type) or (not website))
            if needs_enrichment:
                enriched = await scraper.enrich_company(
                    company_name=company_name,
                    location=location_hint,
                    google_maps_url=google_maps_url,
                    website=website,
                    search_limit=enrichment_search_limit,
                )
                enriched_name = _clean_company_name(enriched.get("company_name"))
                company_name = enriched_name or _clean_company_name(company_name)
                if not company_name and website:
                    company_name = _clean_company_name(scraper._guess_company_name_from_website(website))

                enriched_type = _clean_company_type(enriched.get("company_type"))
                company_type = company_type or (enriched_type or None)
                if company_type:
                    company_type = _clean_company_type(company_type) or None

                website = (_text(website) or _text(enriched.get("company_website"))) or None
                company_city = _clean_city(company_city or enriched.get("company_city")) or None
                company_country = _clean_country(company_country or enriched.get("company_country")) or None

            resolved_company = _resolve_company_fields_for_save(
                company_name=company_name,
                company_type=company_type,
                company_city=company_city,
                company_country=company_country,
                website=website,
                location_hint=location_hint,
                company_row=company,
                mappings=mappings,
                scraper=scraper,
            )

            is_usable_company = bool(resolved_company.get("company_name")) and bool(
                resolved_company.get("company_country") or resolved_company.get("company_city")
            )
            if not is_usable_company:
                return {
                    "idx": idx,
                    "company": company,
                    "location_hint": location_hint,
                    "resolved_company": resolved_company,
                    "results": [],
                }

            remaining_per_company = max_contacts_per_company if max_contacts_per_company else None
            results = await scraper.process_company(
                resolved_company.get("company_name") or "",
                location_hint,
                google_maps_url=google_maps_url,
                website=resolved_company.get("company_website") or None,
                platforms=selected_platforms,
                max_people=remaining_per_company,
                remaining_total=remaining_total,
                search_limit=search_limit,
                deep_search=deep_search,
            )

            return {
                "idx": idx,
                "company": company,
                "location_hint": location_hint,
                "resolved_company": resolved_company,
                "results": results or [],
            }

        for batch_start in range(0, len(companies), concurrency):
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                logger.info("process_job_task.cancelled_during_run job_id=%s processed_companies=%s", job_id, job.processed_companies)
                break
            if max_contacts_total and found_total >= max_contacts_total:
                logger.info("process_job_task.hit_overall_limit job_id=%s found_total=%s", job_id, found_total)
                break

            batch = [(i, companies[i]) for i in range(batch_start, min(batch_start + concurrency, len(companies)))]
            remaining_total = (max_contacts_total - found_total) if max_contacts_total else None
            tasks = [_scrape_one(i, c, remaining_total) for i, c in batch if isinstance(c, dict)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for out in batch_results:
                idx = None
                company = None
                if isinstance(out, Exception):
                    logger.exception("process_job_task.company_error job_id=%s", job_id)
                    continue

                idx = int(out.get("idx", -1))
                company = out.get("company") or {}
                resolved_company = out.get("resolved_company") or {}
                results = out.get("results") or []

                logger.info(
                    "process_job_task.company_results job_id=%s idx=%s results=%s",
                    job_id,
                    idx,
                    len(results),
                )

                is_usable_company = bool(resolved_company.get("company_name")) and bool(
                    resolved_company.get("company_country") or resolved_company.get("company_city")
                )
                for res in results:
                    if max_contacts_total and found_total >= max_contacts_total:
                        break
                    if not is_usable_company:
                        break

                    credit_state = db.query(CreditState).filter(CreditState.id == 1).first()
                    if credit_state is None:
                        credit_state = CreditState(id=1, balance=int(os.getenv("CREDITS_INITIAL_BALANCE", "0") or "0"))
                        db.add(credit_state)
                        db.commit()

                    if credit_state.balance < credits_per_contact:
                        job.stop_reason = "credits_exhausted"
                        job.status = JobStatus.COMPLETED
                        db.commit()
                        logger.info(
                            "process_job_task.credits_exhausted job_id=%s balance=%s needed=%s",
                            job_id,
                            credit_state.balance,
                            credits_per_contact,
                        )
                        break

                    credit_state.balance -= credits_per_contact

                    name_out = _non_empty(res.get("name"), "Unknown")
                    title_out = _non_empty(res.get("title"), "Unknown")
                    platform_out = _non_empty(res.get("platform", "LinkedIn"), "Unknown")

                    dm = DecisionMaker(
                        job_id=job.id,
                        company_name=_text(resolved_company.get("company_name", "")),
                        company_type=_text(resolved_company.get("company_type", "")),
                        company_city=_text(resolved_company.get("company_city", "")),
                        company_country=_text(resolved_company.get("company_country", "")),
                        company_website=_text(resolved_company.get("company_website", "")),
                        name=name_out,
                        title=title_out,
                        platform=platform_out,
                        profile_url=_text(res.get("profile_url")),
                        confidence_score=res.get("confidence"),
                        reasoning=res.get("reasoning"),
                        uploaded_company_data=json.dumps(company, ensure_ascii=False),
                    )
                    db.add(dm)
                    job.decision_makers_found += 1
                    job.credits_spent = (job.credits_spent or 0) + credits_per_contact
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

    required_keys = ["company_name", "industry", "location", "website"]
    missing_mappings = [k for k in required_keys if not _text((job_in.mappings or {}).get(k, ""))]
    if missing_mappings:
        raise HTTPException(status_code=400, detail=f"Missing required mappings: {', '.join(missing_mappings)}")

    selected = [p for p in (job_in.selected_platforms or []) if isinstance(p, str) and p.strip()]
    if not selected:
        raise HTTPException(status_code=400, detail="Select at least one platform")

    required_cols = [(k, job_in.mappings.get(k)) for k in required_keys]
    rows = job_in.file_content or []
    blank_rows = 0
    for row in rows:
        if not isinstance(row, dict):
            blank_rows += 1
            continue
        for _, col in required_cols:
            if not _text(row.get(col, "")):
                blank_rows += 1
                break
    if blank_rows:
        raise HTTPException(status_code=400, detail=f"Some rows have blank values in required columns (rows affected: {blank_rows})")

    # Create Job record
    db_job = Job(
        filename=job_in.filename,
        column_mappings=json.loads(json.dumps(job_in.mappings)),
        companies_data=json.loads(json.dumps(job_in.file_content)),
        total_companies=len(job_in.file_content),
        status=JobStatus.QUEUED,
        selected_platforms=json.loads(json.dumps(selected)),
        max_contacts_total=job_in.max_contacts_total,
        max_contacts_per_company=job_in.max_contacts_per_company,
        credits_spent=0,
        stop_reason=None,
        options={"deep_search": bool(job_in.deep_search)},
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
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    mappings = job.column_mappings or {}
    results = db.query(DecisionMaker).filter(DecisionMaker.job_id == job_id).all()
    return [_dm_to_response(dm, mappings) for dm in results]


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
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    mappings = job.column_mappings or {}
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
    items = [_dm_to_response(dm, mappings) for dm in rows]
    return DecisionMakerListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/results.csv")
async def download_job_results_csv(job_id: int, q: str | None = None, db: Session = Depends(get_db)):
    job = db.query(Job).filter(Job.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    mappings = job.column_mappings or {}
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

    company_cols: list[str] = []
    seen_company_cols: set[str] = set()
    if job and isinstance(job.companies_data, list) and len(job.companies_data) > 0 and isinstance(job.companies_data[0], dict):
        for row in job.companies_data:
            if not isinstance(row, dict):
                continue
            for k in row.keys():
                if k in seen_company_cols:
                    continue
                seen_company_cols.add(k)
                company_cols.append(str(k))

    for dm in rows:
        payload = _parse_uploaded_company_data(getattr(dm, "uploaded_company_data", None))
        for k in payload.keys():
            ks = str(k)
            if ks in seen_company_cols:
                continue
            seen_company_cols.add(ks)
            company_cols.append(ks)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Company Name",
            "Company Type",
            "Company Location",
            "Company Website",
            "Contact Name",
            "Contact Job Title",
            "Platform",
            "Platform Source URL",
            "Confidence",
            "Reasoning",
        ]
        + [f"Uploaded - {c}" for c in company_cols]
    )
    for dm in rows:
        payload = _parse_uploaded_company_data(getattr(dm, "uploaded_company_data", None))
        resolved = _resolve_company_fields(dm, mappings)
        company_location = ", ".join(
            [p for p in [_text(resolved.get("company_city", "")), _text(resolved.get("company_country", ""))] if p]
        )
        writer.writerow(
            [
                _text(resolved.get("company_name", "")),
                _text(resolved.get("company_type", "")),
                company_location,
                _text(resolved.get("company_website", "")),
                _non_empty(getattr(dm, "name", ""), "Unknown"),
                _non_empty(getattr(dm, "title", ""), "Unknown"),
                _non_empty(getattr(dm, "platform", ""), "Unknown"),
                _text(getattr(dm, "profile_url", "")),
                _non_empty(getattr(dm, "confidence_score", ""), "UNKNOWN"),
                _non_empty(getattr(dm, "reasoning", ""), "N/A"),
            ]
            + [_text(payload.get(c, "")) for c in company_cols]
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
