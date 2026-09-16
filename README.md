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
| Bootskatalog | `apps/api/app/models/catalog.py`, `services/catalog.py` | Hersteller → Modell → Generation → Werksvarianten; das Inserat wählt aus, statt Technik abzutippen |
| Revenue-Vorschau | `apps/api/app/services/revenue.py` | Erlös je verfügbarem Bootstag über das Jahr, gegen den klassischen Wochentarif gerechnet |
| Bewertungen und Bildherkunft | `apps/api/app/services/reviews.py` | Eine Bewertung je abgeschlossener Charter, Galerie getrennt nach Anbieter-, Gast- und Modellfoto |
| Portal | `apps/web/` | Suche, Bootsseite, Inserat, Preisoptimierung, Abwicklung |

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

**Stand:** Umgesetzt. `Manufacturer`, `BoatModel`, `ModelVersion` und `VariantOption` bilden
den Katalog; `Boat` verweist über `model_version_id` und `variant_ids` darauf. Beim Einstellen
werden die aufgelösten Werksdaten auf das Boot kopiert, zusammen mit `spec_sources` (Katalog,
Variante oder eigene Angabe je Feld), `spec_overrides` für dokumentierte Abweichungen und
`unknown_specs` für das, was unbelegt bleibt. Unplausible Baujahre und zwei Varianten derselben
Art werden abgewiesen. Weil die Werte kopiert werden, verändert eine spätere Katalogkorrektur
keine bestehende Buchung. `BoatClass` bleibt die Vergleichsklasse fürs Pricing.

Der Katalog ist mit 50 in der Ostsee gängigen Modellen von 15 Werften gefüllt
(`apps/api/app/seed/data/boat_catalog.json`), dazu 223 Werksvarianten: 92 Kiel-, 84 Layout-
und 47 Motorvarianten. Die Daten stammen aus öffentlich zugänglichen Hersteller- und
Fachdatenbankangaben und sind **nicht vom Hersteller bestätigt**. Das ist die entscheidende
Einschränkung, und sie steht deshalb auch im Datensatz selbst:

- Jedes Modell führt Quelle, Quell-URL und Prüfdatum mit.
- Was die Recherche nicht klären konnte, steht als `caveat` am Modell und ist auf der
  Bootsseite sichtbar – bei allen 50 Modellen gibt es mindestens einen solchen Punkt,
  meist Rumpflänge gegen Länge über alles oder eine uneinheitlich gemessene Segelfläche.
- Unbelegte Felder bleiben `null` statt geschätzt zu werden. Vollständig belegt sind Länge,
  Breite, Tiefgang und Verdrängung; Segelfläche (42), Kabinen (42), Nasszellen (40) und
  Kojen (32) lückenhaft, die maximale Personenzahl mit 6 von 50 kaum.
- "Flachkiel" ist eine abgeleitete Einordnung der Plattform, keine Herstelleraussage: nur
  der flachste Kiel eines Modells und nur, wenn er deutlich unter dem tiefsten liegt.

