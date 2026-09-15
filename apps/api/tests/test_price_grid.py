"""Das Preisraster muss vergleichbar sein — sonst führt es in die Irre.

Ein Raster, das je Zelle ein anderes Boot, eine andere Dauer oder einen anderen
Hafen meint, sieht aus wie ein Preisvergleich, ist aber keiner. Diese Tests
halten fest, worauf sich der Vergleich stützt: dieselben Filter wie die Suche,
je Zelle das günstigste Boot, und Preise, die auch ein Angebot hergeben.
"""

from datetime import timedelta

import pytest

from app.services import pricegrid
from app.services.matching import CrewProfile


@pytest.fixture()
def window(dates):
    start, _ = dates
    return start, start + timedelta(days=30)


def _params(start, end, **extra):
    return {
        "window_start": start.isoformat(),
        "window_end": end.isoformat(),
        "min_nights": 5,
        "max_nights": 9,
        "persons": 2,
        "license_level": 2,
        "experience_nm": 2000,
        **extra,
    }


def test_raster_liefert_je_starttag_und_dauer_eine_zelle(client, window):
    start, end = window
    r = client.get("/search/price-grid", params=_params(start, end))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["durations"] == [5, 6, 7, 8, 9]
    assert data["cells"], "Kein einziger Preis im Fenster"
    assert data["boats_considered"] > 0

    gesehen = set()
    for cell in data["cells"]:
        key = (cell["start_date"], cell["nights"])
        assert key not in gesehen, f"Zelle doppelt: {key}"
        gesehen.add(key)
        assert cell["nights"] in data["durations"]
        assert cell["total_cents"] > 0 and cell["per_day_cents"] > 0
        assert cell["boat_slug"] and cell["boat_name"]
        assert cell["boat_count"] >= 1


def test_zellen_bleiben_im_fenster(client, window):
    """Ein Törn, der über das Fenster hinausragt, ist keine Antwort auf die Frage."""
    start, end = window
    r = client.get("/search/price-grid", params=_params(start, end))
    for cell in r.json()["cells"]:
        assert cell["start_date"] >= start.isoformat()
        assert cell["end_date"] <= end.isoformat()


def test_zelle_nennt_das_guenstigste_boot(client, db, window):
    """Sonst steht im Raster ein Preis, den man an anderer Stelle nicht bekommt."""
    start, end = window
    r = client.get("/search/price-grid", params=_params(start, end))
    cells = r.json()["cells"]
    assert cells
    probe = cells[0]

    # Dieselbe Zelle über die Suche gegenprüfen: exakte Daten, ein Ergebnis je Boot.
    s = client.get(
        "/search",
        params={
            "start_date": probe["start_date"],
            "end_date": probe["end_date"],
            "persons": 2,
            "license_level": 2,
            "experience_nm": 2000,
            "sort": "price_asc",
        },
    )
    assert s.status_code == 200, s.text
    treffer = [h for h in s.json()["hits"] if h["available"] and h["total_cents"]]
    assert treffer, "Suche findet die Zelle nicht wieder"
    guenstigster = min(h["total_cents"] for h in treffer)
    assert probe["total_cents"] == guenstigster
    assert probe["boat_count"] == len(treffer)


def test_ein_boot_laesst_sich_einzeln_rastern(client, db, window):
    """Die Bootsseite fragt dasselbe Raster, nur auf ein Schiff eingegrenzt."""
    start, end = window
    voll = client.get("/search/price-grid", params=_params(start, end)).json()
    slug = voll["cells"][0]["boat_slug"]
    eins = client.get("/search/price-grid", params=_params(start, end, boat_slug=slug)).json()
    assert eins["boats_considered"] == 1
    assert {c["boat_slug"] for c in eins["cells"]} == {slug}
    assert {c["boat_count"] for c in eins["cells"]} == {1}


def test_budget_wirkt_je_zelle_nicht_je_boot(client, window):
    """Ein Boot kann in der einen Woche im Rahmen liegen und in der nächsten nicht."""
    start, end = window
    offen = client.get("/search/price-grid", params=_params(start, end)).json()["cells"]
    assert offen
    grenze = min(c["total_cents"] for c in offen) + 1
    eng = client.get("/search/price-grid", params=_params(start, end, max_price=grenze)).json()["cells"]
    assert eng, "Das Budget lässt nichts übrig, obwohl die günstigste Zelle hineinpasst"
    assert all(c["total_cents"] <= grenze for c in eng)
    assert len(eng) < len(offen)


def test_unsinnige_fenster_werden_abgewiesen(client, window):
    start, end = window
    assert client.get("/search/price-grid", params=_params(end, start)).status_code == 422
    # Dauer passt nicht ins Fenster
    kurz = start + timedelta(days=4)
    assert client.get("/search/price-grid", params=_params(start, kurz)).status_code == 422
    # max_nights unter min_nights
    r = client.get("/search/price-grid", params=_params(start, end, min_nights=9, max_nights=5))
    assert r.status_code == 422


def test_langes_fenster_wird_gekappt_statt_abgewiesen(client, dates):
    """Ein zu großes Fenster ist ein Bedienfehler, kein Grund für eine Fehlerseite."""
    start, _ = dates
    end = start + timedelta(days=pricegrid.MAX_WINDOW_DAYS + 60)
    r = client.get("/search/price-grid", params=_params(start, end))
    assert r.status_code == 200
    data = r.json()
    erwartet = start + timedelta(days=pricegrid.MAX_WINDOW_DAYS)
    assert data["window_end"] == erwartet.isoformat()


def test_zahl_der_dauern_ist_gedeckelt(client, dates):
    """Mehr Spalten liest niemand, und jede kostet Rechenzeit."""
    start, _ = dates
    end = start + timedelta(days=60)
    r = client.get("/search/price-grid", params=_params(start, end, min_nights=1, max_nights=40))
    assert len(r.json()["durations"]) == pricegrid.MAX_DURATIONS


def test_deckel_kuerzt_das_raster_und_sagt_es(db, dates, monkeypatch):
    """Lieber eine ehrliche Teilauskunft als eine hängende Seite."""
    start, _ = dates
    monkeypatch.setattr(pricegrid, "MAX_EVALUATIONS", 20)
    grid = pricegrid.build(
        db,
        pricegrid.GridQuery(
            window_start=start,
            window_end=start + timedelta(days=60),
            min_nights=5,
            max_nights=9,
            crew=CrewProfile(persons=2, skip_qualification_check=True),
        ),
    )
    assert grid.truncated is True
    assert grid.evaluations <= 20


def test_guenstigster_torn_rechnet_pro_nacht(db, dates):
    """Über den Gesamtpreis gewönne immer die kürzeste Dauer — das wäre kein Fund."""
    start, _ = dates
    grid = pricegrid.build(
        db,
        pricegrid.GridQuery(
            window_start=start,
            window_end=start + timedelta(days=30),
            min_nights=5,
            max_nights=9,
            crew=CrewProfile(persons=2, skip_qualification_check=True),
        ),
    )
    best = grid.cheapest
    assert best is not None
    assert best.per_day_cents == min(c.per_day_cents for c in grid.cells)

    fuer_sieben = grid.cheapest_for(7)
    assert fuer_sieben is not None and fuer_sieben.nights == 7
    assert fuer_sieben.total_cents == min(c.total_cents for c in grid.cells if c.nights == 7)
