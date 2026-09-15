"""The shipped catalog file is reference data, so it is checked like data, not like code.

These tests guard the two properties that make the catalog trustworthy: every figure can be
traced to a source, and nothing implausible slipped in. A gap is allowed; an invention is not.
"""

from datetime import date

import pytest

from app.seed import catalog_data

# Bounds a sailing yacht of charter size has to sit inside. A value outside them means the
# research picked up the wrong boat or the wrong unit.
BOUNDS = {
    "length_m": (5, 30),
    "beam_m": (1.5, 9),
    "draft_m": (0.4, 4.5),
    "displacement_kg": (800, 40000),
    "sail_area_m2": (15, 300),
    "engine_hp": (5, 250),
    "cabins": (1, 6),
    "berths": (2, 14),
    "heads": (1, 5),
    "max_persons": (2, 14),
    "water_tank_l": (50, 1500),
    "fuel_tank_l": (30, 1000),
}


@pytest.fixture(scope="module")
def models():
    return catalog_data.MODELS


def test_catalog_has_a_usable_number_of_models(models):
    assert len(models) >= 45


def test_every_model_states_where_its_figures_come_from(models):
    """A measurement nobody can trace is worse than a missing one."""
    for model in models:
        label = f"{model['manufacturer']}/{model['slug']}"
        assert model.get("source"), f"{label}: keine Quellenangabe"
        assert model.get("source_url", "").startswith("http"), f"{label}: keine Quell-URL"
        assert date.fromisoformat(model["verified_on"]) <= date.today(), f"{label}: Prüfdatum"


def test_no_figure_is_outside_what_a_charter_yacht_can_be(models):
    for model in models:
        for field, (low, high) in BOUNDS.items():
            value = model["version"].get(field)
            if value is None:
                continue  # unknown is allowed and stays unknown
            assert low <= value <= high, (
                f"{model['manufacturer']}/{model['slug']}: {field}={value} ausserhalb {low}-{high}"
            )


def test_length_is_always_known(models):
    """Length drives the comparison class, so a model without it cannot be priced."""
    for model in models:
        assert model["version"]["length_m"], f"{model['slug']}: ohne Länge"


def test_model_keys_are_unique(models):
    keys = [f"{m['manufacturer']}/{m['slug']}" for m in models]
    assert len(keys) == len(set(keys))


def test_manufacturers_are_declared(models):
    declared = {m["slug"] for m in catalog_data.MANUFACTURERS}
    used = {m["manufacturer"] for m in models}
    assert used <= declared, f"nicht deklariert: {used - declared}"


def test_at_most_one_default_per_variant_kind(models):
    for model in models:
        defaults: dict[str, int] = {}
        for variant in model["variants"]:
            if variant.get("is_default"):
                defaults[variant["kind"]] = defaults.get(variant["kind"], 0) + 1
        for kind, count in defaults.items():
            assert count == 1, f"{model['slug']}: {count} Vorgaben für {kind}"


def test_variant_codes_are_unique_within_a_kind(models):
    for model in models:
        seen = set()
        for variant in model["variants"]:
            key = (variant["kind"], variant["code"])
            assert key not in seen, f"{model['slug']}: doppelte Variante {key}"
            seen.add(key)


def test_build_years_are_ordered_when_known(models):
    for model in models:
        version = model["version"]
        if version.get("year_from") and version.get("year_to"):
            assert version["year_from"] <= version["year_to"], model["slug"]


def test_the_note_says_the_data_is_not_manufacturer_confirmed():
    assert "nicht" in catalog_data.CATALOG_NOTE.lower()
