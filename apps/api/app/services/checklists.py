"""Checklist templates for readiness, handover and return. Data, not code: editable later per boat."""

from app.models.enums import ServiceOrderType


def _item(key: str, label: str, required: bool = True, photo: bool = False) -> dict:
    return {
        "key": key,
        "label": label,
        "required": required,
        "photo_required": photo,
        "done": False,
        "issue": False,
        "note": "",
        "photos": [],
    }


READINESS = [
    _item("engine", "Motor: Ölstand, Kühlwasser, Keilriemen, Probelauf"),
    _item("rigging", "Rigg und Segel: Sichtkontrolle, Fallen, Schoten"),
    _item(
        "safety",
        "Sicherheitsausrüstung: Westen, Lifebelts, Rettungsinsel, Feuerlöscher, Signalmittel",
        photo=True,
    ),
    _item("fuel", "Kraftstoff vollgetankt", photo=True),
    _item("gas", "Gasflasche geprüft, Reserve an Bord"),
    _item("water", "Wassertanks gefüllt"),
    _item("cleaning", "Innen- und Außenreinigung abgeschlossen", photo=True),
    _item("laundry", "Bettwäsche/Handtücher an Bord (falls gebucht)", required=False),
    _item("inventory", "Inventar gemäß Liste vollständig"),
    _item("electronics", "Plotter, Funk, Autopilot, Batterien geprüft"),
    _item("documents", "Bordpapiere, Versicherung, Bootszeugnis an Bord"),
]

HANDOVER = [
    _item("crew_documents", "Crewliste und Führerscheine geprüft"),
    _item("hull_photos", "Rumpf rundum fotografiert", photo=True),
    _item("deck_photos", "Deck, Cockpit, Beschläge fotografiert", photo=True),
    _item("interior_photos", "Innenraum fotografiert", photo=True),
    _item("fuel_level", "Tankstand dokumentiert", photo=True),
    _item("engine_hours", "Motorstunden abgelesen", photo=True),
    _item("briefing_safety", "Sicherheitseinweisung durchgeführt"),
    _item("briefing_systems", "Technische Einweisung: Motor, Elektrik, Toilette, Gas, Heizung"),
    _item("briefing_area", "Revier- und Wettereinweisung, Revierbeschränkungen erklärt"),
    _item("inventory_signed", "Inventarliste gemeinsam geprüft"),
]

RETURN = [
    _item("hull_photos", "Rumpf rundum fotografiert", photo=True),
    _item("deck_photos", "Deck, Cockpit, Beschläge fotografiert", photo=True),
    _item("interior_photos", "Innenraum fotografiert", photo=True),
    _item("fuel_level", "Tankstand dokumentiert", photo=True),
    _item("engine_hours", "Motorstunden abgelesen", photo=True),
    _item("damage_check", "Schäden geprüft (Auffälligkeit als Problem markieren)"),
    _item("inventory", "Inventar vollständig"),
    _item("cleaning_state", "Reinigungszustand dokumentiert", photo=True),
    _item("technical_issues", "Technische Auffälligkeiten laut Crew erfasst", required=False),
]

TEMPLATES: dict[str, list[dict]] = {
    ServiceOrderType.READINESS: READINESS,
    ServiceOrderType.HANDOVER: HANDOVER,
    ServiceOrderType.RETURN: RETURN,
    ServiceOrderType.CLEANING: [_item("cleaning", "Reinigung abgeschlossen", photo=True)],
    ServiceOrderType.TECHNICAL: [_item("work", "Arbeit ausgeführt und dokumentiert", photo=True)],
    ServiceOrderType.LAUNDRY: [_item("laundry", "Wäsche gewechselt")],
}


def template(order_type: str) -> list[dict]:
    import copy

    return copy.deepcopy(TEMPLATES.get(order_type, []))


def is_complete(checklist: list[dict]) -> tuple[bool, list[str]]:
    """All required items done, photo-required items have at least one photo."""
    missing: list[str] = []
    for item in checklist or []:
        if not item.get("required", True):
            continue
        if not item.get("done"):
            missing.append(item.get("label", item.get("key", "?")))
        elif item.get("photo_required") and not item.get("photos"):
            missing.append(f"Foto fehlt: {item.get('label', item.get('key'))}")
    return not missing, missing
