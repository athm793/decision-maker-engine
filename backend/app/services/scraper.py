from playwright.async_api import async_playwright
import asyncio
import random
from typing import List, Dict, Any

from app.services.llm.client import LLMDisabledError, get_llm_client
from app.services.web_search import WebSearchService, guess_person_name_from_title

class ScraperService:
    def __init__(self):
        self.browser = None
        self.context = None
        self.llm = None
        self.web_search = None

    async def start(self):
        if not self.browser:
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

    async def stop(self):
        if self.browser:
            await self.browser.close()
            await self.playwright.stop()
            self.browser = None

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
            print(f"Error scraping LinkedIn for {company_name}: {e}")
            
        return results

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
            print(f"Error scraping Google Maps for {company_name}: {e}")
            
        return results

    async def process_company(
        self,
        company_name: str,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
    ) -> List[Dict[str, Any]]:
        if not self.browser:
            await self.start()

        if self.llm is not None:
            people = await self.llm.research_decision_makers(
                company_name=company_name,
                location=location,
                google_maps_url=google_maps_url,
                website=website,
                max_people=3,
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
            return out
            
        linkedin_results = await self.search_linkedin(company_name, location)
        gmaps_results = await self.search_google_maps(company_name, location)
        
        return linkedin_results + gmaps_results
