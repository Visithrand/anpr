"""
backend/utils/database.py
~~~~~~~~~~~~~~~~~~~~~~~~~~
Production-grade SQLAlchemy database engine with connection pooling.

Features:
  - Configurable pool size, overflow, and recycle interval
  - ``pool_pre_ping=True`` to detect stale/dead connections before use
  - Pool event listeners for monitoring connection health
  - Thread-safe session factory via ``get_db()`` generator
"""

from __future__ import annotations

import logging

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import settings

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Engine — with connection pooling for 24/7 operation
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_recycle=settings.DB_POOL_RECYCLE,
    pool_pre_ping=settings.DB_POOL_PRE_PING,
    pool_timeout=30,
    echo=False,
)

# ---------------------------------------------------------------------------
# Pool event listeners — observability into connection lifecycle
# ---------------------------------------------------------------------------
@event.listens_for(engine, "connect")
def _on_connect(dbapi_conn, connection_record):
    log.debug("DB pool: new connection established")


@event.listens_for(engine, "checkout")
def _on_checkout(dbapi_conn, connection_record, connection_proxy):
    log.debug("DB pool: connection checked out")


@event.listens_for(engine, "checkin")
def _on_checkin(dbapi_conn, connection_record):
    log.debug("DB pool: connection returned")


@event.listens_for(engine, "invalidate")
def _on_invalidate(dbapi_conn, connection_record, exception):
    log.warning("DB pool: connection invalidated — %s", exception)


# ---------------------------------------------------------------------------
# Session factory and declarative base
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a DB session with guaranteed cleanup."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()