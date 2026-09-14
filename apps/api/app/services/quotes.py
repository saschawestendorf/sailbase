"""Quote service: availability + demand + pricing + gap logic -> persisted, time-limited offer."""

from dataclasses import dataclass
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import Boat, PricingMode, Quote
from app.models.entities import utcnow
from app.services.offers import OfferContext
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
    gap: dict
    pickup_base_id: str | None = None
    dropoff_base_id: str | None = None


def compute_price(
    db: Session, boat: Boat, start: date, end: date, today: date | None = None
) -> tuple[PriceResult, float]:
    """Price for an (assumed available) window, gap logic included. No persistence."""
    if boat.pricing is None:
        raise QuoteError("Boot hat keine Preisregel")
    ctx = OfferContext(db, boat, start, end, today=today)
    try:
        result, _gap, offer, note = ctx.price(start, end)
    except ValueError as e:
        raise QuoteError(str(e)) from e
    if not offer:
        raise QuoteError(note or "Zeitraum wird nicht angeboten")
    return result, ctx.occupancy


def draft_quote(
    db: Session,
    boat: Boat,
    start: date,
    end: date,
    persons: int,
    pickup_base_id: str | None = None,
    dropoff_base_id: str | None = None,
) -> QuoteDraft:
    if persons < 1:
        raise QuoteError("Mindestens eine Person")
    if boat.max_persons and persons > boat.max_persons:
        raise QuoteError(f"Maximal {boat.max_persons} Personen")
    if boat.pricing is None:
        raise QuoteError("Boot hat keine Preisregel")
    ctx = OfferContext(db, boat, start, end, pickup_base_id=pickup_base_id, dropoff_base_id=dropoff_base_id)
    ok, reason = ctx.is_free(start, end)
    if not ok:
        raise QuoteError(reason)
    try:
        result, gap, offer, note = ctx.price(start, end)
    except ValueError as e:
        raise QuoteError(str(e)) from e
    if not offer:
        raise QuoteError(note or "Zeitraum wird nicht angeboten")
    _loc, pickup, dropoff = ctx.legs(start)
    return QuoteDraft(boat, start, end, persons, result, ctx.occupancy, gap, pickup, dropoff)


_BALANCE_DUE_DAYS_BEFORE_START = 30


def persist_quote(db: Session, draft: QuoteDraft, user_id: str | None) -> Quote:
    settings = get_settings()
    now = utcnow()
    days_until_start = (draft.start_date - now.date()).days
    deposit = max(1, round(draft.result.total_cents * settings.deposit_percent / 100))
    if days_until_start <= _BALANCE_DUE_DAYS_BEFORE_START:
        deposit = draft.result.total_cents
    q = Quote(
        boat_id=draft.boat.id,
        user_id=user_id,
        start_date=draft.start_date,
        end_date=draft.end_date,
        persons=draft.persons,
        pickup_base_id=draft.pickup_base_id,
        dropoff_base_id=draft.dropoff_base_id,
        currency=draft.result.currency,
        total_cents=draft.result.total_cents,
        breakdown={
            **draft.result.to_dict(),
            "occupancy": draft.occupancy,
            "gap": draft.gap,
            "deposit_cents": deposit,
        },
        expires_at=now + timedelta(minutes=settings.quote_ttl_minutes),
    )
    db.add(q)
    db.flush()
    return q


def quote_is_valid(q: Quote, now: datetime | None = None) -> bool:
    return q.expires_at > (now or utcnow())


def static_price_cents(boat: Boat, start: date, end: date) -> int:
    """What a classic fixed seasonal tariff would have charged (for owner dashboards)."""
    policy = boat.pricing
    if policy is None:
        return 0
    inp = PricingInput(
        boat_id=boat.id,
        mode=PricingMode.FIXED,
        reference_price_cents=policy.reference_price_cents,
        floor_price_cents=policy.floor_price_cents,
        ceiling_price_cents=policy.ceiling_price_cents,
        start_date=start,
        end_date=end,
        today=start,
        season_curve=(boat.base.region.season_curve or None) if boat.base else None,
        cleaning_fee_cents=boat.cleaning_fee_cents,
        currency=policy.currency,
    )
    return PricingEngine().price(inp).total_cents
