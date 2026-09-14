# Sailbase

Eine Plattform, die aus einem Boot einen dynamisch buchbaren Vermögenswert macht: Preisoptimierung,
Zahlung und operative Abwicklung in einem Portal.

Der Chartermarkt vergibt Wochenpreise ein Jahr im Voraus. Sailbase macht es wie die Hotellerie:
Preise folgen Saison, Nachfrage und Vorlaufzeit, und der Kalender kennt mehr als Samstag bis Samstag.

## Was drin ist

| Baustein | Wo | Kern |
|---|---|---|
| Dynamic Pricing | `apps/api/app/services/pricing/` | Tages- und Törnfaktoren, Korridor aus Mindest- und Höchstpreis des Eigners, erklärbare Aufschlüsselung |
| Opportunitätskosten | `apps/api/app/services/pricing/gap.py` | Eine Buchung wird nur angeboten, wenn sie mehr bringt als die Resttage kosten, die sie unverkäuflich macht |
| Flexible Angebote | `apps/api/app/services/offers.py` | „3–5 Nächte zwischen dem 10. und 20. Juni" wird zu konkreten, wirtschaftlich sinnvollen Angeboten |
| Crew-Matching | `apps/api/app/services/matching/` | Harte Filter (Schein, Kojen) plus Fit-Score aus Stehhöhe, Kojenlänge, Charakter und Budget |
| One-Way | `apps/api/app/services/routing.py` | Bootsposition über die Zeit, Überführungskosten, Rückführungsrisiko, Rabatt für die Crew, die zurücksegelt |
| Buchung und Vertrag | `apps/api/app/services/bookings.py`, `contracts.py` | Angebot → Hold → Zahlung → Bestätigung, Vertrag aus Boots- und Buchungsdaten |
| Operations | `apps/api/app/services/operations.py` | Bootsbereitschaft, Übergabe, Rücknahme mit Fotopflicht, Schadenfälle, Kautionseinbehalt, Auszahlung |
| Portal | `apps/web/` | Suche, Bootsdetail mit Preisbegründung, Buchung, Kundenportal |

Rollen: Charterkunde, Bootseigner bzw. Charterunternehmen, Servicepartner, Admin.

## Lokal starten

```bash
# Backend
cd apps/api
uv venv .venv && uv pip install --python .venv/bin/python -e ".[dev]"
.venv/bin/python -m app.seed.seed
.venv/bin/uvicorn app.main:app --reload          # http://localhost:8000/docs

# Portal
cd ../web
npm install
API_URL=http://localhost:8000 npm run dev        # http://localhost:3000
```

Oder alles zusammen: `docker compose up --build`.

## Tests und Linting

```bash
cd apps/api && .venv/bin/python -m pytest -q && .venv/bin/ruff check app tests
cd apps/web && npm run lint && npm run build
```

## Demo-Zugänge

Nach dem Seeding stehen bereit:

| Rolle | E-Mail | Passwort |
|---|---|---|
| Vercharterer | `charter@ostsee-yachting.example` | `charter123` |
| Servicepartner | `service@hafenhelfer.example` | `partner123` |
| Kunde | `segler@example.com` | `segeln123` |

## Deployment

Railway, zwei Services aus diesem Repo plus Postgres. Details in
[`docs/deployment.md`](docs/deployment.md).
