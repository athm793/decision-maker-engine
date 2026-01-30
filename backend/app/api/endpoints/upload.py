from fastapi import APIRouter, UploadFile, File, HTTPException
from app.schemas.upload import FilePreviewResponse
import pandas as pd
import io
from typing import Dict

router = APIRouter()

COLUMN_KEYWORDS = {
    "company_name": ["company", "name", "business", "organization"],
    "google_maps_url": ["maps", "url", "link", "google"],
    "industry": ["industry", "category", "sector"],
    "location": ["location", "city", "address", "state", "country"],
    "website": ["website", "site", "web"]
}

def detect_column_mapping(columns: list) -> Dict[str, str]:
    mapping = {}
    used_cols = set()
    
    for target_field, keywords in COLUMN_KEYWORDS.items():
        best_match = None
        
        # Exact match first
        for col in columns:
            if col.lower() in keywords and col not in used_cols:
                best_match = col
                break
        
        # Partial match if no exact match
        if not best_match:
            for col in columns:
                if col not in used_cols and any(k in col.lower() for k in keywords):
                    best_match = col
                    break
        
        if best_match:
            mapping[target_field] = best_match
            used_cols.add(best_match)
            
    return mapping

@router.post("/upload/preview", response_model=FilePreviewResponse)
async def upload_preview(file: UploadFile = File(...)):
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        # Try UTF-8 first, then Latin-1
        try:
            df = pd.read_csv(io.BytesIO(content), encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(io.BytesIO(content), encoding='latin-1')
            
        if df.empty:
            raise HTTPException(status_code=400, detail="The CSV file is empty")
            
        columns = df.columns.tolist()
        total_rows = len(df)
        preview_rows = df.head(5).fillna("").to_dict(orient='records')
        suggested_mappings = detect_column_mapping(columns)
        
        return FilePreviewResponse(
            filename=file.filename,
            total_rows=total_rows,
            columns=columns,
            preview_rows=preview_rows,
            suggested_mappings=suggested_mappings
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
