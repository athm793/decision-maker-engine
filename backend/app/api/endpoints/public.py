from __future__ import annotations

from fastapi import APIRouter

from app.core.settings import settings


router = APIRouter()


@router.get("/public-config")
async def public_config() -> dict:
    return {
        "supabaseUrl": settings.supabase_url or "",
        "supabaseAnonKey": settings.supabase_anon_key or "",
    }

