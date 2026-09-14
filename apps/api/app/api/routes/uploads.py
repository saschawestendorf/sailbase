"""Photo/document uploads. Local disk for the MVP behind a tiny interface; swap for S3 later."""

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.api.deps import CurrentUser
from app.core.config import get_settings
from app.schemas.ops import UploadOut

router = APIRouter(tags=["uploads"])

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
MAX_BYTES = 12 * 1024 * 1024


def upload_dir() -> Path:
    d = Path(get_settings().upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


@router.post("/uploads", response_model=UploadOut, status_code=201)
async def upload(file: UploadFile, request: Request, user: CurrentUser):
    ext = ALLOWED.get(file.content_type or "")
    if ext is None:
        raise HTTPException(415, "Nur JPEG, PNG, WebP oder PDF")
    data = await file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Datei zu groß (max. 12 MB)")
    if not data:
        raise HTTPException(422, "Leere Datei")
    safe = re.sub(r"[^a-zA-Z0-9_.-]", "_", (file.filename or "upload"))[:60]
    name = f"{uuid.uuid4().hex}_{safe}"
    if not name.endswith(ext):
        name += ext
    (upload_dir() / name).write_bytes(data)
    url = f"{str(request.base_url).rstrip('/')}/media/{name}"
    return UploadOut(url=url, filename=name, size=len(data))
