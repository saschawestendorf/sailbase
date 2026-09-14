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
    PaymentPurpose,
    PaymentStatus,
    Quote,
)
from app.models.entities import utcnow
from app.services import availability, contracts, operations
from app.services.payments import PaymentProvider
from app.services.quotes import quote_is_valid, static_price_cents

BALANCE_DUE_DAYS_BEFORE_START = 30


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
    from app.services.offers import OfferContext

    ctx = OfferContext(
        db,
        boat,
        quote.start_date,
        quote.end_date,
        pickup_base_id=quote.pickup_base_id,
        dropoff_base_id=quote.dropoff_base_id,
    )
    ok, reason = ctx.is_free(quote.start_date, quote.end_date)
    if not ok:
        raise BookingError(reason)

    deposit = max(1, round(quote.total_cents * settings.deposit_percent / 100))
    # Bookings close to the start are paid in full at once
    if (quote.start_date - now.date()).days <= BALANCE_DUE_DAYS_BEFORE_START:
        deposit = quote.total_cents
    commission = round(quote.total_cents * (boat.charterer.commission_percent or 0) / 100)
    balance_due = max(now.date(), quote.start_date - timedelta(days=BALANCE_DUE_DAYS_BEFORE_START))
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
        pickup_base_id=quote.pickup_base_id or boat.base_id,
        dropoff_base_id=quote.dropoff_base_id or quote.pickup_base_id or boat.base_id,
        status=BookingStatus.PENDING_PAYMENT.value,
        currency=quote.currency,
        total_cents=quote.total_cents,
        deposit_cents=deposit,
        commission_cents=commission,
        security_deposit_cents=boat.deposit_cents,
        static_price_cents=static_price_cents(boat, quote.start_date, quote.end_date),
        price_breakdown=quote.breakdown,
        hold_expires_at=now + timedelta(minutes=settings.hold_ttl_minutes),
        balance_due_at=balance_due,
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
            start_base_id=booking.pickup_base_id,
            end_base_id=booking.dropoff_base_id,
        )
    )

    payment = Payment(
        booking_id=booking.id,
        provider=provider.name,
        purpose=PaymentPurpose.DEPOSIT.value,
        amount_cents=deposit,
        currency=quote.currency,
        status=PaymentStatus.PENDING.value,
        due_at=now.date(),
    )
    db.add(payment)
    db.flush()
    start_checkout(
        payment,
        booking,
        boat,
        provider,
        success_url=success_url_template.replace("{reference}", booking.reference),
        cancel_url=cancel_url,
    )
    return booking, payment


_PURPOSE_LABEL = {
    PaymentPurpose.DEPOSIT.value: "Anzahlung",
    PaymentPurpose.BALANCE.value: "Restzahlung",
    PaymentPurpose.SECURITY_DEPOSIT.value: "Kaution",
    PaymentPurpose.EXTRAS.value: "Zusatzleistungen",
}


def start_checkout(
    payment: Payment,
    booking: Booking,
    boat: Boat,
    provider: PaymentProvider,
    *,
    success_url: str,
    cancel_url: str,
) -> Payment:
    """(Re)creates a provider checkout for a pending payment."""
    if payment.status == PaymentStatus.SUCCEEDED.value:
        raise BookingError("Zahlung ist bereits eingegangen")
    label = _PURPOSE_LABEL.get(payment.purpose, payment.purpose)
    checkout = provider.create_checkout(
        booking_id=booking.id,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        description=f"{label} Charter {boat.name} {booking.start_date}–{booking.end_date} "
        f"({booking.reference})",
        success_url=success_url,
        cancel_url=cancel_url,
        customer_email=booking.customer_email,
    )
    payment.provider = checkout.provider
    payment.provider_ref = checkout.provider_ref
    payment.checkout_url = checkout.checkout_url
    payment.status = PaymentStatus.PENDING.value
    payment.raw = checkout.raw
    return payment


def schedule_followup_payments(db: Session, booking: Booking) -> list[Payment]:
    """After the deposit: balance (if any) and security deposit as pending rows. Idempotent."""
    existing = {p.purpose for p in booking.payments}
    created: list[Payment] = []
    balance = booking.total_cents - booking.deposit_cents
    if balance > 0 and PaymentPurpose.BALANCE.value not in existing:
        created.append(
            Payment(
                booking_id=booking.id,
                provider="pending",
                purpose=PaymentPurpose.BALANCE.value,
                amount_cents=balance,
                currency=booking.currency,
                status=PaymentStatus.PENDING.value,
                due_at=booking.balance_due_at,
            )
        )
    if booking.security_deposit_cents > 0 and PaymentPurpose.SECURITY_DEPOSIT.value not in existing:
        created.append(
            Payment(
                booking_id=booking.id,
                provider="pending",
                purpose=PaymentPurpose.SECURITY_DEPOSIT.value,
                amount_cents=booking.security_deposit_cents,
                currency=booking.currency,
                status=PaymentStatus.PENDING.value,
                due_at=booking.start_date - timedelta(days=7),
            )
        )
    for p in created:
        db.add(p)
    if created:
        db.flush()
    return created


def apply_payment_event(db: Session, *, provider_ref: str, succeeded: bool, raw: dict) -> Booking | None:
    """Idempotent: re-delivered webhooks are safe."""
    payment = db.query(Payment).filter(Payment.provider_ref == provider_ref).one_or_none()
    if payment is None:
        return None
    booking = payment.booking
    payment.raw = {**(payment.raw or {}), "last_event": raw}
    is_deposit = payment.purpose == PaymentPurpose.DEPOSIT.value
    if succeeded:
        payment.status = PaymentStatus.SUCCEEDED.value
        if is_deposit and booking.status == BookingStatus.PENDING_PAYMENT.value:
            _confirm(db, booking)
    else:
        payment.status = PaymentStatus.FAILED.value
        if is_deposit and booking.status == BookingStatus.PENDING_PAYMENT.value:
            _release(db, booking, BookingStatus.CANCELLED.value)
    db.flush()
    return booking


def _confirm(db: Session, booking: Booking) -> None:
    booking.status = BookingStatus.CONFIRMED.value
    booking.hold_expires_at = None
    boat = db.get(Boat, booking.boat_id)
    if boat is not None:
        booking.contract = contracts.render(booking, boat, boat.charterer)
    schedule_followup_payments(db, booking)
    operations.create_standard_orders(db, booking)
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
    if booking.status in (
        BookingStatus.CANCELLED.value,
        BookingStatus.SETTLED.value,
        BookingStatus.HANDED_OVER.value,
        BookingStatus.RETURNED.value,
    ):
        raise BookingError("Buchung kann nicht mehr storniert werden")
    for order in booking.service_orders:
        if order.status != "done":
            order.status = "cancelled"
    _release(db, booking, BookingStatus.CANCELLED.value)
    db.flush()
    return booking
