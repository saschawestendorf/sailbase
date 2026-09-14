"""Search: hard filters -> flexible offers (availability + price + gap logic) -> fit score -> ranking."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Base_, Boat, BoatClass, Region
from app.services.matching import CrewProfile, score
from app.services.offers import Offer, OfferContext


@dataclass(frozen=True)
class SearchQuery:
    window_start: date
    window_end: date
    min_nights: int
    max_nights: int
    crew: CrewProfile
    region_slug: str | None = None
    base_id: str | None = None  # home base filter
    pickup_base_id: str | None = None  # location-aware: where the crew wants to start
    dropoff_base_id: str | None = None  # one-way: where the crew wants to end
    boat_class_slug: str | None = None
    min_length_m: float | None = None
    max_length_m: float | None = None
    sort: str = "fit"  # fit | price_asc | price_desc | length_desc
    include_unavailable: bool = False
    offers_per_boat: int = 5
    limit: int = 50

    @property
    def exact(self) -> bool:
        return self.min_nights == self.max_nights == (self.window_end - self.window_start).days


@dataclass
class SearchHit:
    boat: Boat
    available: bool
    unavailable_reason: str = ""
    offers: list[Offer] = field(default_factory=list)
    total_cents: int | None = None  # best offer
    per_day_cents: int | None = None
    breakdown: dict = field(default_factory=dict)
    fit_score: float = 0.0
    fit_reasons: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)


def _candidates(db: Session, q: SearchQuery) -> list[Boat]:
    stmt = (
        select(Boat)
        .join(Base_, Boat.base_id == Base_.id)
        .options(
            selectinload(Boat.pricing),
            selectinload(Boat.base).selectinload(Base_.region),
            selectinload(Boat.boat_class),
            selectinload(Boat.charterer),
        )
        .where(Boat.is_active.is_(True))
    )
    if q.region_slug:
        stmt = stmt.join(Region, Base_.region_id == Region.id).where(Region.slug == q.region_slug)
    if q.base_id:
        stmt = stmt.where(Boat.base_id == q.base_id)
    if q.boat_class_slug:
        stmt = stmt.join(BoatClass, Boat.boat_class_id == BoatClass.id).where(
            BoatClass.slug == q.boat_class_slug
        )
    if q.min_length_m is not None:
        stmt = stmt.where(Boat.length_m >= q.min_length_m)
    if q.max_length_m is not None:
        stmt = stmt.where(Boat.length_m <= q.max_length_m)
    return list(db.execute(stmt).scalars().unique().all())


def search(db: Session, q: SearchQuery) -> list[SearchHit]:
    hits: list[SearchHit] = []
    for boat in _candidates(db, q):
        hit = SearchHit(boat=boat, available=True)
        if boat.pricing is None:
            hit.available, hit.unavailable_reason = False, "Kein Preis hinterlegt"
        else:
            ctx = OfferContext(
                db,
                boat,
                q.window_start,
                q.window_end,
                pickup_base_id=q.pickup_base_id,
                dropoff_base_id=q.dropoff_base_id,
            )
            if q.exact:
                ok, reason = ctx.is_free(q.window_start, q.window_end)
                if ok:
                    try:
                        res, gap, offer, note = ctx.price(q.window_start, q.window_end)
                    except ValueError as e:
                        ok, reason = False, str(e)
                    else:
                        if offer:
                            _loc, pickup, dropoff = ctx.legs(q.window_start)
                            hit.offers = [
                                Offer(
                                    q.window_start,
                                    q.window_end,
                                    res.nights,
                                    res.per_day_cents,
                                    res.total_cents,
                                    {**res.to_dict(), "occupancy": ctx.occupancy},
                                    gap,
                                    note,
                                    pickup_base_id=pickup,
                                    dropoff_base_id=dropoff,
                                )
                            ]
                        else:
                            ok, reason = False, note
                if not ok:
                    hit.available, hit.unavailable_reason = False, reason
            else:
                offers, _rejected = ctx.offers(
                    q.window_start, q.window_end, q.min_nights, q.max_nights, limit=q.offers_per_boat
                )
                hit.offers = offers
                if not offers:
                    hit.available, hit.unavailable_reason = False, "Kein passendes Angebot im Zeitraum"
        if hit.offers:
            best = hit.offers[0]
            hit.total_cents, hit.per_day_cents, hit.breakdown = (
                best.total_cents,
                best.per_day_cents,
                best.breakdown,
            )
        if not hit.available and not q.include_unavailable:
            continue
        fit = score(boat, q.crew, hit.total_cents)
        hit.fit_score, hit.fit_reasons, hit.blockers = fit.score, fit.reasons, fit.blockers
        if not fit.ok and not q.include_unavailable:
            continue
        hits.append(hit)

    key = {
        "price_asc": lambda h: (h.per_day_cents is None, h.per_day_cents or 0),
        "price_desc": lambda h: (h.per_day_cents is None, -(h.per_day_cents or 0)),
        "length_desc": lambda h: -h.boat.length_m,
        "fit": lambda h: (-h.fit_score, h.per_day_cents or 0),
    }.get(q.sort, lambda h: (-h.fit_score, h.per_day_cents or 0))
    hits.sort(key=key)
    return hits[: max(1, q.limit)]