Für den Betrieb heißt das: der Katalog beschleunigt das Inserieren und macht Boote
vergleichbar, ersetzt aber keine Werftfreigabe. Vor kommerzieller Nutzung sollten die
Stammdaten je Modell gegen das Datenblatt der Werft geprüft und `verified_on` neu gesetzt
werden. `apps/api/tests/test_catalog_data.py` hält die Mindestqualität fest: Belege je
Modell, Werte innerhalb plausibler Grenzen, eindeutige Schlüssel, genau ein Standard je
Variantenart.

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
Das Preisraster macht den Zeitraum selbst vergleichbar (siehe „Zum Preisraster").
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
**Stand:** Umgesetzt. `BoatImage` trägt die Herkunft (`model`, `owner`, `guest`, `handover`),
bei Gastfotos den Chartermonat, dazu Uploadzeit und Rechtehinweis getrennt. Übergabefotos sind
nicht öffentlich. `Review` hängt an genau einer Buchung; die Berechtigung leitet der Server aus
deren Status ab, ein Label vom Client genügt nicht. Modell, Zustand des konkreten Bootes und
Service werden getrennt bewertet, dahinter Pflege, Sauberkeit, Beschreibungstreue, Funktion der
Ausstattung, Organisation und Übergabe. Gäste ohne Konto laden Fotos über ihre Buchungsreferenz
hoch. Moderation und Meldewege fehlen noch.

Fotos bringt die Plattform keine mit: Werftbilder haben ungeklärte Nutzungsrechte, und ein
zufälliges Fremdfoto als Modellbild auszuweisen wäre eine Falschaussage über das Schiff.
Wo kein Foto hinterlegt ist, zeichnet das Portal eine Szene (`apps/web/src/lib/illustration.ts`,
ausgeliefert über `/illustration/<seed>.svg`). Sie ist aus dem Namen abgeleitet, damit zwei
Boote nebeneinander verschieden aussehen, und wird in der Galerie ausdrücklich als
Illustration ausgewiesen – nie als Aufnahme.

### Gestaltung

Weiße Fläche, Tinte als Schriftfarbe, Seegrün für Aktionen, Messing für Hinweise. Struktur
entsteht aus Weißraum, Haarlinien und Typografie, nicht aus Farbflächen: eine Karte ist
zuerst eine Linie und erst beim Anfassen ein Objekt. Überschriften und Preise stehen in einer
Buchschrift (Fraunces), Oberfläche und Zahlen in Inter. Die Tokens liegen vollständig in
`apps/web/src/app/globals.css`; Komponenten greifen über Klassen wie `card`, `field`,
`btn-primary`, `chip`, `eyebrow` und `stat-value` darauf zu, statt Farben einzeln zu setzen.
Das Portal ist auf das helle Schema festgelegt (`color-scheme: light`) – ein zweites Schema
mitzupflegen, das niemand verlangt hat, kostet bei jeder Änderung doppelt.

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

## Die fünf Seiten des Kernprozesses

| Seite | Wer | Was dort passiert |
|---|---|---|
| `/search` | Kunde | Feste Daten oder ein Zeitfenster mit Dauer von bis; Preisraster über die Flotte, Treffer nach Passung, je Boot mehrere Termine |
| `/boats/[slug]` | Kunde | Technik mit Quellenangabe, Preisraster für dieses Boot, aufgeschlüsselter Preis, Galerie nach Herkunft, verifizierte Bewertungen |
| `/charterer/boats/new` | Vercharterer | Inserat über den Katalog: Modell, Baureihe, Varianten, dann Regeln und Preisrahmen |
| `/charterer/boats/[id]/pricing` | Vercharterer | Preiskorridor, Strategie und Lückenregel, daneben die Jahresrechnung je verfügbarem Bootstag |
| `/charterer/bookings/[id]` | Vercharterer | Abwicklung: Vertrag, Papiere, Checklisten mit Fotopflicht, Schäden, Kaution, Auszahlung |

Die Gegenseite der Abwicklung liegt unter `/booking/[reference]`: Zahlungen, Vertrag, Crewliste,
Bestätigung von Übernahme und Rückgabe und danach die Bewertung mit eigenen Fotos.

### Zur Charakterachse

Der Segelcharakter ist in der Suche ein Schieberegler, keine Schlagwortliste: von seetüchtig und
klassisch über den Familienfahrtenkreuzer bis zur Sportyacht. Dahinter steht eine Zahl zwischen
-1 und +1. Jedes Boot bekommt aus seinen Eigenschaften eine Position auf derselben Achse, die
Passung ist der Abstand.

Der Vorteil: eine Zahl lässt sich abstufen, eine Menge nicht — ein Boot kann *fast* passen.
Der Preis dafür: die Achse ist eine Einordnung der Plattform, keine Herstellerangabe, und sie
presst mehrere Eigenschaften in eine Dimension. Ein komfortabler Blauwasserfahrer landet in der
Mitte, obwohl er beides ist. Die Schlagworte bleiben deshalb am Boot und in der API erhalten;
die Achse ist eine zusätzliche Sicht, kein Ersatz.

### Zum Preisraster

Ein Preis allein beantwortet die Frage nicht, die vor der Buchung steht: *Wäre eine Woche
später billiger? Spare ich, wenn ich einen Tag früher zurück bin?* Das Preisraster
(`GET /search/price-grid`) rechnet dafür jede Kombination aus Starttag und Dauer im Fenster
durch und behält je Kombination das günstigste passende Boot. Auf der Suchseite läuft es über
die gefilterte Flotte, auf der Bootsseite über ein einziges Schiff — dieselbe Rechnung, nur
enger gestellt.

Drei Blickwinkel auf dieselbe Rechnung: **Kalender** (Preis je Abfahrtstag), **Datumsraster**
(Abfahrt gegen Rückgabe, wie bei Flugpreiskalendern) und **Boote** (jedes Schiff über die Tage,
damit sichtbar wird, wer den günstigsten Preis macht und was die anderen kosten). Die Bootszeilen
gelten immer für eine Dauer; alle Dauern je Boot wären ein Vielfaches an Daten für eine Ansicht,
die ohnehin nur eine zeigt.

Die Farbe vergleicht **innerhalb derselben Dauer**. Ein Vergleich über Dauern hinweg wäre
keiner: sieben Nächte kosten immer mehr als fünf, grün wäre dann nur ein anderes Wort für
„kurz". Der ausgewiesene günstigste Törn rechnet dagegen **pro Nacht**, sonst gewänne stets
die kürzeste Dauer und der Hinweis wäre wertlos.

Zwei Grenzen sind bewusst gesetzt. Die Zahl der Dauern ist gedeckelt, weil mehr Spalten
niemand mehr liest und jede Rechenzeit kostet. Und die Zahl der bepreisten Kombinationen ist
gedeckelt, weil ein offenes Fenster über eine wachsende Flotte sonst eine Einladung wäre, den
Dienst mit einer einzigen Anfrage lahmzulegen. Greift der Deckel, kommt ein gekürztes Raster
zurück und sagt das auch — lieber eine ehrliche Teilauskunft als eine hängende Seite.

### Zur Revenue-Vorschau

Die Vorschau ist eine Modellrechnung, keine Prognose. Sie läuft den Kalender Tag für Tag durch
und trägt dabei die Wahrscheinlichkeit mit, dass das Boot noch frei ist, damit eine Buchung die
Tage blockiert, die sie belegt. Verglichen wird gegen den Markt von heute: fester Saisonpreis,
sieben Nächte, Samstag bis Samstag.

Wie groß der Unterschied ausfällt, hängt an der angenommenen Nachfrage, und die kennt der
Eigner besser als das Modell. Deshalb ist sie ein Eingabewert der Vorschau und kein verstecktes
Konstrukt. Bei einem Boot mit freien Wochen holt Flexibilität Buchungen, die eine starre Woche
nie erreicht; bei einem ohnehin ausgebuchten Boot liegen beide Modelle nah beieinander und es
zählt fast nur noch der Preis. Die Strategie wirkt entsprechend erst, wenn der Kalender
umkämpft ist: in einem leeren Kalender zerschneidet eine Kurzbuchung nichts.

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

### Was der Seed anlegt

Nicht nur Stammdaten, sondern ein durchgespielter Betrieb – sonst lässt sich der
Ablauf nicht ansehen, und die Kennzahlen im Eigner-Dashboard stehen alle auf
null. Alles ist relativ zum heutigen Tag gesetzt und mit festem Zufallsstartwert
erzeugt, also an jedem Tag gleich aufgebaut und trotzdem aktuell:

- **24 Boote** an sechs Häfen bei drei Vercharterern. Die zehn Musterboote sind
  von Hand gepflegt, die übrigen kommen über denselben Katalogweg zustande wie
  ein Inserat im Portal – damit ist auch diese Strecke vorgeführt.
- **Ein Vorgang je Phase** des Ablaufs, damit jeder Zustand der Abwicklungsseite
  erreichbar ist: bestätigt, bereit zur Übernahme, übergeben, zurückgenommen
  (mit offenem Schadenfall), abgerechnet und einer, der auf Zahlung wartet.
- **Historie und Ausblick**: abgerechnete Buchungen der vergangenen Saison und
  bestätigte über die nächsten zwölf Monate, verteilt statt geballt, damit die
  Suche in jeder Woche etwas findet und der Kalender nicht zufällig leer wirkt.
- **Serviceaufträge** zu jeder bestätigten Buchung, wie sie das System beim
  Bestätigen selbst anlegt: Bootsbereitschaft, Übergabe, Rücknahme – mit
  Checklisten, Fotopflicht, Bemerkungen und zugeordnetem Servicepartner.
- **Verträge, Crewlisten, Unterlagen, Zahlungen, Auszahlungen** und Schadenfälle
  in mehreren Ständen; Übergabefotos, die ausdrücklich nicht öffentlich sind.
- **Kalender** mit allen Sperrarten: Winterlager, Werfttermin, Eigennutzung,
  Buchung und eine ablaufende Reservierung.
- **One-Way** auf einem Teil der Flotte eingeschaltet, dazu eine Buchung, die in
  einem anderen Hafen endet – ohne Beispiel bleibt das Merkmal Theorie.

Die Preise stammen aus der echten Preisregel, gerechnet mit dem Vorlauf, den
eine solche Buchung gehabt hätte – nicht mit dem Anreisetag. Sonst zeigte die
Historie lauter Last-Minute-Preise. Für Zeiträume, die der Algorithmus heute gar
nicht anbietet, steht ein Ersatzwert, der im Datensatz als solcher markiert ist.

**Was bewusst leer bleibt:** Stehhöhe, Kojenlänge und maximale Personenzahl am
Katalogmodell, wo die Recherche sie nicht belegt hat. Das sind Tatsachenangaben
über ein Schiff, und an ihnen entscheidet sich, ob eine 1,96 m große Person an
Bord passt – eine erfundene Zahl wäre dort keine Demo, sondern eine
Falschauskunft. Charakter, Standardausstattung und Kurzbeschreibung am Modell
sind dagegen gefüllt: sie sind erkennbar Einordnungen der Plattform und als
solche im Text gekennzeichnet.

`apps/api/tests/test_seed_demo.py` hält den Bestand vollständig: keine leere
Tabelle, keine Spalte ohne Beispiel (bis auf die genannten Ausnahmen), jede
Ablaufphase und jede Sperrart vertreten.

Neu aufbauen lässt sich der Bestand jederzeit mit
`rm apps/api/sailbase.db && .venv/bin/python -m app.seed.seed`.

## Deployment

Railway, zwei Services aus diesem Repo plus Postgres. Details in
[`docs/deployment.md`](docs/deployment.md).
