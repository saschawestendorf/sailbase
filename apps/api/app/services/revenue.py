"""Revenue per available boat day, simulated over a season.

The owner's real question is not "what does this week cost" but "what does this rule earn me
over the year". This module answers it by walking the calendar once and carrying the
probability that the boat is still free, so a booking blocks the days it occupies instead of
being counted alongside every other booking that could have used them.

It is a model, not a forecast: arrivals and price elasticity are assumptions, stated here as
named constants rather than hidden in the arithmetic. Two runs of the same input give the same
numbers, which is what makes a price decision defensible to the owner.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Boat, PricingMode, PricingPolicy, PricingStrategy
from app.services import availability
from app.services.pricing import PricingEngine, PricingInput
from app.services.pricing.engine import _interpolated_season
from app.services.pricing.gap import FreeWindow, GapInput, apply_to_price, evaluate
from app.services.pricing.params import PricingParams

# Daily probability that some crew looks for a boat like this one, at peak season and at the
# reference price. Scaled by the season curve and by how the price compares to the market.
#
# How sought-after a boat is drives the whole picture, and nobody knows it better than its
# owner. So it is an input, not a hidden constant: the levels below are named for the season
# occupancy they produce for a typical Baltic boat, and the preview shows which one was used.
DEMAND_LEVELS: dict[str, float] = {
    "low": 0.14,  # roughly a quarter of the season sold
    "medium": 0.22,  # roughly 40 %, an ordinary boat with room to grow
    "high": 0.35,  # roughly half
    "very_high": 0.55,  # roughly two thirds, a boat that is already well booked
}
DEFAULT_DEMAND_LEVEL = "medium"
PEAK_ARRIVAL_RATE = DEMAND_LEVELS[DEFAULT_DEMAND_LEVEL]
# A charter far in the future is not sold a year ahead; it is sold roughly this long before it
# starts. Without this the lead-time factor would drift from last-minute to early-bird across
# the horizon and swamp the comparison with an artefact of where the simulation begins.
TYPICAL_LEAD_DAYS = 75
# How full comparable boats are in a peak week. The engine's demand factor reads fleet
# occupancy, not this boat's, so the model derives it from the season curve rather than from
# the simulated boat being empty — an empty boat in July does not mean an empty market.
PEAK_FLEET_OCCUPANCY = 0.9
# Constant price elasticity: halving the price multiplies interest by 2**ELASTICITY.
PRICE_ELASTICITY = 1.6
# Bounds keep the model honest at the edges of the corridor.
MIN_CONVERSION_FACTOR = 0.15
MAX_CONVERSION_FACTOR = 3.0
# More likely sold than not: past such a day a candidate is no longer competing for a free
# stretch. In a quiet month that boundary is far away; in a full July it is a couple of days
# out, which is exactly when leaving an unsellable stub starts to cost real money.
CONTESTED_FILL = 0.5
# Durations a crew would realistically ask for, weighted by how common they are.
DURATION_MIX: dict[int, float] = {3: 0.15, 4: 0.15, 7: 0.45, 10: 0.15, 14: 0.10}
# The baseline is the market as it works today: a fixed seasonal week price, Saturday to
# Saturday. Comparing against a fixed price that could also sell four-day trips would credit
# the classic model with flexibility it does not offer.
CLASSIC_NIGHTS = 7
CLASSIC_CHANGEOVER_WEEKDAY = 5  # Saturday
# Demand a crew brings that the week-only model simply cannot serve. Those crews do not vanish
# from the market, they just book elsewhere, so the baseline loses the request.
CLASSIC_REACHABLE_SHARE = DURATION_MIX[CLASSIC_NIGHTS]


@dataclass
class MonthPoint:
    month: int
    label: str
    available_days: int
    booked_days: float
    occupancy: float
    avg_price_cents: int
    revenue_cents: int
    revpabd_cents: int

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class SimulationResult:
    label: str
    available_days: int
    booked_days: float
    occupancy: float
    revenue_cents: int
    revpabd_cents: int  # revenue per available boat day
    avg_price_cents: int
    months: list[MonthPoint] = field(default_factory=list)
    # Probability each day ends up sold. The second pass reads it to bound the free stretch a
    # candidate competes with, instead of judging every gap against an empty calendar.
    fill: dict[date, float] = field(default_factory=dict, repr=False)

    def to_dict(self) -> dict:
        return {
            "label": self.label,
            "available_days": self.available_days,
            "booked_days": round(self.booked_days, 1),
            "occupancy": round(self.occupancy, 4),
            "revenue_cents": self.revenue_cents,
            "revpabd_cents": self.revpabd_cents,
            "avg_price_cents": self.avg_price_cents,
            "months": [m.to_dict() for m in self.months],
        }


@dataclass
class Comparison:
    dynamic: SimulationResult
    static: SimulationResult
    uplift_cents: int
    uplift_percent: float
    assumptions: dict

    def to_dict(self) -> dict:
        return {
            "dynamic": self.dynamic.to_dict(),
            "static": self.static.to_dict(),
            "uplift_cents": self.uplift_cents,
            "uplift_percent": round(self.uplift_percent, 2),
            "assumptions": self.assumptions,
        }


MONTH_LABELS = [
    "Jan",
    "Feb",
    "Mär",
    "Apr",
    "Mai",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Okt",
    "Nov",
    "Dez",
]


def _conversion_factor(offered_cents: int, market_cents: int) -> float:
    """How much more (or less) interest an offer draws than the market reference price."""
    if offered_cents <= 0 or market_cents <= 0:
        return 1.0
    factor = (market_cents / offered_cents) ** PRICE_ELASTICITY
    return max(MIN_CONVERSION_FACTOR, min(MAX_CONVERSION_FACTOR, factor))


def simulate(
    db: Session,
    boat: Boat,
    policy: PricingPolicy,
    *,
    start: date,
    days: int = 365,
    label: str = "dynamisch",
    force_static: bool = False,
    occupancy_hint: float | None = None,
    expected_fill: dict[date, float] | None = None,
    arrival_rate: float | None = None,
) -> SimulationResult:
    """Walk the calendar once, carrying the probability that the boat is still free.

    `expected_fill` is how full each day looked in an earlier pass. The gap logic reads it so a
    candidate is judged against the calendar it will actually compete with: without it an empty
    calendar makes every stub look harmless and the owner's strategy changes nothing.
    """
    engine = PricingEngine()
    params = PricingParams().with_overrides(policy.overrides or None)
    season_curve = (boat.base.region.season_curve or None) if boat.base else None
    strategy = PricingStrategy(policy.strategy or "balanced")
    turnaround = max(0, boat.turnaround_days)
    min_nights = max(1, boat.min_days)
    max_nights = max(min_nights, boat.max_days or 28)
    allowed = {int(n) for n in (boat.allowed_nights or [])}

    if force_static:
        # Week-only, fixed changeover: the classic charter week.
        durations = [(CLASSIC_NIGHTS, DURATION_MIX[CLASSIC_NIGHTS])]
    else:
        durations = [
            (n, w)
            for n, w in DURATION_MIX.items()
            if min_nights <= n <= max_nights and (not allowed or n in allowed)
        ]
        if not durations:
            durations = [(min_nights, 1.0)]
    # Weights stay shares of the whole market, so a rule that serves fewer durations reaches
    # fewer crews instead of redistributing the same demand over what it does offer.
    weight_sum = sum(DURATION_MIX.values())

    # Days the boat is closed or already sold are not available to the model at all.
    horizon_end = start + timedelta(days=days + max_nights + turnaround + 1)
    blocks = availability.overlapping_blocks(db, boat.id, start, horizon_end)
    blocked: set[date] = set()
    for b in blocks:
        cursor = max(b.start_date, start)
        while cursor < min(b.end_date, horizon_end):
            blocked.add(cursor)
            cursor += timedelta(days=1)

    # A day more likely sold than not bounds the stretch a candidate can leave behind.
    contested = {d for d, p in (expected_fill or {}).items() if p >= CONTESTED_FILL}

    releases: dict[int, float] = {}
    fill: dict[date, float] = {}
    free = 1.0
    revenue = 0.0
    booked_days = 0.0
    available_days = 0
    price_weight = 0.0
    price_weighted_sum = 0.0

    monthly: dict[int, dict[str, float]] = {}

    for offset in range(days):
        day = start + timedelta(days=offset)
        free = min(1.0, free + releases.pop(offset, 0.0))
        if day in blocked:
            continue
        available_days += 1
        monthly.setdefault(
            day.month, {"available": 0.0, "booked": 0.0, "revenue": 0.0, "pw": 0.0, "ps": 0.0}
        )["available"] += 1

        season_level = _interpolated_season(season_curve or params.default_season_curve, day)
        arrival = (arrival_rate or PEAK_ARRIVAL_RATE) * max(0.05, season_level)
        market_per_day = max(1, int(round(policy.reference_price_cents * max(0.3, season_level))))
        occupancy = (
            occupancy_hint
            if occupancy_hint is not None
            else min(0.95, max(0.0, season_level * PEAK_FLEET_OCCUPANCY))
        )
        sold_at = day - timedelta(days=min(offset, TYPICAL_LEAD_DAYS))

        taken_total = 0.0
        for nights, weight in durations:
            if force_static and day.weekday() != CLASSIC_CHANGEOVER_WEEKDAY:
                continue
            end = day + timedelta(days=nights)
            if any((day + timedelta(days=i)) in blocked for i in range(nights + turnaround)):
                continue
            result = engine.price(
                PricingInput(
                    boat_id=boat.id,
                    mode=PricingMode.FIXED if force_static else PricingMode(policy.mode),
                    reference_price_cents=policy.reference_price_cents,
                    floor_price_cents=policy.floor_price_cents,
                    ceiling_price_cents=policy.ceiling_price_cents,
                    start_date=day,
                    end_date=end,
                    today=sold_at,
                    season_curve=season_curve,
                    occupancy=occupancy,
                    cleaning_fee_cents=0,  # pass-through, not owner revenue
                    currency=policy.currency,
                    overrides=policy.overrides or None,
                )
            )
            per_day = result.per_day_cents
            if not force_static:
                decision = evaluate(
                    GapInput(
                        candidate_start=day,
                        candidate_end=end,
                        window=FreeWindow(
                            _window_start(blocked | contested, day, start),
                            _window_end(blocked | contested, end, horizon_end),
                        ),
                        min_sellable_nights=max(
                            1,
                            policy.max_dead_gap_days
                            if policy.max_dead_gap_days is not None
                            else boat.min_days,
                        ),
                        expected_day_revenue_cents=market_per_day,
                        season_level=season_level,
                        strategy=strategy,
                        turnaround_days=turnaround,
                    )
                )
                offered, per_day, _note = apply_to_price(
                    decision, per_day, nights, policy.ceiling_price_cents, strategy
                )
                if not offered:
                    continue

            share = weight / weight_sum
            # Nights are counted on the days they occupy. Booking them all into the starting
            # month is what made a July run past 100 % occupancy.
            nights_in_window = [
                day + timedelta(days=i)
                for i in range(nights)
                if 0 <= (day + timedelta(days=i) - start).days < days
            ]
            if force_static:
                # A whole week of arrivals funnels into the one Saturday that can serve them.
                share *= 7
            probability = min(0.95, arrival * share * _conversion_factor(per_day, market_per_day))
            taken = free * probability
            if taken <= 0:
                continue
            taken_total += probability
            counted = len(nights_in_window)
            gross = per_day * counted
            revenue += taken * gross
            booked_days += taken * counted
            price_weighted_sum += taken * counted * per_day
            price_weight += taken * counted
            for sold_day in nights_in_window:
                fill[sold_day] = min(1.0, fill.get(sold_day, 0.0) + taken)
                night_bucket = monthly.setdefault(
                    sold_day.month,
                    {"available": 0.0, "booked": 0.0, "revenue": 0.0, "pw": 0.0, "ps": 0.0},
                )
                night_bucket["booked"] += taken
                night_bucket["revenue"] += taken * per_day
                night_bucket["ps"] += taken * per_day
                night_bucket["pw"] += taken
            releases[offset + nights + turnaround] = releases.get(offset + nights + turnaround, 0.0) + taken

        free = max(0.0, free - free * min(1.0, taken_total))

    months = [
        MonthPoint(
            month=m,
            label=MONTH_LABELS[m - 1],
            available_days=int(v["available"]),
            booked_days=round(v["booked"], 1),
            occupancy=round(v["booked"] / v["available"], 4) if v["available"] else 0.0,
            avg_price_cents=int(round(v["ps"] / v["pw"])) if v["pw"] else 0,
            revenue_cents=int(round(v["revenue"])),
            revpabd_cents=int(round(v["revenue"] / v["available"])) if v["available"] else 0,
        )
        for m, v in sorted(monthly.items())
    ]

    return SimulationResult(
        label=label,
        available_days=available_days,
        booked_days=booked_days,
        occupancy=round(booked_days / available_days, 4) if available_days else 0.0,
        revenue_cents=int(round(revenue)),
        revpabd_cents=int(round(revenue / available_days)) if available_days else 0,
        avg_price_cents=int(round(price_weighted_sum / price_weight)) if price_weight else 0,
        months=months,
        fill=fill,
    )


def _window_end(blocked: set[date], after: date, horizon: date) -> date:
    """First day past `after` that the candidate cannot have, or the horizon."""
    cursor = after
    while cursor < horizon:
        if cursor in blocked:
            return cursor
        cursor += timedelta(days=1)
    return horizon


def _window_start(blocked: set[date], before: date, floor: date) -> date:
    """First day of the free stretch running up to `before`."""
    cursor = before
    while cursor > floor:
        candidate = cursor - timedelta(days=1)
        if candidate in blocked:
            return cursor
        cursor = candidate
    return floor


def compare(
    db: Session,
    boat: Boat,
    policy: PricingPolicy,
    *,
    start: date | None = None,
    days: int = 365,
    demand_level: str = DEFAULT_DEMAND_LEVEL,
) -> Comparison:
    """The proposed rule against the classic fixed seasonal tariff, on the same calendar."""
    start = start or date.today()
    # First pass with an empty calendar, second pass judging gaps against the fill the first
    # pass produced. Two passes are enough: the fill barely moves after that, and a fixed
    # number of passes keeps the result reproducible.
    rate = DEMAND_LEVELS.get(demand_level, PEAK_ARRIVAL_RATE)
    probe = simulate(db, boat, policy, start=start, days=days, arrival_rate=rate)
    dynamic = simulate(
        db,
        boat,
        policy,
        start=start,
        days=days,
        label="dynamisch",
        expected_fill=probe.fill,
        arrival_rate=rate,
    )
    static = simulate(
        db,
        boat,
        policy,
        start=start,
        days=days,
        label="klassischer Wochentarif",
        force_static=True,
        arrival_rate=rate,
    )
    uplift = dynamic.revenue_cents - static.revenue_cents
    return Comparison(
        dynamic=dynamic,
        static=static,
        uplift_cents=uplift,
        uplift_percent=(uplift / static.revenue_cents * 100) if static.revenue_cents else 0.0,
        assumptions={
            "demand_level": demand_level,
            "peak_arrival_rate": rate,
            "price_elasticity": PRICE_ELASTICITY,
            "duration_mix": DURATION_MIX,
            "horizon_days": days,
            "baseline": (
                "Klassischer Wochentarif: fester Saisonpreis, sieben Nächte, Samstag bis Samstag. "
                f"Damit erreicht er nur die {CLASSIC_REACHABLE_SHARE:.0%} der Anfragen, "
                "die genau eine Woche suchen."
            ),
            "note": (
                "Modellrechnung auf Basis angenommener Anfragehäufigkeit und Preiselastizität. "
                "Sie zeigt die Wirkung der Regel, nicht eine zugesicherte Buchungslage. "
                "Wie viel Flexibilität bringt, hängt stark von der Nachfrage ab: bei einem Boot "
                "mit freien Wochen holt sie Buchungen, die eine starre Woche nie erreicht; "
                "bei einem ohnehin ausgebuchten Boot zählt fast nur noch der Preis."
            ),
        },
    )
