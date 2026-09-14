from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, CurrentUser, OptionalUser
from app.core.config import get_settings
from app.models import Base_, Boat, Booking, Quote
from app.schemas.commerce import BookingCreate, BookingCreated, BookingOut, QuoteOut, QuoteRequest
from app.services import bookings as booking_service
from app.services.payments import get_payment_provider
from app.services.quotes import QuoteError, draft_quote, persist_quote, quote_is_valid

router = APIRouter(tags=["commerce"])


def _boat(db, boat_id: str) -> Boat:
    boat = (
        db.execute(
            select(Boat)
            .options(
                selectinload(Boat.pricing),
                selectinload(Boat.base).selectinload(Base_.region),
                selectinload(Boat.charterer),
                selectinload(Boat.boat_class),
            )
            .where(Boat.id == boat_id, Boat.is_active.is_(True))
        )
        .scalars()
        .first()
    )
    if boat is None:
        raise HTTPException(404, "Boot nicht gefunden")
    return boat


@router.post("/quotes", response_model=QuoteOut, status_code=status.HTTP_201_CREATED)
def create_quote(payload: QuoteRequest, db: DB, user: OptionalUser):
    boat = _boat(db, payload.boat_id)
    try:
        draft = draft_quote(db, boat, payload.start_date, payload.end_date, payload.persons)
    except QuoteError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    quote = persist_quote(db, draft, user.id if user else None)
    db.commit()
    return quote


@router.get("/quotes/{quote_id}", response_model=QuoteOut)
def get_quote(quote_id: str, db: DB):
    q = db.get(Quote, quote_id)
    if q is None:
        raise HTTPException(404, "Angebot nicht gefunden")
    return q


@router.post("/bookings", response_model=BookingCreated, status_code=status.HTTP_201_CREATED)
def create_booking(payload: BookingCreate, db: DB, user: OptionalUser, request: Request):
    settings = get_settings()
    quote = db.get(Quote, payload.quote_id)
    if quote is None:
        raise HTTPException(404, "Angebot nicht gefunden")
    if not quote_is_valid(quote):
        raise HTTPException(status.HTTP_409_CONFLICT, "Angebot abgelaufen, bitte neu berechnen")
    if db.query(Booking).filter(Booking.quote_id == quote.id).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "Angebot wurde bereits gebucht")
    boat = _boat(db, quote.boat_id)
    api_base = str(request.base_url).rstrip("/")
    provider = get_payment_provider(api_base)
    try:
        booking, payment = booking_service.create_booking(
            db,
            quote=quote,
            boat=boat,
            customer_email=payload.customer_email.lower(),
            customer_name=payload.customer_name,
            customer_user_id=user.id if user else None,
            provider=provider,
            success_url_template=f"{settings.public_web_url}/booking/{{reference}}?paid=1",
            cancel_url=f"{settings.public_web_url}/boats/{boat.slug}",
        )
    except booking_service.BookingError as e:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    out = BookingOut.model_validate(booking)
    out.boat = boat
    return BookingCreated(booking=out, checkout_url=payment.checkout_url)


@router.get("/bookings/{reference}", response_model=BookingOut)
def get_booking(reference: str, db: DB, email: str | None = None, user: OptionalUser = None):
    """Public lookup by reference + e-mail (guest) or by owner login."""
    b = db.query(Booking).filter(Booking.reference == reference.upper()).one_or_none()
    if b is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    allowed = (user is not None and (user.id == b.customer_user_id or user.role == "admin")) or (
        email is not None and email.lower() == b.customer_email
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Zugriff verweigert")
    out = BookingOut.model_validate(b)
    out.boat = _boat(db, b.boat_id)
    return out


@router.get("/my/bookings", response_model=list[BookingOut])
def my_bookings(db: DB, user: CurrentUser):
    rows = (
        db.query(Booking)
        .filter(Booking.customer_user_id == user.id)
        .order_by(Booking.created_at.desc())
        .all()
    )
    out = []
    for b in rows:
        o = BookingOut.model_validate(b)
        o.boat = db.get(Boat, b.boat_id)
        out.append(o)
    return out


# ------------------------------------------------------------------- webhooks


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(request: Request, db: DB):
    provider = get_payment_provider(str(request.base_url).rstrip("/"))
    if provider.name != "stripe":
        raise HTTPException(404, "Stripe nicht aktiv")
    payload = await request.body()
    event = provider.parse_webhook(payload, request.headers.get("stripe-signature"))
    if event is None:
        raise HTTPException(400, "Ungültiges Event")
    booking_service.apply_payment_event(
        db, provider_ref=event.provider_ref, succeeded=event.succeeded, raw=event.raw
    )
    db.commit()
    return {"ok": True}


@router.get("/webhooks/fake/{provider_ref}", include_in_schema=False)
def fake_webhook(provider_ref: str, db: DB, redirect: str | None = None, fail: bool = False):
    """Development only: simulates the payment provider confirming a checkout."""
    if get_settings().is_production:
        raise HTTPException(404)
    booking = booking_service.apply_payment_event(
        db, provider_ref=provider_ref, succeeded=not fail, raw={"simulated": True}
    )
    db.commit()
    if booking is None:
        raise HTTPException(404, "Zahlung nicht gefunden")
    if redirect:
        return RedirectResponse(redirect)
    return {"ok": True, "booking_reference": booking.reference, "status": booking.status}
