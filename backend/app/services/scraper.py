import os
import re
from typing import Any
from urllib.parse import urlparse

from app.services.cache import TTLCache, make_hash_key
from app.services.llm.client import LLMDisabledError, get_llm_client


def _text(raw: object) -> str:
    return str(raw or "").strip()


class ScraperService:
    def __init__(self):
        self.llm = None
        max_items = int(os.getenv("SCRAPER_CACHE_MAX_ITEMS", "5000") or "5000")
        ttl_s = int(os.getenv("SCRAPER_CACHE_TTL_S", str(24 * 60 * 60)) or str(24 * 60 * 60))
        self._company_cache = TTLCache(max_items=max_items, ttl_s=ttl_s)
        self._people_cache = TTLCache(max_items=max_items, ttl_s=ttl_s)

    async def start(self):
        if self.llm is None:
            try:
                self.llm = get_llm_client()
            except LLMDisabledError:
                self.llm = None

    async def stop(self):
        return

    def _guess_company_name_from_website(self, website: str | None) -> str:
        raw = (website or "").strip()
        if not raw:
            return ""
        if not re.match(r"^https?://", raw, flags=re.IGNORECASE):
            raw = "https://" + raw
        try:
            netloc = urlparse(raw).netloc
        except Exception:
            return ""
        host = netloc.lower()
        host = host[4:] if host.startswith("www.") else host
        parts = [p for p in host.split(".") if p]
        if len(parts) < 2:
            return ""
        base = parts[-2]
        base = re.sub(r"[^a-z0-9-]+", " ", base, flags=re.IGNORECASE).strip()
        base = re.sub(r"\s+", " ", base).strip()
        return base.title() if base else ""

    async def enrich_company(
        self,
        company_name: str | None,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        search_limit: int = 5,
    ) -> dict[str, Any]:
        await self.start()
        if self.llm is None:
            return {
                "company_name": self._guess_company_name_from_website(website),
                "company_type": "",
                "company_city": "",
                "company_country": "",
                "company_website": (website or "").strip(),
            }

        cache_key = make_hash_key(
            "enrich_company",
            {
                "company_name": (company_name or "").strip(),
                "location": (location or "").strip(),
                "google_maps_url": (google_maps_url or "").strip(),
                "website": (website or "").strip(),
                "search_limit": int(search_limit or 0),
            },
        )
        cached = self._company_cache.get(cache_key)
        if isinstance(cached, dict):
            return dict(cached)

        enriched, trace = await self.llm.research_company_with_trace(
            company_name=company_name,
            location=location,
            google_maps_url=google_maps_url,
            website=website,
            search_results=[],
            use_web_search=False,
            max_search_calls=search_limit,
        )
        out: dict[str, Any] = {
            "company_name": _text(enriched.get("company_name", "")),
            "company_type": _text(enriched.get("company_type", "")),
            "company_city": _text(enriched.get("company_city", "")),
            "company_country": _text(enriched.get("company_country", "")),
            "company_website": _text(enriched.get("company_website", "")),
            "_trace_company": (trace or None),
        }
        self._company_cache.set(cache_key, out)
        return out

    async def process_company(
        self,
        company_name: str,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        company_type: str | None = None,
        platforms: list[str] | None = None,
        max_people: int | None = None,
        remaining_total: int | None = None,
        search_limit: int | None = None,
        deep_search: bool = False,
        query_keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        people, _trace = await self.process_company_with_trace(
            company_name=company_name,
            location=location,
            google_maps_url=google_maps_url,
            website=website,
            company_type=company_type,
            platforms=platforms,
            max_people=max_people,
            remaining_total=remaining_total,
            search_limit=search_limit,
            deep_search=deep_search,
            query_keywords=query_keywords,
        )
        return people

    async def process_company_with_trace(
        self,
        *,
        company_name: str,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        company_type: str | None = None,
        platforms: list[str] | None = None,
        max_people: int | None = None,
        remaining_total: int | None = None,
        search_limit: int | None = None,
        deep_search: bool = False,
        query_keywords: list[str] | None = None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        await self.start()
        if self.llm is None:
            return ([], None)
        max_people = max_people or 3
        if remaining_total is not None:
            max_people = min(max_people, max(0, remaining_total))
        if max_people <= 0:
            return ([], None)

        cache_key = make_hash_key(
            "process_company",
            {
                "company_name": (company_name or "").strip(),
                "location": (location or "").strip(),
                "google_maps_url": (google_maps_url or "").strip(),
                "website": (website or "").strip(),
                "company_type": (company_type or "").strip(),
                "platforms": platforms or [],
                "max_people": int(max_people or 0),
                "search_limit": int(search_limit or 0),
                "deep_search": bool(deep_search),
                "query_keywords": query_keywords or [],
            },
        )
        cached = self._people_cache.get(cache_key)
        if isinstance(cached, dict) and isinstance(cached.get("people"), list):
            people = [dict(p) for p in cached.get("people") or [] if isinstance(p, dict)]
            trace = cached.get("trace") if isinstance(cached.get("trace"), dict) else None
            return (people, trace)

        people, trace = await self.llm.research_decision_makers_with_trace(
            company_name=company_name,
            location=location,
            google_maps_url=google_maps_url,
            website=website,
            company_type=company_type,
            platforms=platforms or [],
            search_results=[],
            max_people=int(max_people or 0),
            use_web_search=False,
            deep_search=bool(deep_search),
            role_keywords_override=query_keywords,
            exclude_profile_urls=[],
            max_search_calls=(2 if deep_search else 1),
        )
        trace = trace if isinstance(trace, dict) else {}
        out: list[dict[str, Any]] = []
        seen_urls: set[str] = set()
        for p in people or []:
            if not isinstance(p, dict):
                continue
            url = _text(p.get("profile_url") or "")
            if url:
                if url in seen_urls:
                    continue
                seen_urls.add(url)
            out.append(dict(p))

        trace_out: dict[str, Any] = dict(trace or {})

        self._people_cache.set(cache_key, {"people": out, "trace": (trace_out or None)})
        return (out, (trace_out or None))
