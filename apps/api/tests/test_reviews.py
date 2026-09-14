"""Verified reviews and image provenance."""

from datetime import timedelta

from app.models import Booking, BookingStatus


def _book_and_finish(client, db, dates, status=BookingStatus.RETURNED.value):
    start, end = dates
    boat = client.get("/boats/nordwind").json()
    quote = client.post(
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
            "quote_id": quote["id"],
            "customer_email": "gast@example.com",
            "customer_name": "Gudrun Gast",
            "accept_terms": True,
        },
    ).json()
    ref = created["checkout_url"].split("/webhooks/fake/")[1].split("?")[0]
    client.get(f"/webhooks/fake/{ref}")
    booking = db.query(Booking).filter(Booking.id == created["booking"]["id"]).one()
    booking.status = status
    db.commit()
    return created["booking"]["reference"]


def test_review_requires_a_finished_charter(client, db, dates):
    reference = _book_and_finish(client, db, dates, status=BookingStatus.CONFIRMED.value)
    guest = {"email": "gast@example.com"}

    status = client.get(f"/bookings/{reference}/review", params=guest).json()
    assert status["may_review"] is False and "Rückgabe" in status["reason"]

    r = client.put(f"/bookings/{reference}/review", params=guest, json={"rating_condition": 5})
    assert r.status_code == 409


def test_guest_reviews_and_photos_reach_the_boat_page(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    guest = {"email": "gast@example.com"}

    assert client.get(f"/bookings/{reference}/review", params=guest).json()["may_review"] is True
    r = client.put(
        f"/bookings/{reference}/review",
        params=guest,
        json={
            "rating_model": 5,
            "rating_condition": 4,
            "rating_service": 5,
            "rating_cleanliness": 4,
            "title": "Schöner Törn",
            "body": "Alles wie beschrieben.",
            "photos": ["https://example.test/gast1.jpg", "https://example.test/gast2.jpg"],
        },
    )
    assert r.status_code == 200, r.text
    review = r.json()
    assert review["overall"] == 4.67
    assert review["charter_month"] == dates[0].strftime("%Y-%m")
    assert len(review["photos"]) == 2

    boat = client.get("/boats/nordwind").json()
    guest_images = [i for i in boat["gallery"] if i["origin"] == "guest"]
    assert any(i["url"] == "https://example.test/gast1.jpg" for i in guest_images)
    assert all(i["charter_month"] for i in guest_images), "Gastfotos tragen den Chartermonat"
    assert boat["ratings"]["count"] >= 1
    assert boat["ratings"]["model"] and boat["ratings"]["service"]

    listed = client.get("/boats/nordwind/reviews").json()
    assert listed["summary"]["count"] == len(listed["reviews"])
    assert any(rv["title"] == "Schöner Törn" for rv in listed["reviews"])


def test_one_review_per_booking_and_edit_replaces_photos(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    guest = {"email": "gast@example.com"}
    first = client.put(
        f"/bookings/{reference}/review",
        params=guest,
        json={"rating_condition": 3, "photos": ["https://example.test/a.jpg"]},
    ).json()
    second = client.put(
        f"/bookings/{reference}/review",
        params=guest,
        json={"rating_condition": 5, "photos": ["https://example.test/b.jpg"]},
    ).json()
    assert first["id"] == second["id"], "eine Bewertung je Buchung"
    assert second["rating_condition"] == 5
    assert second["photos"] == ["https://example.test/b.jpg"]

    boat = client.get("/boats/nordwind").json()
    urls = [i["url"] for i in boat["gallery"]]
    assert "https://example.test/a.jpg" not in urls
    assert "https://example.test/b.jpg" in urls


def test_a_stranger_cannot_review_someone_elses_charter(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    r = client.put(
        f"/bookings/{reference}/review",
        params={"email": "fremd@example.com"},
        json={"rating_condition": 1},
    )
    assert r.status_code == 403
    assert client.put(f"/bookings/{reference}/review", json={"rating_condition": 1}).status_code == 403


def test_review_needs_at_least_one_main_rating(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    r = client.put(
        f"/bookings/{reference}/review",
        params={"email": "gast@example.com"},
        json={"rating_cleanliness": 5},
    )
    assert r.status_code == 422


def test_gallery_order_and_handover_photos_stay_private(client, db, dates):
    from app.models import Boat, BoatImage

    boat = db.query(Boat).filter(Boat.slug == "nordwind").one()
    db.add(
        BoatImage(
            boat_id=boat.id,
            url="https://example.test/uebergabe.jpg",
            origin="handover",
            sort_order=1,
        )
    )
    db.commit()
    gallery = client.get("/boats/nordwind").json()["gallery"]
    assert all(i["origin"] != "handover" for i in gallery), "Übergabefotos sind nicht öffentlich"
    origins = [i["origin"] for i in gallery]
    assert origins.index("owner") < origins.index("model"), "Modellfotos stehen hinten"


def test_summary_averages_the_three_dimensions_apart(client, db, dates):
    """Model, boat condition and service are rated separately and stay separate."""
    start, end = dates
    first = _book_and_finish(client, db, dates)
    client.put(
        f"/bookings/{first}/review",
        params={"email": "gast@example.com"},
        json={"rating_model": 5, "rating_condition": 3, "rating_service": 1},
    )
    second = _book_and_finish(client, db, (start + timedelta(days=30), end + timedelta(days=30)))
    client.put(
        f"/bookings/{second}/review",
        params={"email": "gast@example.com"},
        json={"rating_model": 5, "rating_condition": 1, "rating_service": 3},
    )
    ratings = client.get("/boats/nordwind").json()["ratings"]
    assert ratings["count"] == 2
    assert ratings["model"] == 5.0
    assert ratings["condition"] == 2.0
    assert ratings["service"] == 2.0
    assert ratings["overall"] == 3.0


def test_review_window_survives_settlement(client, db, dates):
    reference = _book_and_finish(client, db, dates, status=BookingStatus.SETTLED.value)
    r = client.put(
        f"/bookings/{reference}/review",
        params={"email": "gast@example.com"},
        json={"rating_service": 4},
    )
    assert r.status_code == 200


def test_photo_limit(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    r = client.put(
        f"/bookings/{reference}/review",
        params={"email": "gast@example.com"},
        json={
            "rating_service": 4,
            "photos": [f"https://example.test/{i}.jpg" for i in range(13)],
        },
    )
    assert r.status_code == 422


def test_review_month_follows_the_charter_not_the_upload(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    booking = db.query(Booking).filter(Booking.reference == reference).one()
    booking.start_date = booking.start_date - timedelta(days=400)
    booking.end_date = booking.end_date - timedelta(days=400)
    db.commit()
    review = client.put(
        f"/bookings/{reference}/review",
        params={"email": "gast@example.com"},
        json={"rating_service": 5},
    ).json()
    assert review["charter_month"] == booking.start_date.strftime("%Y-%m")


def test_guest_can_upload_a_photo_with_the_booking_as_proof(client, db, dates):
    reference = _book_and_finish(client, db, dates)
    jpeg = ("bild.jpg", b"\xff\xd8\xff", "image/jpeg")

    assert client.post(f"/bookings/{reference}/uploads", files={"file": jpeg}).status_code == 403
    r = client.post(
        f"/bookings/{reference}/uploads",
        params={"email": "gast@example.com"},
        files={"file": jpeg},
    )
    assert r.status_code == 201 and r.json()["url"].endswith(".jpg")
    assert (
        client.post(
            f"/bookings/{reference}/uploads",
            params={"email": "fremd@example.com"},
            files={"file": jpeg},
        ).status_code
        == 403
    )
