"""Demo-Bestand: die Tabellen, die der Kernseed offen lässt.

Der Kernseed in `seed.py` legt Reviere, Häfen, Katalog, zehn Beispielboote und den
Buchungsbetrieb an. Damit läuft das Portal, aber vieles bleibt unbenutzbar: One-Way
ist auf keinem Boot eingeschaltet, kein Vertrag ist gerendert, keine Crewliste
eingereicht, keine Auszahlung gerechnet, kein Übergabefoto vorhanden. Wer das
Produkt ansehen will, sieht dann leere Karten und kann nicht beurteilen, ob eine
Funktion fehlt oder nur die Daten.

Dieses Modul füllt genau diese Lücken – und zwar in der Reihenfolge, in der das
System sie im Betrieb selbst füllen würde, damit der Bestand konsistent bleibt
und nicht bloß „irgendwo steht etwas drin".

Alles ist deterministisch (fester Zufallsstartwert) und idempotent: ein zweiter
Lauf ändert nichts.
"""

from __future__ import annotations

import random
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.core.security import hash_password
from app.models import (
    AvailabilityBlock,
    Base_,
    BlockType,
    Boat,
    BoatImage,
    Booking,
    BookingStatus,
    Charterer,
    DamageCase,
    ImageOrigin,
    Payment,
    PaymentStatus,
    Payout,
    PricingPolicy,
    Quote,
    Review,
    ServiceOrder,
    ServiceOrderStatus,
    ServiceOrderType,
    ServicePartner,
    User,
    UserRole,
)
from app.models.entities import utcnow
from app.seed import data
from app.services import contracts
from app.services.slugs import slugify

RNG_SEED = 1907

# Die Boote, auf denen das Ablauf-Schaufenster liegt (siehe data.DEMO_LIFECYCLE).
_SHOWCASE_SLUGS = {entry[0] for entry in data.DEMO_LIFECYCLE}

# Der Plattformanteil am Charterpreis. Als Konstante und nicht als Zauberzahl im
# Code, weil er in Auszahlung, Buchung und Dashboard dieselbe Größe sein muss.
COMMISSION_PERCENT = 15


# --------------------------------------------------------------------- Personen

EXTRA_CUSTOMERS = [
    {
        "email": "brandt@example.com",
        "full_name": "Familie Brandt",
        "license_level": 2,
        "experience_nm": 450,
        "height_cm": 190,
    },
    {
        "email": "petersen@example.com",
        "full_name": "Jan Petersen",
        "license_level": 3,
        "experience_nm": 2400,
        "height_cm": 178,
    },
    {
        "email": "seeschwalbe@example.com",
        "full_name": "Crew Seeschwalbe",
        "license_level": 3,
        "experience_nm": 1200,
        "height_cm": 185,
    },
    {
        "email": "koll@example.com",
        "full_name": "Miriam Koll",
        "license_level": 2,
        "experience_nm": 300,
        "height_cm": 165,
    },
    {
        "email": "toernschule@example.com",
        "full_name": "Törnschule Nord",
        "license_level": 4,
        "experience_nm": 8000,
        "height_cm": 182,
    },
    {
        "email": "hansen@example.com",
        "full_name": "Ole Hansen",
        "license_level": 1,
        "experience_nm": 80,
        "height_cm": 196,
    },
    {
        "email": "backbord@example.com",
        "full_name": "Team Backbord",
        "license_level": 3,
        "experience_nm": 1800,
        "height_cm": 187,
    },
    {
        "email": "vos@example.com",
        "full_name": "Sanne Vos",
        "license_level": 2,
        "experience_nm": 620,
        "height_cm": 172,
    },
    # Die beiden schreiben die übrigen Demo-Bewertungen.
    {
        "email": "kock@example.com",
        "full_name": "Miriam Kock",
        "license_level": 2,
        "experience_nm": 540,
        "height_cm": 168,
    },
    {
        "email": "segelclub-travemuende@example.com",
        "full_name": "Segelclub Travemünde",
        "license_level": 4,
        "experience_nm": 15000,
        "height_cm": 184,
    },
]

CHARTERER_PROFILE = {
    "ostsee-yachting": {
        "phone": "+49 4362 900110",
        "description": (
            "Familienbetrieb in Heiligenhafen, seit 1998 im Chartergeschäft. Vier eigene "
            "Yachten, Übergabe durch den Eigner oder den Hafenpartner."
        ),
    },
    "foerde-charter": {
        "phone": "+49 431 220455",
        "description": (
            "Charterbasis an der Kieler Förde mit Schwerpunkt auf Ausbildungstörns. "
            "Jede Yacht wird vor der Saison von einem Sachverständigen abgenommen."
        ),
    },
    "bodden-segler": {
        "phone": "+49 3831 660270",
        "description": (
            "Stralsunder Anbieter für die Bodden- und Rügenreviere. Flachgehende Boote, "
            "Übergabe mit Revierbriefing für Ortsfremde."
        ),
    },
}


