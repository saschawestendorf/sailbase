"""Gap / opportunity-cost logic: Revenue per Available Boat Day.

A candidate booking is only offered when its revenue beats the economic damage it causes:
- dead days: leftover gaps before/after that are too short to be sold (< min sellable nights)
- fragmentation: cutting a free window that could host a full week into two pieces that cannot

The damage is expressed in cents and either added to the price (if the corridor allows) or the
candidate is rejected. The owner's strategy scales how much the calendar is protected.
"""

from dataclasses import dataclass
from datetime import date

from app.models.enums import PricingStrategy

WEEK = 7

# How strongly each strategy weighs opportunity cost (multiplier on the damage)
STRATEGY_WEIGHT = {
    PricingStrategy.CONSERVATIVE: 1.0,
    PricingStrategy.BALANCED: 0.6,
    PricingStrategy.AGGRESSIVE: 0.3,
}
# Probability the protected days would actually sell, by season level (0..1) and strategy
STRATEGY_SELL_PROB_BONUS = {
    PricingStrategy.CONSERVATIVE: 0.15,
    PricingStrategy.BALANCED: 0.0,
    PricingStrategy.AGGRESSIVE: -0.15,
}


@dataclass(frozen=True)
class FreeWindow:
    """The contiguous free range [start, end) that contains the candidate."""

    start: date
    end: date


@dataclass(frozen=True)
class GapInput:
    candidate_start: date
    candidate_end: date
    window: FreeWindow
    min_sellable_nights: int  # gaps shorter than this are dead
    expected_day_revenue_cents: int  # what a protected day would earn (reference * season)
    season_level: float  # 0..1 demand level, drives sell probability
    strategy: PricingStrategy = PricingStrategy.BALANCED
    turnaround_days: int = 0


@dataclass
class GapDecision:
    offer: bool
    opportunity_cost_cents: int
    dead_days_before: int
    dead_days_after: int
    fragments_week: bool
    reason: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def sell_probability(season_level: float, strategy: PricingStrategy) -> float:
    base = 0.25 + 0.65 * max(0.0, min(1.0, season_level))
    return max(0.05, min(0.95, base + STRATEGY_SELL_PROB_BONUS[strategy]))


def evaluate(inp: GapInput) -> GapDecision:
    nights = (inp.candidate_end - inp.candidate_start).days
    if nights <= 0:
        return GapDecision(False, 0, 0, 0, False, "Ungültiger Zeitraum")

    before = (inp.candidate_start - inp.window.start).days - inp.turnaround_days
    after = (inp.window.end - inp.candidate_end).days - inp.turnaround_days
    before, after = max(0, before), max(0, after)

    dead_before = before if 0 < before < inp.min_sellable_nights else 0
    dead_after = after if 0 < after < inp.min_sellable_nights else 0

    window_nights = (inp.window.end - inp.window.start).days
    fragments_week = window_nights >= WEEK and nights < WEEK and before < WEEK and after < WEEK

    p = sell_probability(inp.season_level, inp.strategy)
    weight = STRATEGY_WEIGHT[inp.strategy]
    cost = (dead_before + dead_after) * inp.expected_day_revenue_cents * p
    if fragments_week:
        # Losing a week-booking opportunity: value the unsellable remainder of that week
        lost = max(0, WEEK - nights)
        cost += lost * inp.expected_day_revenue_cents * p * 0.5
    cost = int(round(cost * weight))

    if cost == 0:
        return GapDecision(True, 0, dead_before, dead_after, fragments_week, "Keine Kalenderlücke")
    parts = []
    if dead_before or dead_after:
        parts.append(f"{dead_before + dead_after} unverkäufliche Resttage")
    if fragments_week:
        parts.append("zerteilt eine buchbare Woche")
    return GapDecision(True, cost, dead_before, dead_after, fragments_week, ", ".join(parts))


def apply_to_price(
    decision: GapDecision,
    per_day_cents: int,
    nights: int,
    ceiling_cents: int,
    strategy: PricingStrategy,
) -> tuple[bool, int, str]:
    """Fold the opportunity cost into the price. Returns (offer, new_per_day_cents, note)."""
    if decision.opportunity_cost_cents <= 0:
        return True, per_day_cents, ""
    uplift_per_day = int(round(decision.opportunity_cost_cents / nights))
    new_per_day = per_day_cents + uplift_per_day
    if new_per_day <= ceiling_cents:
        return True, new_per_day, f"Aufschlag {decision.reason}"
    if strategy == PricingStrategy.AGGRESSIVE:
        return True, ceiling_cents, f"Obergrenze erreicht ({decision.reason})"
    return False, per_day_cents, f"Nicht angeboten: {decision.reason}"
