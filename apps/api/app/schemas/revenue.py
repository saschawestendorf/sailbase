"""Schemas for the yearly revenue-per-available-boat-day preview."""

from datetime import date

from pydantic import BaseModel, Field, model_validator

from app.models import Boat, PricingPolicy


class MonthPointOut(BaseModel):
    month: int
    label: str
    available_days: int
    booked_days: float
    occupancy: float
    avg_price_cents: int
    revenue_cents: int
    revpabd_cents: int


class SimulationRunOut(BaseModel):
    label: str
    available_days: int
    booked_days: float
    occupancy: float
    revenue_cents: int
    revpabd_cents: int
    avg_price_cents: int
    months: list[MonthPointOut]


class SimulationOut(BaseModel):
    dynamic: SimulationRunOut
    static: SimulationRunOut
    uplift_cents: int
    uplift_percent: float
    assumptions: dict


class PolicyProposal(BaseModel):
    """A rule to try out. Omitted fields fall back to what the boat already has."""

    mode: str | None = Field(default=None, pattern="^(fixed|corridor|auto)$")
    reference_price_cents: int | None = Field(default=None, gt=0)
    floor_price_cents: int | None = Field(default=None, gt=0)
    ceiling_price_cents: int | None = Field(default=None, gt=0)
    target_price_cents: int | None = Field(default=None, gt=0)
    strategy: str | None = Field(default=None, pattern="^(conservative|balanced|aggressive)$")
    max_dead_gap_days: int | None = Field(default=None, ge=0, le=14)
    overrides: dict | None = None
    start: date | None = None
    days: int = Field(default=365, ge=30, le=730)

    @model_validator(mode="after")
    def _corridor(self):
        lo, hi = self.floor_price_cents, self.ceiling_price_cents
        if lo is not None and hi is not None and lo > hi:
            raise ValueError("floor darf nicht über ceiling liegen")
        ref = self.reference_price_cents
        if ref is not None:
            if lo is not None and ref < lo:
                raise ValueError("Referenzpreis muss innerhalb des Korridors liegen")
            if hi is not None and ref > hi:
                raise ValueError("Referenzpreis muss innerhalb des Korridors liegen")
        return self

    def merged_policy(self, boat: Boat) -> PricingPolicy:
        """A detached policy object for the simulation; nothing is written to the database."""
        current = boat.pricing
        proposed = PricingPolicy(
            boat_id=boat.id,
            mode=self.mode or (current.mode if current else "corridor"),
            currency=current.currency if current else "EUR",
            reference_price_cents=self.reference_price_cents
            or (current.reference_price_cents if current else 0),
            floor_price_cents=self.floor_price_cents or (current.floor_price_cents if current else 0),
            ceiling_price_cents=self.ceiling_price_cents or (current.ceiling_price_cents if current else 0),
            target_price_cents=self.target_price_cents or (current.target_price_cents if current else None),
            strategy=self.strategy or (current.strategy if current else "balanced"),
            max_dead_gap_days=self.max_dead_gap_days
            if self.max_dead_gap_days is not None
            else (current.max_dead_gap_days if current else None),
            overrides=self.overrides
            if self.overrides is not None
            else (current.overrides if current else {}),
        )
        if proposed.reference_price_cents <= 0:
            raise ValueError("Referenzpreis fehlt")
        if proposed.floor_price_cents <= 0:
            proposed.floor_price_cents = max(1, round(proposed.reference_price_cents * 0.5))
        if proposed.ceiling_price_cents < proposed.floor_price_cents:
            proposed.ceiling_price_cents = round(proposed.reference_price_cents * 1.6)
        return proposed
