"""Operational lifecycle after payment: readiness -> handover -> return -> damages -> payout."""

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.models import (
    Boat,
    Booking,
    BookingStatus,
    Charterer,
    DamageCase,
    DamageStatus,
    Payout,
    PayoutStatus,
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderType,
    ServicePartner,
)
from app.models.entities import utcnow
from app.services import checklists


class OperationsError(Exception):
    pass


def create_standard_orders(db: Session, booking: Booking) -> list[ServiceOrder]:
    """Readiness (day before), handover (check-in), return (check-out). Idempotent."""
    existing = {o.order_type for o in booking.service_orders}
    plan = [
        (
            ServiceOrderType.READINESS,
            datetime.combine(booking.start_date - timedelta(days=1), datetime.min.time()).replace(hour=12),
        ),
        (
            ServiceOrderType.HANDOVER,
            datetime.combine(booking.start_date, datetime.min.time()).replace(hour=16),
        ),
        (ServiceOrderType.RETURN, datetime.combine(booking.end_date, datetime.min.time()).replace(hour=9)),
    ]
    created = []
    for order_type, when in plan:
        if order_type in existing:
            continue
        order = ServiceOrder(
            booking_id=booking.id,
            boat_id=booking.boat_id,
            order_type=order_type.value,
            status=ServiceOrderStatus.OPEN.value,
            scheduled_for=when,
            checklist=checklists.template(order_type),
        )
        db.add(order)
        created.append(order)
    db.flush()
    return created


def assign_partner(
    db: Session, order: ServiceOrder, partner: ServicePartner | None, boat: Boat
) -> ServiceOrder:
    if order.status in (ServiceOrderStatus.DONE.value, ServiceOrderStatus.CANCELLED.value):
        raise OperationsError("Auftrag ist bereits abgeschlossen")
    if partner is None:  # owner does it themselves
        order.partner_id = None
        order.price_cents = 0
        order.status = ServiceOrderStatus.ASSIGNED.value
        return order
    if not partner.is_active:
        raise OperationsError("Partner ist inaktiv")
    if partner.base_ids:
        booking = db.get(Booking, order.booking_id)
        if order.order_type == ServiceOrderType.RETURN.value:
            relevant_base_id = (booking.dropoff_base_id if booking else None) or boat.base_id
        else:
            relevant_base_id = (booking.pickup_base_id if booking else None) or boat.base_id
        if relevant_base_id not in partner.base_ids:
            raise OperationsError("Partner bedient diesen Hafen nicht")
    if partner.services and order.order_type not in partner.services:
        raise OperationsError("Partner bietet diese Leistung nicht an")
    order.partner_id = partner.id
    order.price_cents = int((partner.prices or {}).get(order.order_type, 0))
    order.status = ServiceOrderStatus.ASSIGNED.value
    db.flush()
    return order


def update_checklist(
    order: ServiceOrder, updates: list[dict], notes: str | None, photos: list[str] | None
) -> None:
    if order.status in (ServiceOrderStatus.DONE.value, ServiceOrderStatus.CANCELLED.value):
        raise OperationsError("Auftrag ist bereits abgeschlossen")
    # Work on copies: SQLAlchemy only detects JSON changes when a *new* object is assigned.
    checklist = [dict(item) for item in order.checklist or []]
    by_key = {item["key"]: item for item in checklist}
    for upd in updates:
        item = by_key.get(upd.get("key"))
        if item is None:
            continue
        for field in ("done", "issue"):
            if field in upd and upd[field] is not None:
                item[field] = bool(upd[field])
        if upd.get("note") is not None:
            item["note"] = str(upd["note"])[:1000]
        if upd.get("photos") is not None:
            item["photos"] = [str(u) for u in upd["photos"]][:20]
    order.checklist = checklist
    if notes is not None:
        order.notes = notes[:4000]
    if photos is not None:
        order.photos = [str(u) for u in photos][:50]
    if order.status in (ServiceOrderStatus.OPEN.value, ServiceOrderStatus.ASSIGNED.value):
        order.status = ServiceOrderStatus.IN_PROGRESS.value


def complete_order(
    db: Session, order: ServiceOrder, booking: Booking, user_id: str | None
) -> list[DamageCase]:
    ok, missing = checklists.is_complete(order.checklist)
    if not ok:
        raise OperationsError("Checkliste unvollständig: " + "; ".join(missing[:5]))
    order.status = ServiceOrderStatus.DONE.value
    order.completed_at = utcnow()
    order.completed_by_user_id = user_id

    damages: list[DamageCase] = []
    if order.order_type == ServiceOrderType.READINESS.value:
        if booking.status == BookingStatus.CONFIRMED.value:
            booking.status = BookingStatus.READY.value
    elif order.order_type == ServiceOrderType.HANDOVER.value:
        if booking.status in (BookingStatus.CONFIRMED.value, BookingStatus.READY.value):
            booking.status = BookingStatus.HANDED_OVER.value
    elif order.order_type == ServiceOrderType.RETURN.value:
        for item in order.checklist:
            if item.get("issue"):
                damages.append(
                    DamageCase(
                        booking_id=booking.id,
                        source_order_id=order.id,
                        title=item.get("label", "Auffälligkeit"),
                        description=item.get("note", ""),
                        photos=list(item.get("photos") or []),
                        status=DamageStatus.OPEN.value,
                    )
                )
        for d in damages:
            db.add(d)
        if booking.status in (
            BookingStatus.HANDED_OVER.value,
            BookingStatus.READY.value,
            BookingStatus.CONFIRMED.value,
        ):
            booking.status = BookingStatus.RETURNED.value
    db.flush()
    return damages


def assess_damage(
    damage: DamageCase, booking: Booking, estimated_cents: int, withheld_cents: int, description: str | None
) -> None:
    if withheld_cents > booking.security_deposit_cents:
        raise OperationsError("Einbehalt übersteigt die Kaution")
    damage.estimated_cents = max(0, estimated_cents)
    damage.withheld_cents = max(0, withheld_cents)
    if description is not None:
        damage.description = description
    damage.status = DamageStatus.ASSESSED.value


def settle(db: Session, booking: Booking, charterer: Charterer) -> Payout:
    """Release deposit (minus withholdings), compute owner payout. Requires return completed."""
    if booking.status != BookingStatus.RETURNED.value:
        raise OperationsError("Abrechnung erst nach dokumentierter Rückgabe möglich")
    open_damages = [d for d in booking.damages if d.status == DamageStatus.OPEN.value]
    if open_damages:
        raise OperationsError(f"{len(open_damages)} Schadenfälle sind noch nicht bewertet")
    if booking.payout is not None:
        return booking.payout
    withheld = sum(d.withheld_cents for d in booking.damages)
    if withheld > booking.security_deposit_cents:
        raise OperationsError("Einbehalte übersteigen die Kaution")
    service_costs = sum(
        o.price_cents
        for o in booking.service_orders
        if o.status == ServiceOrderStatus.DONE.value and o.partner_id
    )
    payout = Payout(
        booking_id=booking.id,
        charterer_id=charterer.id,
        gross_cents=booking.total_cents,
        commission_cents=booking.commission_cents,
        service_cost_cents=service_costs,
        damage_withheld_cents=withheld,
        net_cents=booking.total_cents - booking.commission_cents - service_costs + withheld,
        status=PayoutStatus.PENDING.value,
    )
    db.add(payout)
    for d in booking.damages:
        d.status = DamageStatus.SETTLED.value
    booking.status = BookingStatus.SETTLED.value
    db.flush()
    return payout
