"""Shared enumerations. Values are stored as strings (portable across DBs)."""

import enum


class UserRole(enum.StrEnum):
    CUSTOMER = "customer"
    CHARTERER = "charterer"
    ADMIN = "admin"


class ListingMode(enum.StrEnum):
    """Hybrid model: how the platform positions itself for this boat."""

    BROKERAGE = "brokerage"  # contract between customer and charterer, platform mediates
    EXCLUSIVE = "exclusive"  # platform holds exclusive contingent and sets price itself


class PricingMode(enum.StrEnum):
    FIXED = "fixed"  # reference price only, no dynamic factors
    CORRIDOR = "corridor"  # dynamic within [floor, ceiling] set by charterer
    AUTO = "auto"  # dynamic, platform decides (floor still respected)


class BoatCharacter(enum.StrEnum):
    GOOD_NATURED = "good_natured"  # gutmütig, verzeiht Fehler, ideal für Einsteiger/Familien
    SPORTY = "sporty"  # sportlich, schnell, anspruchsvoller
    COMFORT = "comfort"  # komfortabel, viel Platz, Fahrtenyacht
    BLUEWATER = "bluewater"  # seetüchtig, Langfahrt
    CLASSIC = "classic"  # klassisch, Charakter-Schiff


class LicenseLevel(int, enum.Enum):
    """Ordered so that higher value => more qualified."""

    NONE = 0
    SBF_BINNEN = 1
    SBF_SEE = 2
    SKS = 3
    SSS = 4
    SHS = 5


class BlockType(enum.StrEnum):
    BOOKING = "booking"  # confirmed booking
    HOLD = "hold"  # temporary hold during checkout (expires)
    MAINTENANCE = "maintenance"
    OWNER_USE = "owner_use"
    CLOSED = "closed"  # outside charter season / not offered


class BookingStatus(enum.StrEnum):
    PENDING_PAYMENT = "pending_payment"
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    COMPLETED = "completed"


class PaymentStatus(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
