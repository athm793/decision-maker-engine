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

def _infer_city_country_from_search_results(items: list[dict[str, Any]]) -> tuple[str, str]:
    city = ""
    country = ""
    rx = re.compile(r"\b([A-Z][a-zA-Z .'-]{2,}),\s*([A-Z][a-zA-Z .'-]{2,})\b")
    country_map = {
        "united states": "United States",
        "usa": "United States",
        "u.s.": "United States",
        "us": "United States",
        "united kingdom": "United Kingdom",
        "uk": "United Kingdom",
        "great britain": "United Kingdom",
        "england": "United Kingdom",
        "scotland": "United Kingdom",
        "wales": "United Kingdom",
        "canada": "Canada",
        "australia": "Australia",
        "new zealand": "New Zealand",
        "ireland": "Ireland",
        "germany": "Germany",
        "france": "France",
        "spain": "Spain",
        "italy": "Italy",
        "netherlands": "Netherlands",
        "sweden": "Sweden",
        "norway": "Norway",
        "denmark": "Denmark",
        "finland": "Finland",
        "switzerland": "Switzerland",
        "austria": "Austria",
        "belgium": "Belgium",
        "portugal": "Portugal",
        "brazil": "Brazil",
        "mexico": "Mexico",
        "india": "India",
        "japan": "Japan",
        "singapore": "Singapore",
        "united arab emirates": "United Arab Emirates",
        "uae": "United Arab Emirates",
        "south africa": "South Africa",
    }
    us_state_names = {
        "alabama","alaska","arizona","arkansas","california","colorado","connecticut","delaware","florida","georgia","hawaii","idaho","illinois","indiana","iowa","kansas","kentucky","louisiana","maine","maryland","massachusetts","michigan","minnesota","mississippi","missouri","montana","nebraska","nevada","new hampshire","new jersey","new mexico","new york","north carolina","north dakota","ohio","oklahoma","oregon","pennsylvania","rhode island","south carolina","south dakota","tennessee","texas","utah","vermont","virginia","washington","west virginia","wisconsin","wyoming",
    }
    us_state_abbrs = {"AL","AK","AZ","AR","CA","CO","CT","DE","FL","GA","HI","ID","IL","IN","IA","KS","KY","LA","ME","MD","MA","MI","MN","MS","MO","MT","NE","NV","NH","NJ","NM","NY","NC","ND","OH","OK","OR","PA","RI","SC","SD","TN","TX","UT","VT","VA","WA","WV","WI","WY"}

    def infer_country_from_text(text: str) -> str:
        t = (text or "").strip()
        if not t:
            return ""
        tl = t.lower()
        for k, v in country_map.items():
            if re.search(rf"\b{re.escape(k)}\b", tl):
                return v
        for ab in us_state_abbrs:
            if re.search(rf"\b{ab}\b", t):
                return "United States"
        for st in us_state_names:
            if re.search(rf"\b{re.escape(st)}\b", tl):
                return "United States"
        return ""

    for item in items:
        snippet = str(item.get("snippet") or "")
        title = str(item.get("title") or "")
        text = f"{title} {snippet}"
        for m in rx.finditer(text):
            a = m.group(1).strip()
            b = m.group(2).strip()
            if not city and a and not re.search(r"\d", a):
                city = a
            if not country and b and not re.search(r"\d", b) and len(b) > 2:
                country = infer_country_from_text(b) or b
        if city and country:
            break
        if not country:
            country = infer_country_from_text(text)
        if city and country:
            break
    return (city, country)

