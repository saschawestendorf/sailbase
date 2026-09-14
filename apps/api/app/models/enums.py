"""Shared enumerations. Values are stored as strings (portable across DBs)."""

import enum


class UserRole(enum.StrEnum):
    CUSTOMER = "customer"
    CHARTERER = "charterer"  # Bootseigner / Charterunternehmen
    PARTNER = "partner"  # lokaler Servicepartner (Übergabe, Reinigung, Technik)
    ADMIN = "admin"


class ListingMode(enum.StrEnum):
    """Hybrid model: how the platform positions itself for this boat."""

    BROKERAGE = "brokerage"  # contract between customer and charterer, platform mediates
    EXCLUSIVE = "exclusive"  # platform holds exclusive contingent and sets price itself


class PricingMode(enum.StrEnum):
    FIXED = "fixed"  # reference price only, no dynamic factors
    CORRIDOR = "corridor"  # dynamic within [floor, ceiling] set by charterer
    AUTO = "auto"  # dynamic, platform decides (floor still respected)


class PricingStrategy(enum.StrEnum):
    """How aggressively the algorithm sells calendar days (owner setting)."""

    CONSERVATIVE = "conservative"  # protect the calendar, reject fragmenting bookings
    BALANCED = "balanced"
    AGGRESSIVE = "aggressive"  # sell every day that clears the floor


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
    CONFIRMED = "confirmed"  # deposit paid, contract generated
    READY = "ready"  # readiness check complete -> "Ready for Charter"
    HANDED_OVER = "handed_over"  # check-in done, crew on board
    RETURNED = "returned"  # check-out done, damages assessed
    SETTLED = "settled"  # deposit released/withheld, owner paid out
    CANCELLED = "cancelled"
    EXPIRED = "expired"

    @classmethod
    def active(cls) -> set[str]:
        return {cls.CONFIRMED, cls.READY, cls.HANDED_OVER, cls.RETURNED, cls.SETTLED}


class PaymentPurpose(enum.StrEnum):
    DEPOSIT = "deposit"  # Anzahlung
    BALANCE = "balance"  # Restzahlung
    SECURITY_DEPOSIT = "security_deposit"  # Kaution
    EXTRAS = "extras"


class ServiceOrderType(enum.StrEnum):
    READINESS = "readiness"  # Bootsbereitschaft vor Charter
    HANDOVER = "handover"  # Übergabe / Check-in
    RETURN = "return"  # Rücknahme / Check-out
    CLEANING = "cleaning"
    TECHNICAL = "technical"
    LAUNDRY = "laundry"


class ServiceOrderStatus(enum.StrEnum):
    OPEN = "open"  # created, nobody assigned
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    CANCELLED = "cancelled"


class DamageStatus(enum.StrEnum):
    OPEN = "open"
    ASSESSED = "assessed"
    SETTLED = "settled"


class PayoutStatus(enum.StrEnum):
    PENDING = "pending"
    PAID = "paid"


class PaymentStatus(enum.StrEnum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    REFUNDED = "refunded"
