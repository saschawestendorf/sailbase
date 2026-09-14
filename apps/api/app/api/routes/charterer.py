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
    BoatImage,
    Booking,
    BookingStatus,
    ModelVersion,
    PricingPolicy,
)
from app.schemas.catalog import BoatDetailOut, PricingPolicyOut
from app.schemas.catalog_master import BoatFromCatalog
from app.schemas.charterer import (
    BlockCreate,
    BlockOut,
    BoatUpsert,
    CalendarGap,
    ChartererOut,
    ChartererStats,
    PricingPolicyUpsert,
)
from app.schemas.commerce import BookingOut
from app.schemas.revenue import PolicyProposal, SimulationOut
from app.services import availability
from app.services import bookings as booking_service
from app.services import catalog as catalog_service
from app.services import revenue as revenue_service
from app.services import reviews as review_service
from app.services.slugs import unique_slug

router = APIRouter(prefix="/charterer", tags=["charterer"])


def _slug(db, name: str, exclude_id: str | None = None) -> str:
    def taken(candidate: str) -> bool:
        q = db.query(Boat).filter(Boat.slug == candidate)
        if exclude_id:
            q = q.filter(Boat.id != exclude_id)
        return q.first() is not None

    return unique_slug(name, taken, fallback="boot")


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
    confirmed = pending = settled = nights = revenue = static = commission = 0
    service_cost = payouts_pending = 0
    if boat_ids:
        rows = db.query(Booking).filter(Booking.boat_id.in_(boat_ids)).all()
        for b in rows:
            if b.status == BookingStatus.PENDING_PAYMENT.value:
                pending += 1
            elif b.status in BookingStatus.active():
                confirmed += 1
                if b.status == BookingStatus.SETTLED.value:
                    settled += 1
                n = (b.end_date - b.start_date).days
                nights += n
                revenue += b.total_cents
                static += b.static_price_cents or b.total_cents
                commission += b.commission_cents
                service_cost += sum(
                    o.price_cents for o in b.service_orders if o.status == "done" and o.partner_id
                )
                if b.payout and b.payout.status == "pending":
                    payouts_pending += b.payout.net_cents
    today = date.today()
    horizon = today + timedelta(days=90)
    occ_total = 0.0
    gaps: list[CalendarGap] = []
    active = [b for b in charterer.boats if b.is_active]
    for boat in active:
        blocks = sorted(
            availability.overlapping_blocks(db, boat.id, today, horizon), key=lambda x: x.start_date
        )
        booked_nights = sum(
            max(0, (min(bl.end_date, horizon) - max(bl.start_date, today)).days)
            for bl in blocks
            if bl.block_type == BlockType.BOOKING.value
        )
        occ_total += booked_nights / 90
        # free gaps between blocks
        cursor = today
        for bl in blocks:
            if bl.start_date > cursor:
                g = (bl.start_date - cursor).days
                gaps.append(
                    CalendarGap(
                        boat_id=boat.id,
                        boat_name=boat.name,
                        start_date=cursor,
                        end_date=bl.start_date,
                        nights=g,
                        sellable=g >= boat.min_days,
                    )
                )
            cursor = max(cursor, bl.end_date)
        if cursor < horizon:
            g = (horizon - cursor).days
            gaps.append(
                CalendarGap(
                    boat_id=boat.id,
                    boat_name=boat.name,
                    start_date=cursor,
                    end_date=horizon,
                    nights=g,
                    sellable=g >= boat.min_days,
                )
            )
    gaps.sort(key=lambda g: (g.sellable, g.start_date))
    return ChartererStats(
        boats=len(charterer.boats),
        bookings_confirmed=confirmed,
        bookings_pending=pending,
        bookings_settled=settled,
        charter_nights=nights,
        revenue_cents=revenue,
        static_revenue_cents=static,
        dynamic_uplift_cents=revenue - static,
        avg_price_per_night_cents=round(revenue / nights) if nights else 0,
        commission_cents=commission,
        service_cost_cents=service_cost,
        payouts_pending_cents=payouts_pending,
        occupancy_next_90d=round(occ_total / len(active), 3) if active else 0.0,
        gaps_next_90d=gaps[:50],
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


# --------------------------------------------------------------- listing from the catalog

# Owner-supplied fields that are not part of the catalog selection.
_OWN_FIELDS = (
    "name",
    "base_id",
    "year_refit",
    "listing_mode",
    "description",
    "required_license",
    "required_experience_nm",
    "min_days",
    "max_days",
    "allowed_nights",
    "min_lead_days",
    "turnaround_days",
    "changeover_weekdays",
    "handover_options",
    "one_way_enabled",
    "one_way_base_ids",
    "one_way_fee_cents",
    "deposit_cents",
    "cleaning_fee_cents",
    "region_restrictions",
    "documents",
    "insurance",
    "is_active",
)


def _apply_catalog(db, boat: Boat, payload: BoatFromCatalog) -> Boat:
    """Copy the resolved specification onto the boat.

    The snapshot is deliberate: pricing, matching and contracts read these columns, so a later
    catalog correction cannot change what a guest already booked.
    """
    if db.get(Base_, payload.base_id) is None:
        raise HTTPException(422, "Unbekannter Stützpunkt")
    try:
        version = catalog_service.load_version(db, payload.version_id)
        variants = catalog_service.validate_selection(
            version, payload.year_built, payload.variant_ids
        ) or catalog_service.default_variants(version)
    except catalog_service.CatalogError as e:
        raise HTTPException(422, str(e)) from e

    spec = catalog_service.resolve(version, variants, payload.spec_overrides)
    boat.model_version_id = version.id
    boat.variant_ids = [v.id for v in variants]
    boat.spec_overrides = {k: v for k, v in (payload.spec_overrides or {}).items() if v is not None}
    boat.spec_sources = spec.sources
    boat.unknown_specs = spec.unknown
    boat.manufacturer = version.model.manufacturer.name
    boat.model = version.model.name
    boat.year_built = payload.year_built
    for field, value in spec.values.items():
        if value is not None:
            setattr(boat, field, value)
    boat.boat_class_id = _class_for_length(db, float(spec.values.get("length_m") or 0)).id

    features = list(spec.features)
    for extra in payload.extra_features:
        if extra not in features:
            features.append(extra)
    boat.features = features
    boat.character = payload.character or spec.character

    for field in _OWN_FIELDS:
        setattr(boat, field, getattr(payload, field))
    return boat


def _sync_gallery(db, boat: Boat, payload: BoatFromCatalog, version_images: list[str]) -> None:
    review_service.add_owner_images(db, boat, payload.images, payload.image_captions)
    # Model photos stay marked as model photos; they never stand in for the actual boat.
    existing_model = {i.url for i in boat.gallery if i.origin == "model"}
    for offset, url in enumerate(version_images):
        if url in existing_model:
            continue
        db.add(
            BoatImage(
                boat_id=boat.id,
                url=url,
                origin="model",
                caption="Modellfoto des Herstellers",
                credit="Hersteller",
                sort_order=1000 + offset,
            )
        )
    boat.images = payload.images or list(version_images)
    db.flush()


@router.post("/boats/from-catalog", response_model=BoatDetailOut, status_code=status.HTTP_201_CREATED)
def create_boat_from_catalog(payload: BoatFromCatalog, db: DB, charterer: CurrentCharterer):
    boat = Boat(charterer_id=charterer.id, slug=_slug(db, payload.name), length_m=0)
    _apply_catalog(db, boat, payload)
    db.add(boat)
    db.flush()
    version = db.get(ModelVersion, boat.model_version_id)
    _sync_gallery(db, boat, payload, list(version.model_images or []) if version else [])
    db.commit()
    db.refresh(boat)
    return boat


@router.put("/boats/{boat_id}/from-catalog", response_model=BoatDetailOut)
def update_boat_from_catalog(boat_id: str, payload: BoatFromCatalog, db: DB, charterer: CurrentCharterer):
    boat = _own_boat(db, charterer, boat_id)
    previous_name = boat.name
    _apply_catalog(db, boat, payload)
    if previous_name != payload.name:
        boat.slug = _slug(db, payload.name, exclude_id=boat.id)
    version = db.get(ModelVersion, boat.model_version_id)
    _sync_gallery(db, boat, payload, list(version.model_images or []) if version else [])
    db.commit()
    db.refresh(boat)
    return boat


# ------------------------------------------------------------------ revenue simulation


@router.post("/boats/{boat_id}/pricing/simulate", response_model=SimulationOut)
def simulate_pricing(boat_id: str, payload: PolicyProposal, db: DB, charterer: CurrentCharterer):
    """What a proposed rule would earn per available boat day over the year, before saving it."""
    boat = _own_boat(db, charterer, boat_id)
    if boat.pricing is None and payload.reference_price_cents is None:
        raise HTTPException(422, "Für dieses Boot ist noch keine Preisregel hinterlegt")
    try:
        proposal = payload.merged_policy(boat)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    comparison = revenue_service.compare(
        db,
        boat,
        proposal,
        start=payload.start,
        days=payload.days,
        demand_level=payload.demand_level,
    )
    return SimulationOut(**comparison.to_dict())
