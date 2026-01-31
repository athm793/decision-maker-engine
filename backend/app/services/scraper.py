import re
from typing import Any
from urllib.parse import urlparse

from app.services.llm.client import LLMDisabledError, get_llm_client


def _text(raw: object) -> str:
    return str(raw or "").strip()


class ScraperService:
    def __init__(self):
        self.llm = None

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
    ) -> dict[str, str]:
        await self.start()
        if self.llm is None:
            return {
                "company_name": self._guess_company_name_from_website(website),
                "company_type": "",
                "company_city": "",
                "company_country": "",
                "company_website": (website or "").strip(),
            }

        enriched = await self.llm.research_company(
            company_name=company_name,
            location=location,
            google_maps_url=google_maps_url,
            website=website,
            search_results=[],
            use_web_search=True,
        )
        return {
            "company_name": _text(enriched.get("company_name", "")),
            "company_type": _text(enriched.get("company_type", "")),
            "company_city": _text(enriched.get("company_city", "")),
            "company_country": _text(enriched.get("company_country", "")),
            "company_website": _text(enriched.get("company_website", "")),
        }

    async def process_company(
        self,
        company_name: str,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        platforms: list[str] | None = None,
        max_people: int | None = None,
        remaining_total: int | None = None,
        search_limit: int | None = None,
        deep_search: bool = False,
        query_keywords: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        await self.start()
        if self.llm is None:
            return []
        max_people = max_people or 3
        if remaining_total is not None:
            max_people = min(max_people, max(0, remaining_total))
        if max_people <= 0:
            return []

        people = await self.llm.research_decision_makers(
            company_name=company_name,
            location=location,
            google_maps_url=google_maps_url,
            website=website,
            platforms=platforms or [],
            search_results=[],
            max_people=max_people,
            use_web_search=True,
            deep_search=bool(deep_search),
            role_keywords_override=query_keywords,
        )
        return list(people or [])

