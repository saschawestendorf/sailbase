"""Availability checks and comparable-boat occupancy (demand signal)."""

from datetime import date, datetime, timedelta

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import AvailabilityBlock, Base_, BlockType, Boat
from app.models.entities import utcnow
from app.services.matching.competitive import similarity

_BLOCKING_TYPES = {
    BlockType.BOOKING.value,
    BlockType.HOLD.value,
    BlockType.MAINTENANCE.value,
    BlockType.OWNER_USE.value,
    BlockType.CLOSED.value,
}


def _active_block_filter(now: datetime):
    """Blocks count unless they are expired holds."""
    return or_(
        AvailabilityBlock.block_type != BlockType.HOLD.value,
        AvailabilityBlock.expires_at.is_(None),
        AvailabilityBlock.expires_at > now,
    )


def purge_expired_holds(db: Session, now: datetime | None = None) -> int:
    now = now or utcnow()
    rows = (
        db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.block_type == BlockType.HOLD.value,
                AvailabilityBlock.expires_at.is_not(None),
                AvailabilityBlock.expires_at <= now,
            )
        )
        .scalars()
        .all()
    )
    for r in rows:
        db.delete(r)
    if rows:
        db.flush()
    return len(rows)


def overlapping_blocks(
    db: Session, boat_id: str, start: date, end: date, now: datetime | None = None
) -> list[AvailabilityBlock]:
    """Blocks intersecting [start, end). Half-open intervals: overlap iff s < end and e > start."""
    now = now or utcnow()
    return list(
        db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.boat_id == boat_id,
                AvailabilityBlock.start_date < end,
                AvailabilityBlock.end_date > start,
                _active_block_filter(now),
            )
        )
        .scalars()
        .all()
    )


def is_available(db: Session, boat: Boat, start: date, end: date) -> tuple[bool, str]:
    """Hard availability + charter-rule check. Returns (ok, reason)."""
    if end <= start:
        return False, "Enddatum muss nach Startdatum liegen"
    nights = (end - start).days
    if nights < max(1, boat.min_days):
        return False, f"Mindestdauer {boat.min_days} Nächte"
    if boat.changeover_weekdays:
        allowed = {int(d) for d in boat.changeover_weekdays}
        if start.weekday() not in allowed or end.weekday() not in allowed:
            return False, "Wechseltag nicht erlaubt"
    pad = timedelta(days=max(0, boat.turnaround_days))
    if overlapping_blocks(db, boat.id, start - pad, end + pad):
        return False, "Zeitraum nicht verfügbar"
    return True, ""


def comparable_occupancy(
    db: Session, boat: Boat, start: date, end: date, now: datetime | None = None
) -> float:
    """Similarity-weighted share of booked/held boat-nights in the window.

    Eligible = same boat class, same region, active. Includes the boat itself.
    Overlapping blocks count once per boat; non-demand blocks do not count.
    Returns 0..1. Robust to empty sets (returns 0).
    """
    now = now or utcnow()
    nights = (end - start).days
    if nights <= 0:
        return 0.0
    comparable_boats = (
        db.execute(
            select(Boat)
            .join(Base_, Boat.base_id == Base_.id)
            .where(
                Boat.is_active.is_(True),
                Boat.boat_class_id == boat.boat_class_id,
                Base_.region_id == boat.base.region_id,
            )
        )
        .scalars()
        .all()
    )
    weights = {b.id: 1.0 if b.id == boat.id else similarity(boat, b) for b in comparable_boats}
    if not weights:
        return 0.0

    blocks = (
        db.execute(
            select(AvailabilityBlock).where(
                AvailabilityBlock.boat_id.in_(weights),
                AvailabilityBlock.start_date < end,
                AvailabilityBlock.end_date > start,
                AvailabilityBlock.block_type.in_([BlockType.BOOKING.value, BlockType.HOLD.value]),
                _active_block_filter(now),
            )
        )
        .scalars()
        .all()
    )

    intervals: dict[str, list[tuple[date, date]]] = {}
    for b in blocks:
        intervals.setdefault(b.boat_id, []).append((max(b.start_date, start), min(b.end_date, end)))
    blocked_nights = 0.0
    for boat_id, ranges in intervals.items():
        last_end = start
        for s, e in sorted(ranges):
            blocked_nights += weights[boat_id] * max(0, (e - max(s, last_end)).days)
            last_end = max(last_end, e)
    capacity = sum(weights.values()) * nights
    return min(1.0, blocked_nights / capacity) if capacity else 0.0
