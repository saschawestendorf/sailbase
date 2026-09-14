"""Operational endpoints: customer-side (contract, crew, payments, confirmations) and
charterer-side (orders, partner assignment, damages, settlement)."""

from fastapi import APIRouter, HTTPException, Request, status

from app.api.deps import DB, CurrentCharterer, OptionalUser
from app.core.config import get_settings
from app.models import (
    Base_,
    Boat,
    Booking,
    BookingStatus,
    DamageCase,
    Payment,
    PaymentStatus,
    ServiceOrder,
    ServiceOrderStatus,
    ServicePartner,
)
from app.models.entities import utcnow
from app.schemas.commerce import PaymentOut
from app.schemas.ops import (
    BookingOpsOut,
    CrewListUpdate,
    DamageAssess,
    DamageOut,
    DocumentIn,
    OrderAssign,
    OrderUpdate,
    PartnerPublic,
    PayoutOut,
    ServiceOrderOut,
)
from app.services import bookings as booking_service
from app.services import operations
from app.services.payments import get_payment_provider

router = APIRouter(tags=["operations"])


def order_out(db, order: ServiceOrder) -> ServiceOrderOut:
    out = ServiceOrderOut.model_validate(order)
    boat = db.get(Boat, order.boat_id)
    booking = db.get(Booking, order.booking_id)
    if boat:
        out.boat_name = boat.name
        base = db.get(Base_, boat.base_id)
        out.base_name = f"{base.name}, {base.city}" if base else None
    if booking:
        out.booking_reference = booking.reference
        out.booking_start = booking.start_date.isoformat()
        out.booking_end = booking.end_date.isoformat()
        out.customer_name = booking.customer_name
    if order.partner:
        out.partner = PartnerPublic.model_validate(order.partner)
    return out


def _customer_booking(db, reference: str, user, email: str | None) -> Booking:
    b = db.query(Booking).filter(Booking.reference == reference.upper()).one_or_none()
    if b is None:
        raise HTTPException(404, "Buchung nicht gefunden")
    allowed = (user is not None and (user.id == b.customer_user_id or user.role == "admin")) or (
        email is not None and email.lower() == b.customer_email
    )
    if not allowed:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Zugriff verweigert")
    return b


# ------------------------------------------------------------------ customer side


@router.get("/bookings/{reference}/ops", response_model=BookingOpsOut)
def booking_ops(reference: str, db: DB, user: OptionalUser, email: str | None = None):
    b = _customer_booking(db, reference, user, email)
    return BookingOpsOut(
        orders=[order_out(db, o) for o in b.service_orders],
        damages=[DamageOut.model_validate(d) for d in b.damages],
        payout=PayoutOut.model_validate(b.payout) if b.payout else None,
        contract=b.contract or {},
        contract_accepted_customer_at=b.contract_accepted_customer_at,
        contract_accepted_charterer_at=b.contract_accepted_charterer_at,
        handover_confirmed_customer_at=b.handover_confirmed_customer_at,
        return_confirmed_customer_at=b.return_confirmed_customer_at,
        crew_list=b.crew_list or [],
        documents=b.documents or [],
    )


@router.post("/bookings/{reference}/accept-contract", response_model=BookingOpsOut)
def accept_contract(reference: str, db: DB, user: OptionalUser, email: str | None = None):
    b = _customer_booking(db, reference, user, email)
    if not b.contract:
        raise HTTPException(409, "Vertrag liegt noch nicht vor")
    if b.contract_accepted_customer_at is None:
        b.contract_accepted_customer_at = utcnow()
        db.commit()
    return booking_ops(reference, db, user, email)


@router.put("/bookings/{reference}/crew", response_model=BookingOpsOut)
def set_crew(reference: str, payload: CrewListUpdate, db: DB, user: OptionalUser, email: str | None = None):
    b = _customer_booking(db, reference, user, email)
    if len(payload.crew) > b.persons:
        raise HTTPException(422, f"Crewliste darf maximal {b.persons} Personen enthalten")
    b.crew_list = [m.model_dump() for m in payload.crew]
    db.commit()
    return booking_ops(reference, db, user, email)


