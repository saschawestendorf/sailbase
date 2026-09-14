"""FastAPI dependencies: DB session, current user, role guards."""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import decode_access_token
from app.models import Charterer, User, UserRole

_bearer = HTTPBearer(auto_error=False)

DB = Annotated[Session, Depends(get_db)]


def get_current_user_optional(
    db: DB, creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]
) -> User | None:
    if creds is None:
        return None
    payload = decode_access_token(creds.credentials)
    if not payload or "sub" not in payload:
        return None
    user = db.get(User, payload["sub"])
    if user is None or not user.is_active:
        return None
    return user


def get_current_user(user: Annotated[User | None, Depends(get_current_user_optional)]) -> User:
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Nicht angemeldet")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]


def get_current_charterer(user: CurrentUser, db: DB) -> Charterer:
    if user.role not in (UserRole.CHARTERER.value, UserRole.ADMIN.value):
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Vercharterer")
    charterer = db.query(Charterer).filter(Charterer.owner_user_id == user.id).one_or_none()
    if charterer is None:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Kein Vercharterer-Profil")
    return charterer


CurrentCharterer = Annotated[Charterer, Depends(get_current_charterer)]


def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Nur für Admins")
    return user
