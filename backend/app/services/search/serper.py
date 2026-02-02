from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx


class SerperError(RuntimeError):
    pass


class _SerperRateLimiter:
    def __init__(self, qps: int) -> None:
        self._qps = max(1, int(qps))
        self._lock = asyncio.Lock()
        self._events: list[float] = []

    async def acquire(self) -> None:
        async with self._lock:
            now = time.monotonic()
            cutoff = now - 1.0
            self._events = [t for t in self._events if t >= cutoff]
            if len(self._events) >= self._qps:
                sleep_for = (self._events[0] + 1.0) - now
            else:
                sleep_for = 0.0
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)
                now = time.monotonic()
                cutoff = now - 1.0
                self._events = [t for t in self._events if t >= cutoff]
            self._events.append(time.monotonic())


class SerperClient:
    def __init__(
        self,
        *,
        api_key: str,
        endpoint: str,
        gl: str,
        hl: str,
        num: int,
        qps: int,
        timeout_s: float = 20.0,
    ) -> None:
        self._api_key = (api_key or "").strip()
        self._endpoint = (endpoint or "").strip()
        self._gl = (gl or "").strip()
        self._hl = (hl or "").strip()
        self._num = max(1, min(int(num or 10), 100))
        self._limiter = _SerperRateLimiter(qps=qps)
        self._client = httpx.AsyncClient(timeout=httpx.Timeout(timeout_s))

    async def aclose(self) -> None:
        await self._client.aclose()

    def _trim_response(self, payload: Any, *, max_organic: int = 8, max_paa: int = 6) -> dict[str, Any]:
        if not isinstance(payload, dict):
            return {"organic": []}

        out: dict[str, Any] = {}
        kg = payload.get("knowledgeGraph")
        if isinstance(kg, dict):
            out["knowledgeGraph"] = {
                k: kg.get(k)
                for k in [
                    "title",
                    "type",
                    "website",
                    "description",
                    "descriptionLink",
                    "address",
                    "rating",
                    "ratingCount",
                    "reviewCount",
                ]
                if k in kg
            }

        organic = payload.get("organic")
        if isinstance(organic, list):
            trimmed: list[dict[str, Any]] = []
            for item in organic[: max(1, max_organic)]:
                if not isinstance(item, dict):
                    continue
                trimmed.append({k: item.get(k) for k in ["title", "link", "snippet"] if k in item})
            out["organic"] = trimmed
        else:
            out["organic"] = []

        paa = payload.get("peopleAlsoAsk")
        if max_paa > 0 and isinstance(paa, list):
            trimmed_paa: list[dict[str, Any]] = []
            for item in paa[: max(0, max_paa)]:
                if not isinstance(item, dict):
                    continue
                trimmed_paa.append({k: item.get(k) for k in ["question", "snippet", "title", "link"] if k in item})
            out["peopleAlsoAsk"] = trimmed_paa

        credits = payload.get("credits")
        if isinstance(credits, (int, float)):
            out["credits"] = credits
        return out

    async def search(
        self,
        *,
        q: str,
        gl: str | None = None,
        hl: str | None = None,
        num: int | None = None,
        page: int | None = None,
        tbs: str | None = None,
        autocorrect: bool | None = None,
        max_organic: int = 8,
        max_paa: int = 6,
    ) -> dict[str, Any]:
        if not self._api_key:
            raise SerperError("SERPER_API_KEY is not configured")
        if not self._endpoint:
            raise SerperError("SERPER_ENDPOINT is not configured")
        query = (q or "").strip()
        if not query:
            return {"organic": []}

        payload: dict[str, Any] = {"q": query}
        payload["gl"] = (gl or self._gl or "us").strip()
        payload["hl"] = (hl or self._hl or "en").strip()
        payload["num"] = max(1, min(int(num or self._num), 100))
        if page is not None:
            payload["page"] = max(1, int(page))
        if tbs:
            payload["tbs"] = str(tbs)
        if autocorrect is not None:
            payload["autocorrect"] = bool(autocorrect)

        await self._limiter.acquire()

        try:
            resp = await self._client.post(
                self._endpoint,
                headers={"X-API-KEY": self._api_key, "Content-Type": "application/json"},
                json=payload,
            )
        except Exception as e:
            raise SerperError(f"Serper request failed: {e}")

        if resp.status_code >= 400:
            detail = ""
            try:
                detail = resp.text[:500]
            except Exception:
                detail = ""
            raise SerperError(f"Serper error {resp.status_code}: {detail}")

        try:
            data = resp.json()
        except Exception as e:
            raise SerperError(f"Serper returned invalid JSON: {e}")

        return self._trim_response(data, max_organic=max_organic, max_paa=max_paa)
