"""Offer generation: turns a boat + a search window into economically sensible, priced offers.

Exact-date search is the special case min_nights == max_nights == window length.
All availability logic here runs in memory on a pre-loaded block list so that hundreds of
candidate (start, nights) combinations per boat stay cheap.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import AvailabilityBlock, Base_, BlockType, Boat, PricingMode, PricingStrategy
from app.services import availability, routing
from app.services.pricing import PriceResult, PricingEngine, PricingInput
from app.services.pricing.engine import _interpolated_season
from app.services.pricing.gap import FreeWindow, GapInput, apply_to_price, evaluate
from app.services.pricing.params import PricingParams

MAX_CANDIDATES_PER_BOAT = 400


@dataclass
class Offer:
    start_date: date
    end_date: date
    nights: int
    per_day_cents: int
    total_cents: int
    breakdown: dict
    gap: dict = field(default_factory=dict)
    note: str = ""
    pickup_base_id: str | None = None
    dropoff_base_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "nights": self.nights,
            "per_day_cents": self.per_day_cents,
            "total_cents": self.total_cents,
            "breakdown": self.breakdown,
            "gap": self.gap,
            "note": self.note,
            "pickup_base_id": self.pickup_base_id,
            "dropoff_base_id": self.dropoff_base_id,
        }


@dataclass
class RejectedOffer:
    start_date: date
    end_date: date
    reason: str


class OfferContext:
    """Per-boat cache: blocks, occupancy, season curve, policy. Built once per search."""

    def __init__(
        self,
        db: Session,
        boat: Boat,
        window_start: date,
        window_end: date,
        today: date | None = None,
        engine: PricingEngine | None = None,
        pickup_base_id: str | None = None,
        dropoff_base_id: str | None = None,
    ):
        self.db = db
        self.boat = boat
        self.today = today or date.today()
        self.engine = engine or PricingEngine()
        pad = timedelta(days=max(0, boat.turnaround_days) + 1)
        self.blocks = sorted(
            availability.overlapping_blocks(db, boat.id, window_start - pad, window_end + pad),
            key=lambda b: b.start_date,
        )
        self.occupancy = availability.comparable_occupancy(db, boat, window_start, window_end)
        self.season_curve = (boat.base.region.season_curve or None) if boat.base else None
        self.policy = boat.pricing
        # One-way support: where is the boat, where does the crew want it
        self.location_at_window_start = routing.location_at(db, boat, window_start)
        self.requested_pickup = pickup_base_id
        self.requested_dropoff = dropoff_base_id
        self._bases: dict[str, Base_] = {}
        self._next_after_window: AvailabilityBlock | None = routing.next_block_after(db, boat, window_end)

    # ---- location helpers
    def base(self, base_id: str | None) -> Base_ | None:
        if not base_id:
            return None
        if base_id not in self._bases:
            self._bases[base_id] = self.db.get(Base_, base_id)
        return self._bases[base_id]

    def location_at(self, start: date) -> str:
        loc = self.location_at_window_start
        for b in self.blocks:
            if b.end_date <= start and b.block_type in (BlockType.BOOKING.value, BlockType.HOLD.value):
                if b.end_base_id:
                    loc = b.end_base_id
        return loc

    def legs(self, start: date) -> tuple[str, str, str]:
        """(location, pickup, dropoff) base ids for a candidate starting on `start`."""
        location = self.location_at(start)
        pickup = self.requested_pickup or location
        dropoff = self.requested_dropoff or pickup
        return location, pickup, dropoff

    def _next_block(self, end: date) -> AvailabilityBlock | None:
        for b in self.blocks:
            if b.start_date >= end:
                return b
        return self._next_after_window

    def _prev_block(self, start: date) -> AvailabilityBlock | None:
        prev = None
        for b in self.blocks:
            if b.end_date <= start:
                prev = b
        return prev

    def _dropoff_allowed(self, dropoff: str) -> bool:
        boat = self.boat
        if boat.one_way_base_ids:
            return dropoff in set(boat.one_way_base_ids)
        target = self.base(dropoff)
        return target is not None and boat.base is not None and target.region_id == boat.base.region_id

    # ---- availability in memory
    def is_free(self, start: date, end: date) -> tuple[bool, str]:
        boat = self.boat
        nights = (end - start).days
        if nights < max(1, boat.min_days):
            return False, f"Mindestdauer {boat.min_days} Nächte"
        if boat.max_days and nights > boat.max_days:
            return False, f"Maximal {boat.max_days} Nächte"
        if boat.allowed_nights and nights not in {int(n) for n in boat.allowed_nights}:
            return False, "Dauer nicht angeboten"
        if (start - self.today).days < max(0, boat.min_lead_days):
            return False, f"Mindestvorlauf {boat.min_lead_days} Tage"
        if boat.changeover_weekdays:
            allowed = {int(d) for d in boat.changeover_weekdays}
            if start.weekday() not in allowed or end.weekday() not in allowed:
                return False, "Wechseltag nicht erlaubt"
        pad = timedelta(days=max(0, boat.turnaround_days))
        s, e = start - pad, end + pad
        for b in self.blocks:
            if b.start_date < e and b.end_date > s:
                return False, "Zeitraum nicht verfügbar"
        return self._one_way_feasible(start, end)

    def _one_way_feasible(self, start: date, end: date) -> tuple[bool, str]:
        boat = self.boat
        location, pickup, dropoff = self.legs(start)
        if pickup != location:
            if not boat.one_way_enabled:
                here = self.base(location)
                return False, f"Boot liegt in {here.name if here else 'anderem Hafen'}"
            repo = routing.repositioning(self.base(location), self.base(pickup))
            prev = self._prev_block(start)
            free_days = (start - prev.end_date).days if prev else 10**6
            if free_days < repo.days + boat.turnaround_days:
                return False, "Überführung zum Abholhafen nicht rechtzeitig möglich"
        if dropoff != pickup:
            if not boat.one_way_enabled:
                return False, "One-Way nicht möglich"
            if not self._dropoff_allowed(dropoff):
                return False, "Abgabehafen nicht erlaubt"
            nxt = self._next_block(end)
            if nxt is not None:
                expected = nxt.start_base_id or boat.base_id
                if expected != dropoff:
                    repo = routing.repositioning(self.base(dropoff), self.base(expected))
                    if (nxt.start_date - end).days < repo.days + boat.turnaround_days:
                        return False, "Rückführung vor der nächsten Buchung nicht möglich"
        return True, ""

    def _apply_one_way(self, result: PriceResult, start: date, end: date) -> dict:
        """Adds transfer, one-way fee, repositioning liability and return-leg incentive as fee lines."""
        boat = self.boat
        settings = get_settings()
        location, pickup, dropoff = self.legs(start)
        info = {"location_base_id": location, "pickup_base_id": pickup, "dropoff_base_id": dropoff}
        if pickup != location:
            repo = routing.repositioning(self.base(location), self.base(pickup))
            result.add_fee("transfer_in", "Überführung zum Abholhafen", repo.cost_cents, f"{repo.nm} sm")
            info["transfer_nm"] = repo.nm
        if dropoff != pickup:
            result.add_fee("one_way_fee", "One-Way-Gebühr", boat.one_way_fee_cents)
            nxt = self._next_block(end)
            expected = (nxt.start_base_id or boat.base_id) if nxt is not None else None
            if expected is not None and expected != dropoff:
                repo = routing.repositioning(self.base(dropoff), self.base(expected))
                result.add_fee(
                    "repositioning", "Rückführung zur nächsten Buchung", repo.cost_cents, f"{repo.nm} sm"
                )
                info["repositioning_nm"] = repo.nm
            elif expected is None and dropoff != boat.base_id:
                repo = routing.repositioning(self.base(dropoff), self.base(boat.base_id))
                liability = int(round(repo.cost_cents * (1 - settings.return_leg_probability)))
                result.add_fee(
                    "repositioning_risk",
                    "Rückführungsrisiko (anteilig)",
                    liability,
                    f"{repo.nm} sm, {settings.return_leg_probability:.0%} Rückleg-Chance",
                )
                info["repositioning_nm"] = repo.nm
        if location != boat.base_id and dropoff == boat.base_id and pickup == location:
            # This crew brings the boat home: share the saved repositioning cost with them
            repo = routing.repositioning(self.base(location), self.base(boat.base_id))
            saved = int(round(repo.cost_cents * settings.return_leg_probability))
            floor_total = (self.policy.floor_price_cents if self.policy else 0) * result.nights
            headroom = max(0, result.charter_cents + result.fees_cents - floor_total)
            discount = min(saved, headroom)
            result.add_fee("return_leg_discount", "Rückführungs-Rabatt", -discount, f"{repo.nm} sm heim")
            info["return_leg"] = True
        return info

    def free_window(self, start: date, end: date, horizon_days: int = 120) -> FreeWindow:
        """Contiguous free range around [start, end), bounded by blocks or horizon."""
        ws = start
        we = end
        earliest = max(self.today, start - timedelta(days=horizon_days))
        latest = end + timedelta(days=horizon_days)
        before = [b.end_date for b in self.blocks if b.end_date <= start]
        after = [b.start_date for b in self.blocks if b.start_date >= end]
        ws = max([earliest] + before)
        we = min([latest] + after)
        return FreeWindow(ws, we)

    # ---- pricing
    def price(self, start: date, end: date) -> tuple[PriceResult, dict, bool, str]:
        """Returns (price_result, gap_dict, offer, note). Price includes gap uplift when offered."""
        policy = self.policy
        if policy is None:
            raise ValueError("Boot hat keine Preisregel")
        inp = PricingInput(
            boat_id=self.boat.id,
            mode=PricingMode(policy.mode),
            reference_price_cents=policy.reference_price_cents,
            floor_price_cents=policy.floor_price_cents,
            ceiling_price_cents=policy.ceiling_price_cents,
            start_date=start,
            end_date=end,
            today=self.today,
            season_curve=self.season_curve,
            occupancy=self.occupancy,
            cleaning_fee_cents=self.boat.cleaning_fee_cents,
            currency=policy.currency,
            overrides=policy.overrides or None,
        )
        result = self.engine.price(inp)
        strategy = PricingStrategy(policy.strategy or "balanced")
        season_level = _season_level(self.season_curve, start, end)
        min_sellable = (
            policy.max_dead_gap_days if policy.max_dead_gap_days is not None else self.boat.min_days
        )
        decision = evaluate(
            GapInput(
                candidate_start=start,
                candidate_end=end,
                window=self.free_window(start, end),
                min_sellable_nights=max(1, min_sellable),
                expected_day_revenue_cents=int(policy.reference_price_cents * max(0.3, season_level)),
                season_level=season_level,
                strategy=strategy,
                turnaround_days=self.boat.turnaround_days,
            )
        )
        offer, per_day, note = apply_to_price(
            decision, result.per_day_cents, result.nights, policy.ceiling_price_cents, strategy
        )
        if offer and per_day != result.per_day_cents:
            result.per_day_cents = per_day
            result.charter_cents = per_day * result.nights
            result.total_cents = result.charter_cents + result.fees_cents
        gap = decision.to_dict()
        gap["note"] = note
        if offer:
            gap["one_way"] = self._apply_one_way(result, start, end)
        return result, gap, offer, note

    # ---- enumeration
    def offers(
        self, window_start: date, window_end: date, min_nights: int, max_nights: int, limit: int = 5
    ) -> tuple[list[Offer], list[RejectedOffer]]:
        min_nights = max(1, min_nights)
        max_nights = max(min_nights, max_nights)
        offers: list[Offer] = []
        rejected: list[RejectedOffer] = []
        candidates = 0
        day = window_start
        while day < window_end and candidates < MAX_CANDIDATES_PER_BOAT:
            for n in range(min_nights, max_nights + 1):
                end = day + timedelta(days=n)
                if end > window_end:
                    break
                candidates += 1
                ok, _ = self.is_free(day, end)
                if not ok:
                    continue
                try:
                    res, gap, offer, note = self.price(day, end)
                except ValueError:
                    continue
                if not offer:
                    rejected.append(RejectedOffer(day, end, note))
                    continue
                _loc, pickup, dropoff = self.legs(day)
                offers.append(
                    Offer(
                        day,
                        end,
                        n,
                        res.per_day_cents,
                        res.total_cents,
                        {**res.to_dict(), "occupancy": self.occupancy},
                        gap,
                        note,
                        pickup_base_id=pickup,
                        dropoff_base_id=dropoff,
                    )
                )
            day += timedelta(days=1)
        # Best value first: lowest per-day price, then longer stays
        offers.sort(key=lambda o: (o.per_day_cents, -o.nights, o.start_date))
        return _diversify(offers, limit), rejected


def _diversify(offers: list[Offer], limit: int) -> list[Offer]:
    """Avoid five near-identical offers: prefer distinct start dates and lengths."""
    picked: list[Offer] = []
    seen_start: set[date] = set()
    seen_len: set[int] = set()
    for o in offers:
        if o.start_date in seen_start and o.nights in seen_len:
            continue
        picked.append(o)
        seen_start.add(o.start_date)
        seen_len.add(o.nights)
        if len(picked) >= limit:
            break
    if len(picked) < limit:
        for o in offers:
            if o not in picked:
                picked.append(o)
                if len(picked) >= limit:
                    break
    return picked


def _season_level(curve: dict | None, start: date, end: date) -> float:
    curve = curve or PricingParams().default_season_curve
    nights = max(1, (end - start).days)
    total = sum(_interpolated_season(curve, start + timedelta(days=i)) for i in range(nights))
    return total / nights


def blocks_for(db: Session, boat_id: str, start: date, end: date) -> list[AvailabilityBlock]:
    return availability.overlapping_blocks(db, boat_id, start, end)
