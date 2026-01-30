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

COMPANY_NAME_NEGATIVE = ["url", "website", "web", "domain", "http", "link"]

def detect_column_mapping(columns: list) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    used_cols: set[str] = set()

    def score(target: str, col: str) -> int:
        c = col.lower()
        s = 0
        for kw in COLUMN_KEYWORDS.get(target, []):
            if c == kw:
                s += 50
            if kw in c:
                s += 10

        if target == "company_name":
            if any(bad in c for bad in COMPANY_NAME_NEGATIVE):
                s -= 100
            if "company" in c:
                s += 25
            if c in {"name", "company"}:
                s += 25

        if target in {"website", "google_maps_url"}:
            if any(k in c for k in ["url", "http", "www", "link"]):
                s += 15
        return s

    for target_field in COLUMN_KEYWORDS.keys():
        best_match = None
        best_score = -10**9
        for col in columns:
            if col in used_cols:
                continue
            sc = score(target_field, col)
            if sc > best_score:
                best_score = sc
                best_match = col

        if best_match and best_score > 0:
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
