from __future__ import annotations

import re
from typing import Any


class WebSearchService:
    def __init__(self, context) -> None:
        self._context = context

    async def search_duckduckgo(self, query: str, limit: int = 5) -> list[dict[str, Any]]:
        limit = max(1, min(limit, 25))
        page = await self._context.new_page()

        try:
            await page.goto("https://duckduckgo.com/")
            await page.fill('input[name="q"]', query)
            await page.press('input[name="q"]', "Enter")
            await page.wait_for_selector('a[data-testid="result-title-a"]', timeout=15000)

            titles = page.locator('a[data-testid="result-title-a"]')
            snippets = page.locator('div[data-testid="result-snippet"]')

            count = await titles.count()
            out: list[dict[str, Any]] = []
            for i in range(min(count, limit)):
                title = (await titles.nth(i).inner_text()).strip()
                url = (await titles.nth(i).get_attribute("href")) or ""
                snippet = ""
                if await snippets.count() > i:
                    snippet = (await snippets.nth(i).inner_text()).strip()
                if not url:
                    continue
                out.append({"title": title, "url": url, "snippet": snippet})
            return out
        finally:
            await page.close()


_PERSON_NAME_PATTERNS = [
    re.compile(r"^(.+?)\s+-\s+.+?\s+\|\s+(LinkedIn|Facebook|Instagram|Yelp)\s*$", re.IGNORECASE),
    re.compile(r"^(.+?)\s+\|\s+(LinkedIn|Facebook|Instagram|Yelp)\s*$", re.IGNORECASE),
]


def guess_person_name_from_title(title: str) -> str | None:
    t = (title or "").strip()
    if not t:
        return None
    for rx in _PERSON_NAME_PATTERNS:
        m = rx.match(t)
        if m:
            return m.group(1).strip()
    return None


def guess_person_title_from_title(title: str) -> str | None:
    t = (title or "").strip()
    if not t:
        return None

    t = re.sub(r"\s+\|\s*(LinkedIn|Facebook|Instagram|Yelp)\s*$", "", t, flags=re.IGNORECASE).strip()
    if not t:
        return None

    parts = [p.strip() for p in t.split(" - ") if p.strip()]
    if len(parts) < 2:
        return None

    role = parts[1]
    role = re.split(r"\s+\bat\b\s+", role, maxsplit=1, flags=re.IGNORECASE)[0].strip()
    role = re.sub(r"\s+", " ", role).strip()
    return role or None


def guess_person_name_from_text(text: str) -> str | None:
    t = (text or "").strip()
    if not t:
        return None
    m = re.search(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+){1,2})\b", t)
    if not m:
        return None
    return m.group(1).strip()
