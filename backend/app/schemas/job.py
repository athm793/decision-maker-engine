from pydantic import BaseModel
from typing import Dict, List, Any, Optional
from datetime import datetime
from enum import Enum

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class JobCreate(BaseModel):
    filename: str
    mappings: Dict[str, str]
    file_content: List[Dict[str, Any]] # Passing full content for now (MVP)
    selected_platforms: List[str] = ["google_maps", "linkedin"]
    max_contacts_total: int = 50
    max_contacts_per_company: int = 1
    deep_search: bool = False

class JobResponse(BaseModel):
    id: int
    filename: str
    status: JobStatus
    total_companies: int
    processed_companies: int
    decision_makers_found: int
    selected_platforms: Optional[List[str]] = None
    max_contacts_total: Optional[int] = None
    max_contacts_per_company: Optional[int] = None
    credits_spent: Optional[int] = None
    stop_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
