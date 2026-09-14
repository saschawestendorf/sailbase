"""Tunable engine parameters. Global defaults; per-boat overrides via PricingPolicy.overrides."""

from dataclasses import asdict, dataclass, field


@dataclass(frozen=True)
class PricingParams:
    # Season: month -> demand level (1.0 = peak). Used when region has no curve.
    default_season_curve: dict[int, float] = field(
        default_factory=lambda: {
            1: 0.35,
            2: 0.35,
            3: 0.40,
            4: 0.55,
            5: 0.70,
            6: 0.85,
            7: 1.00,
            8: 1.00,
            9: 0.80,
            10: 0.60,
            11: 0.40,
            12: 0.35,
        }
    )
    # Price never drops below reference * season_floor_ratio due to season alone
    season_floor_ratio: float = 0.45

    # Weekday uplift on Fri/Sat nights (short breaks compete with weekend demand)
    weekend_uplift: float = 0.08

    # Demand: occupancy of comparable boats in the requested window
    target_occupancy: float = 0.65
    demand_elasticity: float = 0.6  # multiplier = 1 + e * (occ - target)
    demand_min: float = 0.80
    demand_max: float = 1.30

    # Lead time (days until check-in)
    early_bird_days: int = 180
    early_bird_discount: float = 0.06
    last_minute_days: int = 14
    last_minute_discount: float = 0.15  # only when occupancy < target
    last_minute_premium: float = 0.05  # only when occupancy >= target

    # Duration
    short_stay_days: int = 2  # stays <= this get a premium per day
    short_stay_premium: float = 0.10
    # A stay shorter than a full week occupies days a week booking would have taken. When
    # comparable boats are filling up, that displacement is charged for.
    week_nights: int = 7
    below_week_peak_premium: float = 0.12
    long_stay_tiers: dict[int, float] = field(
        default_factory=lambda: {7: 0.03, 14: 0.08, 21: 0.12}
    )  # >= days -> discount

    def with_overrides(self, overrides: dict | None) -> "PricingParams":
        if not overrides:
            return self
        data = asdict(self)
        for key, value in overrides.items():
            if key in data:
                data[key] = value
        # JSON turns int keys into str; normalise
        for k in ("default_season_curve", "long_stay_tiers"):
            data[k] = {int(kk): float(vv) for kk, vv in data[k].items()}
        return PricingParams(**data)
