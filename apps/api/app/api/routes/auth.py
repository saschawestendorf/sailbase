from fastapi import APIRouter, HTTPException, status

from app.api.deps import DB, CurrentUser
from app.core.security import create_access_token, hash_password, verify_password
from app.models import Charterer, ServicePartner, User
from app.schemas.auth import LoginRequest, ProfileUpdate, RegisterRequest, TokenResponse, UserOut
from app.services.slugs import slugify

router = APIRouter(prefix="/auth", tags=["auth"])


def _slugify(value: str) -> str:
    return slugify(value, fallback="charterer")


def _user_out(user: User) -> UserOut:
    out = UserOut.model_validate(user)
    out.charterer_id = user.charterer.id if user.charterer else None
    out.partner_id = user.partner_profile.id if user.partner_profile else None
    return out


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: DB):
    email = payload.email.lower()
    if db.query(User).filter(User.email == email).first():
        raise HTTPException(status.HTTP_409_CONFLICT, "E-Mail bereits registriert")
    user = User(
        email=email,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=payload.role,
    )
    db.add(user)
    db.flush()
    if payload.role == "charterer":
        name = payload.charterer_name or payload.full_name or email.split("@")[0]
        slug = _slugify(name)
        n = 1
        while db.query(Charterer).filter(Charterer.slug == slug).first():
            n += 1
            slug = f"{_slugify(name)}-{n}"
        db.add(Charterer(owner_user_id=user.id, name=name, slug=slug, contact_email=email))
    elif payload.role == "partner":
        name = payload.partner_name or payload.full_name or email.split("@")[0]
        db.add(ServicePartner(user_id=user.id, name=name))
    db.commit()
    return TokenResponse(access_token=create_access_token(user.id, {"role": user.role}))


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: DB):
    user = db.query(User).filter(User.email == payload.email.lower()).one_or_none()
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "E-Mail oder Passwort falsch")
    if not user.is_active:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Konto deaktiviert")
    return TokenResponse(access_token=create_access_token(user.id, {"role": user.role}))


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser):
    return _user_out(user)


@router.patch("/me", response_model=UserOut)
def update_me(payload: ProfileUpdate, user: CurrentUser, db: DB):
    for k, v in payload.model_dump(exclude_unset=True).items():
        setattr(user, k, v)
    db.commit()
    return _user_out(user)
