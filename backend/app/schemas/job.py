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

class JobResponse(BaseModel):
    id: int
    filename: str
    status: JobStatus
    total_companies: int
    processed_companies: int
    decision_makers_found: int
    created_at: datetime
    
    class Config:
        from_attributes = True
