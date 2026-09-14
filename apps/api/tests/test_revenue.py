"""Yearly revenue-per-available-boat-day simulation and its preview endpoint."""

from datetime import date

from app.models import Boat
from app.services import revenue


def _auth(client):
    r = client.post(
        "/auth/login",
        json={"email": "charter@ostsee-yachting.example", "password": "charter123"},
    )
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _boat(db, slug="nordwind") -> Boat:
    return db.query(Boat).filter(Boat.slug == slug).one()


def test_simulation_is_reproducible(db):
    boat = _boat(db)
    a = revenue.compare(db, boat, boat.pricing, start=date(2027, 1, 1))
    b = revenue.compare(db, boat, boat.pricing, start=date(2027, 1, 1))
    assert a.dynamic.revpabd_cents == b.dynamic.revpabd_cents
    assert a.uplift_cents == b.uplift_cents


def test_revpabd_relates_revenue_to_available_days(db):
    boat = _boat(db)
    result = revenue.simulate(db, boat, boat.pricing, start=date(2027, 1, 1))
    assert result.available_days > 0
    assert result.revpabd_cents == round(result.revenue_cents / result.available_days)
    assert 0 <= result.occupancy <= 1
    assert sum(m.available_days for m in result.months) == result.available_days


def test_blocked_days_are_not_available(db):
    """Winter lay-up is not idle capacity, so it must not dilute the figure."""
    from app.models import AvailabilityBlock, BlockType

    boat = _boat(db)
    before = revenue.simulate(db, boat, boat.pricing, start=date(2027, 1, 1))
    db.add(
        AvailabilityBlock(
            boat_id=boat.id,
            start_date=date(2027, 1, 1),
            end_date=date(2027, 4, 1),
            block_type=BlockType.CLOSED.value,
            note="Winterlager",
        )
    )
    db.commit()
    after = revenue.simulate(db, boat, boat.pricing, start=date(2027, 1, 1))
    months = {m.month for m in after.months}
    assert 1 not in months and 2 not in months and 3 not in months
    assert after.available_days == before.available_days - 90
    # Fewer available days but the same quality of demand: the per-day figure must not drop.
    assert after.revpabd_cents > before.revpabd_cents


def test_flexible_durations_beat_the_classic_week(db):
    boat = _boat(db)
    comparison = revenue.compare(db, boat, boat.pricing, start=date(2027, 1, 1))
    assert comparison.static.label.startswith("klassischer")
    assert comparison.dynamic.revpabd_cents > comparison.static.revpabd_cents
    assert comparison.uplift_percent > 0
    assert "Samstag" in comparison.assumptions["baseline"]


def test_a_narrow_corridor_limits_what_the_rule_can_do(db):
    boat = _boat(db)
    policy = boat.pricing
    wide = revenue.simulate(db, boat, policy, start=date(2027, 1, 1))

    policy.floor_price_cents = policy.reference_price_cents
    policy.ceiling_price_cents = policy.reference_price_cents
    narrow = revenue.simulate(db, boat, policy, start=date(2027, 1, 1))
    assert narrow.avg_price_cents == policy.reference_price_cents
    assert narrow.revpabd_cents != wide.revpabd_cents


def test_higher_prices_trade_occupancy_for_yield(db):
    boat = _boat(db)
    policy = boat.pricing
    base = revenue.simulate(db, boat, policy, start=date(2027, 1, 1))
    policy.floor_price_cents = int(policy.reference_price_cents * 1.5)
    policy.ceiling_price_cents = int(policy.reference_price_cents * 2.5)
    policy.reference_price_cents = int(policy.reference_price_cents * 1.8)
    dearer = revenue.simulate(db, boat, policy, start=date(2027, 1, 1))
    assert dearer.avg_price_cents > base.avg_price_cents
    assert dearer.occupancy < base.occupancy


