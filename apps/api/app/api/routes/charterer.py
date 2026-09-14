import re
from datetime import date, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.api.deps import DB, CurrentCharterer
from app.models import (
    AvailabilityBlock,
    Base_,
    BlockType,
    Boat,
    BoatClass,
    Booking,
    BookingStatus,
    PricingPolicy,
)
from app.schemas.catalog import BoatDetailOut, PricingPolicyOut
from app.schemas.charterer import (
    BlockCreate,
    BlockOut,
    BoatUpsert,
    ChartererOut,
    ChartererStats,
    PricingPolicyUpsert,
)
from app.schemas.commerce import BookingOut
from app.services import availability
from app.services import bookings as booking_service

router = APIRouter(prefix="/charterer", tags=["charterer"])


def _slug(db, name: str, exclude_id: str | None = None) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "boot"
    slug, n = base, 1
    while True:
        q = db.query(Boat).filter(Boat.slug == slug)
        if exclude_id:
            q = q.filter(Boat.id != exclude_id)
        if not q.first():
            return slug
        n += 1
        slug = f"{base}-{n}"


def _own_boat(db, charterer, boat_id: str) -> Boat:
    boat = db.get(Boat, boat_id)
    if boat is None or boat.charterer_id != charterer.id:
        raise HTTPException(404, "Boot nicht gefunden")
    return boat


def _class_for_length(db, length_m: float) -> BoatClass:
    cls = (
        db.execute(
            select(BoatClass).where(BoatClass.min_length_m <= length_m, BoatClass.max_length_m > length_m)
        )
        .scalars()
        .first()
    )
    if cls is None:
        cls = db.execute(select(BoatClass).order_by(BoatClass.max_length_m.desc())).scalars().first()
    if cls is None:
        raise HTTPException(500, "Keine Bootsklassen definiert")
    return cls


@router.get("/me", response_model=ChartererOut)
def charterer_me(charterer: CurrentCharterer):
    return charterer


@router.get("/stats", response_model=ChartererStats)
def charterer_stats(db: DB, charterer: CurrentCharterer):
    boat_ids = [b.id for b in charterer.boats]
    confirmed = pending = revenue = 0
    if boat_ids:
        rows = db.query(Booking).filter(Booking.boat_id.in_(boat_ids)).all()
        for b in rows:
            if b.status == BookingStatus.CONFIRMED.value:
                confirmed += 1
                revenue += b.total_cents
            elif b.status == BookingStatus.PENDING_PAYMENT.value:
                pending += 1
    today = date.today()
    horizon = today + timedelta(days=90)
    occ_total = 0.0
    active = [b for b in charterer.boats if b.is_active]
    for boat in active:
        blocks = availability.overlapping_blocks(db, boat.id, today, horizon)
        nights = sum(
            max(0, (min(bl.end_date, horizon) - max(bl.start_date, today)).days)
            for bl in blocks
            if bl.block_type == BlockType.BOOKING.value
        )
        occ_total += nights / 90
    return ChartererStats(
        boats=len(charterer.boats),
        bookings_confirmed=confirmed,
        bookings_pending=pending,
        revenue_cents=revenue,
        occupancy_next_90d=round(occ_total / len(active), 3) if active else 0.0,
    )


@router.get("/boats", response_model=list[BoatDetailOut])
def list_my_boats(db: DB, charterer: CurrentCharterer):
    return db.query(Boat).filter(Boat.charterer_id == charterer.id).order_by(Boat.name).all()


@router.post("/boats", response_model=BoatDetailOut, status_code=status.HTTP_201_CREATED)
def create_boat(payload: BoatUpsert, db: DB, charterer: CurrentCharterer):
    if db.get(Base_, payload.base_id) is None:
        raise HTTPException(422, "Unbekannter Stützpunkt")
    data = payload.model_dump()
    if not data.get("boat_class_id"):
        data["boat_class_id"] = _class_for_length(db, payload.length_m).id
    boat = Boat(charterer_id=charterer.id, slug=_slug(db, payload.name), **data)
    db.add(boat)
    db.commit()
    db.refresh(boat)
    return boat


