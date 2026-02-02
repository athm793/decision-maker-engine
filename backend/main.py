from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.api.endpoints import upload, jobs, billing, account, admin
from app.core.database import engine, Base
from app.core.auth import enforce_basic_auth_for_request
from app.core.settings import settings
import os
from sqlalchemy import inspect, text
import sys
import asyncio

if sys.platform.startswith("win"):
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception:
        pass

app = FastAPI(title="localcontacts.biz API")

# Configure CORS
origins = settings.resolved_cors_origins()
if origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

@app.on_event("startup")
def startup() -> None:
    if settings.basic_auth_enabled and (settings.basic_auth_username is None or settings.basic_auth_password is None):
        raise RuntimeError("Basic Auth is enabled but BASIC_AUTH_USERNAME/BASIC_AUTH_PASSWORD are not set")
    if settings.db_auto_create:
        Base.metadata.create_all(bind=engine)

    inspector = inspect(engine)
    if "jobs" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("jobs")}
        missing: list[tuple[str, str]] = []
        if "user_id" not in existing:
            missing.append(("user_id", "TEXT"))
        if "support_id" not in existing:
            missing.append(("support_id", "TEXT"))
        if "selected_platforms" not in existing:
            missing.append(("selected_platforms", "TEXT"))
        if "max_contacts_total" not in existing:
            missing.append(("max_contacts_total", "INTEGER"))
        if "max_contacts_per_company" not in existing:
            missing.append(("max_contacts_per_company", "INTEGER"))
        if "credits_spent" not in existing:
            missing.append(("credits_spent", "INTEGER"))
        if "stop_reason" not in existing:
            missing.append(("stop_reason", "TEXT"))
        if "options" not in existing:
            missing.append(("options", "TEXT"))
        if "llm_calls_started" not in existing:
            missing.append(("llm_calls_started", "INTEGER"))
        if "llm_calls_succeeded" not in existing:
            missing.append(("llm_calls_succeeded", "INTEGER"))
        if "serper_calls" not in existing:
            missing.append(("serper_calls", "INTEGER"))
        if "llm_prompt_tokens" not in existing:
            missing.append(("llm_prompt_tokens", "INTEGER"))
        if "llm_completion_tokens" not in existing:
            missing.append(("llm_completion_tokens", "INTEGER"))
        if "llm_total_tokens" not in existing:
            missing.append(("llm_total_tokens", "INTEGER"))
        if "llm_cost_usd" not in existing:
            missing.append(("llm_cost_usd", "REAL"))
        if "serper_cost_usd" not in existing:
            missing.append(("serper_cost_usd", "REAL"))
        if "total_cost_usd" not in existing:
            missing.append(("total_cost_usd", "REAL"))
        if "cost_per_contact_usd" not in existing:
            missing.append(("cost_per_contact_usd", "REAL"))

        if missing:
            with engine.begin() as conn:
                for col, col_type in missing:
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"))

    if "decision_makers" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("decision_makers")}
        missing: list[tuple[str, str]] = []
        if "user_id" not in existing:
            missing.append(("user_id", "TEXT"))
        if "company_type" not in existing:
            missing.append(("company_type", "TEXT"))
        if "company_city" not in existing:
            missing.append(("company_city", "TEXT"))
        if "company_country" not in existing:
            missing.append(("company_country", "TEXT"))
        if "company_website" not in existing:
            missing.append(("company_website", "TEXT"))
        if "uploaded_company_data" not in existing:
            missing.append(("uploaded_company_data", "TEXT"))
        if "llm_input" not in existing:
            missing.append(("llm_input", "TEXT"))
        if "serper_queries" not in existing:
            missing.append(("serper_queries", "TEXT"))
        if "llm_output" not in existing:
            missing.append(("llm_output", "TEXT"))

        if missing:
            with engine.begin() as conn:
                for col, col_type in missing:
                    conn.execute(text(f"ALTER TABLE decision_makers ADD COLUMN {col} {col_type}"))

@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    if request.method == "OPTIONS":
        return await call_next(request)

    if settings.supabase_url:
        return await call_next(request)

    try:
        enforce_basic_auth_for_request(request)
    except HTTPException as exc:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=exc.headers,
        )

    return await call_next(request)


# API Routes
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(jobs.router, prefix="/api", tags=["jobs"])
app.include_router(billing.router, prefix="/api", tags=["billing"])
app.include_router(account.router, prefix="/api", tags=["account"])
app.include_router(admin.router, prefix="/api", tags=["admin"])

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# Serve Frontend Static Files (Production Mode)
# Check relative to the backend directory or root depending on where uvicorn runs
# In Docker, we run from /app, so frontend/dist is at /app/frontend/dist
# But uvicorn is running backend.main:app, so CWD might be /app

frontend_dist_path = os.path.join(os.getcwd(), "frontend", "dist")

if os.path.exists(frontend_dist_path):
    # Mount assets
    app.mount("/assets", StaticFiles(directory=os.path.join(frontend_dist_path, "assets")), name="assets")
    
    # Catch-all for SPA
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        # Allow API calls to pass through (though they should be caught by routers above if matched)
        if full_path.startswith("api"):
             return {"message": "API route not found"}

        # Check if specific file exists (e.g. favicon.ico)
        file_path = os.path.join(frontend_dist_path, full_path)
        if os.path.exists(file_path) and os.path.isfile(file_path):
            return FileResponse(file_path)
            
        # Return index.html for everything else
        return FileResponse(os.path.join(frontend_dist_path, "index.html"))

else:
    # Fallback for local development (without dist)
    @app.get("/")
    async def read_root():
        return {"message": "localcontacts.biz API (Frontend not built/served)"}
