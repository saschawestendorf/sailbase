"""Search: hard filters -> availability -> price -> fit score -> ranking."""

from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models import Base_, Boat
from app.services import availability
from app.services.matching import CrewProfile, score
from app.services.quotes import QuoteError, compute_price


@dataclass(frozen=True)
class SearchQuery:
    start_date: date
    end_date: date
    crew: CrewProfile
    region_slug: str | None = None
    base_id: str | None = None
    boat_class_slug: str | None = None
    min_length_m: float | None = None
    max_length_m: float | None = None
    max_price_cents: int | None = None
    sort: str = "fit"  # fit | price_asc | price_desc | length_desc
    include_unavailable: bool = False
    limit: int = 50


@dataclass
class SearchHit:
    boat: Boat
    available: bool
    unavailable_reason: str = ""
    total_cents: int | None = None
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
        from app.models import Region

        stmt = stmt.join(Region, Base_.region_id == Region.id).where(Region.slug == q.region_slug)
    if q.base_id:
        stmt = stmt.where(Boat.base_id == q.base_id)
    if q.boat_class_slug:
        from app.models import BoatClass

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
        ok, reason = availability.is_available(db, boat, q.start_date, q.end_date)
        if not ok:
            hit.available, hit.unavailable_reason = False, reason
            if not q.include_unavailable:
                continue
        if boat.pricing is not None:
            try:
                res, _ = compute_price(db, boat, q.start_date, q.end_date)
                hit.total_cents = res.total_cents
                hit.per_day_cents = res.per_day_cents
                hit.breakdown = res.to_dict()
            except QuoteError:
                pass
        if q.max_price_cents is not None and hit.total_cents is not None:
            if hit.total_cents > q.max_price_cents:
                continue
        fit = score(boat, q.crew, hit.total_cents)
        hit.fit_score, hit.fit_reasons, hit.blockers = fit.score, fit.reasons, fit.blockers
        if not fit.ok and not q.include_unavailable:
            continue
        hits.append(hit)

    key = {
        "price_asc": lambda h: (h.total_cents is None, h.total_cents or 0),
        "price_desc": lambda h: (h.total_cents is None, -(h.total_cents or 0)),
        "length_desc": lambda h: -h.boat.length_m,
        "fit": lambda h: (-h.fit_score, h.total_cents or 0),
    }.get(q.sort, lambda h: (-h.fit_score, h.total_cents or 0))
    hits.sort(key=key)
    return hits[: max(1, q.limit)]
