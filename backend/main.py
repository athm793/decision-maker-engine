from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from app.api.endpoints import upload, jobs
from app.core.database import engine, Base
from app.core.auth import enforce_basic_auth_for_request
from app.core.settings import settings
import os

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
