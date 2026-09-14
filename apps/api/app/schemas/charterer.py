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
    region_restrictions: str = ""
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
        return self


class PricingPolicyUpsert(BaseModel):
    mode: str = Field(default="corridor", pattern="^(fixed|corridor|auto)$")
    currency: str = "EUR"
    reference_price_cents: int = Field(gt=0)
    floor_price_cents: int = Field(gt=0)
    ceiling_price_cents: int = Field(gt=0)
    target_price_cents: int | None = Field(default=None, gt=0)
    strategy: str = Field(default="balanced", pattern="^(conservative|balanced|aggressive)$")
    max_dead_gap_days: int | None = Field(default=None, ge=0, le=14)
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


class CalendarGap(BaseModel):
    boat_id: str
    boat_name: str
    start_date: date
    end_date: date
    nights: int
    sellable: bool


class ChartererStats(BaseModel):
    boats: int
    bookings_confirmed: int
    bookings_pending: int
    bookings_settled: int
    charter_nights: int
    revenue_cents: int  # dynamic, actually achieved (confirmed + later)
    static_revenue_cents: int  # what a fixed seasonal tariff would have earned on the same bookings
    dynamic_uplift_cents: int
    avg_price_per_night_cents: int
    commission_cents: int
    service_cost_cents: int
    payouts_pending_cents: int
    occupancy_next_90d: float
    gaps_next_90d: list[CalendarGap]
