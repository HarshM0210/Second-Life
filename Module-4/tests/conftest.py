"""
tests/conftest.py

Shared fixtures: an isolated in-memory SQLite database per test and a
FastAPI TestClient whose ``get_db`` dependency is overridden to use it.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Ensure the Module-4 root (containing the `green_coin` package) is importable
# and that the rewards catalog resolves regardless of the pytest invocation cwd.
_MODULE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_MODULE_ROOT))
os.environ.setdefault("REWARDS_PATH", str(_MODULE_ROOT / "data" / "rewards.json"))
os.environ.setdefault("DB_URL", "sqlite://")  # keep the app's own engine in-memory during tests

from green_coin.db.database import Base, get_db  # noqa: E402
from green_coin.db import models  # noqa: E402,F401  (register tables)


@pytest.fixture()
def db_session():
    """A fresh in-memory database with all tables created, per test."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    """TestClient with get_db overridden to share the test session, rewards loaded."""
    from fastapi.testclient import TestClient

    from green_coin.core.rewards import load_rewards
    from green_coin.main import app

    load_rewards(os.environ["REWARDS_PATH"])

    def _override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
