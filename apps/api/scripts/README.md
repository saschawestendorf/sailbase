# Katalogdaten erzeugen

`build_boat_catalog.py` baut `app/seed/data/boat_catalog.json` aus den Rohdateien in
`research_input/`. Der Katalog wird nicht von Hand editiert, sondern neu erzeugt – so
bleibt nachvollziehbar, woher jede Zahl stammt.

```bash
python scripts/build_boat_catalog.py
```

## Neue Modelle ergänzen

1. Eine weitere Datei in `research_input/` anlegen, Format siehe `research_input/SCHEMA.md`.
2. Ist die Werft neu, in `YARDS` im Skript eintragen (Slug, Anzeigename, Land der Werft).
3. Skript laufen lassen und die Ausgabe lesen: `PROBLEM`-Zeilen melden Werte außerhalb
   plausibler Grenzen, `ÜBERSPRUNGEN` doppelte oder unbrauchbare Einträge.
4. `pytest tests/test_catalog_data.py` prüft die Mindestqualität des Ergebnisses.

## Regeln, die das Skript durchsetzt

- Unbelegte Werte bleiben `null`. Es wird nichts geschätzt, interpoliert oder von einem
  Schwestermodell übernommen.
- Werte außerhalb der Grenzen in `BOUNDS` werden verworfen statt übernommen; die
  Ausgabe nennt sie.
- Ein Kiel ohne Tiefgangsangabe wird keine Variante, weil er nichts auflösen kann. Er
  verschwindet aber nicht stillschweigend, sondern landet im `notes`-Feld des Modells.
- "Flachkiel" ist abgeleitet, nicht zitiert: nur der flachste Kiel eines Modells und nur,
  wenn er mindestens 15 cm unter dem tiefsten liegt.
