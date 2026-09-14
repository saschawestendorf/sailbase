import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, catalog, charterer, commerce, operations, partner, search, uploads
from app.core.config import get_settings
from app.core.db import Base, engine

logger = logging.getLogger("sailbase")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    import app.models  # noqa: F401

    if not settings.is_production:
        # Dev convenience; production runs Alembic migrations on container start.
        Base.metadata.create_all(bind=engine)
    if settings.seed_on_start:
        # Opt-in demo data. Seeding is idempotent, so a restart never duplicates rows.
        try:
            from app.core.db import SessionLocal
            from app.seed.seed import seed

            with SessionLocal() as db:
                logger.info("Seeding demo catalogue: %s", seed(db))
        except Exception:  # never let seeding take the API down
            logger.exception("Seeding failed, continuing with an empty catalogue")
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title=settings.app_name, version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(search.router)
    app.include_router(commerce.router)
    app.include_router(charterer.router)
    app.include_router(operations.router)
    app.include_router(partner.router)
    app.include_router(uploads.router)

    media = Path(settings.upload_dir)
    media.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(media)), name="media")

    @app.get("/health", tags=["meta"])
    def health():
        """Liveness/readiness probe used by the platform health check."""
        return {"status": "ok", "environment": settings.environment, "version": app.version}

    @app.get("/", include_in_schema=False)
    def root():
        return {"service": settings.app_name, "docs": "/docs", "health": "/health"}

    return app


app = create_app()