@router.post("/bookings/{reference}/documents", response_model=BookingOpsOut)
def add_document(reference: str, payload: DocumentIn, db: DB, user: OptionalUser, email: str | None = None):
    b = _customer_booking(db, reference, user, email)
    docs = list(b.documents or [])
    if len(docs) >= 30:
        raise HTTPException(422, "Maximal 30 Dokumente")
    docs.append(payload.model_dump())
    b.documents = docs
    db.commit()
    return booking_ops(reference, db, user, email)


@router.post("/bookings/{reference}/confirm/{step}", response_model=BookingOpsOut)
def customer_confirm(reference: str, step: str, db: DB, user: OptionalUser, email: str | None = None):
    """Customer counter-signs handover or return after the checklist was completed."""
    b = _customer_booking(db, reference, user, email)
    if step not in ("handover", "return"):
        raise HTTPException(404)
    order = next((o for o in b.service_orders if o.order_type == step), None)
    if order is None or order.status != ServiceOrderStatus.DONE.value:
        raise HTTPException(409, "Checkliste ist noch nicht abgeschlossen")
    field = "handover_confirmed_customer_at" if step == "handover" else "return_confirmed_customer_at"
    if getattr(b, field) is None:
        setattr(b, field, utcnow())
        db.commit()
    return booking_ops(reference, db, user, email)


@router.post("/bookings/{reference}/pay/{purpose}", response_model=PaymentOut)
def pay(reference: str, purpose: str, db: DB, user: OptionalUser, request: Request, email: str | None = None):
    """Starts a checkout for a pending balance / security deposit payment."""
    b = _customer_booking(db, reference, user, email)
    if b.status not in BookingStatus.active():
        raise HTTPException(409, "Buchung ist nicht aktiv")
    payment = next((p for p in b.payments if p.purpose == purpose), None)
    if payment is None:
        raise HTTPException(404, "Keine solche Zahlung")
    if payment.status == PaymentStatus.SUCCEEDED.value:
        raise HTTPException(409, "Bereits bezahlt")
    settings = get_settings()
    boat = db.get(Boat, b.boat_id)
    provider = get_payment_provider(str(request.base_url).rstrip("/"))
    try:
        booking_service.start_checkout(
            payment,
            b,
            boat,
            provider,
            success_url=f"{settings.public_web_url}/booking/{b.reference}?paid={purpose}",
            cancel_url=f"{settings.public_web_url}/booking/{b.reference}",
        )
    except booking_service.BookingError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return payment


# ----------------------------------------------------------------- charterer side


def _own_booking(db, charterer, booking_id: str) -> Booking:
    b = db.get(Booking, booking_id)
    if b is None or b.boat_id not in {x.id for x in charterer.boats}:
        raise HTTPException(404, "Buchung nicht gefunden")
    return b


@router.get("/charterer/bookings/{booking_id}/ops", response_model=BookingOpsOut)
def charterer_booking_ops(booking_id: str, db: DB, charterer: CurrentCharterer):
    b = _own_booking(db, charterer, booking_id)
    return BookingOpsOut(
        orders=[order_out(db, o) for o in b.service_orders],
        damages=[DamageOut.model_validate(d) for d in b.damages],
        payout=PayoutOut.model_validate(b.payout) if b.payout else None,
        contract=b.contract or {},
        contract_accepted_customer_at=b.contract_accepted_customer_at,
        contract_accepted_charterer_at=b.contract_accepted_charterer_at,
        handover_confirmed_customer_at=b.handover_confirmed_customer_at,
        return_confirmed_customer_at=b.return_confirmed_customer_at,
        crew_list=b.crew_list or [],
        documents=b.documents or [],
    )


@router.post("/charterer/bookings/{booking_id}/accept-contract", response_model=BookingOpsOut)
def charterer_accept_contract(booking_id: str, db: DB, charterer: CurrentCharterer):
    b = _own_booking(db, charterer, booking_id)
    if b.contract_accepted_charterer_at is None:
        b.contract_accepted_charterer_at = utcnow()
        db.commit()
    return charterer_booking_ops(booking_id, db, charterer)


@router.get("/charterer/orders", response_model=list[ServiceOrderOut])
def charterer_orders(db: DB, charterer: CurrentCharterer, status_filter: str | None = None):
    boat_ids = [b.id for b in charterer.boats]
    if not boat_ids:
        return []
    q = db.query(ServiceOrder).filter(ServiceOrder.boat_id.in_(boat_ids))
    if status_filter:
        q = q.filter(ServiceOrder.status == status_filter)
    return [order_out(db, o) for o in q.order_by(ServiceOrder.scheduled_for).all()]


