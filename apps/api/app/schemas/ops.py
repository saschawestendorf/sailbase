from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import ORMModel


class ChecklistItemUpdate(BaseModel):
    key: str
    done: bool | None = None
    issue: bool | None = None
    note: str | None = Field(default=None, max_length=1000)
    photos: list[str] | None = None


class OrderUpdate(BaseModel):
    items: list[ChecklistItemUpdate] = []
    notes: str | None = Field(default=None, max_length=4000)
    photos: list[str] | None = None


class OrderAssign(BaseModel):
    partner_id: str | None = None  # None = owner does it themselves
    scheduled_for: datetime | None = None


class PartnerPublic(ORMModel):
    id: str
    name: str
    phone: str
    base_ids: list
    services: list
    prices: dict
    rating: float | None


class PartnerUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=255)
    phone: str | None = Field(default=None, max_length=64)
    base_ids: list[str] | None = None
    services: list[str] | None = None
    prices: dict[str, int] | None = None
    is_active: bool | None = None


class BookingBrief(ORMModel):
    id: str
    reference: str
    boat_id: str
    customer_name: str
    persons: int
    start_date: datetime | None = None
    end_date: datetime | None = None
    status: str


class ServiceOrderOut(ORMModel):
    id: str
    booking_id: str
    boat_id: str
    partner_id: str | None
    order_type: str
    status: str
    scheduled_for: datetime | None
    checklist: list
    photos: list
    notes: str
    price_cents: int
    completed_at: datetime | None
    partner: PartnerPublic | None = None
    boat_name: str | None = None
    base_name: str | None = None
    booking_reference: str | None = None
    booking_start: str | None = None
    booking_end: str | None = None
    customer_name: str | None = None


class DamageAssess(BaseModel):
    estimated_cents: int = Field(ge=0)
    withheld_cents: int = Field(ge=0)
    description: str | None = Field(default=None, max_length=4000)


class DamageOut(ORMModel):
    id: str
    booking_id: str
    source_order_id: str | None
    title: str
    description: str
    photos: list
    estimated_cents: int
    withheld_cents: int
    status: str
    created_at: datetime


class PayoutOut(ORMModel):
    id: str
    booking_id: str
    gross_cents: int
    commission_cents: int
    service_cost_cents: int
    damage_withheld_cents: int
    net_cents: int
    status: str
    paid_at: datetime | None
    created_at: datetime


class CrewMember(BaseModel):
    name: str = Field(min_length=2, max_length=255)
    birthdate: str | None = Field(default=None, max_length=10)
    role: str = Field(default="crew", pattern="^(skipper|co_skipper|crew)$")
    license: str | None = Field(default=None, max_length=100)


class CrewListUpdate(BaseModel):
    crew: list[CrewMember] = Field(max_length=30)


class DocumentIn(BaseModel):
    type: str = Field(pattern="^(license|id|insurance|other)$")
    name: str = Field(max_length=255)
    url: str = Field(max_length=2000)


class UploadOut(BaseModel):
    url: str
    filename: str
    size: int


class BookingOpsOut(BaseModel):
    """Everything the customer portal shows for one booking."""

    orders: list[ServiceOrderOut]
    damages: list[DamageOut]
    payout: PayoutOut | None
    contract: dict
    contract_accepted_customer_at: datetime | None
    contract_accepted_charterer_at: datetime | None
    handover_confirmed_customer_at: datetime | None
    return_confirmed_customer_at: datetime | None
    crew_list: list
    documents: list