# ------------------------------------------------------------------- Zusatzboote
# Aus dem Katalog gebaut, damit jeder Hafen mehrere Boote hat und Suche, Vergleich
# und One-Way überhaupt etwas zu vergleichen haben. Der Katalogschlüssel bestimmt
# alle technischen Daten; hier stehen nur Dinge, die dem einzelnen Schiff gehören.
EXTRA_BOATS = [
    ("Seeschwalbe", "ostsee-yachting", "Marina Heiligenhafen", "bavaria/cruiser-41", 2021, 3),
    ("Bernstein", "ostsee-yachting", "Marina Heiligenhafen", "hanse/388", 2020, 3),
    ("Nordlicht", "ostsee-yachting", "Marina Heiligenhafen", "dufour/430-grand-large", 2022, 4),
    ("Kormoran", "foerde-charter", "Marina Kiel-Schilksee", "jeanneau/sun-odyssey-380", 2022, 3),
    ("Leuchtfeuer", "foerde-charter", "Marina Kiel-Schilksee", "bavaria/cruiser-46", 2019, 4),
    ("Blaue Stunde", "foerde-charter", "Sonwik Marina", "hanse/458", 2021, 4),
    ("Ostwind", "foerde-charter", "Sonwik Marina", "elan/impression-40-1", 2020, 3),
    ("Salzwasser", "foerde-charter", "Sonwik Marina", "dehler/34", 2018, 2),
    ("Silbermöwe", "bodden-segler", "Citymarina Stralsund", "beneteau/oceanis-34-1", 2021, 2),
    ("Kranich", "bodden-segler", "Citymarina Stralsund", "jeanneau/sun-odyssey-349", 2019, 3),
    ("Störtebeker", "bodden-segler", "Marina Breege", "bavaria/cruiser-34", 2020, 2),
    ("Landfall", "bodden-segler", "Marina Breege", "salona/380", 2018, 3),
    ("Aurora", "bodden-segler", "Hohe Düne", "delphia/40-3", 2021, 3),
    ("Sandbank", "bodden-segler", "Hohe Düne", "beneteau/oceanis-38-1", 2020, 3),
]

EXTRA_DESCRIPTIONS = [
    "Gepflegte Yacht aus dem laufenden Chartereinsatz, jährlich gewartet und komplett ausgerüstet.",
    "Leicht zu segeln, übersichtliches Cockpit, gut für Crews mit unterschiedlicher Erfahrung.",
    "Viel Stauraum und ein Salon, in dem auch bei Regen alle sitzen können.",
    "Schnelles Schiff für Crews, die mehr wollen als von Hafen zu Hafen motoren.",
    "Robuster Fahrtensegler mit Ausrüstung für längere Schläge in der offenen Ostsee.",
]

EXTRA_FEATURE_SETS = [
    ["autopilot", "plotter", "sprayhood", "bimini", "heating"],
    ["bowthruster", "autopilot", "plotter", "sprayhood", "dinghy"],
    ["autopilot", "plotter", "furling_main", "sprayhood", "bimini", "heating", "wifi"],
    ["bowthruster", "plotter", "sprayhood", "solar"],
]

EXTRA_CHARACTERS = [
    ["good_natured", "comfort"],
    ["sporty"],
    ["comfort", "bluewater"],
    ["good_natured"],
    ["sporty", "bluewater"],
]


# ----------------------------------------------------------- boot-eigene Angaben
# Revierbeschränkung, Versicherung und Papiere sind keine Katalogdaten: sie hängen
# am einzelnen Schiff und am Vertrag des Eigners.
BOAT_DETAILS = {
    "hiddensee": {
        "region_restrictions": "Nur Bodden- und Küstengewässer bis Rügen, keine Nachtfahrten offshore.",
    },
    "boddenlaeufer": {
        "region_restrictions": (
            "Boddengewässer und Greifswalder Bodden; Fahrt nach Bornholm nur nach Absprache."
        ),
    },
    "jomsborg": {
        "region_restrictions": "Ostsee ohne Einschränkung, Kattegat nach Absprache.",
    },
    "kap-arkona": {
        "region_restrictions": "Kein Auflaufen von Sandbänken – Tiefgang 2,10 m beachten.",
    },
}

INSURERS = [
    ("Pantaenius Yacht", "PY-{n:06d}"),
    ("Schomacker Versicherungen", "SV-{n:06d}"),
    ("Gothaer Yacht", "GY-{n:06d}"),
]


def _season_year(today: date) -> int:
    return today.year + 1 if today.month >= 11 else today.year


# =============================================================== Flotte erweitern


