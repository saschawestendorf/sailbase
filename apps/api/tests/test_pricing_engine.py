from datetime import date

import pytest

from app.models.enums import PricingMode
from app.services.pricing import PricingEngine, PricingInput, PricingParams


def _inp(**kw) -> PricingInput:
    base = dict(
        boat_id="b",
        mode=PricingMode.CORRIDOR,
        reference_price_cents=30000,
        floor_price_cents=15000,
        ceiling_price_cents=45000,
        start_date=date(2027, 7, 5),
        end_date=date(2027, 7, 12),
        today=date(2027, 3, 1),
        occupancy=0.65,
    )
    base.update(kw)
    return PricingInput(**base)


def test_peak_week_target_occupancy_close_to_reference():
    res = PricingEngine().price(_inp())
    assert res.nights == 7
    # July peak, target occupancy, 60+ days lead, 7-night discount + weekend uplift ~ reference
    assert 0.9 * 30000 <= res.per_day_cents <= 1.1 * 30000
    assert res.total_cents == res.charter_cents + res.fees_cents
    assert res.clamped is None


def test_low_season_is_cheaper_but_never_below_floor():
    hi = PricingEngine().price(_inp())
    lo = PricingEngine().price(_inp(start_date=date(2027, 4, 5), end_date=date(2027, 4, 12)))
    assert lo.per_day_cents < hi.per_day_cents
    assert lo.per_day_cents >= 15000
    very_lo = PricingEngine().price(
        _inp(start_date=date(2027, 1, 5), end_date=date(2027, 1, 12), occupancy=0.0, today=date(2026, 12, 30))
    )
    assert very_lo.per_day_cents == 15000
    assert very_lo.clamped == "floor"


def test_high_demand_raises_price_and_caps_at_ceiling():
    normal = PricingEngine().price(_inp(occupancy=0.5))
    hot = PricingEngine().price(_inp(occupancy=1.0))
    assert hot.per_day_cents > normal.per_day_cents
    capped = PricingEngine().price(_inp(occupancy=1.0, ceiling_price_cents=31000, today=date(2027, 7, 1)))
    assert capped.per_day_cents == 31000
    assert capped.clamped == "ceiling"


def test_last_minute_discount_only_when_capacity_free():
    free = PricingEngine().price(_inp(today=date(2027, 7, 1), occupancy=0.2))
    busy = PricingEngine().price(_inp(today=date(2027, 7, 1), occupancy=0.9))
    lead = {f.key: f for f in free.stay_factors}["lead_time"]
    assert lead.multiplier < 1
    lead_busy = {f.key: f for f in busy.stay_factors}["lead_time"]
    assert lead_busy.multiplier > 1


def test_short_stay_premium_and_long_stay_discount():
    p = PricingEngine()
    short = p.price(_inp(start_date=date(2027, 7, 5), end_date=date(2027, 7, 7)))
    week = p.price(_inp())
    two_weeks = p.price(_inp(end_date=date(2027, 7, 19)))
    assert short.per_day_cents > week.per_day_cents > two_weeks.per_day_cents


def test_fixed_mode_ignores_demand_and_lead():
    res = PricingEngine().price(_inp(mode=PricingMode.FIXED, occupancy=1.0, today=date(2027, 7, 4)))
    assert res.stay_factors == []
    assert [f.key for f in res.day_factors] == ["season"]


def test_overrides_are_applied_and_unknown_keys_ignored():
    params = PricingParams().with_overrides({"weekend_uplift": 0.5, "nonsense": 1})
    assert params.weekend_uplift == 0.5
    res = PricingEngine().price(_inp(overrides={"weekend_uplift": 0.5}))
    assert {f.key: f for f in res.day_factors}["weekend"].multiplier > 1.1


def test_invalid_range_raises():
    with pytest.raises(ValueError):
        PricingEngine().price(_inp(end_date=date(2027, 7, 5)))


def test_breakdown_is_serialisable():
    d = PricingEngine().price(_inp()).to_dict()
    assert set(d) >= {"total_cents", "day_factors", "stay_factors", "clamped"}