@router.get("/charterer/partners", response_model=list[PartnerPublic])
def partners_for_charterer(db: DB, charterer: CurrentCharterer, base_id: str | None = None):
    rows = db.query(ServicePartner).filter(ServicePartner.is_active.is_(True)).all()
    if base_id:
        rows = [p for p in rows if not p.base_ids or base_id in p.base_ids]
    return rows


def _own_order(db, charterer, order_id: str) -> ServiceOrder:
    o = db.get(ServiceOrder, order_id)
    if o is None or o.boat_id not in {x.id for x in charterer.boats}:
        raise HTTPException(404, "Auftrag nicht gefunden")
    return o


@router.post("/charterer/orders/{order_id}/assign", response_model=ServiceOrderOut)
def assign(order_id: str, payload: OrderAssign, db: DB, charterer: CurrentCharterer):
    o = _own_order(db, charterer, order_id)
    partner = db.get(ServicePartner, payload.partner_id) if payload.partner_id else None
    if payload.partner_id and partner is None:
        raise HTTPException(404, "Partner nicht gefunden")
    try:
        operations.assign_partner(db, o, partner, db.get(Boat, o.boat_id))
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    if payload.scheduled_for:
        o.scheduled_for = payload.scheduled_for.replace(tzinfo=None)
    db.commit()
    return order_out(db, o)


@router.patch("/charterer/orders/{order_id}", response_model=ServiceOrderOut)
def charterer_update_order(order_id: str, payload: OrderUpdate, db: DB, charterer: CurrentCharterer):
    """Owner works the checklist themselves (no partner)."""
    o = _own_order(db, charterer, order_id)
    try:
        operations.update_checklist(o, [i.model_dump() for i in payload.items], payload.notes, payload.photos)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_out(db, o)


@router.post("/charterer/orders/{order_id}/complete", response_model=ServiceOrderOut)
def charterer_complete_order(order_id: str, db: DB, charterer: CurrentCharterer):
    o = _own_order(db, charterer, order_id)
    try:
        operations.complete_order(db, o, db.get(Booking, o.booking_id), charterer.owner_user_id)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_out(db, o)


@router.get("/charterer/damages", response_model=list[DamageOut])
def charterer_damages(db: DB, charterer: CurrentCharterer):
    boat_ids = [b.id for b in charterer.boats]
    if not boat_ids:
        return []
    return (
        db.query(DamageCase)
        .join(Booking, DamageCase.booking_id == Booking.id)
        .filter(Booking.boat_id.in_(boat_ids))
        .order_by(DamageCase.created_at.desc())
        .all()
    )


@router.post("/charterer/damages/{damage_id}/assess", response_model=DamageOut)
def assess(damage_id: str, payload: DamageAssess, db: DB, charterer: CurrentCharterer):
    d = db.get(DamageCase, damage_id)
    if d is None:
        raise HTTPException(404, "Schadenfall nicht gefunden")
    b = _own_booking(db, charterer, d.booking_id)
    try:
        operations.assess_damage(d, b, payload.estimated_cents, payload.withheld_cents, payload.description)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return d


@router.post("/charterer/bookings/{booking_id}/settle", response_model=PayoutOut)
def settle(booking_id: str, db: DB, charterer: CurrentCharterer):
    b = _own_booking(db, charterer, booking_id)
    try:
        payout = operations.settle(db, b, charterer)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return payout


@router.get("/charterer/payouts", response_model=list[PayoutOut])
def payouts(db: DB, charterer: CurrentCharterer):
    from app.models import Payout

    return (
        db.query(Payout).filter(Payout.charterer_id == charterer.id).order_by(Payout.created_at.desc()).all()
    )


@router.get("/charterer/bookings/{booking_id}/payments", response_model=list[PaymentOut])
def booking_payments(booking_id: str, db: DB, charterer: CurrentCharterer):
    b = _own_booking(db, charterer, booking_id)
    return db.query(Payment).filter(Payment.booking_id == b.id).order_by(Payment.created_at).all()
