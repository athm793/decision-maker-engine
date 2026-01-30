from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from app.api.endpoints import upload, jobs
from app.core.database import engine, Base
import os

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Decision Maker Discovery Engine API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