def expand_fleet(
    db: Session,
    *,
    charterers: dict[str, Charterer],
    bases: dict[str, Base_],
    boat_class_for,
    link_to_catalog,
    seed_gallery,
) -> list[Boat]:
    """Baut die Zusatzboote aus dem Katalog.

    Die technischen Daten kommen aus dem Bootskatalog, genau wie beim Einstellen
    über den Assistenten. Damit zeigt die Demo auch, dass die Katalogstrecke
    funktioniert, statt zehn von Hand getippte Schiffe zu zeigen.
    """
    created: list[Boat] = []
    rng = random.Random(RNG_SEED)
    for index, (name, charterer_key, base_name, catalog_key, year, min_days) in enumerate(
        EXTRA_BOATS
    ):
        charterer = charterers.get(charterer_key)
        base = bases.get(base_name)
        if charterer is None or base is None:
            continue
        existing = db.query(Boat).filter(Boat.name == name).one_or_none()
        if existing is not None:
            created.append(existing)
            continue

        boat = Boat(
            name=name,
            slug=slugify(name, fallback="boot"),
            charterer_id=charterer.id,
            base_id=base.id,
            year_built=year,
            min_days=min_days,
            max_days=21,
            description=EXTRA_DESCRIPTIONS[index % len(EXTRA_DESCRIPTIONS)],
            character=EXTRA_CHARACTERS[index % len(EXTRA_CHARACTERS)],
            features=EXTRA_FEATURE_SETS[index % len(EXTRA_FEATURE_SETS)],
            required_license=2 if index % 4 else 3,
            required_experience_nm=0 if index % 3 else 300,
            cleaning_fee_cents=rng.choice([12000, 15000, 18000, 21000]),
            # Platzhalterwerte: gleich darauf überschreibt der Katalog die Technik.
            manufacturer="",
            model="",
            length_m=10.0,
            cabins=2,
            berths=4,
            max_persons=4,
            heads=1,
            boat_class_id=boat_class_for(10.0).id,
        )
        db.add(boat)
        db.flush()
        link_to_catalog(db, boat, catalog_key)
        # Kaution und Preisrahmen hängen an der Größe, die erst der Katalog kennt.
        boat.deposit_cents = int(round(boat.length_m * 20000, -4))
        reference = int(round(boat.length_m * 26, -1)) * 100
        db.add(
            PricingPolicy(
                boat_id=boat.id,
                mode="corridor",
                reference_price_cents=reference,
                floor_price_cents=int(reference * 0.58),
                ceiling_price_cents=int(reference * 1.45),
            )
        )
        seed_gallery(db, boat)
        created.append(boat)
    db.flush()
    return created


# ============================================================ Stammdaten füllen


def enrich_users(db: Session) -> None:
    """Gäste mit Schein, Meilen und Körpergröße.

    Ohne diese drei Angaben lässt sich die Crew-Passung nicht ausprobieren: die
    Suche filtert auf Qualifikation und rechnet Stehhöhe und Kojenlänge gegen die
    größte Person.
    """
    for entry in EXTRA_CUSTOMERS:
        user = db.query(User).filter(User.email == entry["email"]).one_or_none()
        if user is None:
            user = User(
                email=entry["email"],
                password_hash=hash_password("segeln123"),
                role=UserRole.CUSTOMER.value,
            )
            db.add(user)
        user.full_name = entry["full_name"]
        user.license_level = entry["license_level"]
        user.experience_nm = entry["experience_nm"]
        user.height_cm = entry["height_cm"]
    db.flush()


def enrich_charterers(db: Session) -> None:
    for charterer in db.query(Charterer).all():
        profile = CHARTERER_PROFILE.get(charterer.slug)
        if not profile:
            continue
        charterer.phone = charterer.phone or profile["phone"]
        charterer.description = charterer.description or profile["description"]
    db.flush()


def enrich_boats(db: Session, boats: list[Boat]) -> None:
    """Papiere, Versicherung, Wechseltage, One-Way.

    One-Way ist das Alleinstellungsmerkmal und war auf keinem Boot eingeschaltet –
    die Funktion war damit im Portal unsichtbar. Sie wird jetzt dort aktiviert, wo
    sie plausibel ist: bei Booten in Revieren mit mehreren Häfen.
    """
    rng = random.Random(RNG_SEED + 1)
    season = _season_year(date.today())
    for index, boat in enumerate(boats):
        detail = BOAT_DETAILS.get(boat.slug, {})
        if detail.get("region_restrictions"):
            boat.region_restrictions = boat.region_restrictions or detail["region_restrictions"]

        if not boat.year_refit and boat.year_built and index % 3 == 0:
            boat.year_refit = min(season - 1, boat.year_built + rng.choice([4, 5, 6]))

        # Größere Yachten brauchen einen Tag zwischen zwei Crews, kleine nicht.
        if not boat.turnaround_days and boat.length_m >= 12:
            boat.turnaround_days = 1

        # Ein Teil der Flotte bleibt bewusst auf festen Wechseltagen: nur so lässt
        # sich im Portal sehen, wie die flexible Logik daneben aussieht. Die Boote
        # des Ablauf-Schaufensters bleiben frei – auf ihnen liegen Buchungen mit
        # festen Terminen, und eine Regel, die diese Termine verbietet, würde das
        # Schaufenster still leeren.
        if boat.slug not in _SHOWCASE_SLUGS:
            if index % 5 == 0 and not boat.changeover_weekdays:
                boat.changeover_weekdays = [5]  # Samstag
            elif index % 5 == 1 and not boat.allowed_nights:
                boat.allowed_nights = [3, 4, 7, 10, 14]

        # One-Way innerhalb des eigenen Reviers, sobald es dort mehr als einen
        # Hafen gibt. Die Gebühr deckt die Rückführung grob ab.
        if not boat.one_way_enabled and boat.base and boat.base.region_id:
            siblings = (
                db.query(Base_)
                .filter(Base_.region_id == boat.base.region_id, Base_.id != boat.base_id)
                .all()
            )
            if siblings and index % 3 != 2:
                boat.one_way_enabled = True
                boat.one_way_base_ids = [b.id for b in siblings]
                boat.one_way_fee_cents = int(round(boat.length_m * 1800, -3))

        if not boat.insurance:
            insurer, pattern = INSURERS[index % len(INSURERS)]
            boat.insurance = {
                "insurer": insurer,
                "policy_no": pattern.format(n=100000 + index * 137),
                "valid_until": date(season + 1, 3, 31).isoformat(),
            }
        if not boat.documents:
            boat.documents = [
                {
                    "type": "insurance",
                    "name": "Haftpflicht- und Kaskopolice",
                    "url": f"/dokumente/{boat.slug}-police.pdf",
                    "valid_until": date(season + 1, 3, 31).isoformat(),
                },
                {
                    "type": "certificate",
                    "name": "Sicherheitsabnahme Saison " + str(season),
                    "url": f"/dokumente/{boat.slug}-abnahme.pdf",
                    "valid_until": date(season, 12, 31).isoformat(),
                },
                {
                    "type": "manual",
                    "name": "Bordhandbuch und Revierinformation",
                    "url": f"/dokumente/{boat.slug}-handbuch.pdf",
                },
            ]
    db.flush()


