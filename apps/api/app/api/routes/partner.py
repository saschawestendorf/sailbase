"""Service-partner endpoints: a deliberately tiny surface for a mobile checklist UI."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import DB, CurrentUser
from app.api.routes.operations import order_out
from app.models import Booking, ServiceOrder, ServicePartner, UserRole
from app.schemas.ops import OrderUpdate, PartnerPublic, PartnerUpdate, ServiceOrderOut
from app.services import operations

router = APIRouter(prefix="/partner", tags=["partner"])


def get_current_partner(user: CurrentUser, db: DB) -> ServicePartner:
    if user.role not in (UserRole.PARTNER.value, UserRole.ADMIN.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Servicepartner")
    p = db.query(ServicePartner).filter(ServicePartner.user_id == user.id).one_or_none()
    if p is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Kein Partnerprofil")
    return p


CurrentPartner = Annotated[ServicePartner, Depends(get_current_partner)]


@router.get("/me", response_model=PartnerPublic)
def me(partner: CurrentPartner):
    return partner


@router.patch("/me", response_model=PartnerPublic)
def update_me(payload: PartnerUpdate, db: DB, partner: CurrentPartner):
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(partner, k, v)
    db.commit()
    return partner


@router.get("/orders", response_model=list[ServiceOrderOut])
def my_orders(db: DB, partner: CurrentPartner, include_done: bool = False):
    q = db.query(ServiceOrder).filter(ServiceOrder.partner_id == partner.id)
    if not include_done:
        q = q.filter(ServiceOrder.status.in_(["assigned", "in_progress"]))
    return [order_out(db, o) for o in q.order_by(ServiceOrder.scheduled_for).all()]


def _own(db, partner, order_id) -> ServiceOrder:
    o = db.get(ServiceOrder, order_id)
    if o is None or o.partner_id != partner.id:
        raise HTTPException(404, "Auftrag nicht gefunden")
    return o


@router.get("/orders/{order_id}", response_model=ServiceOrderOut)
def get_order(order_id: str, db: DB, partner: CurrentPartner):
    return order_out(db, _own(db, partner, order_id))


@router.patch("/orders/{order_id}", response_model=ServiceOrderOut)
def update_order(order_id: str, payload: OrderUpdate, db: DB, partner: CurrentPartner):
    o = _own(db, partner, order_id)
    try:
        operations.update_checklist(o, [i.model_dump() for i in payload.items], payload.notes, payload.photos)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_out(db, o)


@router.post("/orders/{order_id}/complete", response_model=ServiceOrderOut)
def complete(order_id: str, db: DB, partner: CurrentPartner):
    o = _own(db, partner, order_id)
    try:
        operations.complete_order(db, o, db.get(Booking, o.booking_id), partner.user_id)
    except operations.OperationsError as e:
        raise HTTPException(409, str(e)) from e
    db.commit()
    return order_out(db, o)
