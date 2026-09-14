"""Charter contract generation from boat, charterer and booking data.

Produces Markdown plus a content hash so both parties accept exactly this text.
Legal review of the template is a business task; the structure is deliberately simple to swap.
"""

import hashlib
from datetime import date

from app.models import Boat, Booking, Charterer

CONTRACT_VERSION = "2026-09-v1"


def _eur(cents: int) -> str:
    return f"{cents / 100:,.2f} €".replace(",", "X").replace(".", ",").replace("X", ".")


def _d(d: date) -> str:
    return d.strftime("%d.%m.%Y")


def _base_name(db_obj_boat: Boat, base_id: str | None) -> str:
    if not base_id or base_id == db_obj_boat.base_id:
        return f"{db_obj_boat.base.name}, {db_obj_boat.base.city}"
    from sqlalchemy import inspect

    session = inspect(db_obj_boat).session
    if session is None:
        return base_id
    from app.models import Base_

    b = session.get(Base_, base_id)
    return f"{b.name}, {b.city}" if b else base_id


def render(booking: Booking, boat: Boat, charterer: Charterer) -> dict:
    nights = (booking.end_date - booking.start_date).days
    pickup = _base_name(boat, booking.pickup_base_id)
    dropoff = _base_name(boat, booking.dropoff_base_id)
    balance_due = _d(booking.balance_due_at) if booking.balance_due_at else "vor Übernahme"
    lines = [
        f"# Chartervertrag {booking.reference}",
        "",
        "## Vertragsparteien",
        f"**Vercharterer:** {charterer.name}, {charterer.contact_email}",
        f"**Charterer (Kunde):** {booking.customer_name}, {booking.customer_email}",
        "",
        "Die Plattform Sailbase vermittelt den Vertrag und wickelt Zahlung, Übergabe und Rücknahme ab."
        if boat.listing_mode == "brokerage"
        else "Sailbase tritt als Vertragspartner auf und stellt das Boot aus exklusivem Kontingent.",
        "",
        "## Yacht",
        f"**{boat.name}** – {boat.manufacturer} {boat.model}, Baujahr {boat.year_built or 'k.A.'}, "
        f"{boat.length_m} m, {boat.cabins} Kabinen, {boat.berths} Kojen, max. {boat.max_persons} Personen",
        f"**Heimathafen:** {boat.base.name}, {boat.base.city}",
        f"**Übernahme in:** {pickup} · **Rückgabe in:** {dropoff}",
        f"**Revierbeschränkungen:** {boat.region_restrictions or 'keine besonderen'}",
        "",
        "## Charterzeitraum",
        f"Übernahme: {_d(booking.start_date)} · Rückgabe: {_d(booking.end_date)} · {nights} Nächte",
        f"Personen an Bord: {booking.persons}",
        "",
        "## Preis und Zahlung",
        f"Charterpreis gesamt: **{_eur(booking.total_cents)}** "
        f"(dynamisch kalkuliert, Angebot {booking.quote_id[:8]})",
        f"Anzahlung: {_eur(booking.deposit_cents)} bei Buchung · Restzahlung: "
        f"{_eur(booking.total_cents - booking.deposit_cents)} bis {balance_due}",
        f"Kaution: {_eur(booking.security_deposit_cents)} vor Übernahme, "
        "Freigabe nach dokumentierter Rückgabe",
        "",
        "## Voraussetzungen",
        f"Erforderlicher Befähigungsnachweis: Stufe {boat.required_license} · "
        f"Erfahrung: mind. {boat.required_experience_nm} sm",
        "Crewliste und Führerscheine sind vor Übernahme über das Kundenportal einzureichen.",
        "",
        "## Übergabe und Rückgabe",
        "Übergabe und Rückgabe erfolgen mit standardisierter Checkliste und Fotodokumentation. "
        "Beide Parteien bestätigen digital. Schäden werden anhand der Vorher/Nachher-Fotos festgestellt.",
        "",
        "## Storno",
        "Bis 60 Tage vor Übernahme: 30 % · bis 30 Tage: 60 % · danach 100 % des Charterpreises, "
        "sofern keine Ersatzbuchung zustande kommt.",
        "",
        f"_Vertragsversion {CONTRACT_VERSION}_",
    ]
    text = "\n".join(lines)
    return {
        "version": CONTRACT_VERSION,
        "text_md": text,
        "hash": hashlib.sha256(text.encode("utf-8")).hexdigest(),
    }
