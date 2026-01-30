from playwright.async_api import async_playwright
import asyncio
import random
from typing import List, Dict, Any
import re
from urllib.parse import urlparse
import logging

from app.services.llm.client import LLMDisabledError, get_llm_client
from app.services.web_search import WebSearchService, guess_person_name_from_title

logger = logging.getLogger(__name__)

class ScraperService:
    def __init__(self):
        self.browser = None
        self.context = None
        self.llm = None
        self.web_search = None

    async def start(self):
        if not self.browser:
            logger.info("scraper.start.launch_browser")
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(headless=True) # Set headless=False to see it in action locally
            self.context = await self.browser.new_context(
                viewport={"width": 1280, "height": 720},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
            )

        if self.web_search is None and self.context is not None:
            self.web_search = WebSearchService(self.context)

        if self.llm is None:
            try:
                self.llm = get_llm_client()
            except LLMDisabledError:
                self.llm = None
        logger.info("scraper.start.ready llm=%s web_search=%s", bool(self.llm), bool(self.web_search))

    async def stop(self):
        if self.browser:
            logger.info("scraper.stop.close_browser")
            await self.browser.close()
            await self.playwright.stop()
            self.browser = None

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
    ) -> dict[str, str]:
        if not self.browser:
            await self.start()

        if self.llm is not None:
            logger.info(
                "scraper.enrich_company.llm company_name=%s location=%s website=%s",
                (str(company_name)[:200] if company_name is not None else ""),
                (str(location)[:200] if location is not None else ""),
                (str(website)[:200] if website is not None else ""),
            )
            enriched = await self.llm.research_company(
                company_name=company_name,
                location=location,
                google_maps_url=google_maps_url,
                website=website,
            )
            name = (enriched.get("company_name") or "").strip()
            site = (enriched.get("company_website") or "").strip()
            ctype = (enriched.get("company_type") or "").strip()
            if re.search(r"https?://|www\.", name, flags=re.IGNORECASE):
                name = ""
            return {
                "company_name": name,
                "company_website": site,
                "company_type": ctype,
            }

        guessed = self._guess_company_name_from_website(website)
        return {
            "company_name": guessed,
            "company_website": (website or "").strip(),
            "company_type": "",
        }

    async def search_linkedin(self, company_name: str, location: str = "") -> List[Dict[str, Any]]:
        results = []
        try:
            if not self.web_search:
                return []

            q = f"{company_name} {location} (CEO OR Founder OR Owner) site:linkedin.com/in"
            items = await self.web_search.search_duckduckgo(q, limit=5)
            for item in items:
                url = item.get("url")
                if not url or "linkedin.com/in" not in url:
                    continue
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                name = guess_person_name_from_title(title) or ""
                results.append(
                    {
                        "name": name,
                        "title": "",
                        "platform": "LinkedIn",
                        "profile_url": url,
                        "confidence": "MEDIUM",
                        "reasoning": snippet or title,
                    }
                )
        except Exception as e:
            logger.exception("scraper.search_linkedin.error company_name=%s location=%s", company_name, location)
            
        return results

    async def search_platform(self, platform: str, company_name: str, location: str = "") -> List[Dict[str, Any]]:
        if platform == "linkedin":
            return await self.search_linkedin(company_name, location)

        if not self.web_search:
            return []

        if platform == "google_maps":
            q = f"{company_name} {location} site:google.com/maps"
            items = await self.web_search.search_duckduckgo(q, limit=3)
            out: list[dict[str, Any]] = []
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                out.append(
                    {
                        "name": "",
                        "title": "",
                        "platform": "Google Maps",
                        "profile_url": url,
                        "confidence": "LOW",
                        "reasoning": item.get("snippet") or item.get("title"),
                    }
                )
            return out

        if platform == "facebook":
            q = f"{company_name} {location} (CEO OR founder OR owner) site:facebook.com"
            items = await self.web_search.search_duckduckgo(q, limit=3)
            out: list[dict[str, Any]] = []
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                out.append(
                    {
                        "name": "",
                        "title": "",
                        "platform": "Facebook",
                        "profile_url": url,
                        "confidence": "LOW",
                        "reasoning": item.get("snippet") or item.get("title"),
                    }
                )
            return out

        if platform == "instagram":
            q = f"{company_name} {location} (founder OR ceo OR owner) site:instagram.com"
            items = await self.web_search.search_duckduckgo(q, limit=3)
            out: list[dict[str, Any]] = []
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                out.append(
                    {
                        "name": "",
                        "title": "",
                        "platform": "Instagram",
                        "profile_url": url,
                        "confidence": "LOW",
                        "reasoning": item.get("snippet") or item.get("title"),
                    }
                )
            return out

        if platform == "yelp":
            q = f"{company_name} {location} site:yelp.com"
            items = await self.web_search.search_duckduckgo(q, limit=3)
            out: list[dict[str, Any]] = []
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                out.append(
                    {
                        "name": "",
                        "title": "",
                        "platform": "Yelp",
                        "profile_url": url,
                        "confidence": "LOW",
                        "reasoning": item.get("snippet") or item.get("title"),
                    }
                )
            return out

        return []

    async def search_google_maps(self, company_name: str, location: str = "") -> List[Dict[str, Any]]:
        results = []
        try:
            if not self.web_search:
                return []

            q = f"{company_name} {location} owner "
            items = await self.web_search.search_duckduckgo(q, limit=3)
            for item in items:
                url = item.get("url")
                if not url:
                    continue
                results.append(
                    {
                        "name": "",
                        "title": "",
                        "platform": "Web",
                        "profile_url": url,
                        "confidence": "LOW",
                        "reasoning": item.get("snippet") or item.get("title"),
                    }
                )
        except Exception as e:
            logger.exception("scraper.search_google_maps.error company_name=%s location=%s", company_name, location)
            
        return results

    async def process_company(
        self,
        company_name: str,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        platforms: list[str] | None = None,
        max_people: int | None = None,
        remaining_total: int | None = None,
    ) -> List[Dict[str, Any]]:
        if not self.browser:
            await self.start()

        selected = platforms or []
        selected = [p for p in selected if isinstance(p, str)]
        max_people = max_people or 3
        if remaining_total is not None:
            max_people = min(max_people, max(0, remaining_total))

        if max_people <= 0:
            return []

        if self.llm is not None:
            logger.info(
                "scraper.process_company.llm company_name=%s platforms=%s max_people=%s",
                (company_name[:200] if company_name else ""),
                selected,
                max_people,
            )
            people = await self.llm.research_decision_makers(
                company_name=company_name,
                location=location,
                google_maps_url=google_maps_url,
                website=website,
                platforms=selected,
                max_people=max_people,
            )
            out: list[dict[str, Any]] = []
            for p in people:
                out.append(
                    {
                        "name": p.get("name"),
                        "title": p.get("title"),
                        "platform": p.get("platform", "Research"),
                        "profile_url": p.get("profile_url"),
                        "confidence": p.get("confidence", "MEDIUM"),
                        "reasoning": p.get("reasoning"),
                    }
                )
            return out[:max_people]

        if selected:
            logger.info(
                "scraper.process_company.waterfall company_name=%s platforms=%s max_people=%s",
                (company_name[:200] if company_name else ""),
                selected,
                max_people,
            )
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            for platform in selected:
                items = await self.search_platform(platform, company_name, location)
                for item in items:
                    url = item.get("profile_url") or ""
                    if url and url in seen:
                        continue
                    if url:
                        seen.add(url)
                    out.append(item)
                    if len(out) >= max_people:
                        return out
            return out
            
        linkedin_results = await self.search_linkedin(company_name, location)
        gmaps_results = await self.search_google_maps(company_name, location)
        
        return linkedin_results + gmaps_results
