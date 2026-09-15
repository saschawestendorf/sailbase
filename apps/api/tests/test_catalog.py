"""Master catalog: browsing, resolving a configuration, listing a boat from it."""

import pytest

from app.models import Boat, ModelVersion, VariantOption
from app.services import catalog as catalog_service


def _auth(client, email="charter@ostsee-yachting.example", password="charter123"):
    r = client.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_browse_catalog(client):
    manufacturers = client.get("/catalog/manufacturers").json()
    assert {m["slug"] for m in manufacturers} >= {"bavaria", "hanse", "x-yachts"}

    models = client.get("/catalog/models", params={"q": "cruiser"}).json()
    assert models and all("Cruiser" in m["name"] for m in models)
    assert client.get("/catalog/models", params={"manufacturer": "dehler"}).json()

    detail = client.get(f"/catalog/models/{models[0]['id']}").json()
    version = detail["versions"][0]
    assert version["source"], "Herkunft der Daten muss sichtbar bleiben"
    assert {v["kind"] for v in version["variants"]} >= {"layout", "keel"}


def test_resolve_applies_variants_over_version(client, db):
    version = (
        db.query(ModelVersion)
        .join(ModelVersion.model)
        .filter(ModelVersion.variants.any(VariantOption.code == "flach"))
        .first()
    )
    assert version is not None
    shoal = next(v for v in version.variants if v.code == "flach")

    plain = client.post("/catalog/resolve", json={"version_id": version.id}).json()
    with_shoal = client.post(
        "/catalog/resolve", json={"version_id": version.id, "variant_ids": [shoal.id]}
    ).json()
    assert with_shoal["values"]["draft_m"] == shoal.draft_m
    assert with_shoal["values"]["draft_m"] < plain["values"]["draft_m"]
    assert with_shoal["sources"]["draft_m"] == f"variant:{shoal.code}"
    assert "shallow_draft" in with_shoal["features"]


def test_resolve_rejects_implausible_year_and_foreign_variant(client, db):
    versions = db.query(ModelVersion).all()
    version, other = versions[0], versions[1]
    r = client.post("/catalog/resolve", json={"version_id": version.id, "year_built": 1975})
    assert r.status_code == 422 and "Baujahr" in r.json()["detail"]

    foreign = other.variants[0]
    r = client.post("/catalog/resolve", json={"version_id": version.id, "variant_ids": [foreign.id]})
    assert r.status_code == 422

    two_keels = [v.id for v in version.variants if v.kind == "keel"][:2]
    if len(two_keels) == 2:
        r = client.post("/catalog/resolve", json={"version_id": version.id, "variant_ids": two_keels})
        assert r.status_code == 422 and "Mehrere Varianten" in r.json()["detail"]


def test_list_boat_from_catalog(client, db):
    headers = _auth(client)
    bases = client.get("/bases").json()
    version = (
        db.query(ModelVersion)
        .join(ModelVersion.model)
        .filter(ModelVersion.variants.any(VariantOption.code == "3-kab"))
        .first()
    )
    three_cabins = next(v for v in version.variants if v.code == "3-kab")
    # Der Katalog wird ohne Werftfotos ausgeliefert (ungeklaerte Bildrechte).
    # Dieser Test prueft die Herkunftstrennung, also hinterlegt er selbst eines.
    version.model_images = ["https://example.test/werksfoto.jpg"]
    db.commit()

    payload = {
        "version_id": version.id,
        "variant_ids": [three_cabins.id],
        "year_built": version.year_from + 1,
        "name": "Katalogboot",
        "base_id": bases[0]["id"],
        "description": "Aus dem Katalog eingestellt.",
        "images": ["https://example.test/eigen.jpg"],
        "min_days": 3,
        "max_days": 21,
        "deposit_cents": 200000,
    }
    r = client.post("/charterer/boats/from-catalog", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    boat = r.json()

    # Specs come from the catalog, not from the form
    assert boat["cabins"] == three_cabins.cabins
    assert boat["length_m"] == version.length_m
    assert boat["manufacturer"] and boat["model"]
    assert boat["spec_sources"]["cabins"] == f"variant:{three_cabins.code}"
    assert boat["spec_sources"]["length_m"] == "version"
    assert boat["model_version_id"] == version.id

    # Gallery keeps origin apart: the owner's photo and the model photo are not the same thing
    detail = client.get(f"/boats/{boat['slug']}").json()
    origins = {i["origin"] for i in detail["gallery"]}
    assert origins == {"owner", "model"}
    assert detail["model_info"]["build_years"]


def test_catalog_listing_rejects_impossible_year(client, db):
    headers = _auth(client)
    bases = client.get("/bases").json()
    version = db.query(ModelVersion).first()
    r = client.post(
        "/charterer/boats/from-catalog",
        headers=headers,
        json={
            "version_id": version.id,
            "year_built": 1960,
            "name": "Zeitreise",
            "base_id": bases[0]["id"],
        },
    )
    assert r.status_code == 422 and "Baujahr" in r.json()["detail"]


def test_owner_deviation_is_documented(client, db):
    headers = _auth(client)
    bases = client.get("/bases").json()
    version = db.query(ModelVersion).first()
    r = client.post(
        "/charterer/boats/from-catalog",
        headers=headers,
        json={
            "version_id": version.id,
            "year_built": version.year_from,
            "name": "Umgebaut",
            "base_id": bases[0]["id"],
            "spec_overrides": {"sail_area_m2": 999},
        },
    )
    assert r.status_code == 201, r.text
    boat = r.json()
    assert boat["sail_area_m2"] == 999
    assert boat["spec_sources"]["sail_area_m2"] == "owner"
    assert boat["spec_overrides"]["sail_area_m2"] == 999


def test_seeded_boats_are_linked_to_the_catalog(db):
    boats = db.query(Boat).all()
    linked = [b for b in boats if b.model_version_id]
    assert len(linked) == len(boats)


def test_resolve_marks_unknown_fields(db):
    version = db.query(ModelVersion).first()
    version.water_tank_l = None
    version.displacement_kg = None
    spec = catalog_service.resolve(version, [])
    assert "displacement_kg" in spec.unknown
    assert spec.values["displacement_kg"] is None


def test_catalog_correction_does_not_touch_a_listed_boat(client, db):
    """A boat keeps the numbers it was listed with; that is what a contract refers to."""
    boat = db.query(Boat).filter(Boat.slug == "nordwind").one()
    original_length = boat.length_m
    version = db.get(ModelVersion, boat.model_version_id)
    version.length_m = original_length + 3
    db.commit()
    assert client.get("/boats/nordwind").json()["length_m"] == pytest.approx(original_length)
