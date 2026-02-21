import asyncio
import json
import logging
import os
import random
import re
import weakref
from datetime import datetime, timezone
from typing import Any

from openai import APIStatusError, AsyncOpenAI

from app.core.settings import settings
from app.services.cache import stable_json_dumps
from app.services.decision_maker_rules import decision_maker_query_keywords
from app.services.search.serper import SerperClient, SerperError

logger = logging.getLogger(__name__)


class LLMDisabledError(RuntimeError):
    pass


DEFAULT_LLM_CONCURRENCY = 50
_LLM_SEMAPHORES: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Semaphore]" = weakref.WeakKeyDictionary()

try:
    from openai import APIConnectionError, APITimeoutError, RateLimitError
except Exception:  # type: ignore[misc]
    APIConnectionError = Exception  # type: ignore[assignment]
    APITimeoutError = Exception  # type: ignore[assignment]
    RateLimitError = Exception  # type: ignore[assignment]


def _get_llm_semaphore() -> asyncio.Semaphore:
    loop = asyncio.get_running_loop()
    sem = _LLM_SEMAPHORES.get(loop)
    if sem is None:
        limit = int(os.getenv("LLM_CONCURRENCY", str(DEFAULT_LLM_CONCURRENCY)) or str(DEFAULT_LLM_CONCURRENCY))
        limit = max(1, limit)
        sem = asyncio.Semaphore(limit)
        _LLM_SEMAPHORES[loop] = sem
    return sem


def _estimate_tokens_from_text(text: str) -> int:
    s = text or ""
    if not s:
        return 0
    return max(1, int(len(s) / 4))


def _estimate_tokens_from_messages(messages: list[dict[str, Any]]) -> int:
    total = 0
    for m in messages or []:
        c = m.get("content")
        if isinstance(c, str):
            total += _estimate_tokens_from_text(c)
        else:
            try:
                total += _estimate_tokens_from_text(json.dumps(c))
            except Exception:
                continue
    return total


def _coerce_people(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, dict) and isinstance(payload.get("people"), list):
        people = payload["people"]
        out: list[dict[str, Any]] = []
        for item in people:
            if not isinstance(item, dict):
                continue
            out.append(item)
        return out
    if isinstance(payload, list):
        out2: list[dict[str, Any]] = []
        for item in payload:
            if isinstance(item, dict):
                out2.append(item)
        return out2
    if isinstance(payload, dict) and isinstance(payload.get("results"), list):
        out3: list[dict[str, Any]] = []
        for item in payload.get("results") or []:
            if isinstance(item, dict):
                out3.append(item)
        return out3
    return []

def _coerce_company(payload: Any) -> dict[str, Any] | None:
    if isinstance(payload, dict) and isinstance(payload.get("company"), dict):
        company = payload["company"]
        out: dict[str, Any] = {}
        for k in [
            "company_name",
            "company_type",
            "company_city",
            "company_country",
            "company_website",
            "company_address",
        ]:
            v = company.get(k)
            if isinstance(v, str):
                out[k] = v.strip()
        rating = company.get("gmaps_rating")
        if isinstance(rating, (int, float)):
            out["gmaps_rating"] = float(rating)
        else:
            try:
                if isinstance(rating, str) and rating.strip():
                    out["gmaps_rating"] = float(rating.strip())
            except Exception:
                pass
        reviews = company.get("gmaps_reviews")
        if isinstance(reviews, int):
            out["gmaps_reviews"] = int(reviews)
        else:
            try:
                if isinstance(reviews, str) and reviews.strip():
                    out["gmaps_reviews"] = int(float(reviews.strip()))
            except Exception:
                pass
        return out
    return None


