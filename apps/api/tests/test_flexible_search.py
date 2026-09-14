from datetime import timedelta


def test_flexible_window_returns_multiple_offers(client, dates):
    start, _ = dates
    window_end = start + timedelta(days=14)
    r = client.get(
        "/search",
        params={
            "start_date": start.isoformat(),
            "end_date": window_end.isoformat(),
            "min_nights": 3,
            "max_nights": 5,
            "persons": 2,
            "license_level": 2,
            "experience_nm": 2000,
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["count"] > 0
    hit = data["hits"][0]
    assert 1 <= len(hit["offers"]) <= 5
    for o in hit["offers"]:
        assert 3 <= o["nights"] <= 5
        assert o["start_date"] >= start.isoformat() and o["end_date"] <= window_end.isoformat()
        assert o["total_cents"] > 0 and "gap" in o
    # best offer is the cheapest per day
    per_day = [o["per_day_cents"] for o in hit["offers"]]
    assert per_day[0] == min(per_day)
    assert hit["total_cents"] == hit["offers"][0]["total_cents"]


def test_flexible_search_validation(client, dates):
    start, _ = dates
    r = client.get(
        "/search",
        params={
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=4)).isoformat(),
            "min_nights": 5,
            "max_nights": 7,
        },
    )
    assert r.status_code == 422


def test_quote_honours_min_lead_and_allowed_nights(client, db, dates):
    from datetime import date

    from app.models import Boat

    start, _ = dates
    boat = db.query(Boat).filter(Boat.slug == "nordwind").one()
    boat.allowed_nights = [7, 14]
    boat.min_lead_days = 3
    db.commit()
    bad = client.post(
        "/quotes",
        json={
            "boat_id": boat.id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=5)).isoformat(),
            "persons": 2,
        },
    )
    assert bad.status_code == 409 and "Dauer" in bad.json()["detail"]
    soon = date.today() + timedelta(days=1)
    bad2 = client.post(
        "/quotes",
        json={
            "boat_id": boat.id,
            "start_date": soon.isoformat(),
            "end_date": (soon + timedelta(days=7)).isoformat(),
            "persons": 2,
        },
    )
    assert bad2.status_code == 409 and "vorlauf" in bad2.json()["detail"].lower()
    ok = client.post(
        "/quotes",
        json={
            "boat_id": boat.id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=7)).isoformat(),
            "persons": 2,
        },
    )
    assert ok.status_code == 201


def test_calendar_marks_rejected_days(client, dates):
    start, _ = dates
    r = client.get("/boats/nordwind/calendar", params={"start": start.isoformat(), "days": 14, "nights": 3})
    assert r.status_code == 200
    days = r.json()["days"]
    assert any(d["available"] for d in days)
    assert all(d["total_cents"] for d in days if d["available"])
