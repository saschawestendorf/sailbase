from datetime import date

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


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
    turnaround_days: int
    changeover_weekdays: list
    deposit_cents: int
    cleaning_fee_cents: int
    base: BaseOut
    boat_class: BoatClassOut
    charterer: ChartererPublic


class BoatDetailOut(BoatOut):
    pricing: PricingPolicyOut | None


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
    reason: str = ""


class CalendarOut(BaseModel):
    boat_id: str
    nights: int
    days: list[CalendarDay]


class SearchHitOut(BaseModel):
    boat: BoatOut
    available: bool
    unavailable_reason: str = ""
    total_cents: int | None
    per_day_cents: int | None
    fit_score: float
    fit_reasons: list[str]
    blockers: list[str]
    breakdown: dict = Field(default_factory=dict)


class SearchOut(BaseModel):
    count: int
    hits: list[SearchHitOut]
