"""Verified reviews and gallery provenance.

A review exists only for a charter the platform itself saw finish: the entitlement is derived
from the booking on the server, never from a flag the client sends.
"""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Boat,
    BoatImage,
    Booking,
    BookingStatus,
    ImageOrigin,
    Review,
    ReviewStatus,
)
from app.models.entities import utcnow

MAX_GUEST_PHOTOS = 12
# Statuses that prove the guest actually completed the charter.
REVIEWABLE_STATUSES = {BookingStatus.RETURNED.value, BookingStatus.SETTLED.value}


class ReviewError(Exception):
    pass


def charter_month(booking: Booking) -> str:
    return booking.start_date.strftime("%Y-%m")


def may_review(booking: Booking) -> tuple[bool, str]:
    if booking.status not in REVIEWABLE_STATUSES:
        return False, "Bewertung ist erst nach dokumentierter Rückgabe möglich"
    return True, ""


@dataclass
class ReviewInput:
    rating_model: int | None = None
    rating_condition: int | None = None
    rating_service: int | None = None
    rating_care: int | None = None
    rating_cleanliness: int | None = None
    rating_accuracy: int | None = None
    rating_equipment: int | None = None
    rating_organisation: int | None = None
    rating_handover: int | None = None
    title: str = ""
    body: str = ""
    photos: list[str] | None = None


RATING_FIELDS = (
    "rating_model",
    "rating_condition",
    "rating_service",
    "rating_care",
    "rating_cleanliness",
    "rating_accuracy",
    "rating_equipment",
    "rating_organisation",
    "rating_handover",
)


def upsert_review(
    db: Session, booking: Booking, boat: Boat, payload: ReviewInput, author_user_id: str | None
) -> Review:
    ok, reason = may_review(booking)
    if not ok:
        raise ReviewError(reason)
    for f in RATING_FIELDS:
        value = getattr(payload, f)
        if value is not None and not 1 <= value <= 5:
            raise ReviewError("Bewertungen liegen zwischen 1 und 5")
    if all(getattr(payload, f) is None for f in ("rating_model", "rating_condition", "rating_service")):
        raise ReviewError("Mindestens eine der drei Hauptbewertungen ist nötig")

    review = db.execute(select(Review).where(Review.booking_id == booking.id)).scalars().first()
    if review is None:
        review = Review(
            booking_id=booking.id,
            boat_id=boat.id,
            charterer_id=boat.charterer_id,
            model_version_id=boat.model_version_id,
            author_user_id=author_user_id,
            author_name=booking.customer_name,
            charter_month=charter_month(booking),
            status=ReviewStatus.PUBLISHED.value,
            published_at=utcnow(),
        )
        db.add(review)
    for f in RATING_FIELDS:
        setattr(review, f, getattr(payload, f))
    review.title = (payload.title or "")[:255]
    review.body = (payload.body or "")[:5000]
    db.flush()

    if payload.photos is not None:
        _replace_guest_photos(db, review, boat, booking, payload.photos)
    return review


def _replace_guest_photos(db: Session, review: Review, boat: Boat, booking: Booking, urls: list[str]) -> None:
    if len(urls) > MAX_GUEST_PHOTOS:
        raise ReviewError(f"Maximal {MAX_GUEST_PHOTOS} Fotos je Bewertung")
    existing = db.execute(select(BoatImage).where(BoatImage.review_id == review.id)).scalars().all()
    for image in existing:
        db.delete(image)
    db.flush()
    start = _next_sort_order(db, boat.id)
    for offset, url in enumerate(urls):
        db.add(
            BoatImage(
                boat_id=boat.id,
                url=url,
                origin=ImageOrigin.GUEST.value,
                charter_month=charter_month(booking),
                booking_id=booking.id,
                review_id=review.id,
                uploaded_by_user_id=review.author_user_id,
                credit=booking.customer_name,
                sort_order=start + offset,
            )
        )
    db.flush()


def _next_sort_order(db: Session, boat_id: str) -> int:
    rows = db.execute(select(BoatImage.sort_order).where(BoatImage.boat_id == boat_id)).scalars().all()
    return (max(rows) + 1) if rows else 0


def add_owner_images(db: Session, boat: Boat, urls: list[str], captions: list[str] | None = None) -> None:
    """Replaces the provider's own pictures; model and guest photos are untouched."""
    for image in list(boat.gallery):
        if image.origin == ImageOrigin.OWNER.value:
            db.delete(image)
    db.flush()
    order = _next_sort_order(db, boat.id)
    for offset, url in enumerate(urls):
        db.add(
            BoatImage(
                boat_id=boat.id,
                url=url,
                origin=ImageOrigin.OWNER.value,
                caption=(captions or [])[offset] if captions and offset < len(captions) else "",
                sort_order=order + offset,
                credit=boat.charterer.name if boat.charterer else "",
            )
        )
    db.flush()


def public_gallery(boat: Boat) -> list[BoatImage]:
    """Owner photos first, then guest photos newest first, model photos last.

    Operational handover pictures never appear here.
    """
    order = {ImageOrigin.OWNER.value: 0, ImageOrigin.GUEST.value: 1, ImageOrigin.MODEL.value: 2}
    visible = [i for i in boat.gallery if i.is_public and i.origin != ImageOrigin.HANDOVER.value]
    return sorted(
        visible,
        key=lambda i: (
            order.get(i.origin, 3),
            -(i.charter_month and int(i.charter_month.replace("-", "")) or 0),
            i.sort_order,
        ),
    )


@dataclass
class RatingSummary:
    count: int
    overall: float | None
    model: float | None
    condition: float | None
    service: float | None
    details: dict[str, float | None]

    def to_dict(self) -> dict:
        return {
            "count": self.count,
            "overall": self.overall,
            "model": self.model,
            "condition": self.condition,
            "service": self.service,
            "details": self.details,
        }


def summarise(reviews: list[Review]) -> RatingSummary:
    published = [r for r in reviews if r.status == ReviewStatus.PUBLISHED.value]

    def avg(field: str) -> float | None:
        values = [getattr(r, field) for r in published if getattr(r, field) is not None]
        return round(sum(values) / len(values), 2) if values else None

    overalls = [r.overall for r in published if r.overall is not None]
    return RatingSummary(
        count=len(published),
        overall=round(sum(overalls) / len(overalls), 2) if overalls else None,
        model=avg("rating_model"),
        condition=avg("rating_condition"),
        service=avg("rating_service"),
        details={
            "care": avg("rating_care"),
            "cleanliness": avg("rating_cleanliness"),
            "accuracy": avg("rating_accuracy"),
            "equipment": avg("rating_equipment"),
            "organisation": avg("rating_organisation"),
            "handover": avg("rating_handover"),
        },
    )
