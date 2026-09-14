"""Base-to-base distances and boat location over time (one-way charter support).

With a handful of relevant ports a distance matrix is trivial; we derive it from base coordinates
(great circle x coastal factor) so new bases need no manual data. Override later with a table.
"""

import math
from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AvailabilityBlock, Base_, BlockType, Boat

_EARTH_NM = 3440.065


def great_circle_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
    return 2 * _EARTH_NM * math.asin(math.sqrt(a))


def distance_nm(a: Base_ | None, b: Base_ | None) -> float:
    if a is None or b is None or a.id == b.id:
        return 0.0
    if None in (a.lat, a.lon, b.lat, b.lon):
        return 120.0  # unknown coordinates: conservative default
    return great_circle_nm(a.lat, a.lon, b.lat, b.lon) * get_settings().coastal_route_factor


@dataclass(frozen=True)
class Repositioning:
    nm: float
    days: int
    cost_cents: int


def repositioning(a: Base_ | None, b: Base_ | None) -> Repositioning:
    nm = distance_nm(a, b)
    if nm <= 0:
        return Repositioning(0.0, 0, 0)
    s = get_settings()
    days = max(1, math.ceil(nm / max(1, s.repositioning_nm_per_day)))
    cost = int(round(nm * s.repositioning_cents_per_nm)) + s.repositioning_fixed_cents
    return Repositioning(round(nm, 1), days, cost)


def location_at(db: Session, boat: Boat, on: date) -> str:
    """Base id where the boat is on the morning of `on`: end base of the last block that ended
    on or before that day (bookings carry it), otherwise the home base."""
    last = (
        db.execute(
            select(AvailabilityBlock)
            .where(
                AvailabilityBlock.boat_id == boat.id,
                AvailabilityBlock.end_date <= on,
                AvailabilityBlock.block_type.in_([BlockType.BOOKING.value, BlockType.HOLD.value]),
            )
            .order_by(AvailabilityBlock.end_date.desc())
            .limit(1)
        )
        .scalars()
        .first()
    )
    if last is not None and last.end_base_id:
        return last.end_base_id
    return boat.base_id


def next_block_after(db: Session, boat: Boat, after: date) -> AvailabilityBlock | None:
    return (
        db.execute(
            select(AvailabilityBlock)
            .where(AvailabilityBlock.boat_id == boat.id, AvailabilityBlock.start_date >= after)
            .order_by(AvailabilityBlock.start_date)
            .limit(1)
        )
        .scalars()
        .first()
    )
