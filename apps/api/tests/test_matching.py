from app.models import Boat
from app.services.matching import CrewProfile, score


def _boat(**kw) -> Boat:
    base = dict(
        id="x",
        name="T",
        slug="t",
        length_m=11,
        cabins=3,
        berths=6,
        max_persons=7,
        headroom_cm=200,
        max_berth_length_cm=205,
        character=["good_natured", "comfort"],
        required_license=2,
        required_experience_nm=300,
        features=["autopilot", "bimini"],
    )
    base.update(kw)
    return Boat(**base)


def test_hard_blockers():
    r = score(_boat(), CrewProfile(persons=8, license_level=2, experience_nm=500), 100000)
    assert not r.ok and any("Personen" in b for b in r.blockers)
    r = score(_boat(), CrewProfile(persons=2, license_level=1, experience_nm=500), 100000)
    assert not r.ok and "Führerschein reicht nicht aus" in r.blockers
    r = score(_boat(), CrewProfile(persons=2, license_level=1, skip_qualification_check=True), 100000)
    assert r.ok


def test_tall_crew_prefers_headroom():
    crew = CrewProfile(persons=2, license_level=2, experience_nm=500, tallest_person_cm=195)
    roomy = score(_boat(headroom_cm=205, max_berth_length_cm=210), crew, None)
    tight = score(_boat(headroom_cm=185, max_berth_length_cm=190), crew, None)
    assert roomy.score > tight.score
    assert any("Stehhöhe" in x for x in roomy.reasons)


def test_character_and_budget_reasons():
    crew = CrewProfile(
        persons=2,
        license_level=2,
        experience_nm=500,
        preferred_character=["good_natured"],
        budget_total_cents=200000,
    )
    r = score(_boat(), crew, 150000)
    assert r.ok and r.score > 60
    assert any("gutmütig" in x for x in r.reasons) and "Im Budget" in r.reasons
    over = score(_boat(), crew, 500000)
    assert over.score < r.score