def _build_people_system_prompt() -> str:
    return (
        "You are a lead research assistant specializing in finding business decision-makers.\n"
        "Analyze the serper_results (Google search evidence) provided in the user message to identify "
        "real people who hold leadership roles at the specified company.\n\n"
        "## Output format\n"
        "Return ONLY a raw JSON object — no markdown fences, no explanation — matching this schema exactly:\n"
        "{\n"
        "  \"people\": [\n"
        "    {\n"
        "      \"name\": \"Full Name\",\n"
        "      \"title\": \"Exact Job Title from evidence\",\n"
        "      \"platform\": \"linkedin|yelp|facebook|instagram|google_maps\",\n"
        "      \"profile_url\": \"https://...\",\n"
        "      \"emails_found\": [\"email@domain.com\"],\n"
        "      \"confidence\": \"HIGH|MEDIUM|LOW\"\n"
        "    }\n"
        "  ],\n"
        "  \"company\": {\n"
        "    \"company_website\": \"\",\n"
        "    \"company_type\": \"\",\n"
        "    \"company_address\": \"\",\n"
        "    \"gmaps_rating\": null,\n"
        "    \"gmaps_reviews\": null\n"
        "  }\n"
        "}\n"
        "If no decision-makers are found, return {\"people\": [], \"company\": {}}.\n\n"
        "## Confidence scoring\n"
        "- HIGH: The person is named in a profile URL (e.g. linkedin.com/in/firstname-lastname) AND "
        "a snippet confirms their title at this specific company.\n"
        "- MEDIUM: A snippet names the person with their title and company, but no direct profile URL is available.\n"
        "- LOW: The person is mentioned only once with no clear title confirmation or company association.\n\n"
        "## Evidence rules — strictly follow these\n"
        "- NEVER include a person not explicitly mentioned in serper_results.\n"
        "- NEVER invent, guess, or hallucinate names, titles, emails, or URLs.\n"
        "- If a result could refer to a different company with a similar name, EXCLUDE it.\n"
        "- If the same person appears in multiple results, include them once at the highest confidence level.\n"
        "- Only include titles that match the role_keywords listed in the input.\n"
        "- Exclude non-leadership roles: assistant, intern, coordinator, receptionist, technician, "
        "support, customer service, representative, specialist, associate, staff, clerk.\n"
        "- Use the exact title wording from the evidence, not a generic label.\n"
        "- Prefer LinkedIn profile URLs; for other platforms include the most direct URL found.\n"
        "- Populate the company object with any website, type, address, or Google Maps rating/review "
        "count you can reliably infer from serper_results; leave fields blank/null if uncertain.\n"
    )


