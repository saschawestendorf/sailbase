"""Preisraster: was kostet ein Törn, wenn er einen Tag später beginnt oder endet?

Die Suche beantwortet „welches Boot passt zu diesem Zeitraum". Das Raster dreht
die Frage um: bei gegebenen Filtern wird jede Kombination aus Startdatum und
Dauer im Fenster bepreist und je Kombination das günstigste Boot behalten. Damit
wird sichtbar, was ein Preis allein nicht zeigt — ob der Törn eine Woche später
oder einen Tag kürzer deutlich billiger wäre.

Zwei Betriebsarten, eine Rechnung:

* über die Flotte (Suchseite): jede Zelle nennt das günstigste passende Boot,
* über ein Boot (Bootsseite): dieselbe Rechnung mit `boat_slug` eingegrenzt.

Aufwand: Boote × Starttage × Dauern. Das ist absichtlich gedeckelt (siehe
`MAX_EVALUATIONS`), denn ein offenes Fenster über eine wachsende Flotte wäre
sonst eine Einladung, den Dienst mit einer einzigen Anfrage lahmzulegen. Wird
der Deckel erreicht, kommt ein gekürztes Raster zurück und sagt das auch
(`truncated`) — lieber eine ehrliche Teilauskunft als eine hängende Seite.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.models import Boat
from app.services import search as search_service
from app.services.matching import CrewProfile, hard_filter
from app.services.offers import OfferContext

# Obergrenze für bepreiste Kombinationen je Anfrage. 20.000 sind bei der
# heutigen Flotte großzügig und decken ein 60-Tage-Fenster mit fünf Dauern ab;
# sie greifen erst, wenn jemand das Fenster und die Flotte gleichzeitig aufreißt.
MAX_EVALUATIONS = 20_000
# Mehr Dauern nebeneinander liest niemand mehr — und jede kostet Rechenzeit.
MAX_DURATIONS = 9
MAX_WINDOW_DAYS = 120


@dataclass(frozen=True)
class GridQuery:
    """Fenster, Dauern und dieselben harten Filter wie die Suche."""

    window_start: date
    window_end: date
    min_nights: int
    max_nights: int
    crew: CrewProfile
    boat_slug: str | None = None
    region_slug: str | None = None
    base_id: str | None = None
    pickup_base_id: str | None = None
    dropoff_base_id: str | None = None
    boat_class_slug: str | None = None
    min_length_m: float | None = None
    max_length_m: float | None = None
    max_boats: int = 60

    @property
    def durations(self) -> list[int]:
        lo = max(1, self.min_nights)
        hi = max(lo, self.max_nights)
        return list(range(lo, min(hi, lo + MAX_DURATIONS - 1) + 1))


@dataclass
class Cell:
    """Die günstigste Möglichkeit, an `start_date` für `nights` Nächte loszufahren."""

    start_date: date
    nights: int
    end_date: date
    total_cents: int
    per_day_cents: int
    boat_id: str
    boat_slug: str
    boat_name: str
    boat_count: int = 1  # wie viele Boote diese Kombination anbieten

    def to_dict(self) -> dict:
        return {
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "nights": self.nights,
            "total_cents": self.total_cents,
            "per_day_cents": self.per_day_cents,
            "boat_id": self.boat_id,
            "boat_slug": self.boat_slug,
            "boat_name": self.boat_name,
            "boat_count": self.boat_count,
        }


@dataclass
class PriceGrid:
    window_start: date
    window_end: date
    durations: list[int]
    cells: list[Cell] = field(default_factory=list)
    boats_considered: int = 0
    evaluations: int = 0
    truncated: bool = False

    @property
    def cheapest(self) -> Cell | None:
        """Absolut günstigster Törn — über alle Dauern hinweg pro Nacht gerechnet.

        Der Gesamtpreis taugt hier nicht: die kürzeste Dauer gewönne immer.
        """
        if not self.cells:
            return None
        return min(self.cells, key=lambda c: (c.per_day_cents, c.total_cents, c.start_date))

    def cheapest_for(self, nights: int) -> Cell | None:
        """Günstigster Start für genau diese Dauer — der Vergleich, den die Spalte zeigt."""
        same = [c for c in self.cells if c.nights == nights]
        return min(same, key=lambda c: (c.total_cents, c.start_date)) if same else None


def _boats(db: Session, q: GridQuery) -> list[Boat]:
    """Dieselbe Kandidatenauswahl wie die Suche, damit Raster und Liste zusammenpassen."""
    probe = search_service.SearchQuery(
        window_start=q.window_start,
        window_end=q.window_end,
        min_nights=q.min_nights,
        max_nights=q.max_nights,
        crew=q.crew,
        region_slug=q.region_slug,
        base_id=q.base_id,
        pickup_base_id=q.pickup_base_id,
        dropoff_base_id=q.dropoff_base_id,
        boat_class_slug=q.boat_class_slug,
        min_length_m=q.min_length_m,
        max_length_m=q.max_length_m,
    )
    boats = search_service.candidates(db, probe)
    if q.boat_slug:
        boats = [b for b in boats if b.slug == q.boat_slug]
    # Harte Ausschlüsse (Crewgröße, Kojen, Schein) einmal je Boot statt je Zelle.
    boats = [b for b in boats if b.pricing is not None and not hard_filter(b, q.crew)]
    # Ein stabiler Schnitt: sonst hinge die Laufzeit an der Reihenfolge der Datenbank.
    boats.sort(key=lambda b: b.slug)
    return boats[: max(1, q.max_boats)]


def build(db: Session, q: GridQuery, today: date | None = None) -> PriceGrid:
    durations = q.durations
    grid = PriceGrid(window_start=q.window_start, window_end=q.window_end, durations=durations)
    window_days = (q.window_end - q.window_start).days
    if window_days <= 0 or not durations:
        return grid

    boats = _boats(db, q)
    grid.boats_considered = len(boats)
    best: dict[tuple[date, int], Cell] = {}

    for boat in boats:
        ctx = OfferContext(
            db,
            boat,
            q.window_start,
            q.window_end,
            today=today,
            pickup_base_id=q.pickup_base_id,
            dropoff_base_id=q.dropoff_base_id,
        )
        for offset in range(window_days):
            day = q.window_start + timedelta(days=offset)
            for nights in durations:
                end = day + timedelta(days=nights)
                if end > q.window_end:
                    break
                if grid.evaluations >= MAX_EVALUATIONS:
                    grid.truncated = True
                    return _finish(grid, best)
                grid.evaluations += 1
                ok, _reason = ctx.is_free(day, end)
                if not ok:
                    continue
                try:
                    res, _gap, offer, _note = ctx.price(day, end)
                except ValueError:
                    continue
                if not offer:
                    continue
                # Budget gilt pro Zelle, nicht pro Boot: dasselbe Boot kann in der
                # einen Woche im Rahmen liegen und in der nächsten darüber.
                if q.crew.budget_total_cents and res.total_cents > q.crew.budget_total_cents:
                    continue
                key = (day, nights)
                current = best.get(key)
                if current is None:
                    best[key] = Cell(
                        start_date=day,
                        nights=nights,
                        end_date=end,
                        total_cents=res.total_cents,
                        per_day_cents=res.per_day_cents,
                        boat_id=boat.id,
                        boat_slug=boat.slug,
                        boat_name=boat.name,
                    )
                else:
                    current.boat_count += 1
                    if res.total_cents < current.total_cents:
                        best[key] = Cell(
                            start_date=day,
                            nights=nights,
                            end_date=end,
                            total_cents=res.total_cents,
                            per_day_cents=res.per_day_cents,
                            boat_id=boat.id,
                            boat_slug=boat.slug,
                            boat_name=boat.name,
                            boat_count=current.boat_count,
                        )
    return _finish(grid, best)


def _finish(grid: PriceGrid, best: dict[tuple[date, int], Cell]) -> PriceGrid:
    grid.cells = sorted(best.values(), key=lambda c: (c.start_date, c.nights))
    return grid


def clamp_window(start: date, end: date) -> date:
    """Kappt das Fenster auf `MAX_WINDOW_DAYS`, statt die Anfrage abzuweisen."""
    return min(end, start + timedelta(days=MAX_WINDOW_DAYS))
