"""Verified reviews: readable by anyone, writable only by the guest who completed the charter."""

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB, OptionalUser
from app.models import Boat, BoatImage, Booking, Review, ReviewStatus
from app.schemas.reviews import (
    RatingSummaryOut,
    ReviewEligibility,
    ReviewOut,
    ReviewsOut,
    ReviewSubmit,
)
from app.services import reviews as review_service

router = APIRouter(tags=["reviews"])


def review_out(db: DB | None, review: Review, photos: list[str] | None = None) -> ReviewOut:
    out = ReviewOut.model_validate(review)
    out.photos = photos if photos is not None else []
    return out


def _photos_by_review(db, review_ids: list[str]) -> dict[str, list[str]]:
    if not review_ids:
        return {}
    rows = (
        db.execute(
            select(BoatImage).where(BoatImage.review_id.in_(review_ids)).order_by(BoatImage.sort_order)
        )
        .scalars()
        .all()
    )
    out: dict[str, list[str]] = {}
    for row in rows:
        out.setdefault(row.review_id, []).append(row.url)
    return out


@router.get("/boats/{slug}/reviews", response_model=ReviewsOut)
def boat_reviews(slug: str, db: DB, limit: int = 50):
    boat = (
        db.execute(select(Boat).options(selectinload(Boat.reviews)).where(Boat.slug == slug))
        .scalars()
        .first()
    )
    if boat is None:
        raise HTTPException(404, "Boot nicht gefunden")
    published = [r for r in boat.reviews if r.status == ReviewStatus.PUBLISHED.value]
    published.sort(key=lambda r: r.published_at or r.created_at, reverse=True)
    photos = _photos_by_review(db, [r.id for r in published[:limit]])
    return ReviewsOut(
        summary=RatingSummaryOut(**review_service.summarise(boat.reviews).to_dict()),
        reviews=[review_out(db, r, photos.get(r.id, [])) for r in published[:limit]],
    )


def _booking_for_guest(db, reference: str, user, email: str | None) -> Booking:
    booking = db.execute(select(Booking).where(Booking.reference == reference.upper())).scalars().first()
    if booking is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    allowed = (user is not None and (user.id == booking.customer_user_id or user.role == "admin")) or (
        email is not None and email.lower() == booking.customer_email
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Zugriff verweigert")
    return booking


@router.get("/bookings/{reference}/review", response_model=ReviewEligibility)
def review_status(reference: str, db: DB, user: OptionalUser, email: str | None = None):
    booking = _booking_for_guest(db, reference, user, email)
    may, reason = review_service.may_review(booking)
    existing = db.execute(select(Review).where(Review.booking_id == booking.id)).scalars().first()
    photos = _photos_by_review(db, [existing.id]) if existing else {}
    return ReviewEligibility(
        may_review=may,
        reason=reason,
        existing=review_out(db, existing, photos.get(existing.id, [])) if existing else None,
    )


@router.put("/bookings/{reference}/review", response_model=ReviewOut)
def submit_review(
    reference: str, payload: ReviewSubmit, db: DB, user: OptionalUser, email: str | None = None
):
    """Entitlement comes from the booking on the server; a client-set label would prove nothing."""
    booking = _booking_for_guest(db, reference, user, email)
    boat = db.get(Boat, booking.boat_id)
    if boat is None:
        raise HTTPException(404, "Boot nicht gefunden")
    try:
        review = review_service.upsert_review(
            db,
            booking,
            boat,
            review_service.ReviewInput(**payload.model_dump()),
            user.id if user else None,
        )
    except review_service.ReviewError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    photos = _photos_by_review(db, [review.id])
    return review_out(db, review, photos.get(review.id, []))
