from datetime import timedelta

from app.models import AvailabilityBlock, BlockType, Booking


def _search(client, start, end, **params):
    r = client.get(
        "/search",
        params={"start_date": start.isoformat(), "end_date": end.isoformat(), "persons": 4, **params},
    )
    assert r.status_code == 200, r.text
    return r.json()


def test_health(client):
    assert client.get("/health").json()["status"] == "ok"


def test_search_ranks_and_prices(client, dates):
    start, end = dates
    data = _search(
        client, start, end, license_level=2, experience_nm=600, tallest_cm=190, character="good_natured"
    )
    assert data["count"] > 0
    top = data["hits"][0]
    assert top["available"] and top["total_cents"] > 0
    assert top["fit_score"] >= data["hits"][-1]["fit_score"]
    assert "breakdown" in top and top["breakdown"]["nights"] == 7
    # unqualified crews are filtered out of a normal search
    sks_only = _search(client, start, end, license_level=1, experience_nm=0)
    assert all(h["boat"]["required_license"] <= 1 for h in sks_only["hits"])


def test_search_rejects_bad_range(client, dates):
    start, _ = dates
    r = client.get("/search", params={"start_date": start.isoformat(), "end_date": start.isoformat()})
    assert r.status_code == 422


def test_quote_booking_payment_flow(client, db, dates):
    start, end = dates
    boat = _search(client, start, end)["hits"][0]["boat"]

    q = client.post(
        "/quotes",
        json={
            "boat_id": boat["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "persons": 4,
        },
    )
    assert q.status_code == 201, q.text
    quote = q.json()
    assert quote["total_cents"] > 0

    b = client.post(
        "/bookings",
        json={
            "quote_id": quote["id"],
            "customer_email": "Kunde@Example.com",
            "customer_name": "Kai Kunde",
            "accept_terms": True,
        },
    )
    assert b.status_code == 201, b.text
    created = b.json()
    booking = created["booking"]
    assert booking["status"] == "pending_payment"
    assert booking["deposit_cents"] == round(quote["total_cents"] * 0.3)
    assert "/webhooks/fake/" in created["checkout_url"]

    # Boat is now held: second quote for same window must fail
    q2 = client.post(
        "/quotes",
        json={
            "boat_id": boat["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "persons": 2,
        },
    )
    assert q2.status_code == 409

    # Same quote cannot be booked twice
    b2 = client.post(
        "/bookings",
        json={
            "quote_id": quote["id"],
            "customer_email": "x@example.com",
            "customer_name": "Doppelt",
            "accept_terms": True,
        },
    )
    assert b2.status_code == 409

    # Simulate provider callback
    ref = created["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
    w = client.get(f"/webhooks/fake/{ref}", follow_redirects=False)
    assert w.status_code in (200, 307)

    g = client.get(f"/bookings/{booking['reference']}", params={"email": "kunde@example.com"})
    assert g.status_code == 200
    assert g.json()["status"] == "confirmed"
    assert g.json()["payments"][0]["status"] == "succeeded"

    # Guest lookup without matching e-mail is refused
    assert client.get(f"/bookings/{booking['reference']}").status_code == 403

    # Block is now a firm booking block
    blocks = db.query(AvailabilityBlock).filter(AvailabilityBlock.booking_id == booking["id"]).all()
    assert len(blocks) == 1 and blocks[0].block_type == BlockType.BOOKING.value


def test_failed_payment_releases_hold(client, db, dates):
    start, end = dates
    boat = _search(client, start, end)["hits"][0]["boat"]
    quote = client.post(
        "/quotes",
        json={
            "boat_id": boat["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "persons": 2,
        },
    ).json()
    created = client.post(
        "/bookings",
        json={
            "quote_id": quote["id"],
            "customer_email": "a@b.de",
            "customer_name": "Anna Bo",
            "accept_terms": True,
        },
    ).json()
    ref = created["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
    client.get(f"/webhooks/fake/{ref}", params={"fail": "true"})
    b = db.get(Booking, created["booking"]["id"])
    db.refresh(b)
    assert b.status == "cancelled"
    assert db.query(AvailabilityBlock).filter(AvailabilityBlock.booking_id == b.id).count() == 0
    # window is free again
    assert (
        client.post(
            "/quotes",
            json={
                "boat_id": boat["id"],
                "start_date": start.isoformat(),
                "end_date": end.isoformat(),
                "persons": 2,
            },
        ).status_code
        == 201
    )


def test_auth_and_charterer_portal(client, dates):
    start, end = dates
    r = client.post(
        "/auth/register",
        json={
            "email": "neu@charter.de",
            "password": "geheim123",
            "full_name": "Neu Charter",
            "role": "charterer",
            "charterer_name": "Neu Charter GmbH",
        },
    )
    assert r.status_code == 201, r.text
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}
    assert (
        client.post("/auth/register", json={"email": "neu@charter.de", "password": "geheim123"}).status_code
        == 409
    )

    me = client.get("/auth/me", headers=headers).json()
    assert me["role"] == "charterer" and me["charterer_id"]

    bases = client.get("/bases").json()
    boat = client.post(
        "/charterer/boats",
        headers=headers,
        json={
            "name": "Testboot",
            "base_id": bases[0]["id"],
            "length_m": 10.5,
            "cabins": 2,
            "berths": 4,
            "max_persons": 4,
            "headroom_cm": 190,
            "character": ["good_natured"],
            "required_license": 2,
            "min_days": 2,
        },
    )
    assert boat.status_code == 201, boat.text
    boat = boat.json()
    assert boat["boat_class"]["slug"] == "cruiser-33-37"

    bad = client.put(
        f"/charterer/boats/{boat['id']}/pricing",
        headers=headers,
        json={"reference_price_cents": 50000, "floor_price_cents": 20000, "ceiling_price_cents": 30000},
    )
    assert bad.status_code == 422
    ok = client.put(
        f"/charterer/boats/{boat['id']}/pricing",
        headers=headers,
        json={"reference_price_cents": 25000, "floor_price_cents": 15000, "ceiling_price_cents": 35000},
    )
    assert ok.status_code == 200

    # Block a window, then it must be unavailable in search
    blk = client.post(
        f"/charterer/boats/{boat['id']}/blocks",
        headers=headers,
        json={
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=3)).isoformat(),
            "block_type": "maintenance",
        },
    )
    assert blk.status_code == 201
    hits = _search(client, start, end, license_level=2)["hits"]
    assert all(h["boat"]["id"] != boat["id"] for h in hits)
    later = _search(client, start + timedelta(days=4), end + timedelta(days=4), license_level=2)["hits"]
    assert any(h["boat"]["id"] == boat["id"] for h in later)

    # Other charterer cannot touch it
    other = client.post(
        "/auth/register", json={"email": "other@charter.de", "password": "geheim123", "role": "charterer"}
    ).json()
    r = client.put(
        f"/charterer/boats/{boat['id']}/pricing",
        headers={"Authorization": f"Bearer {other['access_token']}"},
        json={"reference_price_cents": 1, "floor_price_cents": 1, "ceiling_price_cents": 1},
    )
    assert r.status_code == 404

    # Customers are locked out of the portal
    cust = client.post("/auth/login", json={"email": "segler@example.com", "password": "segeln123"}).json()
    assert (
        client.get(
            "/charterer/boats", headers={"Authorization": f"Bearer {cust['access_token']}"}
        ).status_code
        == 403
    )


def test_calendar(client, dates):
    start, _ = dates
    slug = client.get(
        "/search",
        params={"start_date": start.isoformat(), "end_date": (start + timedelta(days=5)).isoformat()},
    ).json()["hits"][0]["boat"]["slug"]
    r = client.get(f"/boats/{slug}/calendar", params={"start": start.isoformat(), "days": 10, "nights": 5})
    assert r.status_code == 200
    days = r.json()["days"]
    assert len(days) == 10 and all(d["per_day_cents"] for d in days if d["available"])
