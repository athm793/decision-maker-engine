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
    selected_platforms: List[str] = ["linkedin"]
    deep_search: bool = False
    job_titles: Optional[List[str]] = None

class JobResponse(BaseModel):
    id: int
    user_id: Optional[str] = None
    support_id: Optional[str] = None
    filename: str
    status: JobStatus
    total_companies: int
    processed_companies: int
    decision_makers_found: int
    llm_calls_started: Optional[int] = None
    llm_calls_succeeded: Optional[int] = None
    serper_calls: Optional[int] = None
    llm_prompt_tokens: Optional[int] = None
    llm_completion_tokens: Optional[int] = None
    llm_total_tokens: Optional[int] = None
    llm_cost_usd: Optional[float] = None
    serper_cost_usd: Optional[float] = None
    total_cost_usd: Optional[float] = None
    cost_per_contact_usd: Optional[float] = None
    selected_platforms: Optional[List[str]] = None
    max_contacts_total: Optional[int] = None
    max_contacts_per_company: Optional[int] = None
    credits_spent: Optional[int] = None
    stop_reason: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True
