from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel
from app.schemas.reviews import BoatImageOut, RatingSummaryOut


class RegionOut(ORMModel):
    id: str
    slug: str
    name: str
    country: str
    description: str


class BaseOut(ORMModel):
    id: str
    name: str
    city: str
    lat: float | None
    lon: float | None
    region: RegionOut


class BoatClassOut(ORMModel):
    id: str
    slug: str
    name: str
    min_length_m: float
    max_length_m: float


class ChartererPublic(ORMModel):
    id: str
    name: str
    slug: str
    rating: float | None


class PricingPolicyOut(ORMModel):
    mode: str
    currency: str
    reference_price_cents: int
    floor_price_cents: int
    ceiling_price_cents: int
    target_price_cents: int | None
    strategy: str
    max_dead_gap_days: int | None
    overrides: dict


class BoatOut(ORMModel):
    id: str
    slug: str
    name: str
    manufacturer: str
    model: str
    year_built: int | None
    year_refit: int | None
    listing_mode: str
    length_m: float
    beam_m: float | None
    draft_m: float | None
    displacement_kg: int | None
    sail_area_m2: float | None
    engine_hp: int | None
    cabins: int
    berths: int
    max_persons: int
    heads: int
    headroom_cm: int | None
    max_berth_length_cm: int | None
    character: list
    required_license: int
    required_experience_nm: int
    features: list
    description: str
    images: list
    min_days: int
    max_days: int
    allowed_nights: list
    min_lead_days: int
    turnaround_days: int
    changeover_weekdays: list
    handover_options: list
    one_way_enabled: bool
    one_way_base_ids: list
    one_way_fee_cents: int
    deposit_cents: int
    cleaning_fee_cents: int
    region_restrictions: str
    base: BaseOut
    boat_class: BoatClassOut
    charterer: ChartererPublic
    rating_overall: float | None = None
    rating_count: int = 0


class BoatDetailOut(BoatOut):
    pricing: PricingPolicyOut | None
    model_version_id: str | None = None
    variant_ids: list = Field(default_factory=list)
    spec_overrides: dict = Field(default_factory=dict)
    spec_sources: dict = Field(default_factory=dict)
    unknown_specs: list = Field(default_factory=list)
    gallery: list["BoatImageOut"] = Field(default_factory=list)
    ratings: "RatingSummaryOut | None" = None
    model_info: dict = Field(default_factory=dict)


class PriceBreakdown(BaseModel):
    currency: str
    nights: int
    reference_per_day_cents: int
    raw_per_day_cents: int
    per_day_cents: int
    charter_cents: int
    fees_cents: int
    total_cents: int
    clamped: str | None
    day_factors: list[dict]
    stay_factors: list[dict]
    occupancy: float | None = None


class CalendarDay(BaseModel):
    date: date
    available: bool
    per_day_cents: int | None
    total_cents: int | None = None
    reason: str = ""


class CalendarOut(BaseModel):
    boat_id: str
    nights: int
    days: list[CalendarDay]


class OfferOut(BaseModel):
    start_date: date
    end_date: date
    nights: int
    per_day_cents: int
    total_cents: int
    breakdown: dict = Field(default_factory=dict)
    gap: dict = Field(default_factory=dict)
    note: str = ""
    pickup_base_id: str | None = None
    dropoff_base_id: str | None = None


class SearchHitOut(BaseModel):
    boat: BoatOut
    available: bool
    unavailable_reason: str = ""
    total_cents: int | None
    per_day_cents: int | None
    offers: list[OfferOut] = Field(default_factory=list)
    fit_score: float
    fit_reasons: list[str]
    blockers: list[str]
    breakdown: dict = Field(default_factory=dict)


class SearchOut(BaseModel):
    count: int
    hits: list[SearchHitOut]
