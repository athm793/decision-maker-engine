import asyncio
import json
from typing import Any

from app.core.settings import settings


class LLMDisabledError(RuntimeError):
    pass


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
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        if extra_headers:
            kwargs["default_headers"] = extra_headers
        self._client = OpenAI(**kwargs)
        self._model = model
        self._temperature = temperature

    def _chat(self, messages: list[dict[str, str]]) -> str:
        response = self._client.chat.completions.create(
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
        platforms: list[str] | None = None,
        max_people: int = 3,
    ) -> list[dict[str, Any]]:
        system = (
            "You are a research assistant. Find real people who are decision makers for the given company. "
            "Return only JSON."
        )

        user = {
            "company_name": company_name,
            "location": location or "",
            "google_maps_url": google_maps_url or "",
            "website": website or "",
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
            ],
        }

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps(user)},
        ]

        text = await asyncio.to_thread(self._chat, messages)
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

        text = await asyncio.to_thread(self._chat, messages)
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
