"""SQLAlchemy ORM entities for the Sailbase domain.

Design notes
- All money in integer cents to avoid float drift.
- Enum values are stored as plain strings (portable, migration-friendly).
- Flexible attributes that are likely to grow (features, tags, breakdowns) live in JSON columns.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow, nullable=False)


# --------------------------------------------------------------------------- users


class User(TimestampMixin, Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), default="")
    role: Mapped[str] = mapped_column(String(20), default="customer", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Sailing profile (used for matching)
    license_level: Mapped[int] = mapped_column(Integer, default=0)
    experience_nm: Mapped[int] = mapped_column(Integer, default=0)  # logged nautical miles
    height_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)

    charterer: Mapped["Charterer | None"] = relationship(back_populates="owner", uselist=False)
    partner_profile: Mapped["ServicePartner | None"] = relationship(back_populates="user", uselist=False)


# ---------------------------------------------------------------------- charterers


class Charterer(TimestampMixin, Base):
    """A charter company (Vercharterer) listing boats on the platform."""

    __tablename__ = "charterers"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    contact_email: Mapped[str] = mapped_column(String(255), default="")
    phone: Mapped[str] = mapped_column(String(64), default="")
    commission_percent: Mapped[float] = mapped_column(Float, default=15.0)
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)

    owner: Mapped[User] = relationship(back_populates="charterer")
    boats: Mapped[list["Boat"]] = relationship(back_populates="charterer")


# --------------------------------------------------------------------------- places


class Region(Base):
    """Sailing area (Seegebiet), e.g. 'Westliche Ostsee', 'Rügen/Bodden'."""

    __tablename__ = "regions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(2), default="DE")
    description: Mapped[str] = mapped_column(Text, default="")
    # Season demand curve: {"1": 0.3, ..., "7": 1.0, "8": 1.0, ...} per month
    season_curve: Mapped[dict] = mapped_column(JSON, default=dict)

    bases: Mapped[list["Base_"]] = relationship(back_populates="region")


class Base_(Base):
    """Home port / marina (Stützpunkt)."""

    __tablename__ = "bases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    region_id: Mapped[str] = mapped_column(ForeignKey("regions.id"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(255), default="")
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    region: Mapped[Region] = relationship(back_populates="bases")
    boats: Mapped[list["Boat"]] = relationship(back_populates="base")


# ---------------------------------------------------------------------------- boats


class BoatClass(Base):
    """Comparable-boat cluster used for demand measurement, e.g. 'Fahrtenyacht 36-40ft'."""

    __tablename__ = "boat_classes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    min_length_m: Mapped[float] = mapped_column(Float, default=0)
    max_length_m: Mapped[float] = mapped_column(Float, default=99)

    boats: Mapped[list["Boat"]] = relationship(back_populates="boat_class")


class Boat(TimestampMixin, Base):
    __tablename__ = "boats"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    charterer_id: Mapped[str] = mapped_column(ForeignKey("charterers.id"), nullable=False)
    base_id: Mapped[str] = mapped_column(ForeignKey("bases.id"), nullable=False)
    boat_class_id: Mapped[str] = mapped_column(ForeignKey("boat_classes.id"), nullable=False)

    # Catalog link. Resolved specs are copied onto this row at listing time, so a later
    # catalog correction never rewrites a confirmed booking or contract.
    model_version_id: Mapped[str | None] = mapped_column(ForeignKey("model_versions.id"), nullable=True)
    variant_ids: Mapped[list] = mapped_column(JSON, default=list)
    spec_overrides: Mapped[dict] = mapped_column(JSON, default=dict)  # documented deviations
    spec_sources: Mapped[dict] = mapped_column(JSON, default=dict)  # field -> version/variant/owner
    unknown_specs: Mapped[list] = mapped_column(JSON, default=list)  # stays visibly unknown

    slug: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    manufacturer: Mapped[str] = mapped_column(String(255), default="")
    model: Mapped[str] = mapped_column(String(255), default="")
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    year_refit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    listing_mode: Mapped[str] = mapped_column(String(20), default="brokerage", nullable=False)

    # Dimensions
    length_m: Mapped[float] = mapped_column(Float, nullable=False)
    beam_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    draft_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    displacement_kg: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sail_area_m2: Mapped[float | None] = mapped_column(Float, nullable=True)
    engine_hp: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Accommodation (what really matters to crews)
    cabins: Mapped[int] = mapped_column(Integer, default=0)
    berths: Mapped[int] = mapped_column(Integer, default=0)
    max_persons: Mapped[int] = mapped_column(Integer, default=0)
    heads: Mapped[int] = mapped_column(Integer, default=0)
    headroom_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Stehhöhe Salon
    max_berth_length_cm: Mapped[int | None] = mapped_column(Integer, nullable=True)  # längste Koje

    # Character & requirements
    character: Mapped[list] = mapped_column(JSON, default=list)  # list[BoatCharacter]
    required_license: Mapped[int] = mapped_column(Integer, default=2)  # LicenseLevel
    required_experience_nm: Mapped[int] = mapped_column(Integer, default=0)
    features: Mapped[list] = mapped_column(JSON, default=list)  # ["bowthruster", "autopilot", ...]
    description: Mapped[str] = mapped_column(Text, default="")
    images: Mapped[list] = mapped_column(JSON, default=list)  # [url, ...]

    # Charter rules
    min_days: Mapped[int] = mapped_column(Integer, default=3)
    max_days: Mapped[int] = mapped_column(Integer, default=28)
    allowed_nights: Mapped[list] = mapped_column(JSON, default=list)  # [] = any between min/max
    min_lead_days: Mapped[int] = mapped_column(Integer, default=1)  # Mindestvorlauf
    turnaround_days: Mapped[int] = mapped_column(Integer, default=0)
    changeover_weekdays: Mapped[list] = mapped_column(JSON, default=list)  # [] = any day; 0=Mon
    handover_options: Mapped[list] = mapped_column(JSON, default=lambda: ["owner", "partner"])
    # One-way charter: drop the boat at another base; the next crew sails it back.
    one_way_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    one_way_base_ids: Mapped[list] = mapped_column(JSON, default=list)  # [] = any base in the region
    one_way_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    deposit_cents: Mapped[int] = mapped_column(Integer, default=0)  # Kaution
    cleaning_fee_cents: Mapped[int] = mapped_column(Integer, default=0)
    region_restrictions: Mapped[str] = mapped_column(Text, default="")  # Revierbeschränkungen

    # Compliance & documents: [{"type": "insurance"|"certificate"|"manual"|..., "name", "url", "valid_until"}]
    documents: Mapped[list] = mapped_column(JSON, default=list)
    insurance: Mapped[dict] = mapped_column(JSON, default=dict)  # {"insurer", "policy_no", "valid_until"}

    charterer: Mapped[Charterer] = relationship(back_populates="boats")
    base: Mapped[Base_] = relationship(back_populates="boats")
    boat_class: Mapped[BoatClass] = relationship(back_populates="boats")
    pricing: Mapped["PricingPolicy | None"] = relationship(back_populates="boat", uselist=False)
    blocks: Mapped[list["AvailabilityBlock"]] = relationship(
        back_populates="boat", cascade="all, delete-orphan"
    )
    gallery: Mapped[list["BoatImage"]] = relationship(
        back_populates="boat", cascade="all, delete-orphan", order_by="BoatImage.sort_order"
    )
    reviews: Mapped[list["Review"]] = relationship(back_populates="boat")


class PricingPolicy(TimestampMixin, Base):
    """Price corridor per boat; the engine works strictly inside it."""

    __tablename__ = "pricing_policies"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), unique=True, nullable=False)
    mode: Mapped[str] = mapped_column(String(20), default="corridor", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    reference_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # per day, peak
    floor_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # per day, absolute
    ceiling_price_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # per day, absolute
    target_price_cents: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Zielpreis Ø/Tag
    strategy: Mapped[str] = mapped_column(String(20), default="balanced", nullable=False)
    # Gaps shorter than this (in nights) left over by a booking count as economically dead.
    # None = derive from boat.min_days.
    max_dead_gap_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Optional per-boat overrides of engine parameters, e.g. {"weekend_uplift": 0.1}
    overrides: Mapped[dict] = mapped_column(JSON, default=dict)

    boat: Mapped[Boat] = relationship(back_populates="pricing")


class AvailabilityBlock(Base):
    """A date range during which the boat is not bookable. [start, end) half-open."""

    __tablename__ = "availability_blocks"
    __table_args__ = (Index("ix_blocks_boat_range", "boat_id", "start_date", "end_date"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    block_type: Mapped[str] = mapped_column(String(20), nullable=False)
    booking_id: Mapped[str | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)  # for holds
    note: Mapped[str] = mapped_column(String(255), default="")
    # Where the boat is at the start / end of this block. None = home base.
    start_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)
    end_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)

    boat: Mapped[Boat] = relationship(back_populates="blocks")


# ------------------------------------------------------------------------- commerce


class Quote(Base):
    """A priced offer, valid for a limited time. Booking references it to lock the price."""

    __tablename__ = "quotes"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    persons: Mapped[int] = mapped_column(Integer, default=1)
    pickup_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)
    dropoff_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class Booking(TimestampMixin, Base):
    __tablename__ = "bookings"
    __table_args__ = (UniqueConstraint("quote_id", name="uq_booking_quote"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    quote_id: Mapped[str] = mapped_column(ForeignKey("quotes.id"), nullable=False)
    customer_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    customer_email: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    persons: Mapped[int] = mapped_column(Integer, default=1)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    pickup_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)
    dropoff_base_id: Mapped[str | None] = mapped_column(ForeignKey("bases.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_payment", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    total_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    deposit_cents: Mapped[int] = mapped_column(Integer, nullable=False)  # Anzahlung
    commission_cents: Mapped[int] = mapped_column(Integer, default=0)
    security_deposit_cents: Mapped[int] = mapped_column(Integer, default=0)  # Kaution
    static_price_cents: Mapped[int] = mapped_column(Integer, default=0)  # what a fixed tariff would earn
    price_breakdown: Mapped[dict] = mapped_column(JSON, default=dict)
    hold_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    balance_due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")

    # Contract & customer documents
    contract: Mapped[dict] = mapped_column(JSON, default=dict)  # {"version", "text_md", "hash"}
    contract_accepted_customer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contract_accepted_charterer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    crew_list: Mapped[list] = mapped_column(JSON, default=list)  # [{"name", "birthdate", "role"}]
    documents: Mapped[list] = mapped_column(JSON, default=list)  # [{"type", "name", "url"}]
    handover_confirmed_customer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    return_confirmed_customer_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    payments: Mapped[list["Payment"]] = relationship(back_populates="booking")
    service_orders: Mapped[list["ServiceOrder"]] = relationship(back_populates="booking")
    damages: Mapped[list["DamageCase"]] = relationship(back_populates="booking")
    payout: Mapped["Payout | None"] = relationship(back_populates="booking", uselist=False)


class Payment(TimestampMixin, Base):
    __tablename__ = "payments"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)
    provider_ref: Mapped[str] = mapped_column(String(255), default="", index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="deposit", nullable=False)
    amount_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="EUR")
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    due_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    checkout_url: Mapped[str] = mapped_column(Text, default="")
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    booking: Mapped[Booking] = relationship(back_populates="payments")


# ----------------------------------------------------------------------- operations


class ServicePartner(TimestampMixin, Base):
    """Local service provider: handover, cleaning, technical work, laundry."""

    __tablename__ = "service_partners"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[str] = mapped_column(String(64), default="")
    base_ids: Mapped[list] = mapped_column(JSON, default=list)  # bases served
    services: Mapped[list] = mapped_column(JSON, default=list)  # ServiceOrderType values
    prices: Mapped[dict] = mapped_column(JSON, default=dict)  # {"handover": 9000, "cleaning": 15000}
    rating: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped[User] = relationship(back_populates="partner_profile")
    orders: Mapped[list["ServiceOrder"]] = relationship(back_populates="partner")


class ServiceOrder(TimestampMixin, Base):
    """A unit of operational work tied to a booking (readiness, handover, return, ...)."""

    __tablename__ = "service_orders"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    partner_id: Mapped[str | None] = mapped_column(ForeignKey("service_partners.id"), nullable=True)
    order_type: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)
    scheduled_for: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    # [{"key", "label", "required", "done", "issue", "note", "photos": [url]}]
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    photos: Mapped[list] = mapped_column(JSON, default=list)  # general photos [url]
    notes: Mapped[str] = mapped_column(Text, default="")
    price_cents: Mapped[int] = mapped_column(Integer, default=0)  # cost charged to owner
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="service_orders")
    partner: Mapped[ServicePartner | None] = relationship(back_populates="orders")


class DamageCase(TimestampMixin, Base):
    __tablename__ = "damage_cases"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    source_order_id: Mapped[str | None] = mapped_column(ForeignKey("service_orders.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    photos: Mapped[list] = mapped_column(JSON, default=list)
    estimated_cents: Mapped[int] = mapped_column(Integer, default=0)
    withheld_cents: Mapped[int] = mapped_column(Integer, default=0)  # from security deposit
    status: Mapped[str] = mapped_column(String(20), default="open", nullable=False)

    booking: Mapped[Booking] = relationship(back_populates="damages")


class Payout(TimestampMixin, Base):
    """Owner settlement per booking: gross - commission - service costs."""

    __tablename__ = "payouts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), unique=True, nullable=False)
    charterer_id: Mapped[str] = mapped_column(ForeignKey("charterers.id"), nullable=False)
    gross_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    commission_cents: Mapped[int] = mapped_column(Integer, default=0)
    service_cost_cents: Mapped[int] = mapped_column(Integer, default=0)
    damage_withheld_cents: Mapped[int] = mapped_column(Integer, default=0)  # informational
    net_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    booking: Mapped[Booking] = relationship(back_populates="payout")


# ------------------------------------------------------------- gallery and reviews


class BoatImage(TimestampMixin, Base):
    """A picture with its origin kept separate from its upload time.

    Model photos never stand in for pictures of the actual boat, so the origin is stored
    rather than inferred, and guest pictures carry the month they were taken.
    """

    __tablename__ = "boat_images"
    __table_args__ = (Index("ix_boat_images_boat", "boat_id", "sort_order"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    origin: Mapped[str] = mapped_column(String(20), nullable=False)  # ImageOrigin
    caption: Mapped[str] = mapped_column(String(255), default="")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_public: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Provenance: taken and uploaded are separate facts, and either may be unknown.
    charter_month: Mapped[str] = mapped_column(String(7), default="")  # YYYY-MM, guest photos
    taken_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    credit: Mapped[str] = mapped_column(String(255), default="")  # rights holder / licence note
    booking_id: Mapped[str | None] = mapped_column(ForeignKey("bookings.id"), nullable=True)
    review_id: Mapped[str | None] = mapped_column(ForeignKey("reviews.id"), nullable=True)
    uploaded_by_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

    boat: Mapped[Boat] = relationship(back_populates="gallery")


class Review(TimestampMixin, Base):
    """One review per completed charter. Verification is derived from the booking, never claimed."""

    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("booking_id", name="uq_review_booking"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    booking_id: Mapped[str] = mapped_column(ForeignKey("bookings.id"), nullable=False)
    boat_id: Mapped[str] = mapped_column(ForeignKey("boats.id"), nullable=False)
    charterer_id: Mapped[str] = mapped_column(ForeignKey("charterers.id"), nullable=False)
    model_version_id: Mapped[str | None] = mapped_column(ForeignKey("model_versions.id"), nullable=True)
    author_user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    author_name: Mapped[str] = mapped_column(String(255), default="")
    charter_month: Mapped[str] = mapped_column(String(7), default="")  # YYYY-MM

    # The three things a guest can tell apart, kept separate as the specification requires.
    rating_model: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_condition: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_service: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Detail dimensions behind condition and service.
    rating_care: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_cleanliness: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_accuracy: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_equipment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_organisation: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rating_handover: Mapped[int | None] = mapped_column(Integer, nullable=True)

    title: Mapped[str] = mapped_column(String(255), default="")
    body: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="published", nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    boat: Mapped[Boat] = relationship(back_populates="reviews")

    @property
    def overall(self) -> float | None:
        values = [v for v in (self.rating_model, self.rating_condition, self.rating_service) if v is not None]
        return round(sum(values) / len(values), 2) if values else None
