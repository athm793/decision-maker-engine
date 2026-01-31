import sys


def main() -> None:
    import app.services.scraper as runtime_scraper

    assert hasattr(runtime_scraper, "ScraperService")
    assert "playwright" not in sys.modules, list(sys.modules.keys())[:50]
    assert "playwright.async_api" not in sys.modules, list(sys.modules.keys())[:50]


if __name__ == "__main__":
    main()
    print("OK")

