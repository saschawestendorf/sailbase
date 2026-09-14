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

## Produktspezifikation und Ausbau

Startmarkt ist die Ostsee. Ziel ist ein Charter-Marktplatz mit Revenue Management und
operativer Abwicklung. Die folgende Spezifikation beschreibt das Zielbild, nicht eine
Zusicherung bereits fertig implementierter Funktionen.

### Boat Master Catalog und konkrete Boote

Ein zentral gepflegter Katalog bildet Hersteller → Modell → Generation/Modelljahre →
Werksvarianten ab. Modellstammdaten enthalten Maße, Konstruktion, Tankgrößen und zulässige
Layout-, Kiel-, Segel- und Motorvarianten samt Quelle, Prüfdatum und Versionsstand.
Anbieter wählen Modell, Baujahr und tatsächlich verbaute Varianten, statt technische
Daten erneut einzutragen. Unplausible Baujahre und Konfigurationen werden zurückgewiesen.
Unbekannte Daten bleiben als unbekannt erkennbar; externe Daten und Bilder benötigen
eine dokumentierte Nutzungsgrundlage.

Die Boot-Instanz verweist auf die Modellversion und ergänzt Name, Eigner/Vercharterer,
Hafen, tatsächliche Ausstattung, Umbauten, Zustand, Wartung, Dokumente, Kalender und
Preisregeln. Abweichungen vom Katalog werden explizit dokumentiert. Katalogkorrekturen
dürfen bestätigte Buchungs- und Vertragsdaten nicht nachträglich verändern.

**Stand:** `Boat` enthält bislang Modellname und technische Daten direkt. `BoatClass`
ist eine Vergleichsklasse, kein Bootsmodell. Katalogtabellen, Variantenvalidierung und
das darauf aufbauende Anbieter-Onboarding sind noch umzusetzen.

### Dynamic Pricing, Competitive Set und Customer Intent

Zielgröße ist der erwartete Erlös pro verfügbarem Bootstag unter Berücksichtigung von
Conversion, Turnaroundkosten und Opportunitätskosten verbleibender Kalenderlücken.
Eigner konfigurieren Referenzpreis, Mindest-/Höchstpreis, Strategie, Saisonregeln und
erlaubte Dauern. Preisentscheidungen müssen erklärbar und reproduzierbar bleiben.

Ein mehrdimensionales Competitive Set gewichtet echte Alternativen anhand von Hafen,
Revier und räumlicher Austauschbarkeit, Länge, Kabinen, Kojen, Kapazität, Bootscharakter,
Segelkonfiguration (z. B. Rollgroß), Handling (z. B. Doppelruder), Komfort, Alter und
belegtem Zustand. Ein Boat-to-Boat Similarity Score bestimmt das Gewicht jedes Bootes;
Auslastung und vergleichbare Gesamtpreise werden für denselben Zeitraum betrachtet.
Externe Angebote sind eine mögliche spätere Datenquelle mit Herkunft, Aktualität,
Gebührennormalisierung und geklärten Zugriffsrechten. Nicht verfügbare externe Angebote
sind nicht automatisch nachgewiesene Buchungen.

Customer Intent entsteht zunächst aus der aktuellen Suche: Zeitraum/Flexibilität,
Häfen, Crewgröße, Qualifikation, Budget, Komfort- und Segelpräferenzen. Ein optionales
Profil kann Präferenzen speichern. Harte Anforderungen filtern Angebote; weiche
Präferenzen liefern einen erklärbaren Customer-to-Boat Fit-Score. Dieser ist vom
Boat-to-Boat Similarity Score getrennt. Alternative Häfen oder Termine werden sichtbar
als Alternativen angeboten und verletzen keine stillschweigend gesetzten Muss-Kriterien.

**Erste Ausbaustufe:** Die bestehende Nachfrageberechnung nutzt nun ein heuristisch
gewichtetes Competitive Set innerhalb derselben Region und Bootsklasse: Hafen, Länge,
Kabinen, Kojen, Charakter und vorhandene Ausstattung. Überlappende Buchungen/Holds werden
pro Boot zusammengeführt. Abgelaufene Holds und Wartung zählen nicht als Nachfrage.
Das eigene Boot bleibt mit Gewicht 1 enthalten; ohne Vergleichsdaten liefert die
bestehende Schnittstelle 0. Die Gewichte sind noch nicht empirisch kalibriert.
Region/Klasse bleiben grobe Grenzen; Alter, Zustand, dedizierte Segel-/Rudermerkmale,
externe Marktpreise und datenbasierte Kalibrierung folgen nach strukturierter Datenerfassung.
Crew-Matching und das bestehende Pricing bleiben getrennte Services.

### Flexible Charter, Marketplace und Payment

