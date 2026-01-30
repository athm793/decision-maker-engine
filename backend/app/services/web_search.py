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


_LINKEDIN_NAME_PATTERNS = [
    re.compile(r"^(.+?)\s+-\s+.+?\s+\|\s+LinkedIn\s*$", re.IGNORECASE),
    re.compile(r"^(.+?)\s+\|\s+LinkedIn\s*$", re.IGNORECASE),
]


def guess_person_name_from_title(title: str) -> str | None:
    t = (title or "").strip()
    if not t:
        return None
    for rx in _LINKEDIN_NAME_PATTERNS:
        m = rx.match(t)
        if m:
            return m.group(1).strip()
    return None

