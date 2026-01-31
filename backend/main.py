from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.api.endpoints import upload, jobs
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

app = FastAPI(title="Decision Maker Discovery Engine API")

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

        if missing:
            with engine.begin() as conn:
                for col, col_type in missing:
                    conn.execute(text(f"ALTER TABLE jobs ADD COLUMN {col} {col_type}"))

    if "decision_makers" in inspector.get_table_names():
        existing = {c["name"] for c in inspector.get_columns("decision_makers")}
        missing: list[tuple[str, str]] = []
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

        if missing:
            with engine.begin() as conn:
                for col, col_type in missing:
                    conn.execute(text(f"ALTER TABLE decision_makers ADD COLUMN {col} {col_type}"))

    if "credit_state" in inspector.get_table_names():
        with engine.begin() as conn:
            row = conn.execute(text("SELECT id, balance FROM credit_state WHERE id = 1")).fetchone()
            if row is None:
                initial = int(os.getenv("CREDITS_INITIAL_BALANCE", "10000") or "10000")
                conn.execute(text("INSERT INTO credit_state (id, balance) VALUES (1, :b)"), {"b": initial})


@app.middleware("http")
async def basic_auth_middleware(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    if request.method == "OPTIONS":
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
        return {"message": "Decision Maker Discovery Engine API (Frontend not built/served)"}
