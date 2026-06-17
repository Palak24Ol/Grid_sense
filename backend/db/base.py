"""
db/base.py — Single source of truth for SQLAlchemy declarative base.

Imported by every ORM model and by Alembic's env.py for auto-discovery.
Never import ORM models here — that would create circular imports.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass