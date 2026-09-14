"""Idempotent seeding. Run: python -m app.seed.seed"""

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.db import Base, SessionLocal, engine
from app.core.security import hash_password
from app.models import (
    AvailabilityBlock,
    Base_,
    BlockType,
    Boat,
    BoatClass,
    Charterer,
    PricingPolicy,
    Region,
    User,
    UserRole,
)
from app.seed import data


def availability_free(db: Session, boat_id: str, start: date, end: date) -> bool:
    return (
        not db.query(AvailabilityBlock)
        .filter(
            AvailabilityBlock.boat_id == boat_id,
            AvailabilityBlock.start_date < end,
            AvailabilityBlock.end_date > start,
        )
        .first()
    )


def _slug(name: str) -> str:
    import re

    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def seed(db: Session, *, with_demo_bookings: bool = True) -> dict:
    regions = {}
    for r in data.REGIONS:
        obj = db.query(Region).filter(Region.slug == r["slug"]).one_or_none() or Region(slug=r["slug"])
        obj.name, obj.country = r["name"], r["country"]
        obj.description, obj.season_curve = r["description"], r["season_curve"]
        db.add(obj)
        regions[r["slug"]] = obj
    db.flush()

    bases = {}
    for b in data.BASES:
        obj = db.query(Base_).filter(Base_.name == b["name"]).one_or_none() or Base_(name=b["name"])
        obj.region_id, obj.city, obj.lat, obj.lon = regions[b["region"]].id, b["city"], b["lat"], b["lon"]
        db.add(obj)
        bases[b["name"]] = obj
    db.flush()

    classes = []
    for c in data.BOAT_CLASSES:
        obj = db.query(BoatClass).filter(BoatClass.slug == c["slug"]).one_or_none() or BoatClass(
            slug=c["slug"]
        )
        obj.name, obj.min_length_m, obj.max_length_m = c["name"], c["min_length_m"], c["max_length_m"]
        db.add(obj)
        classes.append(obj)
    db.flush()

    def class_for(length: float) -> BoatClass:
        for c in classes:
            if c.min_length_m <= length < c.max_length_m:
                return c
        return classes[-1]

    charterers = {}
    for c in data.CHARTERERS:
        user = db.query(User).filter(User.email == c["email"]).one_or_none()
        if user is None:
            user = User(
                email=c["email"],
                password_hash=hash_password(c["password"]),
                full_name=c["name"],
                role=UserRole.CHARTERER.value,
            )
            db.add(user)
            db.flush()
        obj = db.query(Charterer).filter(Charterer.slug == c["slug"]).one_or_none() or Charterer(
            slug=c["slug"], owner_user_id=user.id, name=c["name"]
        )
        obj.contact_email, obj.commission_percent, obj.rating = (
            c["email"],
            c["commission_percent"],
            c["rating"],
        )
        db.add(obj)
        charterers[c["slug"]] = obj
    db.flush()

    boats = []
    for b in data.BOATS:
        slug = _slug(b["name"])
        obj = db.query(Boat).filter(Boat.slug == slug).one_or_none() or Boat(slug=slug)
        obj.charterer_id = charterers[b["charterer"]].id
        obj.base_id = bases[b["base"]].id
        obj.boat_class_id = class_for(b["length_m"]).id
        for key in (
            "name",
            "manufacturer",
            "model",
            "year_built",
            "year_refit",
            "length_m",
            "beam_m",
            "draft_m",
            "displacement_kg",
            "sail_area_m2",
            "engine_hp",
            "cabins",
            "berths",
            "max_persons",
            "heads",
            "headroom_cm",
            "max_berth_length_cm",
            "character",
            "required_license",
            "required_experience_nm",
            "features",
            "description",
            "min_days",
        ):
            if key in b:
                setattr(obj, key, b[key])
        obj.cleaning_fee_cents = b["cleaning_fee"] * 100
        obj.deposit_cents = b["deposit"] * 100
        obj.images = [f"https://picsum.photos/seed/{slug}/1200/800"]
        db.add(obj)
        db.flush()
        policy = obj.pricing or PricingPolicy(
            boat_id=obj.id, reference_price_cents=0, floor_price_cents=0, ceiling_price_cents=0
        )
        policy.mode = "corridor"
        policy.reference_price_cents = b["ref"] * 100
        policy.floor_price_cents = b["floor"] * 100
        policy.ceiling_price_cents = b["ceiling"] * 100
        db.add(policy)
        boats.append(obj)
    db.flush()

    # Demo users
    for u, role in ((data.DEMO_CUSTOMER, UserRole.CUSTOMER.value), (data.DEMO_ADMIN, UserRole.ADMIN.value)):
        if not db.query(User).filter(User.email == u["email"]).first():
            db.add(
                User(
                    email=u["email"],
                    password_hash=hash_password(u["password"]),
                    full_name=u["full_name"],
                    role=role,
                    license_level=u.get("license_level", 0),
                    experience_nm=u.get("experience_nm", 0),
                    height_cm=u.get("height_cm"),
                )
            )
    db.flush()

    # Demo occupancy so the demand factor has something to chew on (deterministic).
    # Bookings are placed in the *upcoming* season so that searches show varying demand.
    if with_demo_bookings and not db.query(AvailabilityBlock).first():
        rng = random.Random(42)
        today = date.today()
        season_year = today.year + 1 if today.month >= 4 else today.year
        season_start = date(season_year, 4, 1)
        for boat in boats:
            for winter in (season_year - 1, season_year):
                db.add(
                    AvailabilityBlock(
                        boat_id=boat.id,
                        start_date=date(winter, 11, 1),
                        end_date=date(winter + 1, 4, 1),
                        block_type=BlockType.CLOSED.value,
                        note="Winterlager",
                    )
                )
            for _ in range(rng.randint(3, 8)):
                # weighted towards high season, like the real market
                offset = int(rng.triangular(0, 210, 120))
                length = rng.choice([3, 4, 5, 7, 7, 7, 10, 14])
                s = season_start + timedelta(days=offset)
                e = s + timedelta(days=length)
                if availability_free(db, boat.id, s, e):
                    db.add(
                        AvailabilityBlock(
                            boat_id=boat.id,
                            start_date=s,
                            end_date=e,
                            block_type=BlockType.BOOKING.value,
                            note="Demo-Buchung",
                        )
                    )
                    db.flush()
    db.commit()
    return {"regions": len(regions), "bases": len(bases), "boats": len(boats)}


def main() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        print(seed(db))


if __name__ == "__main__":
    main()
