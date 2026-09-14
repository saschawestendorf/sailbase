from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import ORMModel

Rating = int | None


class ReviewSubmit(BaseModel):
    """Guests rate the model, the state of this particular boat and the service separately."""

    rating_model: Rating = Field(default=None, ge=1, le=5)
    rating_condition: Rating = Field(default=None, ge=1, le=5)
    rating_service: Rating = Field(default=None, ge=1, le=5)
    rating_care: Rating = Field(default=None, ge=1, le=5)
    rating_cleanliness: Rating = Field(default=None, ge=1, le=5)
    rating_accuracy: Rating = Field(default=None, ge=1, le=5)
    rating_equipment: Rating = Field(default=None, ge=1, le=5)
    rating_organisation: Rating = Field(default=None, ge=1, le=5)
    rating_handover: Rating = Field(default=None, ge=1, le=5)
    title: str = Field(default="", max_length=255)
    body: str = Field(default="", max_length=5000)
    photos: list[str] | None = Field(default=None, max_length=12)

    @model_validator(mode="after")
    def _at_least_one(self):
        if self.rating_model is None and self.rating_condition is None and self.rating_service is None:
            raise ValueError("Mindestens eine der drei Hauptbewertungen ist nötig")
        return self


class ReviewOut(ORMModel):
    id: str
    boat_id: str
    author_name: str
    charter_month: str
    rating_model: Rating
    rating_condition: Rating
    rating_service: Rating
    rating_care: Rating
    rating_cleanliness: Rating
    rating_accuracy: Rating
    rating_equipment: Rating
    rating_organisation: Rating
    rating_handover: Rating
    overall: float | None
    title: str
    body: str
    published_at: datetime | None
    photos: list[str] = []


class RatingSummaryOut(BaseModel):
    count: int
    overall: float | None
    model: float | None
    condition: float | None
    service: float | None
    details: dict[str, float | None]


class BoatImageOut(ORMModel):
    id: str
    url: str
    origin: str  # model | owner | guest
    caption: str
    charter_month: str
    taken_on: date | None
    credit: str
    created_at: datetime


class ReviewsOut(BaseModel):
    summary: RatingSummaryOut
    reviews: list[ReviewOut]


class ReviewEligibility(BaseModel):
    may_review: bool
    reason: str = ""
    existing: ReviewOut | None = None
