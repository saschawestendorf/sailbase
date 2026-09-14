"""Schemas for the boat master catalog and for listing a boat from it."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class ManufacturerOut(ORMModel):
    id: str
    slug: str
    name: str
    country: str


class VariantOut(ORMModel):
    id: str
    kind: str
    code: str
    name: str
    is_default: bool
    draft_m: float | None
    sail_area_m2: float | None
    engine_hp: int | None
    cabins: int | None
    berths: int | None
    heads: int | None
    max_persons: int | None
    headroom_cm: int | None
    max_berth_length_cm: int | None
    adds_features: list


class ModelVersionOut(ORMModel):
    id: str
    name: str
    year_from: int | None
    year_to: int | None
    length_m: float
    beam_m: float | None
    draft_m: float | None
    displacement_kg: int | None
    sail_area_m2: float | None
    engine_hp: int | None
    headroom_cm: int | None
    max_berth_length_cm: int | None
    cabins: int | None
    berths: int | None
    heads: int | None
    max_persons: int | None
    water_tank_l: int | None
    fuel_tank_l: int | None
    character: list
    standard_features: list
    description: str
    model_images: list
    source: str
    source_url: str
    verified_on: date | None
    revision: int
    caveat: str = ""
    variants: list[VariantOut] = []


class BoatModelOut(ORMModel):
    id: str
    slug: str
    name: str
    designer: str
    hull_type: str
    manufacturer: ManufacturerOut


class BoatModelDetailOut(BoatModelOut):
    versions: list[ModelVersionOut] = []


class ResolvedSpecOut(BaseModel):
    """What the catalog says this configuration is, and where each number comes from."""

    values: dict[str, float | int | None]
    features: list[str]
    character: list[str]
    sources: dict[str, str]
    unknown: list[str]


class SpecPreviewRequest(BaseModel):
    version_id: str
    variant_ids: list[str] = []
    year_built: int | None = Field(default=None, ge=1900, le=2100)
    overrides: dict[str, float | int | None] = {}


class BoatFromCatalog(BaseModel):
    """Listing a boat: pick the model, say what is fitted, add what only you know."""

    # Catalog selection
    version_id: str
    variant_ids: list[str] = []
    year_built: int | None = Field(default=None, ge=1900, le=2100)
    # Documented deviations from the catalog, e.g. a refit that changed the sail area
    spec_overrides: dict[str, float | int | None] = {}

    # The part that is genuinely per boat
    name: str = Field(min_length=1, max_length=255)
    base_id: str
    year_refit: int | None = Field(default=None, ge=1900, le=2100)
    listing_mode: str = Field(default="brokerage", pattern="^(brokerage|exclusive)$")
    description: str = Field(default="", max_length=8000)
    extra_features: list[str] = []
    character: list[str] = []  # empty falls back to the model's typical character
    images: list[str] = []
    image_captions: list[str] = []
    required_license: int = Field(default=2, ge=0, le=5)
    required_experience_nm: int = Field(default=0, ge=0, le=100000)

    # Charter rules
    min_days: int = Field(default=3, ge=1, le=30)
    max_days: int = Field(default=28, ge=1, le=90)
    allowed_nights: list[int] = []
    min_lead_days: int = Field(default=1, ge=0, le=60)
    turnaround_days: int = Field(default=0, ge=0, le=7)
    changeover_weekdays: list[int] = []
    handover_options: list[str] = ["owner", "partner"]
    one_way_enabled: bool = False
    one_way_base_ids: list[str] = []
    one_way_fee_cents: int = Field(default=0, ge=0)
    deposit_cents: int = Field(default=0, ge=0)
    cleaning_fee_cents: int = Field(default=0, ge=0)
    region_restrictions: str = Field(default="", max_length=2000)
    documents: list[dict] = []
    insurance: dict = {}
    is_active: bool = True

    @model_validator(mode="after")
    def _rules(self):
        if self.max_days < self.min_days:
            raise ValueError("max_days muss >= min_days sein")
        if any(n < self.min_days or n > self.max_days for n in self.allowed_nights):
            raise ValueError("allowed_nights müssen zwischen min_days und max_days liegen")
        if any(d < 0 or d > 6 for d in self.changeover_weekdays):
            raise ValueError("changeover_weekdays: 0=Montag … 6=Sonntag")
        if self.year_refit and self.year_built and self.year_refit < self.year_built:
            raise ValueError("Refit kann nicht vor dem Baujahr liegen")
        if self.image_captions and len(self.image_captions) > len(self.images):
            raise ValueError("Mehr Bildunterschriften als Bilder")
        return self
