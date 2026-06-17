from typing import Generator
from backend.db.connection import get_db as connection_get_db

def get_db() -> Generator:
    """Dependency for FastAPI to get a database session."""
    yield from connection_get_db()
