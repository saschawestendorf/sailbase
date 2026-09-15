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
    DamageCase,
    ImageOrigin,
    Manufacturer,
    ModelVersion,
    Payment,
    PaymentPurpose,
    PaymentStatus,
    PricingPolicy,
    Quote,
    Region,
    Review,
    ReviewStatus,
    ServiceOrderStatus,
    ServiceOrderType,
    ServicePartner,
    User,
    UserRole,
    VariantOption,
)
from app.models.entities import utcnow
from app.seed import catalog_data, data, demo
from app.services import catalog as catalog_service
from app.services import operations as operations_service
from app.services import quotes as quote_service
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


def _link_boat_to_catalog(
    db: Session,
    boat: Boat,
    versions: dict[str, ModelVersion],
    link: tuple[str, list[str]] | None = None,
) -> None:
    """Point a demo boat at its catalog entry and take the technical data from there.

    This is the product's own promise applied to our demo fleet: the catalog supplies what it
    knows, the boat keeps only what is genuinely per boat. Figures the catalog has no value for
    (headroom and berth length are rarely published) stay as the provider's own statement and
    are recorded as such, so the boat page can tell the two apart.
    """
    # Ohne ausdrückliche Angabe gilt die Zuordnung der zehn Musterboote; die
    # erweiterte Flotte reicht ihren Katalogschlüssel direkt herein.
    link = link or catalog_data.BOAT_CATALOG_LINK.get(boat.slug)
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


def _guest_email(author: str, index: int) -> str:
    for name, email, _persons in data.DEMO_GUESTS:
        if name == author:
            return email
    for entry in demo.EXTRA_CUSTOMERS:
        if entry["full_name"] == author:
            return entry["email"]
    return f"demo{index}@example.com"


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
            # An ein echtes Gastkonto gehängt, wo es eines gibt: eine verifizierte
            # Bewertung ohne auffindbaren Verfasser ist im Zweifel wertlos.
            customer_email=_guest_email(entry["author"], index),
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


def _partner_for(db: Session, boat: Boat) -> ServicePartner | None:
    """Der Servicepartner, der den Heimathafen des Boots bedient."""
    for partner in db.query(ServicePartner).all():
        if boat.base_id in (partner.base_ids or []):
            return partner
    return None


def _demo_price(
    db: Session, boat: Boat, start: date, nights: int, booked_days_before: int = 45
) -> tuple[int, dict]:
    """Preis für einen Demo-Zeitraum.

    Über die echte Preisregel, damit die Demo dieselben Zahlen zeigt wie eine
    reale Anfrage. Der Buchungszeitpunkt gehört dazu: der Vorlauf geht in den
    Preis ein, und eine Historie, in der jede Buchung am Anreisetag entstanden
    wäre, zeigt lauter Last-Minute-Preise statt eines normalen Jahres.

    Für Zeiträume, die der Algorithmus gar nicht anbietet, wird auf Referenzpreis
    mal Nächte zurückgefallen, statt den Fall zu überspringen: die Historie soll
    vollständig sein, auch wenn heute niemand mehr so buchen könnte.
    """
    end = start + timedelta(days=nights)
    try:
        result, _occupancy = quote_service.compute_price(
            db, boat, start, end, today=start - timedelta(days=booked_days_before)
        )
        return result.total_cents, result.to_dict()
    except Exception:  # noqa: BLE001 - jede Absage führt zum selben Ersatzwert
        reference = boat.pricing.reference_price_cents if boat.pricing else 20000
        total = reference * nights + boat.cleaning_fee_cents
        return total, {"note": "Ersatzwert: dieser Zeitraum wird heute nicht angeboten"}


def _demo_booking(
    db: Session,
    boat: Boat,
    *,
    reference: str,
    status: str,
    start: date,
    nights: int,
    guest: tuple[str, str, int],
    booked_days_before: int = 45,
    block: bool = True,
) -> Booking | None:
    """Legt Angebot, Buchung und Kalendersperre an – oder nichts, wenn belegt."""
    end = start + timedelta(days=nights)
    if not availability_free(db, boat.id, start, end):
        return None
    # Die Regeln des Boots gelten auch für Demo-Daten: ein Bestand, der die
    # eigenen Wechseltage verletzt, führt beim Ansehen in die Irre.
    if boat.changeover_weekdays and start.weekday() not in boat.changeover_weekdays:
        return None
    if boat.allowed_nights and nights not in boat.allowed_nights:
        return None
    name, email, persons = guest
    persons = min(persons, boat.max_persons or persons)
    total, breakdown = _demo_price(db, boat, start, nights, booked_days_before)
    quote = Quote(
        boat_id=boat.id,
        start_date=start,
        end_date=end,
        persons=persons,
        total_cents=total,
        breakdown=breakdown,
        expires_at=utcnow(),
    )
    db.add(quote)
    db.flush()

    deposit = round(total * 0.3)
    booking = Booking(
        reference=reference,
        boat_id=boat.id,
        quote_id=quote.id,
        customer_email=email,
        customer_name=name,
        persons=persons,
        start_date=start,
        end_date=end,
        pickup_base_id=boat.base_id,
        dropoff_base_id=boat.base_id,
        status=status,
        total_cents=total,
        deposit_cents=deposit,
        security_deposit_cents=boat.deposit_cents,
        price_breakdown=breakdown,
        static_price_cents=quote_service.static_price_cents(boat, start, end),
    )
    if status == BookingStatus.PENDING_PAYMENT.value:
        # Die Frist gehört an die Buchung, bevor die Sperre sie übernimmt – sonst
        # steht im Kalender eine Reservierung, die nie abläuft.
        booking.hold_expires_at = utcnow() + timedelta(minutes=45)
    db.add(booking)
    db.flush()

    if block:
        pending = status == BookingStatus.PENDING_PAYMENT.value
        db.add(
            AvailabilityBlock(
                boat_id=boat.id,
                start_date=start,
                end_date=end,
                # Eine unbezahlte Buchung hält den Zeitraum nur vorläufig.
                block_type=BlockType.HOLD.value if pending else BlockType.BOOKING.value,
                booking_id=booking.id,
                expires_at=booking.hold_expires_at if pending else None,
                note=f"{'Hold' if pending else 'Buchung'} {reference}",
                start_base_id=boat.base_id,
                end_base_id=boat.base_id,
            )
        )

    _demo_payments(db, booking, status)
    # Beim Bestätigen legt das System die drei Standardaufträge an. Ohne sie wäre
    # die Abwicklungsseite in der Demo leer und der Ablauf nicht nachvollziehbar.
    _demo_service_orders(db, booking, _partner_for(db, boat))
    db.flush()
    return booking


def _demo_payments(db: Session, booking: Booking, status: str) -> None:
    """Anzahlung und Restzahlung passend zum Stand der Buchung."""
    if status == BookingStatus.PENDING_PAYMENT.value:
        db.add(
            Payment(
                booking_id=booking.id,
                provider="fake",
                purpose=PaymentPurpose.DEPOSIT.value,
                amount_cents=booking.deposit_cents,
                status=PaymentStatus.PENDING.value,
                due_at=date.today(),
            )
        )
        return
    db.add(
        Payment(
            booking_id=booking.id,
            provider="fake",
            purpose=PaymentPurpose.DEPOSIT.value,
            amount_cents=booking.deposit_cents,
            status=PaymentStatus.SUCCEEDED.value,
        )
    )
    balance = booking.total_cents - booking.deposit_cents
    if balance <= 0:
        return
    # Die Restzahlung wird 30 Tage vor Törnbeginn fällig.
    due = booking.start_date - timedelta(days=30)
    db.add(
        Payment(
            booking_id=booking.id,
            provider="fake",
            purpose=PaymentPurpose.BALANCE.value,
            amount_cents=balance,
            status=(
                PaymentStatus.SUCCEEDED.value
                if due <= date.today()
                else PaymentStatus.PENDING.value
            ),
            due_at=due,
        )
    )


