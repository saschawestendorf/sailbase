"""Merge the researched model files into the catalog data file the seed ships.

Anything the research left as null stays null: the catalog records that a measurement is
unknown rather than inventing one, and the boat page shows it as unknown.
"""

import json
import pathlib
import re
import sys
import unicodedata
from datetime import date

HERE = pathlib.Path(__file__).parent
INPUT = HERE / "research_input"
OUT = HERE.parent / "app" / "seed" / "data" / "boat_catalog.json"

# Yard -> slug and country of the yard, not of the designer.
YARDS = {
    "bavaria": ("bavaria", "Bavaria Yachts", "DE"),
    "hanse": ("hanse", "Hanse Yachts", "DE"),
    "dehler": ("dehler", "Dehler", "DE"),
    "beneteau": ("beneteau", "Bénéteau", "FR"),
    "jeanneau": ("jeanneau", "Jeanneau", "FR"),
    "dufour": ("dufour", "Dufour Yachts", "FR"),
    "elan": ("elan", "Elan Yachts", "SI"),
    "x-yachts": ("x-yachts", "X-Yachts", "DK"),
    "hallberg": ("hallberg-rassy", "Hallberg-Rassy", "SE"),
    "salona": ("salona", "Salona Yachts", "HR"),
    "grand soleil": ("grand-soleil", "Grand Soleil", "IT"),
    "pardo": ("grand-soleil", "Grand Soleil (Cantiere del Pardo)", "IT"),
    "najad": ("najad", "Najad Yachts", "SE"),
    "sunbeam": ("sunbeam", "Sunbeam Yachts", "AT"),
    "delphia": ("delphia", "Delphia Yachts", "PL"),
    "moody": ("moody", "Moody", "DE"),
}

NUMERIC = (
    "length_m", "beam_m", "draft_m", "displacement_kg", "sail_area_m2", "engine_hp",
    "cabins", "berths", "heads", "max_persons", "water_tank_l", "fuel_tank_l",
)
INTS = {"displacement_kg", "engine_hp", "cabins", "berths", "heads", "max_persons",
        "water_tank_l", "fuel_tank_l"}
# Sanity bounds. A value outside them is a research error, not a boat, so it is dropped
# and reported rather than quietly stored.
BOUNDS = {
    "length_m": (5, 30), "beam_m": (1.5, 9), "draft_m": (0.4, 4.5),
    "displacement_kg": (800, 40000), "sail_area_m2": (15, 300), "engine_hp": (5, 250),
    "cabins": (1, 6), "berths": (2, 14), "heads": (1, 5), "max_persons": (2, 14),
    "water_tank_l": (50, 1500), "fuel_tank_l": (30, 1000),
}


def slugify(value):
    text = (value or "").translate(str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}))
    text = unicodedata.normalize("NFKD", text)
    text = "".join(c for c in text if not unicodedata.combining(c))
    return re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()


# Researchers wrote model names the way sources do: sometimes with the yard in front, sometimes
# with an alias in brackets or after a slash. Both belong in the yard and the slug respectively,
# not in the model name, or the catalog reads "Hanse Yachts Hanse 315".
ALIAS_SPLIT = re.compile(r"\s*[\(/]|\s+\bauch\b|\s+\baka\b", re.IGNORECASE)


def clean_model_name(name, yard_name):
    text = ALIAS_SPLIT.split(name or "", maxsplit=1)[0].strip(" )-")
    # Longest prefix first, so "Grand Soleil 44" loses both words rather than just "Grand".
    bare_yard = yard_name.split("(")[0].strip()
    for prefix in sorted({bare_yard, bare_yard.split()[0]}, key=len, reverse=True):
        if text.lower().startswith(prefix.lower() + " "):
            return text[len(prefix) + 1 :].strip() or text
    return text or name


def yard_of(name):
    lowered = (name or "").lower()
    for needle, entry in YARDS.items():
        if needle in lowered:
            return entry
    return None


def clean(entry, field, problems, label):
    value = entry.get(field)
    if value is None:
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        problems.append(f"{label}: {field} ist keine Zahl ({entry.get(field)!r})")
        return None
    lo, hi = BOUNDS[field]
    if not lo <= value <= hi:
        problems.append(f"{label}: {field}={value} ausserhalb {lo}-{hi}, verworfen")
        return None
    return int(round(value)) if field in INTS else round(value, 2)


