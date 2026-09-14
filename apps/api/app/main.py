from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.routes import auth, catalog, charterer, commerce, operations, partner, search, uploads
from app.core.config import get_settings
from app.core.db import Base, engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    if not settings.is_production:
        # Dev convenience; production uses Alembic migrations.
        import app.models  # noqa: F401

        Base.metadata.create_all(bind=engine)
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
        return {"status": "ok", "environment": settings.environment}

    return app


app = create_app()
