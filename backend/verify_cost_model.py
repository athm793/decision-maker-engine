from app.services.costs import compute_job_cost_fields


def main() -> None:
    contacts = 50
    llm_input_tokens = 96040
    llm_output_tokens = 20421
    serper_calls = 138

    rates = {
        "input_cost_per_m": 0.02,
        "output_cost_per_m": 0.05,
        "serper_cost_per_1k": 1.0,
    }

    cf = compute_job_cost_fields(
        llm_prompt_tokens=llm_input_tokens,
        llm_completion_tokens=llm_output_tokens,
        serper_calls=serper_calls,
        contacts_found=contacts,
        **rates,
    )

    expected_llm = (llm_input_tokens / 1_000_000.0) * rates["input_cost_per_m"] + (llm_output_tokens / 1_000_000.0) * rates[
        "output_cost_per_m"
    ]
    expected_serper = (serper_calls / 1000.0) * rates["serper_cost_per_1k"]
    expected_total = expected_llm + expected_serper

    expected_llm = round(expected_llm, 6)
    expected_serper = round(expected_serper, 6)
    expected_total = round(expected_total, 6)
    expected_cpc = round(expected_total / contacts, 6)

    assert cf["llm_cost_usd"] == expected_llm
    assert cf["serper_cost_usd"] == expected_serper
    assert cf["total_cost_usd"] == expected_total
    assert cf["cost_per_contact_usd"] == expected_cpc

    print("OK")
    print(f'LLM cost: ${cf["llm_cost_usd"]:.8f}')
    print(f'Serper cost: ${cf["serper_cost_usd"]:.8f}')
    print(f'Total cost: ${cf["total_cost_usd"]:.8f}')
    print(f'Cost/contact: ${cf["cost_per_contact_usd"]:.8f}')


if __name__ == "__main__":
    main()