def enrich_pricing(db: Session, boats: list[Boat]) -> None:
    """Zielpreis, Restlückengrenze, Strategie und Übersteuerungen.

    Drei verschiedene Strategien in der Flotte, damit der Unterschied auf der
    Preisseite nicht nur behauptet, sondern vorgeführt wird.
    """
    strategies = ["balanced", "aggressive", "conservative"]
    for index, boat in enumerate(boats):
        policy = boat.pricing
        if policy is None:
            continue
        policy.strategy = strategies[index % len(strategies)]
        if policy.target_price_cents is None:
            # Zielpreis zwischen Referenz und Untergrenze: das ist der Schnitt, den
            # der Eigner über die Saison erreichen will, nicht der Listenpreis.
            policy.target_price_cents = int(
                policy.floor_price_cents
                + (policy.reference_price_cents - policy.floor_price_cents) * 0.55
            )
        if policy.max_dead_gap_days is None and index % 4 == 0:
            policy.max_dead_gap_days = max(2, boat.min_days - 1)
        if not policy.overrides and index % 6 == 0:
            # Beispiel für eine boot-eigene Abweichung von den Motorparametern.
            policy.overrides = {"weekend_uplift": 0.12}
    db.flush()


# ================================================================ Betrieb füllen


def enrich_bookings(db: Session) -> None:
    """Vertrag, Crewliste, Unterlagen, Provision, Fälligkeiten, Bestätigungen."""
    rng = random.Random(RNG_SEED + 2)
    users_by_email = {u.email: u for u in db.query(User).all()}
    today = date.today()

    for booking in db.query(Booking).all():
        boat = db.get(Boat, booking.boat_id)
        if boat is None:
            continue
        charterer = db.get(Charterer, boat.charterer_id)

        # Der Gast ist ein echtes Konto, wo es eines gibt – sonst bleibt die
        # Buchung eine Gastbuchung, was ausdrücklich erlaubt ist.
        if booking.customer_user_id is None:
            user = users_by_email.get(booking.customer_email)
            if user is not None:
                booking.customer_user_id = user.id

        if not booking.commission_cents and booking.status in BookingStatus.active():
            booking.commission_cents = round(booking.total_cents * COMMISSION_PERCENT / 100)

        if booking.balance_due_at is None:
            booking.balance_due_at = booking.start_date - timedelta(days=30)

        if booking.status == BookingStatus.PENDING_PAYMENT.value and booking.hold_expires_at is None:
            booking.hold_expires_at = utcnow() + timedelta(minutes=45)

        if booking.status not in BookingStatus.active():
            continue

        # Vertrag: wird beim Bestätigen erzeugt, also hat ihn jede bestätigte
        # Buchung. Ohne ihn ist die Vertragskarte auf der Abwicklungsseite leer.
        if not booking.contract and charterer is not None:
            booking.contract = contracts.render(booking, boat, charterer)
            accepted = utcnow() - timedelta(days=max(1, (booking.start_date - today).days // 2))
            booking.contract_accepted_customer_at = accepted
            booking.contract_accepted_charterer_at = accepted + timedelta(hours=3)

        if not booking.documents:
            booking.documents = [
                {
                    "type": "confirmation",
                    "name": f"Buchungsbestätigung {booking.reference}",
                    "url": f"/dokumente/{booking.reference.lower()}-bestaetigung.pdf",
                },
                {
                    "type": "invoice",
                    "name": f"Rechnung Anzahlung {booking.reference}",
                    "url": f"/dokumente/{booking.reference.lower()}-anzahlung.pdf",
                },
            ]

        # Crewliste erst, wenn der Törn nah ist – vorher hat sie im echten Betrieb
        # auch noch niemand eingereicht.
        near = (booking.start_date - today).days <= 21
        if not booking.crew_list and near:
            booking.crew_list = _crew_list(booking, rng)

        if booking.status in (
            BookingStatus.HANDED_OVER.value,
            BookingStatus.RETURNED.value,
            BookingStatus.SETTLED.value,
        ):
            if booking.handover_confirmed_customer_at is None:
                booking.handover_confirmed_customer_at = utcnow() - timedelta(
                    days=max(0, (today - booking.start_date).days)
                )
        if booking.status in (BookingStatus.RETURNED.value, BookingStatus.SETTLED.value):
            if booking.return_confirmed_customer_at is None:
                booking.return_confirmed_customer_at = utcnow() - timedelta(
                    days=max(0, (today - booking.end_date).days)
                )
    db.flush()


_CREW_FIRST = ["Lena", "Jonas", "Mareike", "Tom", "Anke", "Piet", "Frauke", "Nils", "Svenja", "Kai"]
_CREW_LAST = ["Brandt", "Petersen", "Koll", "Hansen", "Vos", "Lorenzen", "Thiel", "Ahrens"]


def _crew_list(booking: Booking, rng: random.Random) -> list[dict]:
    """Eine Crewliste, wie sie der Hafenmeister sehen will: Rolle und Geburtsjahr."""
    crew = [
        {
            "name": booking.customer_name,
            "birthdate": f"{rng.randint(1962, 1988)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
            "role": "skipper",
        }
    ]
    for _ in range(max(0, booking.persons - 1)):
        crew.append(
            {
                "name": f"{rng.choice(_CREW_FIRST)} {rng.choice(_CREW_LAST)}",
                "birthdate": f"{rng.randint(1965, 2012)}-{rng.randint(1, 12):02d}-{rng.randint(1, 28):02d}",
                "role": "crew",
            }
        )
    return crew


_ORDER_NOTES = {
    ServiceOrderType.READINESS.value: [
        "Tank voll, Gas getauscht, Rigg durchgesehen. Boot liegt startklar am Steg.",
        "Motorcheck gemacht, Ölstand ergänzt. Bettwäsche an Bord, Kühlschrank läuft.",
    ],
    ServiceOrderType.HANDOVER.value: [
        "Einweisung vollständig, Crew kennt Motor, Gas und Sicherheitsausrüstung.",
        "Übergabe mit Revierbriefing, Kaution hinterlegt, Schlüssel und Papiere übergeben.",
    ],
    ServiceOrderType.RETURN.value: [
        "Boot sauber zurück, Tank aufgefüllt, keine Auffälligkeiten.",
        "Rücknahme gemeinsam mit der Crew, Inventar vollständig.",
    ],
}


def enrich_orders(db: Session) -> None:
    """Bemerkungen, Fotos und der Name, der den Auftrag abgeschlossen hat."""
    rng = random.Random(RNG_SEED + 3)
    partner_user = {
        p.id: p.user_id for p in db.query(ServicePartner).all()
    }
    for order in db.query(ServiceOrder).filter(ServiceOrder.status == ServiceOrderStatus.DONE.value):
        if not order.notes:
            options = _ORDER_NOTES.get(order.order_type, [])
            if options:
                order.notes = rng.choice(options)
        if not order.photos:
            order.photos = [
                f"/illustration/auftrag-{order.id[:8]}-1.svg",
                f"/illustration/auftrag-{order.id[:8]}-2.svg",
            ]
        if order.completed_by_user_id is None and order.partner_id:
            order.completed_by_user_id = partner_user.get(order.partner_id)
    db.flush()


def enrich_payments(db: Session) -> None:
    """Belegnummern und Anbieterantwort – sonst sieht die Zahlung unfertig aus."""
    for index, payment in enumerate(db.query(Payment).all()):
        if not payment.provider_ref:
            payment.provider_ref = f"fake_pi_{payment.id[:12]}"
        if payment.status == PaymentStatus.PENDING.value and not payment.checkout_url:
            payment.checkout_url = f"/pay/{payment.id}"
        if not payment.raw:
            payment.raw = {
                "provider": "fake",
                "mode": "demo",
                "sequence": index,
                "captured": payment.status == PaymentStatus.SUCCEEDED.value,
            }
    db.flush()


def enrich_images(db: Session) -> None:
    """Aufnahmedatum, Urheber und die nicht öffentlichen Übergabefotos."""
    users = {u.email: u for u in db.query(User).all()}
    charterer_user = next(
        (u for e, u in users.items() if u.role == UserRole.CHARTERER.value), None
    )
    for image in db.query(BoatImage).all():
        if image.taken_on is None:
            if image.charter_month:
                image.taken_on = date.fromisoformat(f"{image.charter_month}-15")
            else:
                image.taken_on = date.today() - timedelta(days=120)
        if image.uploaded_by_user_id is None and image.origin == ImageOrigin.OWNER.value:
            image.uploaded_by_user_id = charterer_user.id if charterer_user else None

    # Übergabefotos hängen an einem Auftrag und sind bewusst nicht öffentlich.
    # Sie fehlten ganz, damit war die Zusage „nicht öffentlich" nicht überprüfbar.
    done_returns = (
        db.query(ServiceOrder)
        .filter(
            ServiceOrder.order_type == ServiceOrderType.RETURN.value,
            ServiceOrder.status == ServiceOrderStatus.DONE.value,
        )
        .limit(12)
        .all()
    )
    for order in done_returns:
        exists = (
            db.query(BoatImage)
            .filter(
                BoatImage.boat_id == order.boat_id,
                BoatImage.origin == ImageOrigin.HANDOVER.value,
                BoatImage.booking_id == order.booking_id,
            )
            .first()
        )
        if exists:
            continue
        db.add(
            BoatImage(
                boat_id=order.boat_id,
                booking_id=order.booking_id,
                url=f"/illustration/rueckgabe-{order.id[:8]}.svg",
                origin=ImageOrigin.HANDOVER.value,
                caption="Zustand bei der Rücknahme",
                taken_on=order.completed_at.date() if order.completed_at else date.today(),
                sort_order=2000,
            )
        )
    db.flush()


_MORE_DAMAGES = [
    {
        "title": "Kratzer am Badeplattform-Scharnier",
        "description": (
            "Beim Anlegen an der Pier entstanden, Lack ist durchgerieben. Kosmetisch, "
            "keine Funktionseinschränkung. Wird beim Winterlager mitgemacht."
        ),
        "estimated_cents": 12000,
        "withheld_cents": 0,
        "status": "assessed",
    },
    {
        "title": "Backbord-Winschkurbel fehlt",
        "description": "Bei der Rücknahme nicht an Bord. Ersatz beschafft, Betrag einbehalten.",
        "estimated_cents": 8900,
        "withheld_cents": 8900,
        "status": "closed",
    },
]


def add_damages(db: Session) -> None:
    """Weitere Schadenfälle in den übrigen Ständen, plus Fotos und Quelle."""
    returns = {
        o.booking_id: o
        for o in db.query(ServiceOrder).filter(
            ServiceOrder.order_type == ServiceOrderType.RETURN.value,
            ServiceOrder.status == ServiceOrderStatus.DONE.value,
        )
    }
    # Vorhandenen Fall an seinen Auftrag hängen – ein Schaden ohne Herkunft ist
    # im Streitfall wertlos.
    for damage in db.query(DamageCase).all():
        if damage.source_order_id is None and damage.booking_id in returns:
            damage.source_order_id = returns[damage.booking_id].id
        if not damage.photos:
            damage.photos = [f"/illustration/schaden-{damage.id[:8]}.svg"]

    settled = (
        db.query(Booking)
        .filter(Booking.status == BookingStatus.SETTLED.value)
        .order_by(Booking.start_date.desc())
        .limit(6)
        .all()
    )
    candidates = [b for b in settled if not b.damages and b.id in returns]
    for entry, booking in zip(_MORE_DAMAGES, candidates, strict=False):
        order = returns[booking.id]
        damage = DamageCase(
            booking_id=booking.id,
            source_order_id=order.id,
            title=entry["title"],
            description=entry["description"],
            estimated_cents=entry["estimated_cents"],
            withheld_cents=entry["withheld_cents"],
            status=entry["status"],
            photos=[f"/illustration/schaden-{booking.reference.lower()}.svg"],
        )
        db.add(damage)
    db.flush()


def add_payouts(db: Session) -> None:
    """Abrechnung je abgerechneter Buchung.

    Gleiche Formel wie `operations.settle`: brutto minus Provision minus bezahlte
    Serviceleistungen, Einbehalte kommen dem Eigner zugute. Ältere Auszahlungen
    sind bereits überwiesen, die jüngsten stehen noch aus – sonst zeigt das
    Dashboard dauerhaft null offene Auszahlungen.
    """
    today = date.today()
    for booking in db.query(Booking).filter(Booking.status == BookingStatus.SETTLED.value):
        if booking.payout is not None:
            continue
        boat = db.get(Boat, booking.boat_id)
        if boat is None:
            continue
        service_costs = sum(
            o.price_cents
            for o in booking.service_orders
            if o.status == ServiceOrderStatus.DONE.value and o.partner_id
        )
        withheld = sum(d.withheld_cents for d in booking.damages)
        commission = booking.commission_cents or round(
            booking.total_cents * COMMISSION_PERCENT / 100
        )
        recent = (today - booking.end_date).days <= 30
        db.add(
            Payout(
                booking_id=booking.id,
                charterer_id=boat.charterer_id,
                gross_cents=booking.total_cents,
                commission_cents=commission,
                service_cost_cents=service_costs,
                damage_withheld_cents=withheld,
                net_cents=booking.total_cents - commission - service_costs + withheld,
                status="pending" if recent else "paid",
                paid_at=None if recent else utcnow() - timedelta(days=7),
            )
        )
    db.flush()


def enrich_quotes(db: Session) -> None:
    """Angebote bekommen ihren Gast und ihre Häfen.

    Ein Angebot ohne Häfen kann keinen One-Way-Törn abbilden; in der Buchung
    stehen sie längst, im Angebot fehlten sie.
    """
    for booking in db.query(Booking).all():
        quote = db.get(Quote, booking.quote_id) if booking.quote_id else None
        if quote is None:
            continue
        if quote.user_id is None:
            quote.user_id = booking.customer_user_id
        if quote.pickup_base_id is None:
            quote.pickup_base_id = booking.pickup_base_id
        if quote.dropoff_base_id is None:
            quote.dropoff_base_id = booking.dropoff_base_id
    db.flush()


def _erster_freier_zeitraum(
    db: Session, boat: Boat, *, nights: int, ab_tagen: int, bis_tagen: int
) -> tuple[date, date] | None:
    """Der erste Zeitraum im Suchbereich, in dem das Boot wirklich frei ist."""
    sperren = db.query(AvailabilityBlock).filter(AvailabilityBlock.boat_id == boat.id).all()
    for versatz in range(ab_tagen, bis_tagen):
        start = date.today() + timedelta(days=versatz)
        end = start + timedelta(days=nights)
        if not any(b.start_date < end and b.end_date > start for b in sperren):
            return start, end
    return None


def add_one_way_booking(db: Session) -> None:
    """Eine Buchung, die in einem anderen Hafen endet.

    One-Way ist der Teil des Zielbilds, der sich am wenigsten erklären lässt und
    am meisten zeigt. Ohne ein Beispiel im Bestand bleibt er Theorie.
    """
    if db.query(Booking).filter(Booking.reference == "SB-OW01").first():
        return
    boat = (
        db.query(Boat)
        .filter(Boat.one_way_enabled.is_(True), Boat.is_active.is_(True))
        .order_by(Boat.name)
        .first()
    )
    if boat is None or not boat.one_way_base_ids:
        return
    dropoff_id = boat.one_way_base_ids[0]
    # Ein fester Abstand zu heute trifft je nach Tag auf eine belegte Woche, und
    # dann fehlte das One-Way-Beispiel im Bestand — ohne dass es jemand merkt,
    # bis die Ansicht leer bleibt. Also wird gesucht, nicht geraten.
    zeitraum = _erster_freier_zeitraum(db, boat, nights=6, ab_tagen=24, bis_tagen=300)
    if zeitraum is None:
        return
    start, end = zeitraum
    nights = (end - start).days
    reference = boat.pricing.reference_price_cents if boat.pricing else 25000
    total = reference * nights + boat.cleaning_fee_cents + boat.one_way_fee_cents
    quote = Quote(
        boat_id=boat.id,
        start_date=start,
        end_date=end,
        persons=min(4, boat.max_persons or 4),
        pickup_base_id=boat.base_id,
        dropoff_base_id=dropoff_id,
        total_cents=total,
        breakdown={"note": "One-Way-Demo", "one_way_fee_cents": boat.one_way_fee_cents},
        expires_at=utcnow(),
    )
    db.add(quote)
    db.flush()
    booking = Booking(
        reference="SB-OW01",
        boat_id=boat.id,
        quote_id=quote.id,
        customer_email="vos@example.com",
        customer_name="Sanne Vos",
        persons=quote.persons,
        start_date=start,
        end_date=end,
        pickup_base_id=boat.base_id,
        dropoff_base_id=dropoff_id,
        status=BookingStatus.CONFIRMED.value,
        total_cents=total,
        deposit_cents=round(total * 0.3),
        security_deposit_cents=boat.deposit_cents,
        price_breakdown=quote.breakdown,
        notes="One-Way: Übernahme im Heimathafen, Rückgabe im Nachbarhafen.",
    )
    db.add(booking)
    db.flush()
    db.add(
        AvailabilityBlock(
            boat_id=boat.id,
            start_date=start,
            end_date=end,
            block_type=BlockType.BOOKING.value,
            booking_id=booking.id,
            note="Buchung SB-OW01",
            start_base_id=boat.base_id,
            end_base_id=dropoff_id,
        )
    )
    db.add(
        Payment(
            booking_id=booking.id,
            provider="fake",
            purpose="deposit",
            amount_cents=booking.deposit_cents,
            status=PaymentStatus.SUCCEEDED.value,
        )
    )
    db.flush()


def add_maintenance_blocks(db: Session, boats: list[Boat]) -> None:
    """Werft- und Eigennutzungszeiten.

    Im Kalender gab es nur Winterlager und Buchungen. Damit ließ sich nicht
    ansehen, wie das Portal mit einer Werftzeit mitten in der Saison umgeht.
    """
    today = date.today()
    for index, boat in enumerate(boats):
        if index % 4:
            continue
        art = BlockType.MAINTENANCE.value if index % 8 == 0 else BlockType.OWNER_USE.value
        if _has_block(db, boat.id, art):
            continue
        # Mit mehreren Anläufen, und zwar in segelbaren Fenstern: ein Termin im
        # Winterlager kollidiert immer, und ein stiller Verzicht ließe eine ganze
        # Sperrart im Bestand fehlen – damit bliebe ungeprüft, wie das Portal sie
        # darstellt. Die Kandidaten decken den Rest dieser Saison und die nächste ab.
        kandidaten = [15, 25, 35, 45, 55, 215, 235, 255, 275, 295, 315, 335]
        for versuch in kandidaten:
            start = today + timedelta(days=versuch + index)
            end = start + timedelta(days=3)
            clash = (
                db.query(AvailabilityBlock)
                .filter(
                    AvailabilityBlock.boat_id == boat.id,
                    AvailabilityBlock.start_date < end,
                    AvailabilityBlock.end_date > start,
                )
                .first()
            )
            if clash:
                continue
            db.add(
                AvailabilityBlock(
                    boat_id=boat.id,
                    start_date=start,
                    end_date=end,
                    block_type=art,
                    note=(
                        "Werfttermin: Unterwasserschiff"
                        if art == BlockType.MAINTENANCE.value
                        else "Eigennutzung durch den Eigner"
                    ),
                )
            )
            db.flush()
            break
    db.flush()


def _has_block(db: Session, boat_id: str, block_type: str) -> bool:
    return (
        db.query(AvailabilityBlock)
        .filter(
            AvailabilityBlock.boat_id == boat_id,
            AvailabilityBlock.block_type == block_type,
        )
        .first()
        is not None
    )


def link_reviews_to_users(db: Session) -> None:
    for review in db.query(Review).all():
        if review.author_user_id is not None:
            continue
        booking = db.get(Booking, review.booking_id)
        if booking and booking.customer_user_id:
            review.author_user_id = booking.customer_user_id
    db.flush()


# =========================================================== Katalog anreichern
#
# Wichtig ist hier die Grenze: Charakter, Standardausstattung und Beschreibungstext
# sind Einordnungen der Plattform – sie entstehen aus den Maßen, die der Katalog
# bereits belegt hat, und sind als Einordnung erkennbar. Stehhöhe, Kojenlänge und
# maximale Personenzahl bleiben leer, wo die Recherche sie nicht belegt hat: das
# sind Tatsachenbehauptungen über das Schiff, und genau an ihnen entscheidet sich,
# ob eine 1,96 m große Person an Bord passt. Eine erfundene Zahl wäre dort kein
# Demo-Inhalt, sondern eine Falschauskunft.

_HULL_KEYWORDS = {
    "sporty": ("dehler", "x-yachts", "salona", "grand-soleil", "sq", "one design"),
    "bluewater": ("hallberg-rassy", "najad", "moody", "xc", "40c", "44"),
    "classic": ("hallberg-rassy", "najad"),
}


def _character_for(version, model_name: str, manufacturer: str) -> list[str]:
    """Charakter aus Werft, Modellname und Maßen – erkennbar eine Einordnung."""
    haystack = f"{manufacturer} {model_name}".lower()
    traits: list[str] = []
    for trait, keywords in _HULL_KEYWORDS.items():
        if any(k in haystack for k in keywords):
            traits.append(trait)
    length = version.length_m or 0
    if not traits:
        traits.append("good_natured" if length < 12 else "comfort")
    if length >= 13 and "comfort" not in traits:
        traits.append("comfort")
    return sorted(set(traits))[:3]


def _standard_features_for(version) -> list[str]:
    """Was in dieser Größenklasse ab Werft üblich ist."""
    length = version.length_m or 0
    features = ["plotter", "sprayhood"]
    if length >= 11:
        features += ["autopilot", "bowthruster"]
    if length >= 13:
        features += ["furling_main", "heating"]
    if (version.engine_hp or 0) >= 40:
        features.append("generator")
    return sorted(set(features))


def _description_for(version, model_name: str, manufacturer: str) -> str:
    length = version.length_m or 0
    cabins = version.cabins
    klasse = (
        "Einsteigerfreundlicher Tourensegler"
        if length < 11
        else "Fahrtenyacht für Familien und Crews"
        if length < 13
        else "Große Fahrtenyacht für längere Törns"
    )
    kabinen = f", {cabins} Kabinen in der Serienaufteilung" if cabins else ""
    return (
        f"{klasse}: {manufacturer} {model_name}, {length:.2f} m Rumpflänge{kabinen}. "
        "Kurzbeschreibung der Plattform auf Basis der Katalogmaße – keine Werftaussage."
    )


def enrich_catalog(db: Session) -> None:
    """Einordnungen und Modellbilder am Katalog.

    Ohne Charakter und Standardausstattung liefert der Einstell-Assistent für ein
    frisch gewähltes Modell eine leere Vorauswahl, und die Suche nach Charakter
    findet nur die von Hand gepflegten Demo-Boote.
    """
    from app.models import ModelVersion

    for version in db.query(ModelVersion).all():
        model = version.model
        manufacturer = model.manufacturer.name if model and model.manufacturer else ""
        model_name = model.name if model else ""
        if not version.character:
            version.character = _character_for(version, model_name, manufacturer)
        if not version.standard_features:
            version.standard_features = _standard_features_for(version)
        if not version.description:
            version.description = _description_for(version, model_name, manufacturer)
        if not version.model_images:
            # Gezeichnet, nicht fotografiert – die Galerie weist es als Illustration
            # aus. Echte Werftfotos brauchen geklärte Bildrechte.
            version.model_images = [f"/illustration/modell-{model.slug if model else version.id}.svg"]
    db.flush()

def fill_boat_details_before_booking(db: Session, boats: list[Boat]) -> None:
    """Regeln, die schon beim Buchen gelten müssen.

    Wechseltage, erlaubte Törnlängen und One-Way schränken ein, was gebucht werden
    darf. Werden sie erst nach dem Buchen gesetzt, widerspricht der Bestand seinen
    eigenen Regeln – Buchungen, die das Portal nie angenommen hätte, stünden im
    Kalender. Also zuerst die Regeln, dann der Betrieb.
    """
    enrich_boats(db, boats)
    enrich_pricing(db, boats)


def fill_everything(db: Session, boats: list[Boat]) -> dict:
    """Alle Anreicherungen in der Reihenfolge ihrer Abhängigkeiten."""
    enrich_catalog(db)
    enrich_users(db)
    enrich_charterers(db)
    enrich_boats(db, boats)
    enrich_pricing(db, boats)
    add_maintenance_blocks(db, boats)
    add_one_way_booking(db)
    enrich_bookings(db)
    enrich_orders(db)
    enrich_payments(db)
    add_damages(db)
    add_payouts(db)
    enrich_images(db)
    enrich_quotes(db)
    link_reviews_to_users(db)
    return {"payouts": db.query(Payout).count(), "damages": db.query(DamageCase).count()}
