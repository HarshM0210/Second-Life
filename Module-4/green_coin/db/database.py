"""
green_coin/db/database.py

SQLAlchemy engine, session factory, and FastAPI dependency.

Identical pattern to Module 3 so the two services are operationally
interchangeable (swap the SQLite URL for Postgres in production).
"""

from __future__ import annotations

from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker

from green_coin.config import settings

engine = create_engine(
    settings.DB_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DB_URL else {},
)

SessionLocal: sessionmaker[Session] = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base: Any = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a SQLAlchemy session and closes it on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
