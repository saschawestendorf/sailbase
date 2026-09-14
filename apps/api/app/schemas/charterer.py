from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel


class BoatUpsert(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    base_id: str
    boat_class_id: str | None = None  # auto-derived from length if omitted
    manufacturer: str = ""
    model: str = ""
    year_built: int | None = Field(default=None, ge=1900, le=2100)
    year_refit: int | None = Field(default=None, ge=1900, le=2100)
    listing_mode: str = Field(default="brokerage", pattern="^(brokerage|exclusive)$")
    length_m: float = Field(gt=3, lt=60)
    beam_m: float | None = Field(default=None, gt=0, lt=20)
    draft_m: float | None = Field(default=None, gt=0, lt=10)
    displacement_kg: int | None = Field(default=None, ge=0)
    sail_area_m2: float | None = Field(default=None, ge=0)
    engine_hp: int | None = Field(default=None, ge=0)
    cabins: int = Field(default=0, ge=0, le=20)
    berths: int = Field(default=0, ge=0, le=40)
    max_persons: int = Field(default=0, ge=0, le=40)
    heads: int = Field(default=0, ge=0, le=10)
    headroom_cm: int | None = Field(default=None, ge=100, le=250)
    max_berth_length_cm: int | None = Field(default=None, ge=100, le=250)
    character: list[str] = []
    required_license: int = Field(default=2, ge=0, le=5)
    required_experience_nm: int = Field(default=0, ge=0)
    features: list[str] = []
    description: str = ""
    images: list[str] = []
    min_days: int = Field(default=3, ge=1, le=30)
    turnaround_days: int = Field(default=0, ge=0, le=7)
    changeover_weekdays: list[int] = []
    deposit_cents: int = Field(default=0, ge=0)
    cleaning_fee_cents: int = Field(default=0, ge=0)
    is_active: bool = True


class PricingPolicyUpsert(BaseModel):
    mode: str = Field(default="corridor", pattern="^(fixed|corridor|auto)$")
    currency: str = "EUR"
    reference_price_cents: int = Field(gt=0)
    floor_price_cents: int = Field(gt=0)
    ceiling_price_cents: int = Field(gt=0)
    overrides: dict = {}

    @model_validator(mode="after")
    def _corridor(self):
        if self.floor_price_cents > self.ceiling_price_cents:
            raise ValueError("floor darf nicht über ceiling liegen")
        if not (self.floor_price_cents <= self.reference_price_cents <= self.ceiling_price_cents):
            raise ValueError("Referenzpreis muss innerhalb des Korridors liegen")
        return self


class BlockCreate(BaseModel):
    start_date: date
    end_date: date
    block_type: str = Field(default="closed", pattern="^(maintenance|owner_use|closed)$")
    note: str = Field(default="", max_length=255)

    @model_validator(mode="after")
    def _dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date muss nach start_date liegen")
        return self


class BlockOut(ORMModel):
    id: str
    boat_id: str
    start_date: date
    end_date: date
    block_type: str
    booking_id: str | None
    note: str


class ChartererOut(ORMModel):
    id: str
    name: str
    slug: str
    description: str
    contact_email: str
    phone: str
    commission_percent: float
    rating: float | None


class ChartererStats(BaseModel):
    boats: int
    bookings_confirmed: int
    bookings_pending: int
    revenue_cents: int
    occupancy_next_90d: float
