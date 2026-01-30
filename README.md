# Decision Maker Discovery Engine

## Product Overview

### Vision Statement
The Decision Maker Discovery Engine automates the discovery of business decision-makers across five social and business platforms: LinkedIn, Google Maps, Yelp, Facebook, and Instagram. Users upload CSV files containing Google Maps business listings; the system hunts down executives, founders, and key personnel using AI-powered analysis of public platform data.

### Product Type
SaaS web application with freemium subscription model. Users access through browser interface; no mobile apps in initial release.

### Target Market
B2B lead generation agencies, sales development representatives, recruiters, business development teams, and marketing agencies requiring contact enrichment at scale.

## Success Metrics

### Primary KPIs
- Decision-maker discovery rate: 70%+ of companies yield at least one verified decision-maker
- Average confidence score: 75+ out of 100
- Processing speed: 50 companies per hour per worker instance
- User retention: 60% monthly active user retention after month three
- Cost per lead: under $0.50 per discovered decision-maker

### Secondary KPIs
- Platform success distribution: LinkedIn 85%, Google Maps 45%, Yelp 30%, Facebook 25%, Instagram 20%
- Average decision-makers per company: 2.3
- Export completion rate: 80% of jobs result in downloaded export file
- API error rate: under 5%
- System uptime: 99.5%

## Tech Stack (Proposed)
- **Frontend**: React (Vite), Tailwind CSS
- **Backend**: Python (FastAPI)
- **Database**: SQLite (Development) / PostgreSQL (Production)
- **AI/Scraping**: Playwright/Selenium, OpenAI API (or similar) for analysis

## Run (Docker)

This builds the frontend and serves it from the FastAPI app on port 8000.

```bash
cp .env.example .env
docker compose up --build
```

Open:
- http://localhost:8000/

To enable Basic Auth in production, set the following in `.env`:

```bash
BASIC_AUTH_ENABLED=true
BASIC_AUTH_USERNAME=your_user
BASIC_AUTH_PASSWORD=your_password
```

## Run (Local dev)

Backend:

```bash
cd backend
python -m uvicorn main:app --reload --port 8000
```

Frontend:

```bash
cd frontend
npm install
npm run dev
```

Open:
- http://localhost:5173/

## Environment Variables

- ENVIRONMENT: development|production (production enables basic auth by default)
- BASIC_AUTH_ENABLED: true|false
- BASIC_AUTH_USERNAME / BASIC_AUTH_PASSWORD
- DATABASE_URL: SQLAlchemy URL (defaults to SQLite file)
- CORS_ALLOW_ORIGINS: comma-separated list or "*" (defaults to localhost dev)
- OpenRouter (recommended)
  - OPENROUTER_API_KEY: OpenRouter API key
  - OPENROUTER_MODEL: e.g. openai/gpt-4o-mini
  - OPENROUTER_SITE_URL / OPENROUTER_APP_NAME: optional headers for OpenRouter attribution
- Generic OpenAI-compatible (advanced)
  - LLM_API_KEY / LLM_BASE_URL / LLM_MODEL / LLM_TEMPERATURE
  - PERPLEXITY_API_KEY: accepted as a legacy alias for LLM_API_KEY
