"""Der Demo-Bestand muss vollständig bleiben.

Ein Seed verfällt leise: jemand fügt eine Tabelle hinzu, ein Feld dazu, und die
Demo zeigt dort ab dann eine leere Karte. Wer das Portal ansieht, kann dann nicht
unterscheiden, ob eine Funktion fehlt oder nur ihre Daten. Diese Tests halten
fest, was der Bestand mindestens hergeben muss.
"""

import pytest
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import app.core.db as dbmod
from app.core.db import Base
from app.models import (
    AvailabilityBlock,
    BlockType,
    Boat,
    Booking,
    BookingStatus,
    DamageCase,
    ImageOrigin,
    Payout,
    ServiceOrderStatus,
)
from app.seed.seed import seed


@pytest.fixture(scope="module")
def db(monkeypatch_module):
    """Eine Datenbank mit dem vollständigen Demo-Bestand.

    Die übrigen Tests laufen bewusst ohne Demo-Buchungen, damit sie ihre eigenen
    Fälle aufbauen. Hier ist der Bestand selbst der Prüfgegenstand, also wird er
    einmal je Modul gebaut.
    """
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    import app.models  # noqa: F401

    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch_module.setattr(dbmod, "SessionLocal", factory)
    monkeypatch_module.setattr(dbmod, "engine", engine)
    session = factory()
    seed(session, with_demo_bookings=True)
    yield session
    session.close()
    engine.dispose()


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch

    mp = MonkeyPatch()
    yield mp
    mp.undo()


# Spalten, die bewusst leer bleiben. Stehhöhe, Kojenlänge und maximale Personen
# sind Tatsachenbehauptungen über ein konkretes Schiff; die Recherche hat sie für
# die meisten Modelle nicht belegt. Eine erfundene Stehhöhe wäre keine Demo,
# sondern eine Falschauskunft an genau die Crew, die danach sucht.
UNBELEGT_ERLAUBT = {
    ("model_versions", "headroom_cm"),
    ("model_versions", "max_berth_length_cm"),
    ("variant_options", "headroom_cm"),
    ("variant_options", "max_berth_length_cm"),
    ("variant_options", "sail_area_m2"),
}


def test_keine_tabelle_bleibt_leer(db):
    insp = inspect(db.get_bind())
    leer = [
        t
        for t in insp.get_table_names()
        if t != "alembic_version"
        and db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() == 0
    ]
    assert not leer, f"Tabellen ohne Demo-Daten: {leer}"


def test_keine_spalte_bleibt_ohne_beispiel(db):
    insp = inspect(db.get_bind())
    leer = []
    for table in insp.get_table_names():
        if table == "alembic_version":
            continue
        for column in insp.get_columns(table):
            name = column["name"]
            if (table, name) in UNBELEGT_ERLAUBT:
                continue
            gefuellt = db.execute(
                text(
                    f"""SELECT COUNT(*) FROM "{table}" WHERE "{name}" IS NOT NULL
                        AND CAST("{name}" AS TEXT) NOT IN ('', '[]', '{{}}')"""
                )
            ).scalar()
            if not gefuellt:
                leer.append(f"{table}.{name}")
    assert not leer, f"Spalten ohne ein einziges Beispiel: {leer}"


def test_jede_phase_des_ablaufs_ist_vertreten(db):
    """Sonst lässt sich die Abwicklungsseite nicht in allen Zuständen ansehen."""
    vorhanden = {b.status for b in db.query(Booking).all()}
    fehlt = {
        BookingStatus.PENDING_PAYMENT.value,
        BookingStatus.CONFIRMED.value,
        BookingStatus.READY.value,
        BookingStatus.HANDED_OVER.value,
        BookingStatus.RETURNED.value,
        BookingStatus.SETTLED.value,
    } - vorhanden
    assert not fehlt, f"Kein Beispiel für: {sorted(fehlt)}"


def test_kalender_kennt_alle_sperrarten(db):
    """Winterlager, Werfttermin, Eigennutzung, Buchung und Reservierung."""
    vorhanden = {b.block_type for b in db.query(AvailabilityBlock).all()}
    fehlt = {t.value for t in BlockType} - vorhanden
    assert not fehlt, f"Kein Beispiel für Sperrart: {sorted(fehlt)}"


def test_one_way_ist_im_bestand_vorgefuehrt(db):
    """Das Alleinstellungsmerkmal braucht ein Boot und eine Buchung."""
    boote = db.query(Boat).filter(Boat.one_way_enabled.is_(True)).count()
    assert boote, "Kein Boot bietet One-Way an"
    einweg = [
        b
        for b in db.query(Booking).all()
        if b.dropoff_base_id and b.dropoff_base_id != b.pickup_base_id
    ]
    assert einweg, "Keine Buchung endet in einem anderen Hafen"


def test_abwicklung_ist_belegt(db):
    """Verträge, Crewlisten, erledigte Aufträge, Schäden und Auszahlungen."""
    bestaetigt = [b for b in db.query(Booking).all() if b.status in BookingStatus.active()]
    assert any(b.contract for b in bestaetigt), "Kein gerenderter Vertrag"
    assert any(b.crew_list for b in bestaetigt), "Keine eingereichte Crewliste"
    assert any(b.documents for b in bestaetigt), "Keine Buchungsunterlagen"
    assert db.query(Payout).count(), "Keine Auszahlung gerechnet"
    assert db.query(DamageCase).count() >= 2, "Zu wenige Schadenfälle für die Ansicht"

    erledigt = [
        o
        for b in bestaetigt
        for o in b.service_orders
        if o.status == ServiceOrderStatus.DONE.value
    ]
    assert erledigt, "Kein erledigter Serviceauftrag"
    assert any(o.photos for o in erledigt), "Kein Auftrag mit Fotobeleg"
    assert any(o.notes for o in erledigt), "Kein Auftrag mit Bemerkung"


def test_uebergabefotos_bleiben_nicht_oeffentlich(db):
    """Sie müssen existieren – und dürfen trotzdem nicht in der Galerie stehen."""
    from app.models import BoatImage

    handover = db.query(BoatImage).filter(BoatImage.origin == ImageOrigin.HANDOVER.value).all()
    assert handover, "Kein Übergabefoto im Bestand"
    boat = db.get(Boat, handover[0].boat_id)
    assert boat is not None
