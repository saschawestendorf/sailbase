"""One-way charter: location-aware availability, transfer/repositioning fees, return-leg discount."""

from datetime import timedelta

from app.models import Boat


def _bases(client):
    return {b["name"]: b for b in client.get("/bases").json()}


def _quote(client, boat_id, start, nights, **extra):
    return client.post(
        "/quotes",
        json={
            "boat_id": boat_id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=nights)).isoformat(),
            "persons": 2,
            **extra,
        },
    )


def _pay(client, quote_id):
    created = client.post(
        "/bookings",
        json={
            "quote_id": quote_id,
            "customer_email": "ow@example.com",
            "customer_name": "One Way",
            "accept_terms": True,
        },
    )
    assert created.status_code == 201, created.text
    ref = created.json()["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
    client.get(f"/webhooks/fake/{ref}")
    reference = created.json()["booking"]["reference"]
    return client.get(f"/bookings/{reference}", params={"email": "ow@example.com"}).json()


def test_one_way_cycle(client, db, dates):
    start, _ = dates
    bases = _bases(client)
    home, kiel, stralsund = (
        bases["Marina Heiligenhafen"],
        bases["Marina Kiel-Schilksee"],
        bases["Citymarina Stralsund"],
    )
    boat = db.query(Boat).filter(Boat.slug == "nordwind").one()
    assert boat.base_id == home["id"]

    # Not enabled: pickup elsewhere is refused, one-way drop-off refused
    r = _quote(client, boat.id, start, 7, pickup_base_id=kiel["id"])
    assert r.status_code == 409 and "liegt in" in r.json()["detail"]
    r = _quote(client, boat.id, start, 7, dropoff_base_id=kiel["id"])
    assert r.status_code == 409

    boat.one_way_enabled = True
    boat.one_way_fee_cents = 20000
    db.commit()

    # Drop-off outside the boat's region is not allowed by default
    r = _quote(client, boat.id, start, 7, dropoff_base_id=stralsund["id"])
    assert r.status_code == 409 and "Abgabehafen" in r.json()["detail"]

    plain = _quote(client, boat.id, start, 7).json()
    one_way = _quote(client, boat.id, start, 7, dropoff_base_id=kiel["id"]).json()
    fees = {f["key"]: f for f in one_way["breakdown"]["fee_lines"]}
    assert "one_way_fee" in fees and fees["one_way_fee"]["amount_cents"] == 20000
    assert "repositioning_risk" in fees and fees["repositioning_risk"]["amount_cents"] > 0
    assert one_way["total_cents"] > plain["total_cents"]
    assert one_way["pickup_base_id"] == home["id"] and one_way["dropoff_base_id"] == kiel["id"]

    booking = _pay(client, one_way["id"])
    assert booking["status"] == "confirmed" and booking["dropoff_base_id"] == kiel["id"]

    # Afterwards the boat is in Kiel: default pickup follows the boat
    later = start + timedelta(days=10)
    search = client.get(
        "/search",
        params={
            "start_date": later.isoformat(),
            "end_date": (later + timedelta(days=7)).isoformat(),
            "license_level": 2,
            "experience_nm": 500,
        },
    ).json()
    hit = next(h for h in search["hits"] if h["boat"]["id"] == boat.id)
    assert hit["offers"][0]["pickup_base_id"] == kiel["id"]

    # Pickup at home now needs a transfer (priced), and the crew sailing it home gets a discount
    transfer = _quote(client, boat.id, later, 7, pickup_base_id=home["id"]).json()
    assert any(f["key"] == "transfer_in" for f in transfer["breakdown"]["fee_lines"])
    back = _quote(client, boat.id, later, 7, pickup_base_id=kiel["id"], dropoff_base_id=home["id"]).json()
    disc = next(f for f in back["breakdown"]["fee_lines"] if f["key"] == "return_leg_discount")
    assert disc["amount_cents"] < 0
    assert back["total_cents"] < transfer["total_cents"]

    # Contract of the one-way booking names both ports
    ops = client.get(f"/bookings/{booking['reference']}/ops", params={"email": "ow@example.com"}).json()
    assert "Kiel" in ops["contract"]["text_md"] and "Heiligenhafen" in ops["contract"]["text_md"]

    # Flexible search with explicit pickup in Kiel lists the boat with Kiel legs
    flex = client.get(
        "/search",
        params={
            "start_date": later.isoformat(),
            "end_date": (later + timedelta(days=14)).isoformat(),
            "min_nights": 3,
            "max_nights": 5,
            "pickup_base_id": kiel["id"],
            "license_level": 2,
            "experience_nm": 500,
        },
    ).json()
    hit = next(h for h in flex["hits"] if h["boat"]["id"] == boat.id)
    assert all(o["pickup_base_id"] == kiel["id"] for o in hit["offers"])


def test_repositioning_must_fit_before_next_booking(client, db, dates):
    start, _ = dates
    bases = _bases(client)
    kiel = bases["Marina Kiel-Schilksee"]
    boat = db.query(Boat).filter(Boat.slug == "nordwind").one()
    boat.one_way_enabled = True
    db.commit()
    # Fixed booking at home starting right after the candidate -> no time to bring the boat back
    nxt = _quote(client, boat.id, start + timedelta(days=7), 7).json()
    _pay(client, nxt["id"])
    r = _quote(client, boat.id, start, 7, dropoff_base_id=kiel["id"])
    assert r.status_code == 409 and "Rückführung" in r.json()["detail"]
    # With a gap of a few days the repositioning is priced instead of refused
    r = _quote(client, boat.id, start, 4, dropoff_base_id=kiel["id"])
    assert r.status_code == 201, r.text
    assert any(f["key"] == "repositioning" for f in r.json()["breakdown"]["fee_lines"])