_ORDER_PROGRESS = {
    # Buchungsstand -> welche Aufträge erledigt sind
    BookingStatus.CONFIRMED.value: (),
    BookingStatus.READY.value: (ServiceOrderType.READINESS.value,),
    BookingStatus.HANDED_OVER.value: (
        ServiceOrderType.READINESS.value,
        ServiceOrderType.HANDOVER.value,
    ),
    BookingStatus.RETURNED.value: (
        ServiceOrderType.READINESS.value,
        ServiceOrderType.HANDOVER.value,
        ServiceOrderType.RETURN.value,
    ),
    BookingStatus.SETTLED.value: (
        ServiceOrderType.READINESS.value,
        ServiceOrderType.HANDOVER.value,
        ServiceOrderType.RETURN.value,
    ),
}


def _demo_service_orders(db: Session, booking: Booking, partner: ServicePartner | None) -> None:
    """Serviceaufträge im Stand, der zum Buchungsstatus passt.

    Ohne das bleibt die Abwicklungsseite leer und man sieht nicht, wofür sie da
    ist: Checklisten, Fotopflicht, Freigabe.
    """
    done_types = _ORDER_PROGRESS.get(booking.status)
    if done_types is None:
        return
    orders = operations_service.create_standard_orders(db, booking)
    for order in orders:
        if partner is not None and order.order_type in (partner.services or []):
            order.partner_id = partner.id
            order.price_cents = int((partner.prices or {}).get(order.order_type, 0))
            order.status = ServiceOrderStatus.ASSIGNED.value
        if order.order_type in done_types:
            order.checklist = [
                {
                    **item,
                    "done": True,
                    # Fotopflichtige Punkte brauchen ein Bild, sonst gilt der
                    # Auftrag als unvollständig und die Freigabe griffe nicht.
                    "photos": ["/illustration/beleg.svg"] if item.get("photo_required") else [],
                }
                for item in (order.checklist or [])
            ]
            order.status = ServiceOrderStatus.DONE.value
            order.completed_at = utcnow()
    db.flush()


def _seed_demo_operations(db: Session, boats_by_slug: dict[str, Boat]) -> None:
    """Ein Betrieb, durch den man klicken kann: jede Phase einmal, dazu Historie."""
    if db.query(Booking).filter(Booking.reference.like("SB-OPS%")).first():
        return
    today = date.today()

    for index, (slug, status, offset, nights, guest_index, note) in enumerate(data.DEMO_LIFECYCLE):
        boat = boats_by_slug.get(slug)
        if boat is None:
            continue
        booking = _demo_booking(
            db,
            boat,
            reference=f"SB-OPS{index:02d}",
            status=status,
            start=today + timedelta(days=offset),
            nights=nights,
            guest=data.DEMO_GUESTS[guest_index % len(data.DEMO_GUESTS)],
        )
        if booking is None:
            continue
        booking.notes = note
        if status == BookingStatus.RETURNED.value:
            db.add(
                DamageCase(
                    booking_id=booking.id,
                    title=data.DEMO_DAMAGE["title"],
                    description=data.DEMO_DAMAGE["description"],
                    estimated_cents=data.DEMO_DAMAGE["estimated_cents"],
                    withheld_cents=data.DEMO_DAMAGE["withheld_cents"],
                    status="open",
                )
            )
    db.flush()



