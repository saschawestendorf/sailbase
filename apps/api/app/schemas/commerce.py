from datetime import date, datetime

from pydantic import BaseModel, EmailStr, Field, model_validator

from app.schemas.catalog import BoatOut, PriceBreakdown
from app.schemas.common import ORMModel


class QuoteRequest(BaseModel):
    boat_id: str
    start_date: date
    end_date: date
    persons: int = Field(default=2, ge=1, le=30)

    @model_validator(mode="after")
    def _check_dates(self):
        if self.end_date <= self.start_date:
            raise ValueError("end_date muss nach start_date liegen")
        if (self.end_date - self.start_date).days > 60:
            raise ValueError("Maximal 60 Nächte")
        return self


class QuoteOut(ORMModel):
    id: str
    boat_id: str
    start_date: date
    end_date: date
    persons: int
    currency: str
    total_cents: int
    breakdown: dict
    expires_at: datetime


class BookingCreate(BaseModel):
    quote_id: str
    customer_email: EmailStr
    customer_name: str = Field(min_length=2, max_length=255)
    accept_terms: bool

    @model_validator(mode="after")
    def _terms(self):
        if not self.accept_terms:
            raise ValueError("AGB müssen akzeptiert werden")
        return self


class PaymentOut(ORMModel):
    id: str
    provider: str
    amount_cents: int
    currency: str
    status: str
    checkout_url: str


class BookingOut(ORMModel):
    id: str
    reference: str
    boat_id: str
    customer_email: str
    customer_name: str
    persons: int
    start_date: date
    end_date: date
    status: str
    currency: str
    total_cents: int
    deposit_cents: int
    price_breakdown: dict
    hold_expires_at: datetime | None
    created_at: datetime
    payments: list[PaymentOut] = []
    boat: BoatOut | None = None


class BookingCreated(BaseModel):
    booking: BookingOut
    checkout_url: str


__all__ = ["PriceBreakdown"]
