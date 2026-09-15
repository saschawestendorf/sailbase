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
    BoatImage,
    BoatModel,
    Booking,
    BookingStatus,
    Charterer,
    ImageOrigin,
    Manufacturer,
    ModelVersion,
    PricingPolicy,
    Quote,
    Region,
    Review,
    ReviewStatus,
    ServicePartner,
    User,
    UserRole,
    VariantOption,
)
from app.models.entities import utcnow
from app.seed import catalog_data, data
from app.services import catalog as catalog_service
from app.services.slugs import slugify


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
    return slugify(name, fallback="boot")


def seed_catalog(db: Session) -> dict[str, ModelVersion]:
    """Manufacturers, models, generations and factory options. Idempotent."""
    manufacturers: dict[str, Manufacturer] = {}
    for m in catalog_data.MANUFACTURERS:
        obj = db.query(Manufacturer).filter(Manufacturer.slug == m["slug"]).one_or_none()
        if obj is None:
            obj = Manufacturer(slug=m["slug"])
        obj.name, obj.country = m["name"], m["country"]
        db.add(obj)
        manufacturers[m["slug"]] = obj
    db.flush()

    versions: dict[str, ModelVersion] = {}
    for entry in catalog_data.MODELS:
        manufacturer = manufacturers[entry["manufacturer"]]
        model = (
            db.query(BoatModel)
            .filter(BoatModel.manufacturer_id == manufacturer.id, BoatModel.slug == entry["slug"])
            .one_or_none()
        )
        if model is None:
            model = BoatModel(manufacturer_id=manufacturer.id, slug=entry["slug"])
        model.name, model.designer = entry["name"], entry["designer"]
        db.add(model)
        db.flush()

        spec = entry["version"]
        version = (
            db.query(ModelVersion)
            .filter(ModelVersion.model_id == model.id, ModelVersion.name == spec["name"])
            .one_or_none()
        )
        if version is None:
            version = ModelVersion(
                model_id=model.id,
                name=spec["name"],
                length_m=spec["length_m"],
                year_from=spec.get("year_from") or 0,
            )
        for field, value in spec.items():
            # A researched None means "not established". Writing it keeps the gap visible,
            # which is the point: the portal shows it as unknown rather than implying a figure.
            if field == "year_from" and not value:
                continue
            setattr(version, field, value)
        version.source = entry.get("source", "")
        version.source_url = entry.get("source_url", "")
        version.verified_on = date.fromisoformat(entry["verified_on"]) if entry.get("verified_on") else None
        version.caveat = entry.get("notes", "")
        # Keine Fotos aus Fremdquellen: ein zufälliges Bild, das als Modellfoto
        # ausgewiesen wird, ist eine Falschaussage über das Schiff und hat
        # obendrein keine geklärten Bildrechte. Bis echte Werftbilder mit
        # geklärter Nutzung vorliegen, bleibt der Katalog bildlos; das Portal
        # zeichnet dann eine klar erkennbare Illustration.
        version.model_images = []
        db.add(version)
        db.flush()

        for variant in entry["variants"]:
            option = (
                db.query(VariantOption)
                .filter(
                    VariantOption.version_id == version.id,
                    VariantOption.code == variant["code"],
                    VariantOption.kind == variant["kind"],
                )
                .one_or_none()
            )
            if option is None:
                option = VariantOption(
                    version_id=version.id, kind=variant["kind"], code=variant["code"], name=variant["name"]
                )
            for field, value in variant.items():
                setattr(option, field, value)
            db.add(option)
        versions[f"{entry['manufacturer']}/{entry['slug']}"] = version
    db.flush()
    return versions


def _link_boat_to_catalog(db: Session, boat: Boat, versions: dict[str, ModelVersion]) -> None:
    """Point a demo boat at its catalog entry and take the technical data from there.

    This is the product's own promise applied to our demo fleet: the catalog supplies what it
    knows, the boat keeps only what is genuinely per boat. Figures the catalog has no value for
    (headroom and berth length are rarely published) stay as the provider's own statement and
    are recorded as such, so the boat page can tell the two apart.
    """
    link = catalog_data.BOAT_CATALOG_LINK.get(boat.slug)
    if link is None:
        return
    model_key, preferred_codes = link
    version = versions.get(model_key)
    if version is None:
        return

    # Preferred codes are a wish, not a requirement: the catalog is researched data that
    # changes, and a demo boat must not break when a variant is renamed.
    chosen: list[VariantOption] = []
    seen: set[str] = set()
    for code in preferred_codes:
        option = next((v for v in version.variants if v.code == code and v.kind not in seen), None)
        if option is not None:
            seen.add(option.kind)
            chosen.append(option)
    for option in version.variants:
        if option.is_default and option.kind not in seen:
            seen.add(option.kind)
            chosen.append(option)

    spec = catalog_service.resolve(version, chosen)
    owner_supplied = {
        field: getattr(boat, field)
        for field, value in spec.values.items()
        if value is None and getattr(boat, field, None) is not None
    }
    for field, value in spec.values.items():
        if value is not None:
            setattr(boat, field, value)

    boat.manufacturer = version.model.manufacturer.name
    boat.model = version.model.name
    boat.model_version_id = version.id
    boat.variant_ids = [v.id for v in chosen]
    boat.spec_overrides = owner_supplied
    boat.spec_sources = {**spec.sources, **{f: "owner" for f in owner_supplied}}
    boat.unknown_specs = [f for f in spec.unknown if f not in owner_supplied]
    boat.features = sorted({*(boat.features or []), *spec.features})
    boat.boat_class_id = _class_for_length_in_seed(db, boat.length_m)


