"""Quote service: availability + demand + pricing -> persisted, time-limited price offer."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Boat, PricingMode, Quote
from app.models.entities import utcnow
from app.services import availability
from app.services.pricing import PriceResult, PricingEngine, PricingInput


class QuoteError(Exception):
    pass


@dataclass
class QuoteDraft:
    boat: Boat
    start_date: date
    end_date: date
    persons: int
    result: PriceResult
    occupancy: float


def compute_price(
    db: Session,
    boat: Boat,
    start: date,
    end: date,
    today: date | None = None,
    engine: PricingEngine | None = None,
) -> tuple[PriceResult, float]:
    """Pure price computation for an (assumed available) window. No persistence."""
    if boat.pricing is None:
        raise QuoteError("Boot hat keine Preisregel")
    today = today or utcnow().date()
    occ = availability.comparable_occupancy(db, boat, start, end)
    policy = boat.pricing
    inp = PricingInput(
        boat_id=boat.id,
        mode=PricingMode(policy.mode),
        reference_price_cents=policy.reference_price_cents,
        floor_price_cents=policy.floor_price_cents,
        ceiling_price_cents=policy.ceiling_price_cents,
        start_date=start,
        end_date=end,
        today=today,
        season_curve=boat.base.region.season_curve or None,
        occupancy=occ,
        cleaning_fee_cents=boat.cleaning_fee_cents,
        currency=policy.currency,
        overrides=policy.overrides or None,
    )
    return (engine or PricingEngine()).price(inp), occ


def draft_quote(db: Session, boat: Boat, start: date, end: date, persons: int) -> QuoteDraft:
    ok, reason = availability.is_available(db, boat, start, end)
    if not ok:
        raise QuoteError(reason)
    if persons < 1:
        raise QuoteError("Mindestens eine Person")
    if boat.max_persons and persons > boat.max_persons:
        raise QuoteError(f"Maximal {boat.max_persons} Personen")
    result, occ = compute_price(db, boat, start, end)
    return QuoteDraft(boat, start, end, persons, result, occ)


def persist_quote(db: Session, draft: QuoteDraft, user_id: str | None) -> Quote:
    settings = get_settings()
    q = Quote(
        boat_id=draft.boat.id,
        user_id=user_id,
        start_date=draft.start_date,
        end_date=draft.end_date,
        persons=draft.persons,
        currency=draft.result.currency,
        total_cents=draft.result.total_cents,
        breakdown={**draft.result.to_dict(), "occupancy": draft.occupancy},
        expires_at=utcnow() + timedelta(minutes=settings.quote_ttl_minutes),
    )
    db.add(q)
    db.flush()
    return q


def quote_is_valid(q: Quote, now: datetime | None = None) -> bool:
    return q.expires_at > (now or utcnow())
