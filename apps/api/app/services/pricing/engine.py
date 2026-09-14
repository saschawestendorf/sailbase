"""Dynamic pricing engine.

Pipeline
--------
1. Day factors (multiplicative per calendar day): season, weekday.
2. Stay factors (multiplicative on the whole stay): demand, lead time, duration.
3. Corridor clamp: average per-day price is clamped into [floor, ceiling].
4. Fees (cleaning etc.) are added on top and reported separately.

The engine is pure: it takes a `PricingInput` snapshot and returns a `PriceResult` with a
machine-readable breakdown, so it is testable without a database and can later be swapped
for a learned model behind the same interface.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Protocol

from app.models.enums import PricingMode
from app.services.pricing.params import PricingParams


@dataclass(frozen=True)
class PricingInput:
    boat_id: str
    mode: PricingMode
    reference_price_cents: int
    floor_price_cents: int
    ceiling_price_cents: int
    start_date: date
    end_date: date  # exclusive
    today: date
    season_curve: dict[int, float] | None = None  # month -> level, from region
    occupancy: float = 0.0  # 0..1 comparable boats booked in window
    cleaning_fee_cents: int = 0
    currency: str = "EUR"
    overrides: dict | None = None

    @property
    def nights(self) -> int:
        return (self.end_date - self.start_date).days

    @property
    def lead_days(self) -> int:
        return (self.start_date - self.today).days


@dataclass
class FactorLine:
    key: str
    label: str
    multiplier: float
    detail: str = ""


@dataclass
class PriceResult:
    currency: str
    nights: int
    reference_per_day_cents: int
    raw_per_day_cents: int  # after factors, before clamp
    per_day_cents: int  # after clamp
    charter_cents: int
    fees_cents: int
    total_cents: int
    clamped: str | None  # None | "floor" | "ceiling"
    day_factors: list[FactorLine] = field(default_factory=list)
    stay_factors: list[FactorLine] = field(default_factory=list)
    per_day_prices: list[int] = field(default_factory=list)  # before clamp, per night
    fee_lines: list[dict] = field(default_factory=list)  # {key,label,amount_cents,detail}

    def add_fee(self, key: str, label: str, amount_cents: int, detail: str = "") -> None:
        if amount_cents == 0:
            return
        self.fee_lines.append(
            {"key": key, "label": label, "amount_cents": int(amount_cents), "detail": detail}
        )
        self.fees_cents += int(amount_cents)
        self.total_cents = self.charter_cents + self.fees_cents

    def to_dict(self) -> dict:
        return {
            "currency": self.currency,
            "nights": self.nights,
            "reference_per_day_cents": self.reference_per_day_cents,
            "raw_per_day_cents": self.raw_per_day_cents,
            "per_day_cents": self.per_day_cents,
            "charter_cents": self.charter_cents,
            "fees_cents": self.fees_cents,
            "total_cents": self.total_cents,
            "clamped": self.clamped,
            "day_factors": [f.__dict__ for f in self.day_factors],
            "stay_factors": [f.__dict__ for f in self.stay_factors],
            "fee_lines": list(self.fee_lines),
        }


# ------------------------------------------------------------------ factor protocols


class DayFactor(Protocol):
    key: str
    label: str

    def multiplier(self, inp: PricingInput, params: PricingParams, day: date) -> float: ...


class StayFactor(Protocol):
    key: str
    label: str

    def multiplier(self, inp: PricingInput, params: PricingParams) -> tuple[float, str]: ...


# ------------------------------------------------------------------------ factors


class SeasonFactor:
    key = "season"
    label = "Saison"

    def multiplier(self, inp: PricingInput, params: PricingParams, day: date) -> float:
        curve = inp.season_curve or params.default_season_curve
        level = _interpolated_season(curve, day)
        return max(params.season_floor_ratio, min(1.0, level))


class WeekendFactor:
    key = "weekend"
    label = "Wochenende"

    def multiplier(self, inp: PricingInput, params: PricingParams, day: date) -> float:
        return 1.0 + params.weekend_uplift if day.weekday() in (4, 5) else 1.0


class DemandFactor:
    key = "demand"
    label = "Nachfrage vergleichbarer Boote"

    def multiplier(self, inp: PricingInput, params: PricingParams) -> tuple[float, str]:
        occ = _clamp(inp.occupancy, 0.0, 1.0)
        m = 1.0 + params.demand_elasticity * (occ - params.target_occupancy)
        m = _clamp(m, params.demand_min, params.demand_max)
        return m, f"Auslastung {occ:.0%} (Ziel {params.target_occupancy:.0%})"


class LeadTimeFactor:
    key = "lead_time"
    label = "Buchungsvorlauf"

    def multiplier(self, inp: PricingInput, params: PricingParams) -> tuple[float, str]:
        lead = inp.lead_days
        if lead >= params.early_bird_days:
            return 1.0 - params.early_bird_discount, f"Frühbucher ({lead} Tage Vorlauf)"
        if lead <= params.last_minute_days:
            if inp.occupancy < params.target_occupancy:
                return 1.0 - params.last_minute_discount, f"Last Minute ({lead} Tage), freie Kapazität"
            return 1.0 + params.last_minute_premium, f"Kurzfristig ({lead} Tage), hohe Nachfrage"
        return 1.0, f"{lead} Tage Vorlauf"


class DurationFactor:
    """Length-of-stay pricing, and it has to know how busy the window is.

    A long-stay discount buys occupancy with yield: it is worth paying in a quiet week and
    ruinous in a full one, where those days would have sold anyway at the full rate. So the
    discount fades out as comparable boats fill up, and the short-stay premium grows.
    """

    key = "duration"
    label = "Dauer"

    def multiplier(self, inp: PricingInput, params: PricingParams) -> tuple[float, str]:
        n = inp.nights
        headroom = params.target_occupancy
        pressure = _clamp((inp.occupancy - headroom) / max(0.05, 1.0 - headroom), 0.0, 1.0)
        if n <= params.short_stay_days:
            premium = params.short_stay_premium * (1.0 + pressure)
            return 1.0 + premium, f"Kurztörn ({n} Nächte)"
        if n < params.week_nights and pressure > 0:
            # Shorter than a week while the fleet fills up: those days would have gone to a
            # full week, so the stay carries that displacement rather than undercutting it.
            premium = params.below_week_peak_premium * pressure
            return 1.0 + premium, f"{n} Nächte in nachgefragter Zeit"
        discount = 0.0
        for threshold in sorted(params.long_stay_tiers):
            if n >= threshold:
                discount = params.long_stay_tiers[threshold]
        if not discount:
            return 1.0, f"{n} Nächte"
        effective = discount * (1.0 - pressure)
        if effective < 0.005:
            return 1.0, f"{n} Nächte, kein Rabatt bei hoher Nachfrage"
        detail = f"Langtörn-Rabatt ({n} Nächte)"
        if pressure > 0.05:
            detail += f", wegen Nachfrage auf {effective:.0%} reduziert"
        return 1.0 - effective, detail


DEFAULT_DAY_FACTORS: Sequence[DayFactor] = (SeasonFactor(), WeekendFactor())
DEFAULT_STAY_FACTORS: Sequence[StayFactor] = (DemandFactor(), LeadTimeFactor(), DurationFactor())
FIXED_DAY_FACTORS: Sequence[DayFactor] = (SeasonFactor(),)


# ------------------------------------------------------------------------- engine


class PricingEngine:
    def __init__(
        self,
        params: PricingParams | None = None,
        day_factors: Sequence[DayFactor] | None = None,
        stay_factors: Sequence[StayFactor] | None = None,
    ):
        self.params = params or PricingParams()
        self.day_factors = day_factors
        self.stay_factors = stay_factors

    def price(self, inp: PricingInput) -> PriceResult:
        if inp.nights <= 0:
            raise ValueError("end_date must be after start_date")
        params = self.params.with_overrides(inp.overrides)
        mode = PricingMode(inp.mode)

        if mode == PricingMode.FIXED:
            day_factors = self.day_factors or FIXED_DAY_FACTORS
            stay_factors: Sequence[StayFactor] = ()
        else:
            day_factors = self.day_factors or DEFAULT_DAY_FACTORS
            stay_factors = self.stay_factors or DEFAULT_STAY_FACTORS

        # 1. per-day prices
        per_day_prices: list[int] = []
        day_mult_sum: dict[str, float] = {f.key: 0.0 for f in day_factors}
        for i in range(inp.nights):
            day = inp.start_date + timedelta(days=i)
            m = 1.0
            for f in day_factors:
                fm = f.multiplier(inp, params, day)
                day_mult_sum[f.key] += fm
                m *= fm
            per_day_prices.append(round(inp.reference_price_cents * m))

        day_lines = [
            FactorLine(f.key, f.label, round(day_mult_sum[f.key] / inp.nights, 4), "Ø über Törn")
            for f in day_factors
        ]

        # 2. stay factors
        stay_lines: list[FactorLine] = []
        stay_mult = 1.0
        for f in stay_factors:
            m, detail = f.multiplier(inp, params)
            stay_lines.append(FactorLine(f.key, f.label, round(m, 4), detail))
            stay_mult *= m

        raw_charter = sum(per_day_prices) * stay_mult
        raw_per_day = raw_charter / inp.nights

        # 3. corridor clamp (floor always wins, also in FIXED/AUTO mode)
        floor = inp.floor_price_cents
        ceiling = max(inp.ceiling_price_cents, floor)
        clamped: str | None = None
        per_day = raw_per_day
        if per_day < floor:
            per_day, clamped = floor, "floor"
        elif per_day > ceiling and mode != PricingMode.FIXED:
            per_day, clamped = ceiling, "ceiling"

        per_day_int = int(round(per_day))
        charter = per_day_int * inp.nights

        result = PriceResult(
            currency=inp.currency,
            nights=inp.nights,
            reference_per_day_cents=inp.reference_price_cents,
            raw_per_day_cents=int(round(raw_per_day)),
            per_day_cents=per_day_int,
            charter_cents=charter,
            fees_cents=0,
            total_cents=charter,
            clamped=clamped,
            day_factors=day_lines,
            stay_factors=stay_lines,
            per_day_prices=per_day_prices,
        )
        result.add_fee("cleaning", "Endreinigung", max(0, inp.cleaning_fee_cents))
        return result


# ------------------------------------------------------------------------ helpers


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _interpolated_season(curve: dict[int, float], day: date) -> float:
    """Linear interpolation between mid-month anchor points for a smooth curve."""
    normalised = {int(k): float(v) for k, v in curve.items()}
    if len(normalised) < 12:
        return normalised.get(day.month, 0.5)
    this_m = day.month
    # position within month relative to its middle (day 15)
    days_in_month = (date(day.year + (this_m == 12), this_m % 12 + 1, 1) - date(day.year, this_m, 1)).days
    t = (day.day - 15) / days_in_month  # -0.5 .. +0.5
    if t >= 0:
        other = this_m % 12 + 1
        w = t
    else:
        other = 12 if this_m == 1 else this_m - 1
        w = -t
    return normalised[this_m] * (1 - w) + normalised[other] * w
