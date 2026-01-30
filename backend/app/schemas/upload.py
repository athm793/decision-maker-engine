from pydantic import BaseModel
from typing import List, Dict, Any, Optional

class FilePreviewResponse(BaseModel):
    filename: str
    total_rows: int
    columns: List[str]
    preview_rows: List[Dict[str, Any]]
    suggested_mappings: Dict[str, str]

class ValidationResult(BaseModel):
    valid_count: int
    invalid_count: int
    errors: List[str]
