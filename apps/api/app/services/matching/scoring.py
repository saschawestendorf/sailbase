"""Crew-to-boat fit scoring.

Hard constraints filter; soft criteria produce a 0..100 score plus human-readable reasons.
Weights are data, not code, so they can be tuned or personalised later.
"""

from dataclasses import dataclass, field

from app.models import Boat
from app.models.enums import BoatCharacter


@dataclass(frozen=True)
class CrewProfile:
    persons: int = 2
    license_level: int = 0
    experience_nm: int = 0
    tallest_person_cm: int | None = None
    preferred_character: list[str] = field(default_factory=list)
    budget_total_cents: int | None = None
    wanted_features: list[str] = field(default_factory=list)
    min_cabins: int | None = None
    skip_qualification_check: bool = False  # e.g. skipper is booked separately


@dataclass(frozen=True)
class ScoreWeights:
    character: float = 30
    comfort: float = 25  # headroom & berth length vs tallest person
    space: float = 15  # cabins/berths headroom over crew size
    features: float = 15
    budget: float = 15


@dataclass
class FitResult:
    ok: bool
    score: float
    reasons: list[str]
    blockers: list[str]


DEFAULT_WEIGHTS = ScoreWeights()
HEADROOM_MARGIN_CM = 5
BERTH_MARGIN_CM = 8


def hard_filter(boat: Boat, crew: CrewProfile) -> list[str]:
    blockers: list[str] = []
    if boat.max_persons and crew.persons > boat.max_persons:
        blockers.append(f"Max. {boat.max_persons} Personen")
    if boat.berths and crew.persons > boat.berths:
        blockers.append(f"Nur {boat.berths} Kojen")
    if crew.min_cabins and boat.cabins < crew.min_cabins:
        blockers.append(f"Nur {boat.cabins} Kabinen")
    if not crew.skip_qualification_check:
        if crew.license_level < boat.required_license:
            blockers.append("Führerschein reicht nicht aus")
        if crew.experience_nm < boat.required_experience_nm:
            blockers.append(f"Mind. {boat.required_experience_nm} sm Erfahrung nötig")
    return blockers


def score(
    boat: Boat, crew: CrewProfile, total_cents: int | None, weights: ScoreWeights | None = None
) -> FitResult:
    weights = weights or DEFAULT_WEIGHTS
    blockers = hard_filter(boat, crew)
    if blockers:
        return FitResult(ok=False, score=0.0, reasons=[], blockers=blockers)

    reasons: list[str] = []
    total = 0.0
    max_total = 0.0

    # Character
    max_total += weights.character
    chars = set(boat.character or [])
    if crew.preferred_character:
        wanted = set(crew.preferred_character)
        hit = chars & wanted
        ratio = len(hit) / len(wanted)
        total += weights.character * ratio
        if hit:
            reasons.append("Charakter passt: " + ", ".join(_char_label(c) for c in sorted(hit)))
    else:
        total += weights.character * 0.6  # neutral

    # Comfort vs tallest person
    max_total += weights.comfort
    if crew.tallest_person_cm:
        c = 0.0
        if boat.headroom_cm:
            if boat.headroom_cm >= crew.tallest_person_cm + HEADROOM_MARGIN_CM:
                c += 0.5
                reasons.append(f"Stehhöhe {boat.headroom_cm} cm ausreichend")
            elif boat.headroom_cm >= crew.tallest_person_cm:
                c += 0.25
        else:
            c += 0.25  # unknown, don't punish hard
        if boat.max_berth_length_cm:
            if boat.max_berth_length_cm >= crew.tallest_person_cm + BERTH_MARGIN_CM:
                c += 0.5
                reasons.append(f"Koje bis {boat.max_berth_length_cm} cm")
            elif boat.max_berth_length_cm >= crew.tallest_person_cm:
                c += 0.25
        else:
            c += 0.25
        total += weights.comfort * c
    else:
        total += weights.comfort * 0.6

    # Space: spare berths and cabins relative to crew
    max_total += weights.space
    if boat.berths:
        spare = boat.berths - crew.persons
        ratio = min(1.0, 0.5 + 0.25 * spare)
        total += weights.space * max(0.0, ratio)
        if boat.cabins and crew.persons <= boat.cabins * 2 and crew.persons <= boat.cabins + 1:
            reasons.append(f"{boat.cabins} Kabinen für {crew.persons} Personen")
    else:
        total += weights.space * 0.5

    # Features
    max_total += weights.features
    if crew.wanted_features:
        have = set(boat.features or [])
        hit = have & set(crew.wanted_features)
        total += weights.features * (len(hit) / len(crew.wanted_features))
        if hit:
            reasons.append("Ausstattung: " + ", ".join(sorted(hit)))
    else:
        total += weights.features * 0.6

    # Budget
    max_total += weights.budget
    if crew.budget_total_cents and total_cents is not None:
        if total_cents <= crew.budget_total_cents:
            total += weights.budget
            reasons.append("Im Budget")
        else:
            over = (total_cents - crew.budget_total_cents) / crew.budget_total_cents
            total += weights.budget * max(0.0, 1.0 - over * 2)
    else:
        total += weights.budget * 0.6

    return FitResult(ok=True, score=round(100 * total / max_total, 1), reasons=reasons, blockers=[])


def _char_label(c: str) -> str:
    labels = {
        BoatCharacter.GOOD_NATURED.value: "gutmütig",
        BoatCharacter.SPORTY.value: "sportlich",
        BoatCharacter.COMFORT.value: "komfortabel",
        BoatCharacter.BLUEWATER.value: "seetüchtig",
        BoatCharacter.CLASSIC.value: "klassisch",
    }
    return labels.get(c, c)
