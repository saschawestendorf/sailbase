# Ausgabeformat je Modell

```json
{
  "manufacturer": "Bavaria Yachts",
  "model": "Cruiser 46",
  "designer": "Farr Yacht Design",
  "year_from": 2014,
  "year_to": 2019,
  "length_m": 14.27,
  "beam_m": 4.35,
  "draft_m": 2.15,
  "displacement_kg": 11500,
  "sail_area_m2": 105.0,
  "engine_hp": 57,
  "cabins": 3,
  "berths": 6,
  "heads": 2,
  "max_persons": 8,
  "water_tank_l": 360,
  "fuel_tank_l": 210,
  "keel_variants": [
    {"code": "standard", "name": "Standardkiel", "draft_m": 2.15},
    {"code": "flach", "name": "Flachkiel", "draft_m": 1.75}
  ],
  "layout_variants": [
    {"code": "3-kab", "name": "3 Kabinen", "cabins": 3, "berths": 6, "heads": 2},
    {"code": "4-kab", "name": "4 Kabinen", "cabins": 4, "berths": 8, "heads": 2}
  ],
  "sources": ["https://...", "https://..."],
  "notes": "Was unklar blieb oder widersprüchlich war"
}
```

## Regeln

- `length_m` ist die Rumpflänge über alles ohne Bugspriet, in Metern.
- Nie raten. Was nicht in den Suchergebnissen steht, wird `null`. Ein `null` ist ein
  gültiges Ergebnis, eine erfundene Zahl ist ein Fehler.
- Widersprechen sich zwei Quellen, nimm die konkretere und notiere den Konflikt in `notes`.
- `keel_variants` und `layout_variants` nur, wenn die Alternativen tatsächlich belegt sind.
  Ist nur ein Tiefgang bekannt, bleibt die Liste leer.
- `sources` sind die URLs aus den Suchergebnissen, auf die du dich stützt. Mindestens eine.
