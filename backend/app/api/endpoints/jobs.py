from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session
from app.core.database import get_db, SessionLocal
from app.core.settings import settings
from app.core.security import CurrentUser, get_current_user, require_admin
from app.models.job import Job, JobStatus
from app.models.decision_maker import DecisionMaker
from app.schemas.job import JobCreate, JobResponse
from app.services.costs import compute_job_cost_fields
from app.services.decision_maker_rules import decision_maker_query_keywords, is_decision_maker_title, title_matches_keywords
from app.services.credits_engine import recalculate_effective_balance, spend_credits_for_job
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
from datetime import datetime
from uuid import uuid4

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)

def _parse_iso_datetime(raw: object) -> datetime | None:
    s = str(raw or "").strip()
    if not s:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None

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

    address = _text(getattr(dm, "company_address", ""))
    if _is_placeholder_value(address):
        address = ""
    if not address:
        address = _text(raw_location)

    return {
        "company_name": name,
        "company_type": ctype,
        "company_city": city,
        "company_country": country,
        "company_website": site,
        "company_address": address,
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
    company_address: str
    gmaps_rating: float | None = None
    gmaps_reviews: int | None = None
    name: str
    title: str
    platform: str
    profile_url: str
    emails_found: str
    confidence_score: str

def _dm_to_response(dm: DecisionMaker, mappings: dict | None = None) -> DecisionMakerResponse:
    resolved = _resolve_company_fields(dm, mappings or {})
    return DecisionMakerResponse(
        id=int(dm.id),
        company_name=resolved.get("company_name", ""),
        company_type=resolved.get("company_type", ""),
        company_city=resolved.get("company_city", ""),
        company_country=resolved.get("company_country", ""),
        company_website=resolved.get("company_website", ""),
        company_address=resolved.get("company_address", ""),
        gmaps_rating=(float(getattr(dm, "gmaps_rating")) if getattr(dm, "gmaps_rating", None) is not None else None),
        gmaps_reviews=(int(getattr(dm, "gmaps_reviews")) if getattr(dm, "gmaps_reviews", None) is not None else None),
        name=_non_empty(getattr(dm, "name", ""), "Unknown"),
        title=_non_empty(getattr(dm, "title", ""), "Unknown"),
        platform=_non_empty(getattr(dm, "platform", ""), "Unknown"),
        profile_url=_text(getattr(dm, "profile_url", "")),
        emails_found=_text(getattr(dm, "emails_found", "")),
        confidence_score=_non_empty(getattr(dm, "confidence_score", ""), "UNKNOWN"),
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
        platforms_multiplier = 1
        job_options = getattr(job, "options", None) or {}
        deep_search = bool(job_options.get("deep_search"))
        platforms_for_search: list[str] = []
        job_titles = job_options.get("job_titles")
        job_titles = [str(x).strip() for x in (job_titles or []) if str(x).strip()] if isinstance(job_titles, list) else []
        query_keywords = job_titles[:5] if job_titles else decision_maker_query_keywords()[:5]
        credits_per_company = 1
        if not job.user_id:
            job.status = JobStatus.FAILED
            job.stop_reason = "missing_user"
            db.commit()
            return
        
        company_col = mappings.get("company_name")
        location_col = mappings.get("location", "")
        gmaps_col = mappings.get("google_maps_url", "")
        website_col = mappings.get("website", "")
        company_type_col = mappings.get("industry", "")
        city_col = mappings.get("city", "")
        country_col = mappings.get("country", "")
        
        logger.info(
            "process_job_task.options job_id=%s selected_platforms=%s credits_per_company=%s deep_search=%s",
            job_id,
            selected_platforms,
            credits_per_company,
            deep_search,
        )

        concurrency = int(os.getenv("JOB_CONCURRENCY", "25") or "25")
        concurrency = max(1, min(concurrency, 500))
        search_limit = 3
        max_people_per_company = int(os.getenv("MAX_PEOPLE_PER_COMPANY", "25") or "25")
        max_people_per_company = max(1, min(max_people_per_company, 100))

        async def _scrape_one(idx: int, company: dict) -> dict:
            llm_started = 0
            llm_succeeded = 0
            serper_calls = 0
            llm_prompt_tokens = 0
            llm_completion_tokens = 0
            llm_total_tokens = 0

            def add_llm_usage(trace: dict) -> None:
                nonlocal llm_prompt_tokens, llm_completion_tokens, llm_total_tokens
                usage = trace.get("llm_usage") if isinstance(trace.get("llm_usage"), dict) else {}
                for phase in ["plan", "final"]:
                    u = usage.get(phase) if isinstance(usage.get(phase), dict) else {}
                    llm_prompt_tokens += int(u.get("prompt_tokens") or 0)
                    llm_completion_tokens += int(u.get("completion_tokens") or 0)
                    llm_total_tokens += int(u.get("total_tokens") or 0)
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
            if not company_name and website:
                company_name = _clean_company_name(scraper._guess_company_name_from_website(website))

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

            is_usable_company = bool(resolved_company.get("company_name"))
            if not is_usable_company:
                return {
                    "idx": idx,
                    "company": company,
                    "location_hint": location_hint,
                    "resolved_company": resolved_company,
                    "results": [],
                    "llm_started": llm_started,
                    "llm_succeeded": llm_succeeded,
                }

            results, trace_people = await scraper.process_company_with_trace(
                company_name=resolved_company.get("company_name") or "",
                location=location_hint,
                google_maps_url=google_maps_url,
                website=resolved_company.get("company_website") or None,
                company_type=resolved_company.get("company_type") or None,
                platforms=platforms_for_search,
                max_people=max_people_per_company,
                search_limit=search_limit,
                deep_search=deep_search,
                query_keywords=query_keywords,
            )
            if isinstance(trace_people, dict):
                llm_started += int(trace_people.get("llm_calls") or 0)
                llm_succeeded += int(trace_people.get("llm_calls") or 0)
                serper_calls += int(trace_people.get("serper_calls") or 0)
                add_llm_usage(trace_people)
            if isinstance(results, list):
                for r in results:
                    if not isinstance(r, dict):
                        continue
                    if isinstance(trace_people, dict):
                        r["_trace_people"] = trace_people
                    website_found = _text(r.get("company_website", ""))
                    if website_found and not _text(resolved_company.get("company_website", "")):
                        resolved_company["company_website"] = website_found
                    ctype_found = _text(r.get("company_type", ""))
                    if ctype_found and not _text(resolved_company.get("company_type", "")):
                        resolved_company["company_type"] = ctype_found
                    addr_found = _text(r.get("company_address", ""))
                    if addr_found and not _text(resolved_company.get("company_address", "")):
                        resolved_company["company_address"] = addr_found
                    if "gmaps_rating" in r and "gmaps_rating" not in resolved_company:
                        resolved_company["gmaps_rating"] = r.get("gmaps_rating")
                    if "gmaps_reviews" in r and "gmaps_reviews" not in resolved_company:
                        resolved_company["gmaps_reviews"] = r.get("gmaps_reviews")

            return {
                "idx": idx,
                "company": company,
                "location_hint": location_hint,
                "resolved_company": resolved_company,
                "results": results or [],
                "llm_started": llm_started,
                "llm_succeeded": llm_succeeded,
                "serper_calls": serper_calls,
                "llm_prompt_tokens": llm_prompt_tokens,
                "llm_completion_tokens": llm_completion_tokens,
                "llm_total_tokens": llm_total_tokens,
            }

        abort_job = False
        for batch_start in range(0, len(companies), concurrency):
            db.refresh(job)
            if job.status == JobStatus.CANCELLED:
                logger.info("process_job_task.cancelled_during_run job_id=%s processed_companies=%s", job_id, job.processed_companies)
                break

            batch = [(i, companies[i]) for i in range(batch_start, min(batch_start + concurrency, len(companies)))]
            tasks = [_scrape_one(i, c) for i, c in batch if isinstance(c, dict)]
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)

            for out in batch_results:
                idx = None
                company = None
                if isinstance(out, Exception):
                    logger.exception("process_job_task.company_error job_id=%s", job_id)
                    job.status = JobStatus.FAILED
                    job.stop_reason = "company_error"
                    db.commit()
                    abort_job = True
                    break

                idx = int(out.get("idx", -1))
                company = out.get("company") or {}
                resolved_company = out.get("resolved_company") or {}
                results = out.get("results") or []
                job.llm_calls_started = int(job.llm_calls_started or 0) + int(out.get("llm_started") or 0)
                job.llm_calls_succeeded = int(job.llm_calls_succeeded or 0) + int(out.get("llm_succeeded") or 0)
                if hasattr(job, "serper_calls"):
                    job.serper_calls = int(getattr(job, "serper_calls", 0) or 0) + int(out.get("serper_calls") or 0)
                if hasattr(job, "llm_prompt_tokens"):
                    job.llm_prompt_tokens = int(getattr(job, "llm_prompt_tokens", 0) or 0) + int(out.get("llm_prompt_tokens") or 0)
                if hasattr(job, "llm_completion_tokens"):
                    job.llm_completion_tokens = int(getattr(job, "llm_completion_tokens", 0) or 0) + int(
                        out.get("llm_completion_tokens") or 0
                    )
                if hasattr(job, "llm_total_tokens"):
                    job.llm_total_tokens = int(getattr(job, "llm_total_tokens", 0) or 0) + int(out.get("llm_total_tokens") or 0)
                if hasattr(job, "llm_cost_usd") and hasattr(job, "serper_cost_usd") and hasattr(job, "total_cost_usd"):
                    cf = compute_job_cost_fields(
                        llm_prompt_tokens=int(getattr(job, "llm_prompt_tokens", 0) or 0),
                        llm_completion_tokens=int(getattr(job, "llm_completion_tokens", 0) or 0),
                        serper_calls=int(getattr(job, "serper_calls", 0) or 0),
                        contacts_found=int(job.decision_makers_found or 0),
                        input_cost_per_m=float(settings.llm_input_cost_per_m),
                        output_cost_per_m=float(settings.llm_output_cost_per_m),
                        serper_cost_per_1k=float(settings.serper_cost_per_1k),
                    )
                    job.llm_cost_usd = float(cf.get("llm_cost_usd") or 0.0)
                    job.serper_cost_usd = float(cf.get("serper_cost_usd") or 0.0)
                    job.total_cost_usd = float(cf.get("total_cost_usd") or 0.0)
                    if hasattr(job, "cost_per_contact_usd"):
                        job.cost_per_contact_usd = float(cf.get("cost_per_contact_usd") or 0.0)

                logger.info(
                    "process_job_task.company_results job_id=%s idx=%s results=%s",
                    job_id,
                    idx,
                    len(results),
                )

                is_usable_company = bool(resolved_company.get("company_name")) and bool(
                    resolved_company.get("company_country")
                    or resolved_company.get("company_city")
                    or resolved_company.get("company_website")
                )
                company_name_out = _text(resolved_company.get("company_name", ""))
                company_type_out = _text(resolved_company.get("company_type", ""))
                company_city_out = _text(resolved_company.get("company_city", ""))
                company_country_out = _text(resolved_company.get("company_country", ""))
                company_website_out = _text(resolved_company.get("company_website", ""))
                company_address_out = _text(resolved_company.get("company_address", "")) or _text(company.get(location_col) if location_col else "")
                gmaps_rating_out = None
                gmaps_reviews_out = None
                try:
                    if resolved_company.get("gmaps_rating") is not None:
                        gmaps_rating_out = float(resolved_company.get("gmaps_rating"))
                except Exception:
                    gmaps_rating_out = None
                try:
                    if resolved_company.get("gmaps_reviews") is not None:
                        gmaps_reviews_out = int(float(resolved_company.get("gmaps_reviews")))
                except Exception:
                    gmaps_reviews_out = None
                valid_results: list[dict] = []
                for res in results:
                    if not is_usable_company:
                        break
                    title_candidate = _text(res.get("title"))
                    ok_title = False
                    if query_keywords:
                        ok_title = title_matches_keywords(title_candidate, query_keywords)
                    else:
                        ok_title, _ = is_decision_maker_title(title_candidate)
                    if not ok_title:
                        continue
                    name_candidate = _text(res.get("name"))
                    if not name_candidate or name_candidate.strip().lower() in {"unknown", "n/a", "na", "-"}:
                        continue
                    
                    # Filter out common hallucinations
                    if name_candidate.strip().lower() in {"john doe", "jane doe"}:
                        continue
                    
                    prof_url = _text(res.get("profile_url")).lower()
                    if "linkedin.com/in/johndoe" in prof_url or "linkedin.com/in/janedoe" in prof_url:
                        continue

                    if isinstance(res, dict):
                        valid_results.append(res)

                if is_usable_company:
                    try:
                        spend_credits_for_job(db, user_id=job.user_id, amount=credits_per_company, job_id=job.id, commit=False)
                    except Exception:
                        job.stop_reason = "credits_exhausted"
                        job.status = JobStatus.COMPLETED
                        db.commit()
                        logger.info("process_job_task.credits_exhausted job_id=%s needed=%s", job_id, credits_per_company)
                        abort_job = True
                        break
                    job.credits_spent = (job.credits_spent or 0) + credits_per_company

                for res in valid_results:
                    title_candidate = _text(res.get("title"))
                    name_candidate = _text(res.get("name"))
                    name_out = _non_empty(name_candidate, "Unknown")
                    title_out = _non_empty(title_candidate, "Unknown")
                    platform_out = _non_empty(res.get("platform", "Web"), "Web")
                    emails_in = res.get("emails_found")
                    emails_list: list[str] = []
                    if isinstance(emails_in, list):
                        for x in emails_in:
                            xs = _text(x)
                            if xs:
                                emails_list.append(xs)
                    elif isinstance(emails_in, str):
                        emails_list = [x.strip() for x in emails_in.split(",") if x.strip()]
                    seen_emails: set[str] = set()
                    emails_norm: list[str] = []
                    for e in emails_list:
                        k = e.strip().lower()
                        if not k or k in seen_emails:
                            continue
                        seen_emails.add(k)
                        emails_norm.append(k)
                    emails_out = ", ".join(emails_norm[:25])
                    trace_company = resolved_company.get("_trace_company") if isinstance(resolved_company, dict) else None
                    trace_company = trace_company if isinstance(trace_company, dict) else None
                    trace_people = res.get("_trace_people") if isinstance(res, dict) else None
                    trace_people = trace_people if isinstance(trace_people, dict) else None
                    llm_input = None
                    serper_queries = None
                    llm_output = None
                    if trace_company or trace_people:
                        llm_input = json.dumps(
                            {
                                "company": (trace_company.get("llm_input") if trace_company else None),
                                "people": (trace_people.get("llm_input") if trace_people else None),
                            },
                            ensure_ascii=False,
                        )
                        serper_queries = json.dumps(
                            {
                                "company": (trace_company.get("serper_queries") if trace_company else None),
                                "people": (trace_people.get("serper_queries") if trace_people else None),
                            },
                            ensure_ascii=False,
                        )
                        llm_output = json.dumps(
                            {
                                "company": (trace_company.get("llm_output") if trace_company else None),
                                "people": (trace_people.get("llm_output") if trace_people else None),
                            },
                            ensure_ascii=False,
                        )

                    llm_call_ts = _parse_iso_datetime(
                        _text((trace_people.get("llm_call_timestamp") if trace_people else None))
                        or _text((trace_company.get("llm_call_timestamp") if trace_company else None))
                    )
                    serper_call_ts = _parse_iso_datetime(
                        _text((trace_people.get("serper_call_timestamp") if trace_people else None))
                        or _text((trace_company.get("serper_call_timestamp") if trace_company else None))
                    )

                    dm = DecisionMaker(
                        user_id=job.user_id,
                        job_id=job.id,
                        company_name=company_name_out,
                        company_type=company_type_out,
                        company_city=company_city_out,
                        company_country=company_country_out,
                        company_website=company_website_out,
                        company_address=company_address_out,
                        gmaps_rating=gmaps_rating_out,
                        gmaps_reviews=gmaps_reviews_out,
                        name=name_out,
                        title=title_out,
                        platform=platform_out,
                        profile_url=_text(res.get("profile_url")),
                        emails_found=emails_out,
                        confidence_score=str(res.get("confidence") or "").strip().upper() or "UNKNOWN",
                        uploaded_company_data=json.dumps(company, ensure_ascii=False),
                        llm_input=llm_input,
                        serper_queries=serper_queries,
                        llm_output=llm_output,
                        llm_call_timestamp=llm_call_ts,
                        serper_call_timestamp=serper_call_ts,
                    )
                    db.add(dm)
                    job.decision_makers_found += 1

                job.processed_companies += 1
                logger.info(
                    "process_job_task.company_done job_id=%s idx=%s processed_companies=%s decision_makers_found=%s credits_spent=%s",
                    job_id,
                    idx,
                    job.processed_companies,
                    job.decision_makers_found,
                    job.credits_spent,
                )
            
            db.commit()

            if abort_job:
                break
            
        if job.status == JobStatus.PROCESSING:
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
async def create_job(
    job_in: JobCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    logger.info(
        "create_job.request filename=%s rows=%s selected_platforms=%s",
        job_in.filename,
        len(job_in.file_content or []),
        job_in.selected_platforms,
    )

    mappings = job_in.mappings or {}
    company_col = _text(mappings.get("company_name", ""))
    if not company_col:
        raise HTTPException(status_code=400, detail="Missing required mapping: Company Name")
    if not _text(mappings.get("location", "")):
        raise HTTPException(status_code=400, detail="Missing required mapping: Address")
    website_col = _text(mappings.get("website", ""))

    raw_titles = job_in.job_titles or []
    titles = [str(x).strip() for x in raw_titles if str(x).strip()]
    deduped_titles: list[str] = []
    seen_titles: set[str] = set()
    for t in titles:
        k = t.lower()
        if k in seen_titles:
            continue
        seen_titles.add(k)
        deduped_titles.append(t)
    deduped_titles = deduped_titles[:5]
    if not deduped_titles:
        raise HTTPException(status_code=400, detail="Please provide 1-5 job titles")

    selected = ["linkedin"]
    if "linkedin" not in selected:
        selected = ["linkedin", *selected]

    rows = job_in.file_content or []
    kept_rows: list[dict] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        name_ok = bool(company_col and _text(row.get(company_col, "")))
        website_ok = bool(website_col and _text(row.get(website_col, "")))
        if name_ok or website_ok:
            kept_rows.append(row)
    if not kept_rows:
        raise HTTPException(
            status_code=400,
            detail="All rows were blank for both Company Name and Company Website. Fill at least one of those fields, or map Company Website.",
        )

    # Create Job record
    db_job = Job(
        user_id=current_user.id,
        support_id=uuid4().hex[:12].upper(),
        filename=job_in.filename,
        column_mappings=json.loads(json.dumps(mappings)),
        companies_data=json.loads(json.dumps(kept_rows)),
        total_companies=len(kept_rows),
        status=JobStatus.QUEUED,
        selected_platforms=json.loads(json.dumps(selected)),
        max_contacts_total=0,
        max_contacts_per_company=0,
        credits_spent=0,
        stop_reason=None,
        options={
            "deep_search": bool(job_in.deep_search),
            "job_titles": deduped_titles,
        },
    )
    
    db.add(db_job)
    db.commit()
    db.refresh(db_job)
    
    # Trigger background task
    background_tasks.add_task(process_job_task, db_job.id)
    logger.info("create_job.created job_id=%s status=%s", db_job.id, db_job.status)
    
    return db_job


@router.get("/jobs", response_model=List[JobResponse])
async def list_jobs(
    limit: int = 25,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    limit = max(1, min(limit, 100))
    offset = max(0, offset)

    jobs = (
        db.query(Job)
        .filter(Job.user_id == current_user.id)
        .order_by(Job.created_at.desc(), Job.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jobs

@router.get("/jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
        return job

    job.status = JobStatus.CANCELLED
    db.commit()
    db.refresh(job)
    return job

@router.get("/jobs/{job_id}/results", response_model=List[DecisionMakerResponse])
async def get_job_results(job_id: int, db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deep_search = bool((getattr(job, "options", None) or {}).get("deep_search"))
    mappings = job.column_mappings or {}
    results = (
        db.query(DecisionMaker)
        .filter(
            DecisionMaker.job_id == job_id,
            DecisionMaker.name.isnot(None),
            DecisionMaker.name != "",
            DecisionMaker.name != "Unknown",
            func.upper(DecisionMaker.confidence_score) != "LOW",
            func.lower(DecisionMaker.name) != "john doe",
            func.lower(DecisionMaker.name) != "jane doe",
            ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/johndoe%"),
            ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/janedoe%"),
        )
        .order_by(DecisionMaker.id.asc())
        .all()
    )
    items = [_dm_to_response(dm, mappings) for dm in results]
    if not deep_search:
        for it in items:
            it.platform = "Default sources"
    return items


@router.get("/jobs/{job_id}/results/paged", response_model=DecisionMakerListResponse)
async def get_job_results_paged(
    job_id: int,
    q: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deep_search = bool((getattr(job, "options", None) or {}).get("deep_search"))
    mappings = job.column_mappings or {}
    query = db.query(DecisionMaker).filter(
        DecisionMaker.job_id == job_id,
        DecisionMaker.name.isnot(None),
        DecisionMaker.name != "",
        DecisionMaker.name != "Unknown",
        func.upper(DecisionMaker.confidence_score) != "LOW",
        func.lower(DecisionMaker.name) != "john doe",
        func.lower(DecisionMaker.name) != "jane doe",
        ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/johndoe%"),
        ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/janedoe%"),
    )

    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.company_address.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.emails_found.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
            )
        )

    total = query.count()
    rows = query.order_by(DecisionMaker.id.asc()).offset(offset).limit(limit).all()
    items = [_dm_to_response(dm, mappings) for dm in rows]
    if not deep_search:
        for it in items:
            it.platform = "Default sources"
    return DecisionMakerListResponse(items=items, total=total, limit=limit, offset=offset)


@router.get("/jobs/{job_id}/results.csv")
async def download_job_results_csv(
    job_id: int,
    q: str | None = None,
    db: Session = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user),
):
    job = db.query(Job).filter(Job.id == job_id, Job.user_id == current_user.id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    deep_search = bool((getattr(job, "options", None) or {}).get("deep_search"))
    mappings = job.column_mappings or {}
    query = db.query(DecisionMaker).filter(
        DecisionMaker.job_id == job_id,
        DecisionMaker.name.isnot(None),
        DecisionMaker.name != "",
        DecisionMaker.name != "Unknown",
        func.upper(DecisionMaker.confidence_score) != "LOW",
        func.lower(DecisionMaker.name) != "john doe",
        func.lower(DecisionMaker.name) != "jane doe",
        ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/johndoe%"),
        ~func.coalesce(DecisionMaker.profile_url, "").ilike("%linkedin.com/in/janedoe%"),
    )

    if q:
        q_like = f"%{q}%"
        query = query.filter(
            or_(
                DecisionMaker.company_name.ilike(q_like),
                DecisionMaker.company_type.ilike(q_like),
                DecisionMaker.company_city.ilike(q_like),
                DecisionMaker.company_country.ilike(q_like),
                DecisionMaker.company_website.ilike(q_like),
                DecisionMaker.company_address.ilike(q_like),
                DecisionMaker.name.ilike(q_like),
                DecisionMaker.title.ilike(q_like),
                DecisionMaker.platform.ilike(q_like),
                DecisionMaker.emails_found.ilike(q_like),
                DecisionMaker.profile_url.ilike(q_like),
            )
        )

    rows = query.order_by(DecisionMaker.id.asc()).all()
    resolved_rows: list[tuple[DecisionMaker, dict]] = []
    for dm in rows:
        resolved_rows.append((dm, _resolve_company_fields(dm, mappings)))

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Person Name",
            "Job Title",
            "Emails Found",
            "Company Website",
            "Company Name",
            "Company Type",
            "Company Address",
            "GMaps Rating",
            "GMaps Reviews",
            "Company Location",
            "Confidence",
        ]
    )
    for dm, resolved in resolved_rows:
        company_location = ", ".join(
            [p for p in [_text(resolved.get("company_city", "")), _text(resolved.get("company_country", ""))] if p]
        )
        writer.writerow(
            [
                _non_empty(getattr(dm, "name", ""), "Unknown"),
                _non_empty(getattr(dm, "title", ""), "Unknown"),
                _text(getattr(dm, "emails_found", "")),
                _text(resolved.get("company_website", "")),
                _text(resolved.get("company_name", "")),
                _text(resolved.get("company_type", "")),
                _text(resolved.get("company_address", "")),
                (str(getattr(dm, "gmaps_rating", "") or "") if getattr(dm, "gmaps_rating", None) is not None else ""),
                (str(getattr(dm, "gmaps_reviews", "") or "") if getattr(dm, "gmaps_reviews", None) is not None else ""),
                company_location,
                _non_empty(getattr(dm, "confidence_score", ""), "UNKNOWN"),
            ]
        )

    filename = f"job-{job_id}-results.csv"
    return Response(
        content=output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=\"{filename}\""},
    )


@router.get("/credits", response_model=CreditResponse)
async def get_credits(db: Session = Depends(get_db), current_user: CurrentUser = Depends(get_current_user)):
    balance = recalculate_effective_balance(db, current_user.id)
    return CreditResponse(balance=int(balance))
