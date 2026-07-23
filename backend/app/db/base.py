"""Declarative base and shared column mixins.

Kept free of model imports to avoid circular imports (models import ``Base``
from here). Code that needs the full metadata for Alembic autogenerate must
import ``app.models`` explicitly first — see ``alembic/env.py``.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import TIMESTAMP


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all ORM models."""


class TimestampMixin:
    """Adds a timezone-aware ``created_at`` set by the DB server."""

    created_at: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
