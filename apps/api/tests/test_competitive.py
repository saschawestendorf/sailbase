from datetime import date, timedelta

import pytest
from sqlalchemy import select

from app.models import AvailabilityBlock, Boat
from app.models.entities import utcnow
from app.services.availability import comparable_occupancy
from app.services.matching.competitive import similarity, similarity_components


def boat(**changes):
    values = dict(
        base_id="port",
        length_m=12,
        cabins=3,
        berths=6,
        character=["sporty"],
        features=["autopilot", "furling_main"],
    )
    return Boat(**(values | changes))


def test_similarity_is_symmetric_and_explains_differences():
    a = boat()
    b = boat(base_id="other", length_m=14, cabins=4, features=["autopilot"])
    assert similarity(a, a) == 1
    assert 0 < similarity(a, b) < 1
    assert similarity(a, b) == similarity(b, a)
    assert similarity_components(a, b)["features"][0] == 0.5
    assert similarity(a, boat(character=["comfort"])) < 1


def test_missing_data_is_not_a_perfect_match():
    assert similarity(Boat(), Boat()) == 0
    assert "features" not in similarity_components(boat(features=[]), boat(features=[]))


def test_weighted_occupancy_merges_blocks_and_excludes_non_demand(db):
    boats = list(db.scalars(select(Boat)))
    subject, near, far = boats[:3]
    for b in boats:
        b.is_active = b in (subject, near, far)
    for b in (near, far):
        b.base_id = subject.base_id
        b.boat_class_id = subject.boat_class_id
        b.length_m = subject.length_m
        b.cabins = subject.cabins
        b.berths = subject.berths
        b.character = list(subject.character)
        b.features = list(subject.features)
    far.length_m = subject.length_m + 4
    far.cabins = subject.cabins + 3
    start, end = date(2030, 7, 1), date(2030, 7, 11)
    now = utcnow()
    for kind, s, e, expiry, target in (
        ("booking", start - timedelta(days=2), end, None, near),
        ("hold", start, end + timedelta(days=2), now + timedelta(hours=1), near),
        ("hold", start, end, now - timedelta(seconds=1), far),
        ("maintenance", start, end, None, far),
        ("owner_use", start, end, None, subject),
        ("booking", end, end + timedelta(days=2), None, far),
    ):
        db.add(
            AvailabilityBlock(boat_id=target.id, block_type=kind, start_date=s, end_date=e, expires_at=expiry)
        )
    db.flush()
    expected = 1 / (2 + similarity(subject, far))
    assert comparable_occupancy(db, subject, start, end, now) == pytest.approx(expected)
    assert comparable_occupancy(db, subject, end, start, now) == 0
    near.is_active = False
    db.flush()
    assert comparable_occupancy(db, subject, start, end, now) == 0
