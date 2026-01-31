from pathlib import Path

from app.services.llm.client import DEFAULT_LLM_CONCURRENCY


def main() -> None:
    assert DEFAULT_LLM_CONCURRENCY == 500

    repo = Path(__file__).resolve().parents[1]
    jobs_py = (repo / "backend" / "app" / "api" / "endpoints" / "jobs.py").read_text(encoding="utf-8")
    assert "Platform Source URL" not in jobs_py
    assert "limit: int = 50" in jobs_py
    assert ".order_by(DecisionMaker.id.asc())" in jobs_py

    app_jsx = (repo / "frontend" / "src" / "App.jsx").read_text(encoding="utf-8")
    assert "useState(50)" in app_jsx


if __name__ == "__main__":
    main()
    print("OK")