def _seed_demo_season(db: Session, boats: list[Boat]) -> None:
    """Winterlager, Historie und Vorausbuchungen.

    Die vergangenen Buchungen tragen Umsatz und Auslastung im Dashboard, die
    kommenden geben der Nachfragestufe im Preis etwas zu rechnen. Beides sind
    echte Buchungen und keine bloßen Kalendersperren – sonst zeigt die
    Vercharterer-Ansicht Zahlen, die es im System gar nicht gibt.
    """
    if db.query(Booking).filter(Booking.reference.like("SB-S%")).first():
        return
    rng = random.Random(42)
    today = date.today()
    season_year = today.year + 1 if today.month >= 4 else today.year
    counter = 0

    for boat in boats:
        for winter in (season_year - 2, season_year - 1, season_year):
            db.add(
                AvailabilityBlock(
                    boat_id=boat.id,
                    start_date=date(winter, 11, 1),
                    end_date=date(winter + 1, 4, 1),
                    block_type=BlockType.CLOSED.value,
                    note="Winterlager",
                )
            )
        db.flush()

        # Rückblick: abgerechnet. Ausblick: bestätigt, verteilt über die nächsten
        # zwölf Monate statt erst ab der nächsten Saison – sonst steht der
        # Kalender genau in dem Zeitraum leer, den das Dashboard zeigt.
        plan = [
            (date(season_year - 1, 4, 1), 210, BookingStatus.SETTLED.value, rng.randint(4, 7)),
            (today + timedelta(days=1), 330, BookingStatus.CONFIRMED.value, rng.randint(6, 10)),
        ]
        for window_start, window_days, status, count in plan:
            placed = 0
            # Mit Versuchen statt mit einem Wurf: ein Termin im Winterlager oder
            # auf einer belegten Woche wird abgelehnt, und ohne Wiederholung
            # bliebe der Kalender genau dort leer, wo die Demo voll sein soll.
            for _ in range(count * 12):
                if placed >= count:
                    break
                # Leicht nach vorne gewichtet, aber über das ganze Fenster
                # verteilt: liegt der Schwerpunkt zu nah, drängen die Wiederholungen
                # alles in die wenigen verbleibenden Saisonwochen und die Suche
                # findet dort gar nichts mehr.
                offset = int(rng.triangular(0, window_days, window_days * 0.45))
                nights = rng.choice([3, 4, 5, 7, 7, 7, 10, 14])
                start = window_start + timedelta(days=offset)
                if start <= today and status == BookingStatus.CONFIRMED.value:
                    continue
                if start > today and status == BookingStatus.SETTLED.value:
                    continue
                counter += 1
                created = _demo_booking(
                    db,
                    boat,
                    reference=f"SB-S{counter:03d}",
                    status=status,
                    start=start,
                    nights=nights,
                    guest=data.DEMO_GUESTS[counter % len(data.DEMO_GUESTS)],
                    booked_days_before=rng.choice([14, 30, 45, 60, 90, 120]),
                )
                if created is not None:
                    placed += 1
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

    # Betrieb statt leerer Datenbank: erst der Ablauf-Schaufenster mit je einem
    # Vorgang pro Phase, dann Historie und Vorausbuchungen fürs Mengengerüst.
    if with_demo_bookings:
        # Erst die Flotte auf eine Größe bringen, in der sich Suche, Vergleich und
        # One-Way überhaupt zeigen lassen – danach wird gebucht.
        boats += demo.expand_fleet(
            db,
            charterers=charterers,
            bases=bases,
            boat_class_for=class_for,
            link_to_catalog=lambda db_, boat, key: _link_boat_to_catalog(
                db_, boat, versions, link=(key, [])
            ),
            seed_gallery=_seed_gallery,
        )
        # Die Preisregeln wurden in dieser Sitzung gerade erst angelegt; ohne das
        # Verfallen der Beziehungen sieht boat.pricing noch None und die Demo
        # bekäme Ersatzpreise statt der Zahlen des Algorithmus.
        db.expire_all()
        boats = [db.get(Boat, b.id) for b in boats]
        demo.fill_boat_details_before_booking(db, boats)
        _seed_demo_operations(db, {b.slug: b for b in boats})
        _seed_demo_season(db, boats)
        db.expire_all()
        boats = [db.get(Boat, b.id) for b in boats]
        demo.fill_everything(db, boats)
    db.commit()
    return {
        "regions": len(regions),
        "bases": len(bases),
        "boats": len(boats),
        "models": len(versions),
        "reviews": db.query(Review).count(),
        "bookings": db.query(Booking).count(),
    }


def main() -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        print(seed(db))


if __name__ == "__main__":
    main()
