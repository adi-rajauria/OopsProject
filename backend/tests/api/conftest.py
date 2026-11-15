"""API/SQL fixtures. Default: SQLite in-memory (no setup needed).
Set ITSM_TEST_DATABASE_URL=postgresql+psycopg://.../itsm_test to run the same tests on PostgreSQL
(tables are dropped and recreated around each test - never point it at the real database)."""

import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import Settings
from app.core.db import make_engine, make_session_factory
from app.main import build_infrastructure, create_app
from app.repositories.orm import Base
from tests.conftest import FakeClock

TEST_DATABASE_URL = os.environ.get("ITSM_TEST_DATABASE_URL", "sqlite://")


@pytest.fixture
def settings() -> Settings:
    return Settings(
        database_url=TEST_DATABASE_URL,
        jwt_secret="api-test-secret-that-is-long-enough-123",
        log_level="WARNING",
        sla_monitor_enabled=False,
        _env_file=None,
    )


@pytest.fixture
def session_factory(settings) -> sessionmaker[Session]:
    engine = make_engine(settings.database_url)
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield make_session_factory(engine)
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(settings, session_factory, clock) -> TestClient:
    app = create_app(settings, session_factory=session_factory, infra=build_infrastructure(settings, clock))
    with TestClient(app) as test_client:
        yield test_client