@router.put("/boats/{boat_id}", response_model=BoatDetailOut)
def update_boat(boat_id: str, payload: BoatUpsert, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    data = payload.model_dump()
    if not data.get("boat_class_id"):
        data["boat_class_id"] = _class_for_length(db, payload.length_m).id
    for k, v in data.items():
        setattr(boat, k, v)
    if boat.name != payload.name:
        boat.slug = _slug(db, payload.name, exclude_id=boat.id)
    db.commit()
    db.refresh(boat)
    return boat


@router.put("/boats/{boat_id}/pricing", response_model=PricingPolicyOut)
def upsert_pricing(boat_id: str, payload: PricingPolicyUpsert, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    policy = boat.pricing or PricingPolicy(boat_id=boat.id, **payload.model_dump())
    for k, v in payload.model_dump().items():
        setattr(policy, k, v)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


@router.get("/boats/{boat_id}/blocks", response_model=list[BlockOut])
def list_blocks(boat_id: str, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    availability.purge_expired_holds(db)
    db.commit()
    return (
        db.query(AvailabilityBlock)
        .filter(AvailabilityBlock.boat_id == boat.id)
        .order_by(AvailabilityBlock.start_date)
        .all()
    )


@router.post("/boats/{boat_id}/blocks", response_model=BlockOut, status_code=201)
def create_block(boat_id: str, payload: BlockCreate, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    conflicts = [
        b
        for b in availability.overlapping_blocks(db, boat.id, payload.start_date, payload.end_date)
        if b.block_type in (BlockType.BOOKING.value, BlockType.HOLD.value)
    ]
    if conflicts:
        raise HTTPException(status.HTTP_409_CONFLICT, "Zeitraum enthält Buchungen")
    block = AvailabilityBlock(boat_id=boat.id, **payload.model_dump())
    db.add(block)
    db.commit()
    db.refresh(block)
    return block


@router.delete("/boats/{boat_id}/blocks/{block_id}", status_code=204)
def delete_block(boat_id: str, block_id: str, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    block = db.get(AvailabilityBlock, block_id)
    if block is None or block.boat_id != boat.id:
        raise HTTPException(404, "Block nicht gefunden")
    if block.block_type in (BlockType.BOOKING.value, BlockType.HOLD.value):
        raise HTTPException(status.HTTP_409_CONFLICT, "Buchungsblöcke können nicht gelöscht werden")
    db.delete(block)
    db.commit()


@router.get("/bookings", response_model=list[BookingOut])
def list_bookings(db: DB, charterer: CurrentCharterer):
    boat_ids = [b.id for b in charterer.boats]
    if not boat_ids:
        return []
    booking_service.expire_stale_bookings(db)
    db.commit()
    rows = db.query(Booking).filter(Booking.boat_id.in_(boat_ids)).order_by(Booking.start_date.desc()).all()
    out = []
    for b in rows:
        o = BookingOut.model_validate(b)
        o.boat = db.get(Boat, b.boat_id)
        out.append(o)
    return out


@router.post("/bookings/{booking_id}/cancel", response_model=BookingOut)
def cancel(booking_id: str, db: DB, charterer: CurrentCharterer):
    b = db.get(Booking, booking_id)
    if b is None or b.boat_id not in {x.id for x in charterer.boats}:
        raise HTTPException(404, "Buchung nicht gefunden")
    try:
        booking_service.cancel_booking(db, b)
    except booking_service.BookingError as e:
        raise HTTPException(status.HTTP_409_CONFLICT, str(e)) from e
    db.commit()
    o = BookingOut.model_validate(b)
    o.boat = db.get(Boat, b.boat_id)
    return o
