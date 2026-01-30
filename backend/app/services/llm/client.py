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


class OpenAICompatibleLLM:
    def __init__(self, api_key: str, base_url: str | None, model: str, temperature: float) -> None:
        from openai import OpenAI

        kwargs: dict[str, Any] = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
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


def get_llm_client() -> OpenAICompatibleLLM:
    if settings.llm_api_key is None:
        raise LLMDisabledError("LLM is not configured")

    base_url = settings.llm_base_url
    model = settings.llm_model or "sonar"
    temperature = settings.llm_temperature
    return OpenAICompatibleLLM(
        api_key=settings.llm_api_key,
        base_url=base_url,
        model=model,
        temperature=temperature,
    )