def main():
    today = date.today().isoformat()
    models, manufacturers, problems, skipped = [], {}, [], []
    seen_slugs = set()

    for path in sorted(INPUT.glob("*.json")):
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = raw if isinstance(raw, list) else raw.get("models", [])
        for entry in entries:
            label = f"{entry.get('manufacturer')} {entry.get('model')}"
            yard = yard_of(entry.get("manufacturer"))
            if yard is None:
                skipped.append(f"{label}: Werft nicht zugeordnet")
                continue
            yard_slug, yard_name, country = yard
            manufacturers[yard_slug] = {"slug": yard_slug, "name": yard_name, "country": country}

            values = {f: clean(entry, f, problems, label) for f in NUMERIC}
            if values["length_m"] is None:
                skipped.append(f"{label}: ohne Länge nicht katalogfähig")
                continue
            if not entry.get("sources"):
                skipped.append(f"{label}: ohne Quelle nicht katalogfähig")
                continue

            model_name = clean_model_name(entry["model"], yard_name)
            slug = slugify(model_name)
            key = f"{yard_slug}/{slug}"
            if key in seen_slugs:
                skipped.append(f"{label}: doppelter Eintrag")
                continue
            seen_slugs.add(key)

            variants = []
            keels = entry.get("keel_variants") or []
            keel_drafts = [
                clean(k, "draft_m", [], label) for k in keels
                if clean(k, "draft_m", [], label) is not None
            ]
            # "Shallow draft" is the platform's own classification, derived from the numbers
            # rather than claimed by the yard: only the shallowest keel of a model earns it,
            # and only when it is meaningfully below the deepest, so a mid keel on a boat with
            # three options is not sold as shallow.
            shallow_draft = None
            if keel_drafts and min(keel_drafts) <= max(keel_drafts) - 0.15:
                shallow_draft = min(keel_drafts)
            # A keel option whose draft nobody publishes cannot change a resolved spec and
            # cannot be compared, so it is not offered as a choice. It is not simply dropped
            # either: the note keeps the option visible as a known gap instead of pretending
            # the boat only ever had the keels we found numbers for.
            undocumented_keels = []
            for keel in keels:
                keel_label = keel.get("name") or keel.get("code")
                draft = clean(keel, "draft_m", problems, f"{label} Kiel {keel.get('code')}")
                if draft is None:
                    undocumented_keels.append(keel_label)
                    continue
                variants.append({
                    "kind": "keel", "code": slugify(keel.get("code") or keel.get("name")),
                    "name": keel_label,
                    "is_default": len(variants) == 0, "draft_m": draft,
                    "adds_features": ["shallow_draft"] if draft == shallow_draft else [],
                })
            if not any(v["kind"] == "keel" for v in variants) and values["draft_m"] is not None:
                variants.append({"kind": "keel", "code": "standard", "name": "Standardkiel",
                                 "is_default": True, "draft_m": values["draft_m"]})

            layouts = entry.get("layout_variants") or []
            for index, layout in enumerate(layouts):
                variants.append({
                    "kind": "layout", "code": slugify(layout.get("code") or layout.get("name")),
                    "name": layout.get("name") or layout.get("code"),
                    "is_default": index == 0,
                    "cabins": clean(layout, "cabins", problems, label),
                    "berths": clean(layout, "berths", problems, label),
                    "heads": clean(layout, "heads", problems, label),
                    "max_persons": clean(layout, "max_persons", problems, label),
                })
            if not layouts and values["cabins"]:
                variants.append({
                    "kind": "layout", "code": f"{values['cabins']}-kab",
                    "name": f"{values['cabins']} Kabinen", "is_default": True,
                    "cabins": values["cabins"], "berths": values["berths"],
                    "heads": values["heads"], "max_persons": values["max_persons"],
                })
            if values["engine_hp"]:
                variants.append({"kind": "engine", "code": f"{values['engine_hp']}ps",
                                 "name": f"{values['engine_hp']} PS", "is_default": True,
                                 "engine_hp": values["engine_hp"]})

            sources = [s for s in entry["sources"] if isinstance(s, str) and s.startswith("http")]
            models.append({
                "manufacturer": yard_slug,
                "slug": slug,
                "name": model_name,
                "designer": entry.get("designer") or "",
                "version": {
                    "name": "Serienstand",
                    "year_from": entry.get("year_from"),
                    "year_to": entry.get("year_to"),
                    **values,
                    "description": entry.get("description") or "",
                },
                "variants": variants,
                "source": "Öffentliche Herstellerangaben und Fachdatenbanken, recherchiert",
                "source_url": sources[0] if sources else "",
                "all_sources": sources,
                "verified_on": today,
                "notes": " ".join(
                    part for part in (
                        entry.get("notes") or "",
                        (
                            "Ohne Tiefgangsangabe und daher nicht als Variante geführt: "
                            + ", ".join(undocumented_keels)
                            + "."
                        ) if undocumented_keels else "",
                    ) if part
                ),
            })

    missing_year = [m["name"] for m in models if not m["version"]["year_from"]]
    payload = {
        "generated_on": today,
        "note": (
            "Recherchiert aus öffentlich zugänglichen Herstellerangaben und Fachdatenbanken. "
            "Nicht vom Hersteller bestätigt. Felder ohne Beleg stehen als null und werden im "
            "Portal als unbekannt ausgewiesen."
        ),
        "manufacturers": sorted(manufacturers.values(), key=lambda m: m["name"]),
        "models": sorted(models, key=lambda m: (m["manufacturer"], m["slug"])),
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    coverage = {f: sum(1 for m in models if m["version"][f] is not None) for f in NUMERIC}
    print(f"{len(models)} Modelle, {len(payload['manufacturers'])} Werften -> {OUT}")
    print("Belegung je Feld:")
    for field, count in sorted(coverage.items(), key=lambda kv: -kv[1]):
        print(f"  {field:18} {count:3}/{len(models)}")
    if missing_year:
        print(f"ohne Bauzeit: {', '.join(missing_year)}")
    for line in skipped:
        print("ÜBERSPRUNGEN", line)
    for line in problems:
        print("PROBLEM", line)
    return 0 if models else 1


if __name__ == "__main__":
    sys.exit(main())
