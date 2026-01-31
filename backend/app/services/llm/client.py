import asyncio
import json
import os
import weakref
from typing import Any

from app.core.settings import settings
from app.services.decision_maker_rules import decision_maker_query_keywords


class LLMDisabledError(RuntimeError):
    pass


DEFAULT_LLM_CONCURRENCY = 500
_LLM_SEMAPHORES: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()


def _get_llm_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _LLM_SEMAPHORES.get(loop)
    if sem is None:
        limit = int(os.getenv("LLM_CONCURRENCY", str(DEFAULT_LLM_CONCURRENCY)) or str(DEFAULT_LLM_CONCURRENCY))
        limit = max(1, limit)
        sem = asyncio.Semaphore(limit)
        _LLM_SEMAPHORES[loop] = sem
    return sem


def _coerce_people(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("people"), list):
        people = payload["people"]
        out: list[dict[str, Any]] = []
        for item in people:
            if not isinstance(item, dict):
                continue
            out.append(item)
        return out
    return []

def _coerce_company(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict) and isinstance(payload.get("company"), dict):
        company = payload["company"]
        out: dict[str, Any] = {}
        for k in ["company_name", "company_type", "company_city", "company_country", "company_website"]:
            v = company.get(k)
            if isinstance(v, str):
                out[k] = v.strip()
        return out
    return None


class OpenAICompatibleLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        temperature: float,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        from openai import AsyncOpenAI
        import httpx

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if extra_headers:
            kwargs["default_headers"] = extra_headers
        kwargs["http_client"] = httpx.AsyncClient(
            limits=httpx.Limits(max_connections=2000, max_keepalive_connections=500),
            timeout=httpx.Timeout(60.0),
        )
        self._client = AsyncOpenAI(**kwargs)
        self._model = model
        self._temperature = temperature

    async def _chat(self, messages: list[dict[str, str]]) -> str:
        sem = _get_llm_semaphore()
        async with sem:
            response = await self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=self._temperature,
            )
            content = response.choices[0].message.content
            return content or ""

    async def research_decision_makers(
        self,
        company_name: str,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
        platforms: list[str] | None = None,
        max_people: int = 3,
    ) -> list[dict[str, Any]]:
        role_keywords = [str(k).strip().strip('"') for k in decision_maker_query_keywords()]
        system = (
            "You are a research assistant. Find real people who are decision makers for the given company. "
            "Return only JSON."
        )

        user = {
            "company_name": company_name,
            "location": location or "",
            "google_maps_url": google_maps_url or "",
            "website": website or "",
            "search_results": search_results or [],
            "platforms": platforms or [],
            "max_people": max_people,
            "output_schema": {
                "people": [
                    {
                        "name": "",
                        "title": "",
                        "platform": "",
                        "profile_url": "",
                        "confidence": "HIGH|MEDIUM|LOW",
                        "reasoning": "",
                    }
                ]
            },
            "constraints": [
                "Only include people you have strong evidence for.",
                "Prefer LinkedIn profile URLs when available.",
                "Confidence must be one of HIGH, MEDIUM, LOW.",
                f"Each person title must include at least one decision-maker keyword: {', '.join(role_keywords)}.",
                "Exclude staff/support roles like assistant, intern, coordinator, receptionist, technician, support, customer service, representative, specialist, associate.",
            ],
        }

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ]

        text = await self._chat(messages)
        try:
            payload = json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                payload = json.loads(text[start : end + 1])
            else:
                return []

        return _coerce_people(payload)

    async def research_company(
        self,
        company_name: str | None,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        system = (
            "You are a research assistant. Normalize the company identity from the provided row hints. "
            "Return only JSON."
        )

        user = {
            "company_name_hint": (company_name or "").strip(),
            "location": (location or "").strip(),
            "google_maps_url": (google_maps_url or "").strip(),
            "website_hint": (website or "").strip(),
            "search_results": search_results or [],
            "output_schema": {
                "company": {
                    "company_name": "",
                    "company_type": "",
                    "company_city": "",
                    "company_country": "",
                    "company_website": "",
                }
            },
            "constraints": [
                "company_name must be the business name only (no URL).",
                "company_type must be a short category/industry only (not an address).",
                "company_city must be a city only (no country, no state if possible).",
                "company_country must be a country only.",
                "company_website must be a website URL or domain only (no extra text).",
                "Use search_results as evidence when hints are missing or ambiguous.",
                "If uncertain, leave fields as empty strings.",
            ],
        }

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ]

        text = await self._chat(messages)
        try:
            payload = json.loads(text)
        except Exception:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                payload = json.loads(text[start : end + 1])
            else:
                return {"company_name": "", "company_type": "", "company_city": "", "company_country": "", "company_website": ""}

        company = _coerce_company(payload) or {}
        return {
            "company_name": company.get("company_name", "") or "",
            "company_type": company.get("company_type", "") or "",
            "company_city": company.get("company_city", "") or "",
            "company_country": company.get("company_country", "") or "",
            "company_website": company.get("company_website", "") or "",
        }


def get_llm_client() -> OpenAICompatibleLLM:
    if settings.llm_api_key is None:
        raise LLMDisabledError("LLM is not configured")

    base_url = settings.llm_base_url
    model = settings.llm_model or ("openai/gpt-4o-mini" if (base_url and "openrouter.ai" in base_url) else "sonar")
    temperature = settings.llm_temperature
    extra_headers: dict[str, str] = {}
    if base_url and "openrouter.ai" in base_url:
        if settings.openrouter_site_url:
            extra_headers["HTTP-Referer"] = settings.openrouter_site_url
        if settings.openrouter_app_name:
            extra_headers["X-Title"] = settings.openrouter_app_name
    return OpenAICompatibleLLM(
        api_key=settings.llm_api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
        extra_headers=(extra_headers or None),
    )
