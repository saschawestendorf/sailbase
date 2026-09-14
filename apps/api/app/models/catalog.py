"""Boat master catalog: manufacturer -> model -> version (generation) -> factory variants.

A listing points at a model version and the variants actually fitted, instead of the owner
retyping technical data. Resolved specifications are copied onto the boat at listing time, so
a later catalog correction never rewrites a confirmed booking or contract.
"""

from datetime import date

from sqlalchemy import JSON, Boolean, Date, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.entities import TimestampMixin, new_id


class Manufacturer(TimestampMixin, Base):
    __tablename__ = "manufacturers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="")

    models: Mapped[list["BoatModel"]] = relationship(back_populates="manufacturer")


class BoatModel(TimestampMixin, Base):
    """A model line, e.g. "Cruiser 37". Generations live in ModelVersion."""

    __tablename__ = "boat_models"
    __table_args__ = (UniqueConstraint("manufacturer_id", "slug", name="uq_model_slug"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    manufacturer_id: Mapped[str] = mapped_column(ForeignKey("manufacturers.id"), nullable=False)
    slug: Mapped[str] = mapped_column(String(120), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    designer: Mapped[str] = mapped_column(String(255), default="")
    hull_type: Mapped[str] = mapped_column(String(40), default="monohull")

    manufacturer: Mapped[Manufacturer] = relationship(back_populates="models")
    versions: Mapped[list["ModelVersion"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )


class ModelVersion(TimestampMixin, Base):
    """One generation with its build years and factory-standard measurements."""

    __tablename__ = "model_versions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    model_id: Mapped[str] = mapped_column(ForeignKey("boat_models.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)  # e.g. "Generation 2"
    # Both may be unknown: for some yards the build years are simply not published, and a
    # guessed span would reject perfectly real boats.
    year_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_to: Mapped[int | None] = mapped_column(Integer, nullable=True)  # None = still built

    # Factory-standard hull data. None means unknown and stays visibly unknown.
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    beam_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    displacement_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sail_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headroom_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_berth_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cabins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    berths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    water_tank_l: Mapped[int | None] = mapped_column(Integer, nullable=True)
    fuel_tank_l: Mapped[int | None] = mapped_column(Integer, nullable=True)

    character: Mapped[list] = mapped_column(JSON, default=list)  # typical character of the model
    standard_features: Mapped[list] = mapped_column(JSON, default=list)
    description: Mapped[str] = mapped_column(Text, default="")
    model_images: Mapped[list] = mapped_column(JSON, default=list)  # stock photos, marked as such

    # Provenance, as the specification demands
    source: Mapped[str] = mapped_column(String(255), default="")
    source_url: Mapped[str] = mapped_column(Text, default="")
    verified_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    # What the research could not settle: sources that disagreed, a figure that is the length
    # overall rather than the hull, a sail area summed from individual sails. It rides with the
    # data because a reader comparing two boats needs to know which number is soft.
    caveat: Mapped[str] = mapped_column(Text, default="")

    model: Mapped[BoatModel] = relationship(back_populates="versions")
    variants: Mapped[list["VariantOption"]] = relationship(
        back_populates="version", cascade="all, delete-orphan"
    )

    @property
    def build_years(self) -> tuple[int | None, int | None]:
        return self.year_from, self.year_to

    def covers_year(self, year: int) -> bool:
        """Unknown build years cannot rule a year out, so they accept it."""
        if self.year_from is None:
            return True
        return year >= self.year_from and (self.year_to is None or year <= self.year_to)


class VariantOption(TimestampMixin, Base):
    """A factory option that changes the specification, e.g. a shoal keel or a 3-cabin layout.

    Only the fields an option actually changes are set; everything else stays inherited.
    """

    __tablename__ = "variant_options"
    __table_args__ = (UniqueConstraint("version_id", "kind", "code", name="uq_variant_code"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    version_id: Mapped[str] = mapped_column(ForeignKey("model_versions.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # layout | keel | rig | engine
    code: Mapped[str] = mapped_column(String(60), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Overrides applied on top of the version. None = no change.
    draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    sail_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)
    cabins: Mapped[int | None] = mapped_column(Integer, nullable=True)
    berths: Mapped[int | None] = mapped_column(Integer, nullable=True)
    heads: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_persons: Mapped[int | None] = mapped_column(Integer, nullable=True)
    headroom_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    max_berth_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)
    adds_features: Mapped[list] = mapped_column(JSON, default=list)

    version: Mapped[ModelVersion] = relationship(back_populates="variants")


VARIANT_KINDS = ("layout", "keel", "rig", "engine")

# Fields a variant may override, in the order they are applied to the resolved specification.
VARIANT_FIELDS = (
    "draft_m",
    "sail_area_m2",
    "engine_hp",
    "cabins",
    "berths",
    "heads",
    "max_persons",
    "headroom_cm",
    "max_berth_length_cm",
)

# Fields the version contributes. Variants may override the subset above.
VERSION_FIELDS = (
    "length_m",
    "beam_m",
    "draft_m",
    "displacement_kg",
    "sail_area_m2",
    "engine_hp",
    "headroom_cm",
    "max_berth_length_cm",
    "cabins",
    "berths",
    "heads",
    "max_persons",
)
