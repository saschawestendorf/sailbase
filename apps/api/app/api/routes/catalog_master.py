"""Public browsing of the boat master catalog, plus a preview of what a selection resolves to."""

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.api.deps import DB
from app.models import BoatModel, Manufacturer, ModelVersion
from app.schemas.catalog_master import (
    BoatModelDetailOut,
    BoatModelOut,
    ManufacturerOut,
    ModelVersionOut,
    ResolvedSpecOut,
    SpecPreviewRequest,
)
from app.services import catalog as catalog_service

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.get("/manufacturers", response_model=list[ManufacturerOut])
def manufacturers(db: DB):
    return db.execute(select(Manufacturer).order_by(Manufacturer.name)).scalars().all()


@router.get("/models", response_model=list[BoatModelOut])
def models(
    db: DB,
    q: str | None = Query(default=None, max_length=100, description="Freitext über Hersteller und Modell"),
    manufacturer: str | None = None,
):
    return catalog_service.search_models(db, q, manufacturer)


@router.get("/models/{model_id}", response_model=BoatModelDetailOut)
def model_detail(model_id: str, db: DB):
    model = (
        db.execute(
            select(BoatModel)
            .options(
                selectinload(BoatModel.manufacturer),
                selectinload(BoatModel.versions).selectinload(ModelVersion.variants),
            )
            .where(BoatModel.id == model_id)
        )
        .scalars()
        .first()
    )
    if model is None:
        raise HTTPException(404, "Modell nicht gefunden")
    return model


@router.get("/versions/{version_id}", response_model=ModelVersionOut)
def version_detail(version_id: str, db: DB):
    try:
        return catalog_service.load_version(db, version_id)
    except catalog_service.CatalogError as e:
        raise HTTPException(404, str(e)) from e


@router.post("/resolve", response_model=ResolvedSpecOut)
def resolve_spec(payload: SpecPreviewRequest, db: DB):
    """What this configuration actually is, and which number came from where."""
    try:
        version = catalog_service.load_version(db, payload.version_id)
        # Validates the build year in both cases; an empty selection falls back to the defaults.
        variants = catalog_service.validate_selection(
            version, payload.year_built, payload.variant_ids
        ) or catalog_service.default_variants(version)
    except catalog_service.CatalogError as e:
        raise HTTPException(422, str(e)) from e
    spec = catalog_service.resolve(version, variants, payload.overrides)
    return ResolvedSpecOut(**spec.to_dict())