class ScraperService:
    def __init__(self):
        self.browser = None
        self.context = None
        self.llm = None
        self.web_search = None
        self._search_cache: dict[tuple[str, int], list[dict[str, Any]]] = {}
        self._enrich_cache: dict[tuple[str, str, str, str, int, bool], dict[str, str]] = {}

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

    async def _cached_search(self, query: str, limit: int) -> list[dict[str, Any]]:
        q = (query or "").strip()
        limit = max(1, min(int(limit or 5), 25))
        if not q or self.web_search is None:
            return []
        key = (q, limit)
        cached = self._search_cache.get(key)
        if cached is not None:
            return cached
        try:
            items = await self.web_search.search_duckduckgo(q, limit=limit)
        except Exception:
            items = []
        self._search_cache[key] = items
        return items

    async def enrich_company(
        self,
        company_name: str | None,
        location: str = "",
        google_maps_url: str | None = None,
        website: str | None = None,
        search_limit: int = 5,
    ) -> dict[str, str]:
        if not self.browser:
            await self.start()

        key = (
            str(company_name or "").strip().lower(),
            str(location or "").strip().lower(),
            str(google_maps_url or "").strip(),
            str(website or "").strip().lower(),
            int(search_limit or 5),
            bool(self.llm),
        )
        cached_enrich = self._enrich_cache.get(key)
        if cached_enrich is not None:
            return cached_enrich

        search_results: list[dict[str, Any]] = []
        q = " ".join([p for p in [str(company_name or "").strip(), str(location or "").strip(), str(website or "").strip()] if p])
        if q:
            search_results = await self._cached_search(q, limit=search_limit)

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
                search_results=search_results,
            )
            name = (enriched.get("company_name") or "").strip()
            site = (enriched.get("company_website") or "").strip()
            ctype = (enriched.get("company_type") or "").strip()
            city = (enriched.get("company_city") or "").strip()
            country = (enriched.get("company_country") or "").strip()
            if not city or not country:
                inferred_city, inferred_country = _infer_city_country_from_search_results(search_results)
                city = city or inferred_city
                country = country or inferred_country
            if re.search(r"https?://|www\.", name, flags=re.IGNORECASE):
                name = ""
            out = {
                "company_name": name,
                "company_website": site,
                "company_type": ctype,
                "company_city": city,
                "company_country": country,
            }
            self._enrich_cache[key] = out
            return out

        guessed = self._guess_company_name_from_website(website)
        inferred_city, inferred_country = _infer_city_country_from_search_results(search_results)
        out = {
            "company_name": guessed,
            "company_website": (website or "").strip(),
            "company_type": "",
            "company_city": inferred_city,
            "company_country": inferred_country,
        }
        self._enrich_cache[key] = out
        return out

    async def search_linkedin(self, company_name: str, location: str = "", search_limit: int = 5) -> List[Dict[str, Any]]:
        results = []
        try:
            if not self.web_search:
                return []

            titles = ["CEO", "Founder", "Owner", "President", "\"General Manager\"", "\"Managing Director\"", "\"Operations Manager\""]
            q = f"{company_name} {location} ({' OR '.join(titles)}) site:linkedin.com/in"
            items = await self._cached_search(q, limit=search_limit or 5)
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

    async def search_platform(
        self,
        platform: str,
        company_name: str,
        location: str = "",
        search_limit: int = 3,
        deep_search: bool = False,
    ) -> List[Dict[str, Any]]:
        if platform == "linkedin":
            out = await self.search_linkedin(company_name, location, search_limit=search_limit or 5)
            if deep_search and self.web_search:
                titles = [
                    "\"Managing Partner\"",
                    "\"Managing Member\"",
                    "Partner",
                    "Principal",
                    "COO",
                    "Director",
                    "\"Operations Manager\"",
                    "\"Vice President\"",
                    "VP",
                    "\"Head of\"",
                ]
                q2 = f"\"{company_name}\" {location} ({' OR '.join(titles)}) site:linkedin.com/in"
                items2 = await self._cached_search(q2, limit=max(1, min(search_limit, 10)))
                for item in items2:
                    url = item.get("url")
                    if not url or "linkedin.com/in" not in url:
                        continue
                    title = item.get("title", "")
                    snippet = item.get("snippet", "")
                    name = guess_person_name_from_title(title) or ""
                    out.append(
                        {
                            "name": name,
                            "title": "",
                            "platform": "LinkedIn",
                            "profile_url": url,
                            "confidence": "LOW",
                            "reasoning": snippet or title,
                        }
                    )
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for x in out:
                u = (x.get("profile_url") or "").strip()
                if u and u in seen:
                    continue
                if u:
                    seen.add(u)
                deduped.append(x)
            return deduped

        if not self.web_search:
            return []

        if platform == "google_maps":
            q = f"{company_name} {location} site:google.com/maps"
            items = await self._cached_search(q, limit=search_limit)
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
            if deep_search:
                q2 = f"\"{company_name}\" {location} \"Google Maps\" owner"
                items2 = await self._cached_search(q2, limit=search_limit)
                for item in items2:
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
            q = f"{company_name} {location} site:facebook.com (owner OR founder OR ceo)"
            items = await self._cached_search(q, limit=search_limit)
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
            if deep_search:
                q2 = f"\"{company_name}\" {location} site:facebook.com (about OR team OR management)"
                items2 = await self._cached_search(q2, limit=search_limit)
                for item in items2:
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
            items = await self._cached_search(q, limit=search_limit)
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
            if deep_search:
                q2 = f"\"{company_name}\" {location} site:instagram.com (bio OR founder)"
                items2 = await self._cached_search(q2, limit=search_limit)
                for item in items2:
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
            items = await self._cached_search(q, limit=search_limit)
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
            if deep_search:
                q2 = f"\"{company_name}\" {location} site:yelp.com \"Business owner\""
                items2 = await self._cached_search(q2, limit=search_limit)
                for item in items2:
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

    async def search_google_maps(self, company_name: str, location: str = "", search_limit: int = 3) -> List[Dict[str, Any]]:
        results = []
        try:
            if not self.web_search:
                return []

            q = f"{company_name} {location} owner "
            items = await self._cached_search(q, limit=search_limit)
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
        search_limit: int | None = None,
        deep_search: bool = False,
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

        if selected and self.web_search:
            logger.info(
                "scraper.process_company.waterfall company_name=%s platforms=%s max_people=%s",
                (company_name[:200] if company_name else ""),
                selected,
                max_people,
            )
            out: list[dict[str, Any]] = []
            seen: set[str] = set()
            deep_platform = None
            if deep_search:
                deep_platform = "linkedin" if "linkedin" in selected else (selected[0] if selected else None)
            for platform in selected:
                items = await self.search_platform(
                    platform,
                    company_name,
                    location,
                    search_limit=(search_limit or 3),
                    deep_search=bool(deep_platform and platform == deep_platform),
                )
                for item in items:
                    url = item.get("profile_url") or ""
                    if url and url in seen:
                        continue
                    if url:
                        seen.add(url)
                    out.append(item)
                    if len(out) >= max_people:
                        return out
            if out:
                return out

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
            
        linkedin_results = await self.search_linkedin(company_name, location, search_limit=5)
        gmaps_results = await self.search_google_maps(company_name, location, search_limit=(search_limit or 3))
        
        return linkedin_results + gmaps_results
