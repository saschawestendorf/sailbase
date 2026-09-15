"""Boat master catalog shipped with the seed.

The model data lives in `data/boat_catalog.json` rather than in a Python literal: it is
researched reference data that gets corrected over time, and a JSON file can be regenerated
and diffed without touching code. Every version carries where its figures came from and when
they were checked, and a measurement without a source stays null so the portal can show it as
unknown instead of implying precision that is not there.
"""

import json
from functools import lru_cache
from pathlib import Path

CATALOG_PATH = Path(__file__).parent / "data" / "boat_catalog.json"


@lru_cache(maxsize=1)
def load_catalog() -> dict:
    return json.loads(CATALOG_PATH.read_text(encoding="utf-8"))


MANUFACTURERS = load_catalog()["manufacturers"]
MODELS = load_catalog()["models"]
CATALOG_NOTE = load_catalog()["note"]


def model_index() -> dict[str, dict]:
    """`manufacturer/slug` -> model, for linking a boat to its catalog entry."""
    return {f"{m['manufacturer']}/{m['slug']}": m for m in MODELS}


# Existing demo boats -> the catalog entry they were built from.
# Demo boats -> the catalog entry they were built from, plus the variants they happen to have.
# The codes are a preference: if the catalog renames one, the model's default fills in instead,
# so researched data can be corrected without breaking the demo fleet.
BOAT_CATALOG_LINK: dict[str, tuple[str, list[str]]] = {
    "nordwind": ("bavaria/cruiser-37", ["3-kab", "standard"]),
    "sturmvogel": ("dehler/38-sq", ["3-kab", "competition"]),
    "foerdeperle": ("hanse/418", ["3-kab", "standard"]),
    "kleine-freiheit": ("jeanneau/sun-odyssey-319", ["2-kab", "standard"]),
    "jomsborg": ("hallberg-rassy/40c", ["2-kab", "standard"]),
    "windsbraut": ("jeanneau/sun-odyssey-349", ["3-kab", "standard"]),
    "baltic-star": ("beneteau/oceanis-46-1", ["4-kab-2-wc", "standard"]),
    "hiddensee": ("bavaria/cruiser-34", ["2-kab", "flach"]),
    "boddenlaeufer": ("dufour/390-grand-large", ["3-kab", "standard"]),
    "kap-arkona": ("x-yachts/x4-3", ["tief"]),
}

# Demo reviews so the boat page shows something. Keyed by boat slug.
DEMO_REVIEWS = [
    {
        "boat": "nordwind",
        "author": "Familie Brandt",
        "month_offset": -4,
        "ratings": {
            "rating_model": 5,
            "rating_condition": 5,
            "rating_service": 5,
            "rating_care": 5,
            "rating_cleanliness": 5,
            "rating_accuracy": 5,
            "rating_equipment": 4,
            "rating_organisation": 5,
            "rating_handover": 5,
        },
        "title": "Genau das Boot für unsere erste eigene Woche",
        "body": "Sehr gutmütig zu segeln, im Salon konnte unser 1,90er Sohn aufrecht stehen. "
        "Die Übergabe war gründlich, alles war sauber und vollgetankt.",
    },
    {
        "boat": "nordwind",
        "author": "Jan Petersen",
        "month_offset": -11,
        "ratings": {
            "rating_model": 4,
            "rating_condition": 4,
            "rating_service": 5,
            "rating_care": 4,
            "rating_cleanliness": 5,
            "rating_accuracy": 5,
            "rating_equipment": 4,
            "rating_organisation": 5,
            "rating_handover": 4,
        },
        "title": "Solide Fahrtenyacht, ehrliche Beschreibung",
        "body": "Das Boot war exakt so wie im Inserat. Das Großsegel hat ein paar Jahre auf dem "
        "Buckel, stört beim Fahrtensegeln aber nicht.",
    },
    {
        "boat": "kleine-freiheit",
        "author": "Miriam Kock",
        "month_offset": -6,
        "ratings": {
            "rating_model": 4,
            "rating_condition": 5,
            "rating_service": 4,
            "rating_care": 5,
            "rating_cleanliness": 5,
            "rating_accuracy": 4,
            "rating_equipment": 3,
            "rating_organisation": 4,
            "rating_handover": 4,
        },
        "title": "Handlich zu zweit",
        "body": "Für ein Paar völlig ausreichend und im Hafen leicht zu manövrieren. "
        "Kartenplotter ist älteres Modell, Papierkarte war an Bord.",
    },
    {
        "boat": "baltic-star",
        "author": "Segelclub Travemünde",
        "month_offset": -3,
        "ratings": {
            "rating_model": 5,
            "rating_condition": 4,
            "rating_service": 4,
            "rating_care": 4,
            "rating_cleanliness": 4,
            "rating_accuracy": 5,
            "rating_equipment": 5,
            "rating_organisation": 4,
            "rating_handover": 4,
        },
        "title": "Viel Platz für acht Leute",
        "body": "Die vier Kabinen machen den Unterschied, niemand musste im Salon schlafen. "
        "Tiefgang muss man in den Bodden im Blick behalten.",
    },
]