Kunden suchen konkrete Daten oder ein Zeitfenster mit Mindest-/Höchstdauer. Wochenenden,
Kurzcharter und längere Törns berücksichtigen Vorlauf, Wechseltage, Sperren, Turnaround,
Dienstleisterkapazität und Restlücken. Der Gesamtpreis zeigt Charter, Pflichtgebühren,
Extras und Kaution getrennt. Der Ablauf ist Angebot mit Ablaufzeit → temporärer Hold →
Zahlung → bestätigte Buchung/Vertrag. Wiederholte Zahlungsereignisse dürfen keine doppelten
Buchungen oder Zahlungen auslösen. Storno, Erstattung, Restzahlung, Kaution und Auszahlung
benötigen nachvollziehbare Statuswechsel und Zugriffsrechte.

**Stand:** Flexible Angebote, Holds, Verträge, Payment-Provider und Abrechnung existieren.
Produktionsreife des Zahlungsbetriebs und konkurrierender Buchungen ist separat zu prüfen;
ein vorhandener Provider-Adapter ersetzt diese Prüfung nicht.

### Charter Readiness und Servicepartner

Vor Abfahrt werden Dokumentgültigkeit, Sicherheitsausrüstung, Technik, Reinigung,
Inventar und notwendige Fotos geprüft. Offene kritische Mängel verhindern die Freigabe.
Übergabe und Rückgabe sind getrennte Workflows mit versionierten Checklisten,
Pflichtfotos je Prüfschritt, Zeitstempel, Verantwortlichem und Bestätigung beider Seiten.
Vorschäden, neue Schäden und strittige Feststellungen bleiben getrennt nachvollziehbar.
Eine geänderte Checkliste darf abgeschlossene Protokolle nicht rückwirkend umschreiben.

Das Servicepartner-Netzwerk umfasst Hafenabdeckung, Leistungen, Preise, Verfügbarkeit,
Zuweisung/Annahme, Durchführung und Abrechnung für Übergabe, Rücknahme, Reinigung und
Technik. Anbieter können selbst übergeben oder einen Partner beauftragen.
**Stand:** Servicepartner, Aufträge, Readiness-/Übergabe-/Rückgabechecklisten, Fotos,
Schäden und Auszahlung existieren; Kapazitätsplanung und vollständige Auditierung folgen.

### Bewertungen und Bildherkunft

Nur der berechtigte Kunde einer nachweislich abgeschlossenen Charter darf eine Bewertung
und Charterfotos veröffentlichen. Die Verifikation wird serverseitig aus der Buchung
abgeleitet; ein frei gesetztes Label genügt nicht. Pro Buchung ist eine Bewertung mit
kontrollierbarer Bearbeitung vorgesehen. Bootsmodell, Zustand des konkreten Bootes und
Service des Vercharterers/Partners werden getrennt bewertet. Dimensionen umfassen Pflege,
Sauberkeit, Beschreibungstreue und Funktion der Ausstattung sowie Organisation und Übergabe.

Die Galerie trennt sichtbar Hersteller-/Modellbilder (als Stock-/Modellfoto markiert),
Originalfotos des Anbieters und Fotos verifizierter Chartergäste mit Chartermonat/-jahr.
Modellbilder ersetzen keine aktuellen Fotos des konkreten Bootes. Aufnahmezeit (sofern
belegt), Uploadzeit und Herkunft sind getrennte Angaben. Private Übergabe-/Schadensfotos
werden nicht automatisch öffentlich. Moderation, Meldung, Bildrechte und Schutz
personenbezogener Inhalte gehören zum Veröffentlichungsablauf. Aktualität kann später
als transparentes Signal dienen; wenige Bewertungen bedeuten nicht schlechte Qualität.
**Stand:** Bilder sind bislang URL-Listen; Bildherkunft und verifizierte Reviews fehlen.

### Rollen und nächste Schritte

| Rolle | Verantwortungsbereich |
|---|---|
| Eigentümer/Vercharterer (`charterer`) | Eigene Boote, Kalender, Preisregeln, Dokumente, Serviceaufträge und Abrechnung |
| Charterkunde (`customer`) | Eigene Suche, Buchung, Zahlung, Crew, Bestätigungen und verifizierte Bewertung |
| Servicepartner (`partner`) | Zugewiesene Aufträge und benötigte Checklisten/Fotos |
| Admin (`admin`) | Katalogpflege, Moderation, Rollenverwaltung und nachvollziehbare Konfliktbearbeitung |

Im Code bezeichnet `charterer` den **Vercharterer**, nicht den Chartergast.
Objektbezogene Rechte müssen auf dem Server durchgesetzt werden.
Auf die erste Competitive-Set-Stufe folgen Katalog/Varianten mit migrationsfähiger
Boot-Verknüpfung, Bildherkunft und verifizierte Reviews. Anschließend werden die
strukturierten Daten für feinere Similarity-Scores und Operations-Planung genutzt.

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
