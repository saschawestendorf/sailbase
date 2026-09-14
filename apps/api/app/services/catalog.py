"""Resolving a catalog selection into a concrete boat specification.

The resolved values are copied onto the boat when it is listed. That snapshot is what pricing,
matching and contracts read, so correcting the catalog later never rewrites an existing booking.
"""

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.models.catalog import (
    VARIANT_FIELDS,
    VARIANT_KINDS,
    VERSION_FIELDS,
    BoatModel,
    Manufacturer,
    ModelVersion,
    VariantOption,
)

# A boat older or newer than its generation by more than this many years is rejected outright;
# the small tolerance covers hulls sold across a model-year boundary.
YEAR_TOLERANCE = 1


class CatalogError(Exception):
    pass


@dataclass
class ResolvedSpec:
    values: dict[str, float | int | None]
    features: list[str]
    character: list[str]
    sources: dict[str, str] = field(default_factory=dict)  # field -> "version" | variant code | "owner"
    unknown: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "values": self.values,
            "features": self.features,
            "character": self.character,
            "sources": self.sources,
            "unknown": self.unknown,
        }


def load_version(db: Session, version_id: str) -> ModelVersion:
    version = (
        db.execute(
            select(ModelVersion)
            .options(selectinload(ModelVersion.variants), selectinload(ModelVersion.model))
            .where(ModelVersion.id == version_id)
        )
        .scalars()
        .first()
    )
    if version is None:
        raise CatalogError("Modellversion nicht gefunden")
    return version


def validate_selection(
    version: ModelVersion, year_built: int | None, variant_ids: list[str]
) -> list[VariantOption]:
    """Reject implausible build years and impossible option combinations."""
    if year_built is not None and not version.covers_year(year_built):
        lo = version.year_from - YEAR_TOLERANCE
        hi = (version.year_to or version.year_from + 60) + YEAR_TOLERANCE
        if not (lo <= year_built <= hi):
            span = f"{version.year_from}–{version.year_to or 'heute'}"
            raise CatalogError(f"Baujahr {year_built} passt nicht zu dieser Generation ({span})")

    by_id = {v.id: v for v in version.variants}
    chosen: list[VariantOption] = []
    seen_kinds: set[str] = set()
    for vid in variant_ids:
        option = by_id.get(vid)
        if option is None:
            raise CatalogError("Variante gehört nicht zu dieser Modellversion")
        if option.kind in seen_kinds:
            raise CatalogError(f"Mehrere Varianten für {option.kind} gewählt")
        seen_kinds.add(option.kind)
        chosen.append(option)
    return chosen


def default_variants(version: ModelVersion) -> list[VariantOption]:
    picked: dict[str, VariantOption] = {}
    for option in version.variants:
        if option.is_default and option.kind not in picked:
            picked[option.kind] = option
    return [picked[k] for k in VARIANT_KINDS if k in picked]


def resolve(
    version: ModelVersion,
    variants: list[VariantOption],
    overrides: dict | None = None,
) -> ResolvedSpec:
    """Version defaults, then variant overrides, then documented owner deviations."""
    values: dict[str, float | int | None] = {}
    sources: dict[str, str] = {}
    for f in VERSION_FIELDS:
        value = getattr(version, f, None)
        values[f] = value
        if value is not None:
            sources[f] = "version"

    for option in variants:
        for f in VARIANT_FIELDS:
            value = getattr(option, f, None)
            if value is not None:
                values[f] = value
                sources[f] = f"variant:{option.code}"

    features = list(version.standard_features or [])
    for option in variants:
        for feature in option.adds_features or []:
            if feature not in features:
                features.append(feature)

    for f, value in (overrides or {}).items():
        if f in values and value is not None:
            values[f] = value
            sources[f] = "owner"

    unknown = [f for f, v in values.items() if v is None]
    return ResolvedSpec(
        values=values,
        features=features,
        character=list(version.character or []),
        sources=sources,
        unknown=unknown,
    )


def search_models(db: Session, query: str | None, manufacturer_slug: str | None) -> list[BoatModel]:
    stmt = (
        select(BoatModel)
        .join(Manufacturer, BoatModel.manufacturer_id == Manufacturer.id)
        .options(selectinload(BoatModel.manufacturer), selectinload(BoatModel.versions))
        .order_by(Manufacturer.name, BoatModel.name)
    )
    if manufacturer_slug:
        stmt = stmt.where(Manufacturer.slug == manufacturer_slug)
    if query:
        like = f"%{query.strip().lower()}%"
        stmt = stmt.where((BoatModel.name.ilike(like)) | (Manufacturer.name.ilike(like)))
    return list(db.execute(stmt).scalars().unique().all())
