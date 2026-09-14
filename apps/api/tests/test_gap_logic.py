from datetime import date

from app.models.enums import PricingStrategy
from app.services.pricing.gap import FreeWindow, GapInput, apply_to_price, evaluate


def _inp(start, end, ws, we, strategy=PricingStrategy.BALANCED, min_sellable=3):
    return GapInput(
        candidate_start=date(2027, 7, start),
        candidate_end=date(2027, 7, end),
        window=FreeWindow(date(2027, 7, ws), date(2027, 7, we)),
        min_sellable_nights=min_sellable,
        expected_day_revenue_cents=30000,
        season_level=1.0,
        strategy=strategy,
    )


def test_no_cost_when_candidate_fills_window():
    d = evaluate(_inp(10, 17, 10, 17))
    assert d.offer and d.opportunity_cost_cents == 0


def test_dead_days_are_charged():
    # window 10..24 (14 nights), candidate 10..22 leaves 2 dead nights
    d = evaluate(_inp(10, 22, 10, 24))
    assert d.dead_days_after == 2 and d.opportunity_cost_cents > 0
    # a leftover of 7 nights is sellable and costs nothing
    d2 = evaluate(_inp(10, 17, 10, 24))
    assert d2.dead_days_after == 0 and not d2.fragments_week


def test_three_day_request_that_fragments_two_weeks_is_expensive():
    d = evaluate(_inp(13, 16, 10, 24, PricingStrategy.CONSERVATIVE))
    assert d.fragments_week is False  # 3 before, 8 after -> a week still fits after
    d = evaluate(_inp(13, 16, 10, 20, PricingStrategy.CONSERVATIVE))
    assert d.fragments_week is True and d.opportunity_cost_cents > 0


def test_strategy_scales_cost():
    c = evaluate(_inp(13, 16, 10, 20, PricingStrategy.CONSERVATIVE)).opportunity_cost_cents
    b = evaluate(_inp(13, 16, 10, 20, PricingStrategy.BALANCED)).opportunity_cost_cents
    a = evaluate(_inp(13, 16, 10, 20, PricingStrategy.AGGRESSIVE)).opportunity_cost_cents
    assert c > b > a > 0


def test_apply_to_price_uplifts_or_rejects():
    d = evaluate(_inp(13, 16, 10, 20, PricingStrategy.CONSERVATIVE))
    offer, per_day, note = apply_to_price(d, 30000, 3, 45000, PricingStrategy.CONSERVATIVE)
    if offer:
        assert per_day > 30000
    offer, per_day, note = apply_to_price(d, 30000, 3, 30500, PricingStrategy.CONSERVATIVE)
    assert offer is False and note.startswith("Nicht angeboten")
    offer, per_day, _ = apply_to_price(d, 30000, 3, 30500, PricingStrategy.AGGRESSIVE)
    assert offer is True and per_day == 30500
