"""Booking lifecycle: quote -> hold + pending booking -> payment -> confirmed."""

import secrets
from datetime import timedelta

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models import (
    AvailabilityBlock,
    BlockType,
    Boat,
    Booking,
    BookingStatus,
    Payment,
    PaymentStatus,
    Quote,
)
from app.models.entities import utcnow
from app.services import availability
from app.services.payments import PaymentProvider
from app.services.quotes import quote_is_valid


class BookingError(Exception):
    pass


def _reference() -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    return "SB-" + "".join(secrets.choice(alphabet) for _ in range(6))


def create_booking(
    db: Session,
    *,
    quote: Quote,
    boat: Boat,
    customer_email: str,
    customer_name: str,
    customer_user_id: str | None,
    provider: PaymentProvider,
    success_url_template: str,
    cancel_url: str,
) -> tuple[Booking, Payment]:
    """`success_url_template` may contain `{reference}`, filled with the booking reference."""
    settings = get_settings()
    now = utcnow()
    if not quote_is_valid(quote, now):
        raise BookingError("Angebot abgelaufen, bitte neu berechnen")
    if quote.boat_id != boat.id:
        raise BookingError("Angebot gehört zu einem anderen Boot")
    availability.purge_expired_holds(db, now)
    ok, reason = availability.is_available(db, boat, quote.start_date, quote.end_date)
    if not ok:
        raise BookingError(reason)

    deposit = max(1, round(quote.total_cents * settings.deposit_percent / 100))
    commission = round(quote.total_cents * (boat.charterer.commission_percent or 0) / 100)
    booking = Booking(
        reference=_reference(),
        boat_id=boat.id,
        quote_id=quote.id,
        customer_user_id=customer_user_id,
        customer_email=customer_email,
        customer_name=customer_name,
        persons=quote.persons,
        start_date=quote.start_date,
        end_date=quote.end_date,
        status=BookingStatus.PENDING_PAYMENT.value,
        currency=quote.currency,
        total_cents=quote.total_cents,
        deposit_cents=deposit,
        commission_cents=commission,
        price_breakdown=quote.breakdown,
        hold_expires_at=now + timedelta(minutes=settings.hold_ttl_minutes),
    )
    db.add(booking)
    db.flush()

    db.add(
        AvailabilityBlock(
            boat_id=boat.id,
            start_date=quote.start_date,
            end_date=quote.end_date,
            block_type=BlockType.HOLD.value,
            booking_id=booking.id,
            expires_at=booking.hold_expires_at,
            note=f"Hold {booking.reference}",
        )
    )

    checkout = provider.create_checkout(
        booking_id=booking.id,
        amount_cents=deposit,
        currency=quote.currency,
        description=f"Anzahlung Charter {boat.name} {quote.start_date}–{quote.end_date}",
        success_url=success_url_template.replace("{reference}", booking.reference),
        cancel_url=cancel_url,
        customer_email=customer_email,
    )
    payment = Payment(
        booking_id=booking.id,
        provider=checkout.provider,
        provider_ref=checkout.provider_ref,
        amount_cents=deposit,
        currency=quote.currency,
        status=PaymentStatus.PENDING.value,
        checkout_url=checkout.checkout_url,
        raw=checkout.raw,
    )
    db.add(payment)
    db.flush()
    return booking, payment


def apply_payment_event(db: Session, *, provider_ref: str, succeeded: bool, raw: dict) -> Booking | None:
    """Idempotent: re-delivered webhooks are safe."""
    payment = db.query(Payment).filter(Payment.provider_ref == provider_ref).one_or_none()
    if payment is None:
        return None
    booking = payment.booking
    payment.raw = {**(payment.raw or {}), "last_event": raw}
    if succeeded:
        payment.status = PaymentStatus.SUCCEEDED.value
        if booking.status == BookingStatus.PENDING_PAYMENT.value:
            _confirm(db, booking)
    else:
        payment.status = PaymentStatus.FAILED.value
        if booking.status == BookingStatus.PENDING_PAYMENT.value:
            _release(db, booking, BookingStatus.CANCELLED.value)
    db.flush()
    return booking


def _confirm(db: Session, booking: Booking) -> None:
    booking.status = BookingStatus.CONFIRMED.value
    booking.hold_expires_at = None
    blocks = db.query(AvailabilityBlock).filter(AvailabilityBlock.booking_id == booking.id).all()
    if blocks:
        for b in blocks:
            b.block_type = BlockType.BOOKING.value
            b.expires_at = None
            b.note = f"Buchung {booking.reference}"
    else:  # hold expired before payment arrived; re-block if still free
        db.add(
            AvailabilityBlock(
                boat_id=booking.boat_id,
                start_date=booking.start_date,
                end_date=booking.end_date,
                block_type=BlockType.BOOKING.value,
                booking_id=booking.id,
                note=f"Buchung {booking.reference}",
            )
        )


def _release(db: Session, booking: Booking, new_status: str) -> None:
    booking.status = new_status
    for b in db.query(AvailabilityBlock).filter(AvailabilityBlock.booking_id == booking.id).all():
        db.delete(b)


def expire_stale_bookings(db: Session) -> int:
    now = utcnow()
    stale = (
        db.query(Booking)
        .filter(
            Booking.status == BookingStatus.PENDING_PAYMENT.value,
            Booking.hold_expires_at.is_not(None),
            Booking.hold_expires_at <= now,
        )
        .all()
    )
    for b in stale:
        _release(db, b, BookingStatus.EXPIRED.value)
    if stale:
        db.flush()
    return len(stale)


def cancel_booking(db: Session, booking: Booking) -> Booking:
    if booking.status in (BookingStatus.CANCELLED.value, BookingStatus.COMPLETED.value):
        raise BookingError("Buchung kann nicht mehr storniert werden")
    _release(db, booking, BookingStatus.CANCELLED.value)
    db.flush()
    return booking
