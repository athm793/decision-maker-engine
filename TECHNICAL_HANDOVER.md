# Technical Handover Documentation: GMaps People Scraper

## 1. Executive Summary

This application is an **AI-Powered Decision Maker Discovery Engine**. Despite the name "GMaps People Scraper," it acts more like an autonomous research agent than a traditional web scraper. It ingests company lists (CSV), uses **Google Search (via Serper)** to find employees, and utilizes **LLMs (OpenAI/OpenRouter)** to analyze search snippets and identify decision-makers (CEOs, Founders, etc.) and their contact info.

**Core Workflow:**
1.  **Ingest**: User uploads a CSV of companies.
2.  **Enrich**: AI normalizes company data (Name, Website, Industry).
3.  **Discover**: AI generates search queries (e.g., `site:linkedin.com/in "CEO" "ExampleCorp"`), executes them via Serper, and parses results to find people.
4.  **Deliver**: Results are saved to a PostgreSQL database and exported as CSV.

---

## 2. Technical Stack Analysis

### Backend
*   **Language**: Python 3.11+
*   **Framework**: [FastAPI](https://fastapi.tiangolo.com/) (Async web framework)
*   **Server**: [Uvicorn](https://www.uvicorn.org/) (ASGI server)
*   **Database**:
    *   **ORM**: [SQLAlchemy](https://www.sqlalchemy.org/) (v2.0+ style)
    *   **Driver**: `psycopg2-binary` (PostgreSQL) or `sqlite` (Dev)
    *   **Migrations**: [Alembic](https://alembic.sqlalchemy.org/)
*   **AI & Search**:
    *   **LLM Client**: `openai` (Python SDK used for both OpenAI and OpenRouter)
    *   **Search API**: [Serper.dev](https://serper.dev/) (Google Search API)
*   **Background Tasks**: Native `FastAPI.BackgroundTasks` + `asyncio`
*   **Utilities**:
    *   `pandas`: CSV processing
    *   `playwright`: (Present in deps but largely superseded by Serper+LLM approach)
    *   `python-dotenv`: Env var management

### Frontend
*   **Language**: JavaScript / JSX (React)
*   **Framework**: [Vite](https://vitejs.dev/) + React 18
*   **Routing**: `react-router-dom` v6
*   **Styling**: [Tailwind CSS](https://tailwindcss.com/) v3
*   **Icons**: `lucide-react`
*   **Auth**: `@supabase/supabase-js` (Client-side auth handling)
*   **HTTP Client**: `axios`

### Infrastructure
*   **Containerization**: Docker (Multi-stage build)
*   **Authentication Service**: [Supabase Auth](https://supabase.com/auth)
*   **Payments**: LemonSqueezy (Webhook integration)
*   **Hosting Target**: Render.com (implied by project history) or any Docker-compatible PaaS.

---

## 3. Detailed Component Architecture

### 3.1 Backend Architecture (`backend/app`)

The backend follows a standard service-layer pattern within FastAPI.

*   **`main.py`**: Entry point. Configures CORS, middleware, and mounts routers.
*   **`api/`**: Controllers.
    *   **`endpoints/jobs.py`**: The core controller. Handles CSV upload (`create_job`), status polling, and result retrieval.
    *   **`endpoints/billing.py`**: Handles LemonSqueezy webhooks for credits.
*   **`core/`**: Infrastructure.
    *   **`config.py` / `settings.py`**: Pydantic-based or class-based settings loading from `.env`.
    *   **`database.py`**: SQLAlchemy `SessionLocal` and `Base` setup.
    *   **`security.py`**: JWT validation middleware (validates Supabase tokens).
*   **`services/`**: Business Logic.
    *   **`scraper.py`**: The orchestrator. Manages the high-level loop of processing companies.
    *   **`llm/client.py`**: Wrapper around OpenAI API. Handles "Planning" (generating queries) and "Analysis" (parsing results).
    *   **`search/serper.py`**: Client for executing Google searches.
    *   **`credits_engine.py`**: Manages user credit deduction logic.
*   **`models/`**: SQLAlchemy Database Models.

### 3.2 Frontend Architecture (`frontend/src`)

*   **`App.jsx`**: Main layout wrapper.
*   **`auth/`**:
    *   `AuthProvider.jsx`: Manages Supabase session state.
    *   `RequireAuth.jsx`: Protected route wrapper.
*   **`pages/`**:
    *   `App.jsx` (Home): Main dashboard. Handles file upload and shows job list.
    *   `JobProgress.jsx`: Shows live status of a running job.
    *   `ResultsTable.jsx`: Displays found decision makers.

### 3.3 Data Flow: The "Job" Lifecycle

1.  **Creation**: User POSTs `multipart/form-data` (CSV) to `/api/jobs`.
    *   Backend creates a `Job` record (status: `QUEUED`).
    *   FastAPI triggers `background_tasks.add_task(process_job_task, job_id)`.
2.  **Processing** (`process_job_task` in `backend/app/api/endpoints/jobs.py`):
    *   Loads CSV rows from `job.companies_data`.
    *   Iterates (with concurrency control) through companies.
    *   **Step A: Enrich**: `ScraperService.enrich_company` calls LLM to normalize name/website.
    *   **Step B: Research**: `ScraperService.process_company` calls `LLM.research_decision_makers`.
        *   LLM "Plan" -> Generates Google Queries.
        *   Serper -> Executes Queries.
        *   LLM "Final" -> Extracts People from search snippets.
    *   **Step C: Save**: `DecisionMaker` records are inserted into DB.
    *   **Step D: Charge**: Credits are deducted from `CreditAccount`.
3.  **Completion**: Job status updates to `COMPLETED`. User downloads CSV.

---

## 4. File-by-File Implementation Review

### Backend Key Files
| File Path | Description |
| :--- | :--- |
| `backend/app/api/endpoints/jobs.py` | **CRITICAL**. Contains the background worker logic (`process_job_task`). It handles the main loop, error handling, and credit deduction. Note the specific Windows `ProactorEventLoop` workaround. |
| `backend/app/services/scraper.py` | **CRITICAL**. The "Brain". Contains `enrich_company` and `process_company`. It manages caching (`TTLCache`) and delegates to the LLM client. |
| `backend/app/services/llm/client.py` | Wrapper around OpenAI API. Handles "Planning" (generating queries) and "Analysis" (parsing results). Implements `OpenAICompatibleLLM`. |
| `backend/app/services/search/serper.py` | Simple wrapper for Serper.dev API. |
| `backend/app/models/job.py` | Defines the `Job` schema. Stores `companies_data` (input) and metrics (tokens used, cost). |
| `backend/app/core/settings.py` | Loads all config. Critical for understanding `LLM_MODEL`, `SERPER_API_KEY`, etc. |

### Frontend Key Files
| File Path | Description |
| :--- | :--- |
| `frontend/src/AppRoutes.jsx` | Defines the routing map (`/login`, `/plans`, `/admin`, `/`). |
| `frontend/src/supabaseClient.js` | Initializes the Supabase JS client. |
| `frontend/src/components/FileUpload.jsx` | Handles CSV parsing and mapping selection (mapping CSV columns to system fields). |
| `frontend/src/components/JobProgress.jsx` | Polls the job status and visualizes progress. |

---

## 5. Known Issues and Technical Debt Inventory

1.  **Memory Scalability (High Impact)**:
    *   **Issue**: `Job.companies_data` stores the entire input CSV as a JSON blob in the database and loads it fully into memory during processing.
    *   **Risk**: Large CSVs (10k+ rows) will cause OOM (Out of Memory) crashes or database bloat.
    *   **Fix**: Move to streaming processing or store input rows in a separate `JobRow` table or S3.

2.  **Windows Specific Workarounds (Medium Impact)**:
    *   **Issue**: `process_job_task` has a `sys.platform.startswith("win")` check to force `ProactorEventLoop`.
    *   **Risk**: Makes the code platform-dependent and harder to test in Linux/Docker environments if not careful.
    *   **Fix**: Standardize on Docker for dev/prod to remove OS-specific hacks.

3.  **Error Handling Granularity (Medium Impact)**:
    *   **Issue**: If the background task crashes hard, the job might remain in `PROCESSING` forever (stale state).
    *   **Fix**: Implement a "Zombie Job" sweeper that checks for jobs stuck in processing for >1 hour.

4.  **Cost Control (Business Impact)**:
    *   **Issue**: The app uses `gpt-4o-mini` or similar. If a user uploads 1000 companies, it fires ~2000-3000 LLM calls and ~2000 Search calls immediately.
    *   **Fix**: Implement strict rate limiting per user or a queue system (Celery/BullMQ) instead of simple `BackgroundTasks`.

---

## 6. Quality of Life Improvements

### Developer Experience
*   **Unified Dev Command**: Currently requires running Backend (`uvicorn`) and Frontend (`vite`) separately. Adding a `make dev` or `docker-compose up` workflow would streamline onboarding.
*   **Type Safety**: The backend uses Pydantic/FastAPI which is good, but `services/scraper.py` has some loose typing (`dict[str, Any]`). Introducing explicit Pydantic models for internal service data passing would reduce runtime errors.

### User Experience
*   **Cost Estimator**: Before starting a job, show the user an estimated cost/credit usage based on row count.
*   **Live Row Preview**: During the "Mapping" phase, show a preview of how the first 5 rows will be parsed.
*   **Detailed Failure Reasons**: If a specific company fails, show *why* (e.g., "No website found", "Search returned 0 results") in the results CSV.

---

## 7. Production Readiness Assessment

*   **Environment Variables**: The app is well-configured via `.env`. Ensure `SERPER_API_KEY`, `LLM_API_KEY`, and `DATABASE_URL` are set in production.
*   **Database**:
    *   **Current**: Uses `sqlite` default in some places, but `psycopg2` is installed.
    *   **Action**: Ensure `DATABASE_URL` points to a real PostgreSQL instance (e.g., Supabase Transaction Pooler port 6543) in production.
*   **Concurrency**:
    *   Controlled by `JOB_CONCURRENCY` env var (default 25). Tune this based on database connection limits.
*   **Logging**:
    *   Basic Python `logging` is used. Recommended to integrate Sentry for error tracking.

---

## 8. Deployment and Infrastructure

### Docker Deployment
The project uses a **Multi-Stage Dockerfile**:
1.  **Build Stage**: Compiles React frontend to static files.
2.  **Runtime Stage**: Installs Python backend, copies compiled frontend to `/app/frontend/dist`.
3.  **Run**: `uvicorn` serves the API, and likely serves the frontend static files (check `main.py` static mounts).

**Build Command:**
```bash
docker build -t gmaps-scraper .
```

**Run Command:**
```bash
docker run -p 8000:8000 --env-file .env gmaps-scraper
```

### CI/CD
*   Currently no CI/CD pipeline definition (GitHub Actions/GitLab CI) was found.
*   **Recommendation**: Create a `.github/workflows/deploy.yml` to build the Docker image and push to a registry (GHCR/DockerHub) on merge to main.

---

## 9. Testing Coverage Analysis

*   **Status**: Minimal to Non-Existent automated tests.
*   **Found**: `scripts/serper_smoke_test.py` and some `verify_*.py` scripts in `backend/`.
*   **Gaps**:
    *   **Unit Tests**: No pytest suite found for core logic (`scraper.py`).
    *   **Integration Tests**: No API tests (`TestClient`).
*   **Action Plan**:
    1.  Install `pytest` and `httpx`.
    2.  Create `backend/tests/`.
    3.  Write a mock test for `ScraperService` that mocks the `LLM` and `Serper` calls to verify logic without spending money.
