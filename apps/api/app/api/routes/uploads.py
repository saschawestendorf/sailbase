"""Photo/document uploads. Local disk for the MVP behind a tiny interface; swap for S3 later."""

import re
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request, UploadFile

from app.api.deps import DB, CurrentUser, OptionalUser
from app.core.config import get_settings
from app.schemas.ops import UploadOut

router = APIRouter(tags=["uploads"])

ALLOWED = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "application/pdf": ".pdf"}
MAX_BYTES = 12 * 1024 * 1024


def upload_dir() -> Path:
    d = Path(get_settings().upload_dir)
    d.mkdir(parents=True, exist_ok=True)
    return d


async def _store(file: UploadFile, request: Request) -> UploadOut:
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
    return UploadOut(
        url=f"{str(request.base_url).rstrip('/')}/media/{name}",
        filename=name,
        size=len(data),
    )


@router.post("/uploads", response_model=UploadOut, status_code=201)
async def upload(file: UploadFile, request: Request, user: CurrentUser):
    return await _store(file, request)


@router.post("/bookings/{reference}/uploads", response_model=UploadOut, status_code=201)
async def guest_upload(
    reference: str,
    file: UploadFile,
    request: Request,
    db: DB,
    user: OptionalUser,
    email: str | None = None,
):
    """Guests have no account, so the booking itself is what proves they may upload."""
    from app.models import Booking

    booking = db.query(Booking).filter(Booking.reference == reference.upper()).one_or_none()
    if booking is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    allowed = (user is not None and (user.id == booking.customer_user_id or user.role == "admin")) or (
        email is not None and email.lower() == booking.customer_email
    )
    if not allowed:
        raise HTTPException(403, "Zugriff verweigert")
    return await _store(file, request)
