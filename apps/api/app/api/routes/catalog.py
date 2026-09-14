from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models import Base_, Boat, BoatClass, Region
from app.schemas.catalog import (
    BaseOut,
    BoatClassOut,
    BoatDetailOut,
    CalendarDay,
    CalendarOut,
    RegionOut,
)
from app.services.offers import OfferContext

router = APIRouter(tags=["catalog"])


@router.get("/regions", response_model=list[RegionOut])
def list_regions(db: DB):
    return db.execute(select(Region).order_by(Region.name)).scalars().all()


@router.get("/bases", response_model=list[BaseOut])
def list_bases(db: DB, region: str | None = None):
    stmt = select(Base_).options(selectinload(Base_.region)).order_by(Base_.name)
    if region:
        stmt = stmt.join(Region).where(Region.slug == region)
    return db.execute(stmt).scalars().all()


@router.get("/boat-classes", response_model=list[BoatClassOut])
def list_boat_classes(db: DB):
    return db.execute(select(BoatClass).order_by(BoatClass.min_length_m)).scalars().all()


def _load_boat(db, slug_or_id: str) -> Boat:
    stmt = (
        select(Boat)
        .options(
            selectinload(Boat.pricing),
            selectinload(Boat.base).selectinload(Base_.region),
            selectinload(Boat.boat_class),
            selectinload(Boat.charterer),
        )
        .where((Boat.slug == slug_or_id) | (Boat.id == slug_or_id), Boat.is_active.is_(True))
    )
    boat = db.execute(stmt).scalars().first()
    if boat is None:
        raise HTTPException(404, "Boot nicht gefunden")
    return boat


@router.get("/boats/{slug}", response_model=BoatDetailOut)
def get_boat(slug: str, db: DB):
    return _load_boat(db, slug)


@router.get("/boats/{slug}/calendar", response_model=CalendarOut)
def boat_calendar(
    slug: str,
    db: DB,
    start: date | None = None,
    days: int = Query(default=60, ge=1, le=180),
    nights: int | None = Query(default=None, ge=1, le=60),
    pickup_base_id: str | None = None,
    dropoff_base_id: str | None = None,
):
    """Per-day start price for a stay of `nights` starting on that day (a hotel-style calendar)."""
    boat = _load_boat(db, slug)
    start = start or date.today()
    nights = nights or max(1, boat.min_days)
    out: list[CalendarDay] = []
    if boat.pricing is None:
        for i in range(days):
            d = start + timedelta(days=i)
            out.append(CalendarDay(date=d, available=False, per_day_cents=None, reason="Kein Preis"))
        return CalendarOut(boat_id=boat.id, nights=nights, days=out)
    ctx = OfferContext(
        db,
        boat,
        start,
        start + timedelta(days=days + nights),
        pickup_base_id=pickup_base_id,
        dropoff_base_id=dropoff_base_id,
    )
    for i in range(days):
        d = start + timedelta(days=i)
        e = d + timedelta(days=nights)
        ok, reason = ctx.is_free(d, e)
        price = total = None
        if ok:
            try:
                res, _gap, offer, note = ctx.price(d, e)
            except ValueError:
                ok, reason = False, "Kein Preis"
            else:
                if offer:
                    price, total = res.per_day_cents, res.total_cents
                else:
                    ok, reason = False, note
        out.append(CalendarDay(date=d, available=ok, per_day_cents=price, total_cents=total, reason=reason))
    return CalendarOut(boat_id=boat.id, nights=nights, days=out)
