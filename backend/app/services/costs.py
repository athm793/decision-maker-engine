from __future__ import annotations

from typing import Any


def llm_cost_usd(*, prompt_tokens: int, completion_tokens: int, input_cost_per_m: float, output_cost_per_m: float) -> float:
    pt = max(0, int(prompt_tokens or 0))
    ct = max(0, int(completion_tokens or 0))
    return (pt / 1_000_000.0) * float(input_cost_per_m) + (ct / 1_000_000.0) * float(output_cost_per_m)


def serper_cost_usd(*, serper_calls: int, cost_per_1k: float) -> float:
    sc = max(0, int(serper_calls or 0))
    return (sc / 1000.0) * float(cost_per_1k)


def safe_round_money(v: float) -> float:
    try:
        return round(float(v), 6)
    except Exception:
        return 0.0


def compute_job_cost_fields(
    *,
    llm_prompt_tokens: int,
    llm_completion_tokens: int,
    serper_calls: int,
    contacts_found: int,
    input_cost_per_m: float,
    output_cost_per_m: float,
    serper_cost_per_1k: float,
) -> dict[str, Any]:
    llm = llm_cost_usd(
        prompt_tokens=llm_prompt_tokens,
        completion_tokens=llm_completion_tokens,
        input_cost_per_m=input_cost_per_m,
        output_cost_per_m=output_cost_per_m,
    )
    serper = serper_cost_usd(serper_calls=serper_calls, cost_per_1k=serper_cost_per_1k)
    total = llm + serper
    denom = max(1, int(contacts_found or 0))
    return {
        "llm_cost_usd": safe_round_money(llm),
        "serper_cost_usd": safe_round_money(serper),
        "total_cost_usd": safe_round_money(total),
        "cost_per_contact_usd": safe_round_money(total / denom),
    }