class OpenAICompatibleLLM:
    def __init__(
        self,
        api_key: str,
        base_url: str | None,
        model: str,
        temperature: float,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
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

    def _extract_json(self, text: str) -> Any | None:
        raw = (text or "").strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except Exception:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start : end + 1])
                except Exception:
                    return None
        return None

    async def _chat_completion(
        self,
        *,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        tool_choice: str | None = None,
        purpose: str = "",
        json_mode: bool = True,
        capture_usage: bool = False,
    ) -> Any:
        sem = _get_llm_semaphore()
        async with sem:
            max_retries = max(1, int(os.getenv("LLM_MAX_RETRIES", "4") or "4"))
            base_sleep_s = float(os.getenv("LLM_RETRY_BASE_S", "0.7") or "0.7")
            use_response_format = bool(int(os.getenv("LLM_USE_JSON_RESPONSE_FORMAT", "1") or "1"))

            def build_kwargs(*, include_response_format: bool) -> dict[str, Any]:
                kwargs: dict[str, Any] = {
                    "model": self._model,
                    "messages": messages,
                    "temperature": self._temperature,
                }
                if tools is not None:
                    kwargs["tools"] = tools
                if tool_choice is not None:
                    kwargs["tool_choice"] = tool_choice
                if json_mode and include_response_format and use_response_format:
                    kwargs["response_format"] = {"type": "json_object"}
                return kwargs

            last_err: Exception | None = None
            include_response_format = True

            for attempt in range(1, max_retries + 1):
                try:
                    response = await self._client.chat.completions.create(
                        **build_kwargs(include_response_format=include_response_format)
                    )
                    usage = getattr(response, "usage", None)
                    prompt_tokens = getattr(usage, "prompt_tokens", None)
                    completion_tokens = getattr(usage, "completion_tokens", None)
                    total_tokens = getattr(usage, "total_tokens", None)
                    logger.info(
                        "llm.request_done model=%s purpose=%s messages=%s est_prompt_tokens=%s prompt_tokens=%s completion_tokens=%s total_tokens=%s",
                        self._model,
                        purpose or "",
                        len(messages or []),
                        _estimate_tokens_from_messages(messages),
                        prompt_tokens,
                        completion_tokens,
                        total_tokens,
                    )
                    if capture_usage:
                        return (
                            response,
                            {
                                "prompt_tokens": (int(prompt_tokens) if prompt_tokens is not None else None),
                                "completion_tokens": (int(completion_tokens) if completion_tokens is not None else None),
                                "total_tokens": (int(total_tokens) if total_tokens is not None else None),
                            },
                        )
                    return response
                except APIStatusError as e:
                    status = getattr(e, "status_code", None)
                    if status == 402:
                        raise LLMDisabledError("OpenRouter: insufficient credits. Add credits in OpenRouter settings.")
                    msg = str(e).lower()
                    if status == 400 and include_response_format and "response_format" in msg:
                        include_response_format = False
                        last_err = e
                        continue
                    if status in {408, 409, 425, 429, 500, 502, 503, 504} and attempt < max_retries:
                        sleep_s = base_sleep_s * (2 ** (attempt - 1)) + random.random() * 0.25
                        await asyncio.sleep(min(15.0, sleep_s))
                        last_err = e
                        continue
                    raise
                except (APIConnectionError, APITimeoutError, RateLimitError) as e:  # type: ignore[misc]
                    if attempt < max_retries:
                        sleep_s = base_sleep_s * (2 ** (attempt - 1)) + random.random() * 0.25
                        await asyncio.sleep(min(15.0, sleep_s))
                        last_err = e  # type: ignore[assignment]
                        continue
                    raise

            if last_err is not None:
                raise last_err
            raise RuntimeError("LLM call failed")

    def _serper_tool_schema(self) -> list[dict[str, Any]]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "serper_search",
                    "description": "Google search via Serper.dev. Use this to fetch evidence from the web.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "q": {"type": "string"},
                            "gl": {"type": "string"},
                            "hl": {"type": "string"},
                            "num": {"type": "integer"},
                            "page": {"type": "integer"},
                            "tbs": {"type": "string"},
                            "autocorrect": {"type": "boolean"},
                        },
                        "required": ["q"],
                    },
                },
            }
        ]

    async def _run_serper_planner(
        self,
        *,
        system_prompt: str,
        user_payload: dict[str, Any],
        max_search_calls: int,
        parse_mode: str,
        return_trace: bool = False,
    ) -> dict[str, Any] | list[dict[str, Any]]:
        max_search_calls = max(0, int(max_search_calls or 0))
        serper = SerperClient(
            api_key=settings.serper_api_key or "",
            endpoint=settings.serper_endpoint,
            gl=settings.serper_gl,
            hl=settings.serper_hl,
            num=settings.serper_num,
            qps=settings.serper_qps,
        )

        def _normalize_role_terms(items: list[str]) -> list[str]:
            out: list[str] = []
            seen: set[str] = set()
            for raw in items or []:
                s = str(raw or "").strip()
                if not s:
                    continue
                s = s.replace("|", " ").replace(" OR ", " ").replace("OR", " ")
                s = s.replace('"', " ").replace("'", " ")
                s = s.replace("-", " ")
                s = re.sub(r"\s+", " ", s).strip()
                if not s:
                    continue
                for tok in s.split(" "):
                    t = tok.strip()
                    if not t:
                        continue
                    k = t.lower()
                    if k in seen:
                        continue
                    seen.add(k)
                    out.append(t)
            return out

        def build_default_query() -> str:
            if parse_mode == "company":
                name = str(user_payload.get("company_name_hint") or "").strip()
                loc = str(user_payload.get("location") or "").strip()
                web = str(user_payload.get("website_hint") or "").strip()
                parts = [p for p in [name, loc, web, "website"] if p]
                return " ".join(parts).strip()
            name = str(user_payload.get("company_name") or "").strip()
            loc = str(user_payload.get("location") or "").strip()
            platforms = user_payload.get("platforms") or []
            role_kw = []
            sg = user_payload.get("search_guidance") or {}
            sg = user_payload.get("search_guidance") or {}
            if isinstance(sg, dict) and isinstance(sg.get("role_keywords"), list):
                role_kw = [str(x) for x in sg.get("role_keywords") if str(x).strip()]
            platform = str(platforms[0]).lower() if platforms else "linkedin"
            tpls = {}
            if isinstance(sg, dict) and isinstance(sg.get("platform_query_templates"), dict):
                tpls = sg.get("platform_query_templates") or {}
            tpl = str(tpls.get(platform) or "")
            loc_hint = loc if loc else ""
            roles_terms = _normalize_role_terms(role_kw)[:14] if role_kw else []
            roles = " ".join(roles_terms).strip()
            if tpl:
                return tpl.format(company=name, location_hint=loc_hint, roles=roles).strip()
            kw = roles if roles else "CEO Founder Co Founder Owner President Managing Director General Manager Director"
            return f"linkedin.com/in ({kw}) {name} {loc_hint}".strip()

        try:
            deep_search = bool(user_payload.get("deep_search"))
            max_organic = 8 if deep_search else 4
            max_paa = 6 if deep_search else 0

            plan_messages: list[dict[str, Any]] = []
            plan_usage: dict[str, Any] = {}
            plan_text = ""
            plan_payload: dict[str, Any] | None = None

            queries: list[dict[str, Any]] = []
            if parse_mode == "people":
                def _normalize_deep_hint(raw: str) -> str:
                    s = str(raw or "").strip().strip('"').strip()
                    if not s:
                        return ""
                    try:
                        from urllib.parse import urlparse

                        if re.match(r"^https?://", s, flags=re.IGNORECASE):
                            host = urlparse(s).netloc
                        else:
                            host = ""
                        if host:
                            host = host.lower()
                            host = host[4:] if host.startswith("www.") else host
                            return host.strip()
                    except Exception:
                        pass
                    s = s.replace('"', " ").strip()
                    s = re.sub(r"\s+", " ", s).strip()
                    return s

                company = str(user_payload.get("company_name") or "").strip()
                loc = str(user_payload.get("location") or "").strip()
                web = str(user_payload.get("website") or "").strip()
                ctype = str(user_payload.get("company_type") or "").strip()
                sg = user_payload.get("search_guidance") or {}
                role_kw = []
                if isinstance(sg, dict) and isinstance(sg.get("role_keywords"), list):
                    role_kw = [str(x) for x in sg.get("role_keywords") if str(x).strip()]
                titles = [str(x).strip().strip('"') for x in role_kw if str(x).strip()]
                titles = titles[:5]
                titles_clean = [t.replace('"', "").strip() for t in titles]
                titles_quoted = [f"\"{t}\"" for t in titles_clean if t]
                roles_expr = " OR ".join(titles_quoted)
                company_clean = company.replace('"', "").strip()
                loc_clean = loc.replace('"', "").strip()
                if loc_clean:
                    base_q = f"(\"{company_clean}\") AND ({roles_expr}) AND \"{loc_clean}\"".strip()
                else:
                    base_q = f"(\"{company_clean}\") AND ({roles_expr})".strip()
                queries = [{"q": base_q}]
                if deep_search:
                    deep_hint = _normalize_deep_hint(loc) or _normalize_deep_hint(web) or _normalize_deep_hint(ctype)
                    if deep_hint:
                        queries.append({"q": f"{base_q} OR ({deep_hint})".strip()})
            else:
                planner_input: dict[str, Any] = {
                    "company_name_hint": user_payload.get("company_name_hint") or "",
                    "location": user_payload.get("location") or "",
                    "google_maps_url": user_payload.get("google_maps_url") or "",
                    "website_hint": user_payload.get("website_hint") or "",
                    "search_limit": max_search_calls,
                }

                plan_system = (
                    "You are a search planner. Return only JSON with this shape: "
                    "{\"queries\":[{\"q\":\"...\",\"gl\":\"..\",\"hl\":\"..\",\"num\":10,\"page\":1}],\"notes\":\"\"}. "
                    f"Maximum queries: {max_search_calls}. "
                    "Do NOT include the generic phrase \"decision maker\" or \"decision makers\" in q. "
                    "Prefer platform-specific and title-specific queries."
                )
                plan_messages = [
                    {"role": "system", "content": plan_system},
                    {"role": "user", "content": stable_json_dumps(planner_input)},
                ]
                plan_resp, plan_usage = await self._chat_completion(
                    messages=plan_messages,
                    purpose=f"{parse_mode}.plan",
                    json_mode=True,
                    capture_usage=True,
                )
                plan_text = getattr(plan_resp.choices[0].message, "content", None) or ""
                plan_payload = self._extract_json(plan_text) if plan_text else None

                if isinstance(plan_payload, dict) and isinstance(plan_payload.get("queries"), list):
                    for qobj in plan_payload.get("queries") or []:
                        if isinstance(qobj, dict):
                            q = str(qobj.get("q") or "").strip()
                            if not q:
                                continue
                            queries.append(qobj)
                if not queries:
                    queries = [{"q": build_default_query()}]

            queries = queries[:max_search_calls] if max_search_calls else []

            serper_results: list[dict[str, Any]] = []
            total_serper_chars = 0
            serper_call_timestamp: datetime | None = None
            for qobj in queries:
                q = str(qobj.get("q") or "")
                q = re.sub(r"\bdecision\s+makers?\b", "", q, flags=re.IGNORECASE).strip()
                try:
                    if serper_call_timestamp is None:
                        serper_call_timestamp = datetime.now(timezone.utc)
                    result = await serper.search(
                        q=q,
                        gl=(qobj.get("gl") if isinstance(qobj.get("gl"), str) else None),
                        hl=(qobj.get("hl") if isinstance(qobj.get("hl"), str) else None),
                        num=(qobj.get("num") if isinstance(qobj.get("num"), int) else None),
                        page=(qobj.get("page") if isinstance(qobj.get("page"), int) else None),
                        tbs=(qobj.get("tbs") if isinstance(qobj.get("tbs"), str) else None),
                        autocorrect=(qobj.get("autocorrect") if isinstance(qobj.get("autocorrect"), bool) else None),
                        max_organic=max_organic,
                        max_paa=max_paa,
                    )
                except SerperError as e:
                    result = {"error": str(e)}
                blob = json.dumps(result, ensure_ascii=False)
                total_serper_chars += len(blob)
                serper_results.append({"q": q, "result": result})

            logger.info(
                "serper.batch_done mode=%s queries=%s deep_search=%s total_chars=%s avg_chars=%s",
                parse_mode,
                len(serper_results),
                deep_search,
                total_serper_chars,
                int(total_serper_chars / max(1, len(serper_results))) if serper_results else 0,
            )

            final_payload = dict(user_payload)
            final_payload["serper_results"] = serper_results
            emails_found: list[str] = []
            if parse_mode == "people":
                try:
                    blob = json.dumps(serper_results, ensure_ascii=False)
                except Exception:
                    blob = ""
                found = re.findall(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", blob, flags=re.IGNORECASE)
                seen_emails: set[str] = set()
                for e in found:
                    es = str(e).strip().lower()
                    if not es:
                        continue
                    if es in seen_emails:
                        continue
                    seen_emails.add(es)
                    emails_found.append(es)
                emails_found = emails_found[:25]
                final_payload["emails_found"] = emails_found

            final_messages: list[dict[str, Any]] = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": stable_json_dumps(final_payload)},
            ]
            llm_call_timestamp = datetime.now(timezone.utc)
            final_resp, final_usage = await self._chat_completion(
                messages=final_messages,
                purpose=f"{parse_mode}.final",
                json_mode=True,
                capture_usage=True,
            )
            final_text = getattr(final_resp.choices[0].message, "content", None) or ""
            payload = self._extract_json(final_text)
            trace = {
                "llm_input": {"plan_messages": plan_messages, "final_messages": final_messages},
                "serper_queries": [str(x.get("q") or "") for x in serper_results if isinstance(x, dict)],
                "serper_calls": int(len(serper_results)),
                "llm_calls": (1 if parse_mode == "people" else 2),
                "llm_call_timestamp": (llm_call_timestamp.isoformat() if llm_call_timestamp else None),
                "serper_call_timestamp": (serper_call_timestamp.isoformat() if serper_call_timestamp else None),
                "llm_usage": ({"final": final_usage} if parse_mode == "people" else {"plan": plan_usage, "final": final_usage}),
                "llm_output": ({"final_text": final_text} if parse_mode == "people" else {"plan_text": plan_text, "final_text": final_text}),
            }
            if parse_mode == "company" and isinstance(payload, dict):
                if return_trace:
                    return {"payload": payload, "trace": trace}
                return payload
            if parse_mode == "people" and (isinstance(payload, dict) or isinstance(payload, list)):
                company_obj = _coerce_company(payload)
                if emails_found:
                    items = _coerce_people(payload)
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        if "emails_found" not in it:
                            it["emails_found"] = emails_found
                        elif isinstance(it.get("emails_found"), str):
                            it["emails_found"] = [x.strip() for x in str(it.get("emails_found") or "").split(",") if x.strip()] or emails_found
                        elif isinstance(it.get("emails_found"), list):
                            pass
                        else:
                            it["emails_found"] = emails_found
                        if company_obj and "company_website" not in it and isinstance(company_obj.get("company_website"), str):
                            it["company_website"] = company_obj.get("company_website")
                        if company_obj and "company_type" not in it and isinstance(company_obj.get("company_type"), str):
                            it["company_type"] = company_obj.get("company_type")
                        if company_obj and "company_address" not in it and isinstance(company_obj.get("company_address"), str):
                            it["company_address"] = company_obj.get("company_address")
                        if company_obj and "gmaps_rating" not in it and isinstance(company_obj.get("gmaps_rating"), (int, float)):
                            it["gmaps_rating"] = company_obj.get("gmaps_rating")
                        if company_obj and "gmaps_reviews" not in it and isinstance(company_obj.get("gmaps_reviews"), int):
                            it["gmaps_reviews"] = company_obj.get("gmaps_reviews")
                    payload = items
                elif company_obj:
                    items = _coerce_people(payload)
                    for it in items:
                        if not isinstance(it, dict):
                            continue
                        if "company_website" not in it and isinstance(company_obj.get("company_website"), str):
                            it["company_website"] = company_obj.get("company_website")
                        if "company_type" not in it and isinstance(company_obj.get("company_type"), str):
                            it["company_type"] = company_obj.get("company_type")
                        if "company_address" not in it and isinstance(company_obj.get("company_address"), str):
                            it["company_address"] = company_obj.get("company_address")
                        if "gmaps_rating" not in it and isinstance(company_obj.get("gmaps_rating"), (int, float)):
                            it["gmaps_rating"] = company_obj.get("gmaps_rating")
                        if "gmaps_reviews" not in it and isinstance(company_obj.get("gmaps_reviews"), int):
                            it["gmaps_reviews"] = company_obj.get("gmaps_reviews")
                    payload = items
                if return_trace:
                    return {"payload": payload, "trace": trace}
                return payload
            raise RuntimeError("LLM returned invalid JSON")
        finally:
            await serper.aclose()

    async def research_decision_makers(
        self,
        company_name: str,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        company_type: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
        platforms: list[str] | None = None,
        max_people: int = 3,
        use_web_search: bool = True,
        deep_search: bool = False,
        role_keywords_override: list[str] | None = None,
        max_search_calls: int = 0,
    ) -> list[dict[str, Any]]:
        base_keywords = role_keywords_override if role_keywords_override else decision_maker_query_keywords()
        role_keywords = [str(k).strip().strip('"') for k in base_keywords]
        system = _build_people_system_prompt()

        user = {
            "company_name": company_name,
            "location": location or "",
            "google_maps_url": google_maps_url or "",
            "website": website or "",
            "company_type": company_type or "",
            "search_results": search_results or [],
            "platforms": platforms or [],
            "max_people": max_people,
            "deep_search": bool(deep_search),
            "search_limit": int(max_search_calls or 0),
            "search_guidance": {
                "must_not_include_terms": ["decision maker", "decision makers"],
                "role_keywords": role_keywords,
                "platform_query_templates": {
                    "linkedin": "linkedin.com/in ({roles}) {company} {location_hint}",
                    "google_maps": "google.com/maps ({roles}) {company} {location_hint}",
                    "yelp": "yelp.com ({roles}) {company} {location_hint}",
                    "facebook": "facebook.com ({roles}) {company} {location_hint}",
                    "instagram": "instagram.com ({roles}) {company} {location_hint}",
                    "x": "x.com ({roles}) {company} {location_hint}",
                    "twitter": "x.com ({roles}) {company} {location_hint}",
                    "github": "github.com ({roles}) {company}",
                    "crunchbase": "crunchbase.com ({roles}) {company}",
                },
                "location_hint": "Use the provided location if available, otherwise omit it.",
            },
            "output_schema": {
                "company": {
                    "company_website": "",
                    "company_type": "",
                    "company_address": "",
                    "gmaps_rating": None,
                    "gmaps_reviews": None,
                },
                "people": [
                    {
                        "name": "",
                        "title": "",
                        "platform": "",
                        "profile_url": "",
                        "emails_found": [],
                        "confidence": "HIGH|MEDIUM|LOW",
                    }
                ]
            },
            "constraints": [
                "Only include people you have strong evidence for.",
                "Prefer LinkedIn profile URLs when available.",
                "Confidence must be one of HIGH, MEDIUM, LOW.",
                "Each person title must include at least one leadership keyword from search_guidance.role_keywords.",
                "Each person title must be a real job title (e.g. CEO, Founder, Owner, President, VP, Director). Do not use generic titles like 'Decision Maker'.",
                "Exclude staff/support roles like assistant, intern, coordinator, receptionist, technician, support, customer service, representative, specialist, associate.",
                "If you can infer company website/type/address/rating/reviews from serper_results, put them in output_schema.company; otherwise leave blank/null.",
            ],
        }

        payload = await self._run_serper_planner(system_prompt=system, user_payload=user, max_search_calls=max_search_calls, parse_mode="people")
        return _coerce_people(payload)

    async def research_decision_makers_with_trace(
        self,
        company_name: str,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        company_type: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
        platforms: list[str] | None = None,
        max_people: int = 3,
        use_web_search: bool = True,
        deep_search: bool = False,
        role_keywords_override: list[str] | None = None,
        exclude_profile_urls: list[str] | None = None,
        max_search_calls: int = 0,
    ) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        payload = await self._run_serper_planner(
            system_prompt=_build_people_system_prompt(),
            user_payload={
                "company_name": company_name,
                "location": location or "",
                "google_maps_url": google_maps_url or "",
                "website": website or "",
                "company_type": company_type or "",
                "search_results": search_results or [],
                "platforms": platforms or [],
                "max_people": max_people,
                "deep_search": bool(deep_search),
                "search_limit": int(max_search_calls or 0),
                "exclude_profile_urls": [str(x) for x in (exclude_profile_urls or []) if str(x).strip()],
                "search_guidance": {
                    "must_not_include_terms": ["decision maker", "decision makers"],
                    "role_keywords": [
                        str(k).strip().strip('"')
                        for k in (role_keywords_override if role_keywords_override else decision_maker_query_keywords())
                    ],
                    "platform_query_templates": {
                        "linkedin": "linkedin.com/in ({roles}) {company} {location_hint}",
                        "google_maps": "google.com/maps ({roles}) {company} {location_hint}",
                        "yelp": "yelp.com ({roles}) {company} {location_hint}",
                        "facebook": "facebook.com ({roles}) {company} {location_hint}",
                        "instagram": "instagram.com ({roles}) {company} {location_hint}",
                        "x": "x.com ({roles}) {company} {location_hint}",
                        "twitter": "x.com ({roles}) {company} {location_hint}",
                        "github": "github.com ({roles}) {company}",
                        "crunchbase": "crunchbase.com ({roles}) {company}",
                    },
                    "location_hint": "Use the provided location if available, otherwise omit it.",
                },
                "output_schema": {
                    "company": {
                        "company_website": "",
                        "company_type": "",
                        "company_address": "",
                        "gmaps_rating": None,
                        "gmaps_reviews": None,
                    },
                    "people": [
                        {
                            "name": "",
                            "title": "",
                            "platform": "",
                            "profile_url": "",
                            "emails_found": [],
                            "confidence": "HIGH|MEDIUM|LOW",
                        }
                    ]
                },
                "constraints": [
                    "Only include people you have strong evidence for.",
                    "Prefer LinkedIn profile URLs when available.",
                    "Confidence must be one of HIGH, MEDIUM, LOW.",
                    "Each person title must include at least one leadership keyword from search_guidance.role_keywords.",
                    "Each person title must be a real job title (e.g. CEO, Founder, Owner, President, VP, Director). Do not use generic titles like 'Decision Maker'.",
                    "Exclude staff/support roles like assistant, intern, coordinator, receptionist, technician, support, customer service, representative, specialist, associate.",
                    "Do not return any person whose profile_url is in exclude_profile_urls.",
                ],
            },
            max_search_calls=max_search_calls,
            parse_mode="people",
            return_trace=True,
        )
        if isinstance(payload, dict) and isinstance(payload.get("payload"), (dict, list)) and isinstance(payload.get("trace"), dict):
            return (_coerce_people(payload.get("payload")), payload.get("trace"))
        return (_coerce_people(payload), {})

    async def research_company(
        self,
        company_name: str | None,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
        use_web_search: bool = True,
        max_search_calls: int = 0,
    ) -> dict[str, Any]:
        system = (
            "You are a research assistant. Normalize the company identity from the provided row hints. "
            + "You will be given serper_results (search evidence). Use it to validate the company and website when needed. "
            + f"You may run at most {int(max_search_calls or 0)} searches during planning. "
            + "Return only JSON."
        )

        user = {
            "company_name_hint": (company_name or "").strip(),
            "location": (location or "").strip(),
            "google_maps_url": (google_maps_url or "").strip(),
            "website_hint": (website or "").strip(),
            "search_results": search_results or [],
            "search_limit": int(max_search_calls or 0),
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
        payload = await self._run_serper_planner(system_prompt=system, user_payload=user, max_search_calls=max_search_calls, parse_mode="company")
        company = _coerce_company(payload) or {}
        return {
            "company_name": company.get("company_name", "") or "",
            "company_type": company.get("company_type", "") or "",
            "company_city": company.get("company_city", "") or "",
            "company_country": company.get("company_country", "") or "",
            "company_website": company.get("company_website", "") or "",
        }

    async def research_company_with_trace(
        self,
        company_name: str | None,
        location: str | None = None,
        google_maps_url: str | None = None,
        website: str | None = None,
        search_results: list[dict[str, Any]] | None = None,
        use_web_search: bool = True,
        max_search_calls: int = 0,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        system = (
            "You are a research assistant. Normalize the company identity from the provided row hints. "
            + "You will be given serper_results (search evidence). Use it to validate the company and website when needed. "
            + f"You may run at most {int(max_search_calls or 0)} searches during planning. "
            + "Return only JSON."
        )
        user = {
            "company_name_hint": (company_name or "").strip(),
            "location": (location or "").strip(),
            "google_maps_url": (google_maps_url or "").strip(),
            "website_hint": (website or "").strip(),
            "search_results": search_results or [],
            "search_limit": int(max_search_calls or 0),
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
        payload = await self._run_serper_planner(
            system_prompt=system,
            user_payload=user,
            max_search_calls=max_search_calls,
            parse_mode="company",
            return_trace=True,
        )
        if isinstance(payload, dict) and isinstance(payload.get("payload"), dict) and isinstance(payload.get("trace"), dict):
            company = _coerce_company(payload.get("payload")) or {}
            return (
                {
                    "company_name": company.get("company_name", "") or "",
                    "company_type": company.get("company_type", "") or "",
                    "company_city": company.get("company_city", "") or "",
                    "company_country": company.get("company_country", "") or "",
                    "company_website": company.get("company_website", "") or "",
                },
                payload.get("trace"),
            )
        company = _coerce_company(payload) or {}
        return (
            {
                "company_name": company.get("company_name", "") or "",
                "company_type": company.get("company_type", "") or "",
                "company_city": company.get("company_city", "") or "",
                "company_country": company.get("company_country", "") or "",
                "company_website": company.get("company_website", "") or "",
            },
            {},
        )


def get_llm_client() -> OpenAICompatibleLLM:
    if settings.llm_api_key is None:
        raise LLMDisabledError("LLM is not configured")

    base_url = settings.llm_base_url
    model = settings.llm_model
    if not model:
        raise LLMDisabledError(
            "LLM model is not configured. Set the LLM_MODEL (or OPENROUTER_MODEL) environment variable."
        )
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