def test_preview_endpoint_returns_both_runs(client, db):
    headers = _auth(client)
    boat = _boat(db)
    r = client.post(
        f"/charterer/boats/{boat.id}/pricing/simulate",
        headers=headers,
        json={"strategy": "aggressive", "days": 365},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dynamic"]["revpabd_cents"] > 0
    assert data["static"]["label"].startswith("klassischer")
    assert len(data["dynamic"]["months"]) >= 6
    assert data["assumptions"]["price_elasticity"]
    assert "Modellrechnung" in data["assumptions"]["note"]


def test_preview_does_not_persist_the_proposal(client, db):
    headers = _auth(client)
    boat = _boat(db)
    original = boat.pricing.reference_price_cents
    client.post(
        f"/charterer/boats/{boat.id}/pricing/simulate",
        headers=headers,
        json={
            "reference_price_cents": original * 2,
            "floor_price_cents": original,
            "ceiling_price_cents": original * 3,
        },
    )
    db.refresh(boat.pricing)
    assert boat.pricing.reference_price_cents == original


def test_preview_rejects_an_impossible_corridor(client, db):
    headers = _auth(client)
    boat = _boat(db)
    r = client.post(
        f"/charterer/boats/{boat.id}/pricing/simulate",
        headers=headers,
        json={"floor_price_cents": 50000, "ceiling_price_cents": 20000},
    )
    assert r.status_code == 422


def test_preview_is_owner_scoped(client, db):
    other = client.post(
        "/auth/register",
        json={"email": "fremd@charter.de", "password": "geheim123", "role": "charterer"},
    ).json()
    boat = _boat(db)
    r = client.post(
        f"/charterer/boats/{boat.id}/pricing/simulate",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={},
    )
    assert r.status_code == 404


def test_demand_level_drives_occupancy_and_is_reported(db):
    """How sought-after the boat is, is an input the owner sets, not a hidden constant."""
    boat = _boat(db)
    results = {
        level: revenue.compare(
            db, boat, boat.pricing, start=date(2027, 1, 1), demand_level=level
        )
        for level in ("low", "medium", "high", "very_high")
    }
    occupancies = [results[level].dynamic.occupancy for level in ("low", "medium", "high", "very_high")]
    assert occupancies == sorted(occupancies), "mehr Nachfrage muss mehr Auslastung bedeuten"
    assert all(o <= 1.0 for o in occupancies), "Auslastung kann 100 % nicht überschreiten"
    assert results["medium"].assumptions["demand_level"] == "medium"
    assert results["low"].assumptions["peak_arrival_rate"] < results["high"].assumptions["peak_arrival_rate"]


def test_no_month_exceeds_full_occupancy(db):
    """Nights count on the days they occupy, not on the month the booking started in."""
    boat = _boat(db)
    for level in ("medium", "very_high"):
        comparison = revenue.compare(
            db, boat, boat.pricing, start=date(2027, 1, 1), demand_level=level
        )
        for run in (comparison.dynamic, comparison.static):
            for month in run.months:
                assert month.occupancy <= 1.0, f"{run.label} {month.label}: {month.occupancy}"
                assert month.booked_days <= month.available_days + 0.01


def test_long_stay_discount_fades_when_comparable_boats_fill_up(db):
    """A discount that buys occupancy is ruinous in a week that would have sold anyway."""
    from app.models.enums import PricingMode
    from app.services.pricing import PricingEngine, PricingInput

    def duration_factor(occupancy: float) -> float:
        result = PricingEngine().price(
            PricingInput(
                boat_id="b",
                mode=PricingMode.CORRIDOR,
                reference_price_cents=30000,
                floor_price_cents=10000,
                ceiling_price_cents=90000,
                start_date=date(2027, 7, 5),
                end_date=date(2027, 7, 19),
                today=date(2027, 4, 1),
                occupancy=occupancy,
            )
        )
        return {f.key: f for f in result.stay_factors}["duration"].multiplier

    quiet = duration_factor(0.3)
    busy = duration_factor(0.98)
    assert quiet < 1.0, "in einer ruhigen Zeit gibt es den Langtörn-Rabatt"
    assert busy > quiet
    assert busy >= 0.999, "bei voller Nachfrage bleibt kein Rabatt übrig"
