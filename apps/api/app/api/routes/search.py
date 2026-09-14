from datetime import date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import DB, OptionalUser
from app.schemas.catalog import SearchHitOut, SearchOut
from app.services import reviews as review_service
from app.services.matching import CrewProfile
from app.services.search import SearchQuery, search

router = APIRouter(tags=["search"])


@router.get("/search", response_model=SearchOut)
def search_boats(
    db: DB,
    user: OptionalUser,
    start_date: date,
    end_date: date,
    persons: int = Query(default=2, ge=1, le=30),
    min_nights: int | None = Query(default=None, ge=1, le=60, description="Flexible Suche: kürzeste Dauer"),
    max_nights: int | None = Query(default=None, ge=1, le=60, description="Flexible Suche: längste Dauer"),
    region: str | None = None,
    base_id: str | None = None,
    pickup_base_id: str | None = Query(default=None, description="Abholhafen (standortbewusst)"),
    dropoff_base_id: str | None = Query(default=None, description="Abgabehafen für One-Way"),
    boat_class: str | None = None,
    min_length: float | None = Query(default=None, ge=0),
    max_length: float | None = Query(default=None, ge=0),
    max_price: int | None = Query(default=None, ge=0, description="Gesamtbudget in Cent"),
    character: Annotated[list[str] | None, Query()] = None,
    features: Annotated[list[str] | None, Query()] = None,
    tallest_cm: int | None = Query(default=None, ge=100, le=250),
    license_level: int | None = Query(default=None, ge=0, le=5),
    experience_nm: int | None = Query(default=None, ge=0),
    min_cabins: int | None = Query(default=None, ge=0),
    with_skipper: bool = False,
    sort: str = Query(default="fit", pattern="^(fit|price_asc|price_desc|length_desc)$"),
    include_unavailable: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
):
    if end_date <= start_date:
        raise HTTPException(422, "end_date muss nach start_date liegen")
    window_nights = (end_date - start_date).days
    if window_nights > 90:
        raise HTTPException(422, "Suchfenster maximal 90 Tage")
    # Exact search = window is the stay. Flexible search = any stay of min..max nights inside the window.
    if min_nights is None and max_nights is None:
        min_nights = max_nights = window_nights
    else:
        min_nights = min_nights or 1
        max_nights = max_nights or min_nights
        if max_nights < min_nights:
            raise HTTPException(422, "max_nights muss >= min_nights sein")
        if max_nights > window_nights:
            max_nights = window_nights
        if min_nights > window_nights:
            raise HTTPException(422, "min_nights passt nicht ins Suchfenster")

    # Profile defaults from logged-in user; explicit query params win.
    # Unknown qualification (no params, no profile) must not hide the whole catalogue:
    # we then skip the hard qualification filter and let the UI show requirements instead.
    eff_license = license_level if license_level is not None else (user.license_level if user else None)
    eff_exp = experience_nm if experience_nm is not None else (user.experience_nm if user else None)
    qualification_unknown = eff_license is None and eff_exp is None
    crew = CrewProfile(
        persons=persons,
        license_level=eff_license or 0,
        experience_nm=eff_exp or 0,
        tallest_person_cm=tallest_cm if tallest_cm is not None else (user.height_cm if user else None),
        preferred_character=character or [],
        budget_total_cents=max_price,
        wanted_features=features or [],
        min_cabins=min_cabins,
        skip_qualification_check=with_skipper or qualification_unknown,
    )
    q = SearchQuery(
        window_start=start_date,
        window_end=end_date,
        min_nights=min_nights,
        max_nights=max_nights,
        crew=crew,
        region_slug=region,
        base_id=base_id,
        pickup_base_id=pickup_base_id,
        dropoff_base_id=dropoff_base_id,
        boat_class_slug=boat_class,
        min_length_m=min_length,
        max_length_m=max_length,
        sort=sort,
        include_unavailable=include_unavailable,
        limit=limit,
    )
    hits = search(db, q)
    out = []
    for h in hits:
        item = SearchHitOut(
            boat=h.boat,
            available=h.available,
            unavailable_reason=h.unavailable_reason,
            total_cents=h.total_cents,
            per_day_cents=h.per_day_cents,
            offers=[o.to_dict() for o in h.offers],
            fit_score=h.fit_score,
            fit_reasons=h.fit_reasons,
            blockers=h.blockers,
            breakdown=h.breakdown,
        )
        # Verified ratings travel with the card, so the list is comparable at a glance.
        summary = review_service.summarise(h.boat.reviews)
        item.boat.rating_overall = summary.overall
        item.boat.rating_count = summary.count
        out.append(item)
    return SearchOut(count=len(out), hits=out)
