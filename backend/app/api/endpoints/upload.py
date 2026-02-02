from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from app.schemas.upload import FilePreviewResponse
from app.core.security import get_current_user
import io
import csv
from typing import Dict

router = APIRouter(dependencies=[Depends(get_current_user)])

COLUMN_KEYWORDS = {
    "company_name": ["company", "name", "business", "organization"],
    "industry": ["industry", "category", "sector"],
    "city": ["city", "town"],
    "country": ["country", "nation"],
    "location": ["location", "address", "state", "region", "province"],
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

        if target in {"website"}:
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


def _decode_csv_bytes(content: bytes) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        return content.decode("latin-1")


def _build_preview(text: str) -> tuple[list[str], int, list[dict[str, str]]]:
    reader = csv.DictReader(io.StringIO(text))
    columns = [str(c).strip() for c in (reader.fieldnames or []) if str(c).strip()]
    if not columns:
        raise HTTPException(status_code=400, detail="The CSV file has no header row")

    preview_rows: list[dict[str, str]] = []
    total_rows = 0
    for row in reader:
        total_rows += 1
        if len(preview_rows) < 5:
            preview_rows.append({col: str(row.get(col) or "").strip() for col in columns})

    return columns, total_rows, preview_rows


@router.post("/upload/preview", response_model=FilePreviewResponse)
async def upload_preview(file: UploadFile = File(...)):
    if not file.filename.endswith(('.csv', '.CSV')):
        raise HTTPException(status_code=400, detail="Only CSV files are allowed")
    
    try:
        content = await file.read()
        if not content:
            raise HTTPException(status_code=400, detail="The CSV file is empty")

        text = _decode_csv_bytes(content)
        columns, total_rows, preview_rows = _build_preview(text)
        suggested_mappings = detect_column_mapping(columns)
        
        return FilePreviewResponse(
            filename=file.filename,
            total_rows=total_rows,
            columns=columns,
            preview_rows=preview_rows,
            suggested_mappings=suggested_mappings
        )
        
    except Exception as e:
        if isinstance(e, HTTPException):
            raise
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")
