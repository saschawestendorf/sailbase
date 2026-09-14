from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import ORMModel


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    full_name: str = Field(default="", max_length=255)
    role: str = Field(default="customer", pattern="^(customer|charterer|partner)$")
    charterer_name: str | None = Field(default=None, max_length=255)
    partner_name: str | None = Field(default=None, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class ProfileUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=255)
    license_level: int | None = Field(default=None, ge=0, le=5)
    experience_nm: int | None = Field(default=None, ge=0, le=500000)
    height_cm: int | None = Field(default=None, ge=100, le=250)


class UserOut(ORMModel):
    id: str
    email: str
    full_name: str
    role: str
    license_level: int
    experience_nm: int
    height_cm: int | None
    charterer_id: str | None = None
    partner_id: str | None = None
