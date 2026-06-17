"""
db/connection.py — SQLAlchemy engine and session factory.

Uses PostgreSQL exclusively (no SQLite fallback — see Readiness Review §1.8).
Connection string comes from config.DATABASE_URL.
"""

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from backend.config import get_settings
from backend.core.logging import get_logger

logger = get_logger(__name__)

_engine = None
_SessionLocal = None


def get_engine():
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_engine(
            settings.DATABASE_URL,
            pool_pre_ping=True,       # Detect stale connections before use
            pool_size=5,
            max_overflow=10,
            echo=False,               # Set True for SQL debug logging
        )
        logger.info(f"Database engine created: {settings.DATABASE_URL.split('@')[-1]}")
    return _engine


def get_session_local():
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=get_engine(),
        )
    return _SessionLocal


def get_db():
    """FastAPI dependency that yields a database session and ensures cleanup."""
    SessionLocal = get_session_local()
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """Health check — returns True if database is reachable."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return False