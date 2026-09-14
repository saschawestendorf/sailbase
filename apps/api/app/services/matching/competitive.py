"""Deterministic boat-to-boat similarity, independent of customer fit.

Region and class eligibility are handled by the caller. Missing measurements or
empty feature lists provide no evidence of similarity and are omitted.
"""

from app.models import Boat


def similarity_components(left: Boat, right: Boat) -> dict[str, tuple[float, float]]:
    """Return dimension -> (similarity 0..1, weight) for known dimensions."""
    components = {}
    if left.base_id and right.base_id:
        components["port"] = (1.0 if left.base_id == right.base_id else 0.5, 25.0)
    for name, tolerance, weight in (
        ("length_m", 4.0, 25.0),
        ("cabins", 3.0, 20.0),
        ("berths", 6.0, 10.0),
    ):
        a, b = getattr(left, name), getattr(right, name)
        if a is not None and b is not None and a > 0 and b > 0:
            components[name] = (max(0.0, 1.0 - abs(a - b) / tolerance), weight)
    for name, weight in (("character", 10.0), ("features", 10.0)):
        a, b = set(getattr(left, name) or []), set(getattr(right, name) or [])
        if a and b:
            components[name] = (len(a & b) / len(a | b), weight)
    return components


def similarity(left: Boat, right: Boat) -> float:
    """Weighted score in [0, 1]; no known dimensions means no evidence (0)."""
    components = similarity_components(left, right)
    weight = sum(w for _, w in components.values())
    return sum(s * w for s, w in components.values()) / weight if weight else 0.0
