from app.services.archive.scraper_playwright import _build_deep_search_queries


def main() -> None:
    qs = _build_deep_search_queries(
        company_name="Acme Inc",
        location="New York, United States",
        selected_platforms=["linkedin", "facebook", "instagram"],
        website="https://acme.example",
        query_keywords=None,
    )
    assert any("site:linkedin.com/in" in q for q in qs), qs
    assert any("site:facebook.com" in q for q in qs), qs
    assert any("leadership OR management OR executives OR team" in q for q in qs), qs


if __name__ == "__main__":
    main()
    print("OK")