def _class_for_length_in_seed(db: Session, length_m: float) -> str:
    row = (
        db.query(BoatClass)
        .filter(BoatClass.min_length_m <= length_m, BoatClass.max_length_m > length_m)
        .first()
    )
    if row is None:
        row = db.query(BoatClass).order_by(BoatClass.max_length_m.desc()).first()
    return row.id


def _seed_gallery(db: Session, boat: Boat) -> None:
    if any(i.origin == ImageOrigin.OWNER.value for i in boat.gallery):
        return
    db.add(
        BoatImage(
            boat_id=boat.id,
            url=f"/illustration/boot-{boat.slug}.svg",
            origin=ImageOrigin.OWNER.value,
            # Keine erfundene Bildunterschrift: die Demo zeigt eine Zeichnung,
            # und genau das steht auch darunter.
            caption="Illustration – für dieses Boot liegt noch kein Foto vor",
            credit="",
            sort_order=0,
        )
    )
    version = db.get(ModelVersion, boat.model_version_id) if boat.model_version_id else None
    for offset, url in enumerate(list(version.model_images or []) if version else []):
        db.add(
            BoatImage(
                boat_id=boat.id,
                url=url,
                origin=ImageOrigin.MODEL.value,
                caption="Modellfoto des Herstellers",
                credit="Hersteller",
                sort_order=1000 + offset,
            )
        )


def _seed_reviews(db: Session, boats_by_slug: dict[str, Boat]) -> None:
    """Reviews hang off a finished booking, so the demo creates that booking too."""
    if db.query(Review).first():
        return
    today = date.today()
    for index, entry in enumerate(catalog_data.DEMO_REVIEWS):
        boat = boats_by_slug.get(entry["boat"])
        if boat is None:
            continue
        month = today.replace(day=1) + timedelta(days=31 * entry["month_offset"])
        start = month.replace(day=8)
        end = start + timedelta(days=7)
        total = (boat.pricing.reference_price_cents if boat.pricing else 20000) * 7
        quote = Quote(
            boat_id=boat.id,
            start_date=start,
            end_date=end,
            persons=min(4, boat.max_persons or 4),
            total_cents=total,
            breakdown={},
            expires_at=utcnow(),
        )
        db.add(quote)
        db.flush()
        booking = Booking(
            reference=f"SB-DEMO{index:02d}",
            boat_id=boat.id,
            quote_id=quote.id,
            customer_email=f"demo{index}@example.com",
            customer_name=entry["author"],
            persons=min(4, boat.max_persons or 4),
            start_date=start,
            end_date=end,
            pickup_base_id=boat.base_id,
            dropoff_base_id=boat.base_id,
            status=BookingStatus.SETTLED.value,
            total_cents=total,
            deposit_cents=0,
            security_deposit_cents=boat.deposit_cents,
        )
        db.add(booking)
        db.flush()
        review = Review(
            booking_id=booking.id,
            boat_id=boat.id,
            charterer_id=boat.charterer_id,
            model_version_id=boat.model_version_id,
            author_name=entry["author"],
            charter_month=start.strftime("%Y-%m"),
            title=entry["title"],
            body=entry["body"],
            status=ReviewStatus.PUBLISHED.value,
            published_at=utcnow(),
            **entry["ratings"],
        )
        db.add(review)
        db.flush()
        db.add(
            BoatImage(
                boat_id=boat.id,
                url=f"/illustration/gast-{boat.slug}-{index}.svg",
                origin=ImageOrigin.GUEST.value,
                caption=entry["title"],
                credit=entry["author"],
                charter_month=start.strftime("%Y-%m"),
                booking_id=booking.id,
                review_id=review.id,
                sort_order=100 + index,
            )
        )
    db.flush()


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

    versions = seed_catalog(db)

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
        # Das Titelbild kommt aus der Galerie; die Demo hinterlegt dort eine
        # gezeichnete Szene statt eines fremden Fotos.
        obj.images = [f"/illustration/boot-{slug}.svg"]
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
        _link_boat_to_catalog(db, obj, versions)
        _seed_gallery(db, obj)
        boats.append(obj)
    db.flush()
    if with_demo_bookings:
        # Demo reviews hang off demo bookings, so they belong to the same switch.
        _seed_reviews(db, {b.slug: b for b in boats})

    # Service partners
    for pdata in data.PARTNERS:
        user = db.query(User).filter(User.email == pdata["email"]).one_or_none()
        if user is None:
            user = User(
                email=pdata["email"],
                password_hash=hash_password(pdata["password"]),
                full_name=pdata["name"],
                role=UserRole.PARTNER.value,
            )
            db.add(user)
            db.flush()
        partner = db.query(ServicePartner).filter(ServicePartner.user_id == user.id).one_or_none()
        if partner is None:
            partner = ServicePartner(user_id=user.id, name=pdata["name"])
        partner.phone = pdata["phone"]
        partner.base_ids = [bases[n].id for n in pdata["bases"] if n in bases]
        partner.services = pdata["services"]
        partner.prices = pdata["prices"]
        partner.rating = 4.8
        db.add(partner)
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
    return {
        "regions": len(regions),
        "bases": len(bases),
        "boats": len(boats),
        "models": len(versions),
        "reviews": db.query(Review).count(),
    }


def main() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        print(seed(db))


if __name__ == "__main__":
    main()
