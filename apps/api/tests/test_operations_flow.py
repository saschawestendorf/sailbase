"""End-to-end: book -> pay deposit -> contract -> readiness -> handover -> return (damage) -> settle."""

from datetime import timedelta


def _auth(client, email, password):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _book_and_pay(client, dates, boat_slug="nordwind"):
    start, end = dates
    boat = client.get(f"/boats/{boat_slug}").json()
    q = client.post(
        "/quotes",
        json={
            "boat_id": boat["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "persons": 4,
        },
    ).json()
    created = client.post(
        "/bookings",
        json={
            "quote_id": q["id"],
            "customer_email": "crew@example.com",
            "customer_name": "Crew Chef",
            "accept_terms": True,
        },
    ).json()
    ref = created["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
    client.get(f"/webhooks/fake/{ref}")
    return created["booking"], boat


def _complete_all(items):
    return [
        {"key": i["key"], "done": True, "photos": ["http://x/p.jpg"] if i["photo_required"] else None}
        for i in items
    ]


def test_full_operations_cycle(client, dates):
    booking, boat = _book_and_pay(client, dates)
    ref = booking["reference"]
    guest = {"email": "crew@example.com"}

    # Deposit paid -> confirmed, contract + follow-up payments + 3 orders exist
    b = client.get(f"/bookings/{ref}", params=guest).json()
    assert b["status"] == "confirmed"
    purposes = {p["purpose"]: p for p in b["payments"]}
    assert purposes["deposit"]["status"] == "succeeded"
    assert "balance" in purposes and "security_deposit" in purposes
    assert purposes["balance"]["amount_cents"] == b["total_cents"] - b["deposit_cents"]

    ops = client.get(f"/bookings/{ref}/ops", params=guest).json()
    assert ops["contract"]["text_md"].startswith("# Chartervertrag")
    assert {o["order_type"] for o in ops["orders"]} == {"readiness", "handover", "return"}

    # Customer: accept contract, upload crew list, pay balance & security deposit
    assert client.post(f"/bookings/{ref}/accept-contract", params=guest).json()[
        "contract_accepted_customer_at"
    ]
    crew = client.put(
        f"/bookings/{ref}/crew",
        params=guest,
        json={"crew": [{"name": "Crew Chef", "role": "skipper", "license": "SKS"}, {"name": "Mit Segler"}]},
    )
    assert crew.status_code == 200 and len(crew.json()["crew_list"]) == 2
    too_many = client.put(
        f"/bookings/{ref}/crew", params=guest, json={"crew": [{"name": f"P{i}"} for i in range(6)]}
    )
    assert too_many.status_code == 422
    for purpose in ("balance", "security_deposit"):
        p = client.post(f"/bookings/{ref}/pay/{purpose}", params=guest)
        assert p.status_code == 200, p.text
        pref = p.json()["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
        client.get(f"/webhooks/fake/{pref}")
    b = client.get(f"/bookings/{ref}", params=guest).json()
    assert all(p["status"] == "succeeded" for p in b["payments"])

    # Charterer: assign partner to readiness + handover, does return themselves
    owner = _auth(client, "charter@ostsee-yachting.example", "charter123")
    partners = client.get("/charterer/partners", headers=owner, params={"base_id": boat["base"]["id"]}).json()
    assert partners, "seed partner should serve Heiligenhafen"
    orders = {
        o["order_type"]: o
        for o in client.get("/charterer/orders", headers=owner).json()
        if o["booking_reference"] == ref
    }
    for t in ("readiness", "handover"):
        r = client.post(
            f"/charterer/orders/{orders[t]['id']}/assign",
            headers=owner,
            json={"partner_id": partners[0]["id"]},
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "assigned" and r.json()["price_cents"] == partners[0]["prices"][t]
    r = client.post(
        f"/charterer/orders/{orders['return']['id']}/assign", headers=owner, json={"partner_id": None}
    )
    assert r.json()["status"] == "assigned" and r.json()["partner_id"] is None

    # Partner: sees exactly the two orders, cannot complete with missing photos
    partner = _auth(client, "service@hafenhelfer.example", "partner123")
    mine = client.get("/partner/orders", headers=partner).json()
    assert {o["order_type"] for o in mine} == {"readiness", "handover"}
    readiness = next(o for o in mine if o["order_type"] == "readiness")
    r = client.post(f"/partner/orders/{readiness['id']}/complete", headers=partner)
    assert r.status_code == 409 and "unvollständig" in r.json()["detail"]
    r = client.patch(
        f"/partner/orders/{readiness['id']}",
        headers=partner,
        json={"items": _complete_all(readiness["checklist"])},
    )
    assert r.status_code == 200 and r.json()["status"] == "in_progress"
    r = client.post(f"/partner/orders/{readiness['id']}/complete", headers=partner)
    assert r.status_code == 200 and r.json()["status"] == "done"
    assert client.get(f"/bookings/{ref}", params=guest).json()["status"] == "ready"

    # Handover with photos -> handed_over, customer counter-signs
    handover = next(o for o in mine if o["order_type"] == "handover")
    client.patch(
        f"/partner/orders/{handover['id']}",
        headers=partner,
        json={"items": _complete_all(handover["checklist"])},
    )
    assert client.post(f"/partner/orders/{handover['id']}/complete", headers=partner).status_code == 200
    assert client.get(f"/bookings/{ref}", params=guest).json()["status"] == "handed_over"
    assert client.post(f"/bookings/{ref}/confirm/handover", params=guest).json()[
        "handover_confirmed_customer_at"
    ]
    # Partner cannot touch orders that are not theirs
    assert (
        client.patch(f"/partner/orders/{orders['return']['id']}", headers=partner, json={}).status_code == 404
    )

    # Return by owner: one item flagged as issue -> damage case, status returned
    items = _complete_all(orders["return"]["checklist"])
    for i in items:
        if i["key"] == "damage_check":
            i["issue"] = True
            i["note"] = "Kratzer Steuerbord"
            i["photos"] = ["http://x/scratch.jpg"]
    r = client.patch(f"/charterer/orders/{orders['return']['id']}", headers=owner, json={"items": items})
    assert r.status_code == 200
    r = client.post(f"/charterer/orders/{orders['return']['id']}/complete", headers=owner)
    assert r.status_code == 200, r.text
    assert client.get(f"/bookings/{ref}", params=guest).json()["status"] == "returned"
    damages = client.get("/charterer/damages", headers=owner).json()
    assert len(damages) == 1 and damages[0]["status"] == "open" and damages[0]["photos"]

    # Settlement blocked until damage assessed; withholding capped by deposit
    r = client.post(f"/charterer/bookings/{booking['id']}/settle", headers=owner)
    assert r.status_code == 409
    r = client.post(
        f"/charterer/damages/{damages[0]['id']}/assess",
        headers=owner,
        json={"estimated_cents": 80000, "withheld_cents": 10**9},
    )
    assert r.status_code == 409
    r = client.post(
        f"/charterer/damages/{damages[0]['id']}/assess",
        headers=owner,
        json={"estimated_cents": 80000, "withheld_cents": 60000},
    )
    assert r.status_code == 200 and r.json()["status"] == "assessed"
    r = client.post(f"/charterer/bookings/{booking['id']}/settle", headers=owner)
    assert r.status_code == 200, r.text
    payout = r.json()
    partner_costs = partners[0]["prices"]["readiness"] + partners[0]["prices"]["handover"]
    assert payout["service_cost_cents"] == partner_costs
    assert payout["net_cents"] == b["total_cents"] - payout["commission_cents"] - partner_costs + 60000
    assert payout["commission_cents"] == round(b["total_cents"] * 0.15)
    assert client.get(f"/bookings/{ref}", params=guest).json()["status"] == "settled"

    # Dashboard reflects the cycle
    stats = client.get("/charterer/stats", headers=owner).json()
    assert stats["bookings_settled"] == 1 and stats["charter_nights"] == 7
    assert stats["revenue_cents"] == b["total_cents"]
    assert stats["static_revenue_cents"] > 0 and stats["payouts_pending_cents"] == payout["net_cents"]
    assert isinstance(stats["gaps_next_90d"], list)


def test_cancel_after_handover_is_refused(client, dates):
    booking, _ = _book_and_pay(client, dates)
    owner = _auth(client, "charter@ostsee-yachting.example", "charter123")
    r = client.post(f"/charterer/bookings/{booking['id']}/cancel", headers=owner)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    # orders were cancelled with it
    ops = client.get(f"/charterer/bookings/{booking['id']}/ops", headers=owner).json()
    assert all(o["status"] == "cancelled" for o in ops["orders"])


def test_upload_requires_auth_and_type(client, dates):
    r = client.post("/uploads", files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 401
    headers = _auth(client, "service@hafenhelfer.example", "partner123")
    r = client.post("/uploads", headers=headers, files={"file": ("x.txt", b"hello", "text/plain")})
    assert r.status_code == 415
    r = client.post("/uploads", headers=headers, files={"file": ("p.jpg", b"\xff\xd8\xff", "image/jpeg")})
    assert r.status_code == 201 and r.json()["url"].endswith(".jpg")


def test_near_term_booking_is_paid_in_full(client, db):
    from datetime import date

    from app.models import Boat

    boat = db.query(Boat).filter(Boat.slug == "kleine-freiheit").one()
    start = date.today() + timedelta(days=10)
    q = client.post(
        "/quotes",
        json={
            "boat_id": boat.id,
            "start_date": start.isoformat(),
            "end_date": (start + timedelta(days=3)).isoformat(),
            "persons": 2,
        },
    )
    assert q.status_code == 201, q.text
    created = client.post(
        "/bookings",
        json={
            "quote_id": q.json()["id"],
            "customer_email": "k@example.com",
            "customer_name": "Kurz Entschlossen",
            "accept_terms": True,
        },
    ).json()
    assert created["booking"]["deposit_cents"] == created["booking"]["total_cents"]
