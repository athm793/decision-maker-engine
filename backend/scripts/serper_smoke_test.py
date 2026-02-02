from dotenv import load_dotenv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv(".env")

import asyncio
import json

from app.services.llm.client import OpenAICompatibleLLM


class _Fn:
    def __init__(self, name: str, arguments: str) -> None:
        self.name = name
        self.arguments = arguments


class _ToolCall:
    def __init__(self, id_: str, fn: _Fn) -> None:
        self.id = id_
        self.function = fn


class _Msg:
    def __init__(self, content: str | None, tool_calls: list[_ToolCall] | None = None) -> None:
        self.content = content
        self.tool_calls = tool_calls or []


class _Choice:
    def __init__(self, msg: _Msg) -> None:
        self.message = msg


class _Resp:
    def __init__(self, msg: _Msg) -> None:
        self.choices = [_Choice(msg)]


class MockLLM(OpenAICompatibleLLM):
    def __init__(self) -> None:
        super().__init__(api_key="x", base_url="https://openrouter.ai/api/v1", model="mock", temperature=0.0)
        self._n = 0

    async def _chat_completion(self, *, messages, tools=None, tool_choice=None, purpose=""):
        self._n += 1
        if self._n == 1 and "plan" in str(purpose):
            payload = {"queries": [{"q": "OpenAI official website", "gl": "us"}], "notes": ""}
            return _Resp(_Msg(json.dumps(payload)))
        payload = {
            "company": {
                "company_name": "OpenAI",
                "company_type": "AI research and deployment company",
                "company_city": "San Francisco",
                "company_country": "United States",
                "company_website": "https://openai.com",
            }
        }
        return _Resp(_Msg(json.dumps(payload)))


async def main() -> None:
    llm = MockLLM()
    out = await llm._run_serper_planner(
        system_prompt="Return only JSON.",
        user_payload={"company_name_hint": "OpenAI", "location": "", "google_maps_url": "", "website_hint": "", "deep_search": False},
        max_search_calls=0,
        parse_mode="company",
    )
    print(out)


asyncio.run(main())
