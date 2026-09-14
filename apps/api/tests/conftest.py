import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["ENVIRONMENT"] = "test"
os.environ["PAYMENT_PROVIDER"] = "fake"
os.environ["UPLOAD_DIR"] = (
    "/tmp/claude-0/-home-user-sailbase/b6abb400-0d98-57e6-88b3-5ee30169d95c/scratchpad/uploads-test"
)

from datetime import date  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

import app.core.db as dbmod  # noqa: E402
from app.core.db import Base  # noqa: E402
from app.main import create_app  # noqa: E402
from app.seed.seed import seed  # noqa: E402


@pytest.fixture()
def engine():
    eng = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    import app.models  # noqa: F401

    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture()
def db(engine, monkeypatch):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(dbmod, "SessionLocal", factory)
    monkeypatch.setattr(dbmod, "engine", engine)
    session = factory()
    seed(session, with_demo_bookings=False)
    yield session
    session.close()


@pytest.fixture()
def client(db, engine):
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def _override():
        s = factory()
        try:
            yield s
        finally:
            s.close()

    app = create_app()
    app.dependency_overrides[dbmod.get_db] = _override
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def dates():
    y = date.today().year + 1
    return date(y, 7, 4), date(y, 7, 11)
