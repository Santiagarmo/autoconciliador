"""Repository pattern base classes.

- ``AbstractRepository``: the interface services depend on (Dependency
  Inversion). Declares the generic persistence contract.
- ``SQLAlchemyRepository``: a concrete generic implementation over an
  ``AsyncSession``.

Repositories NEVER commit. Flushing is used so generated PKs/defaults are
available, but the transaction boundary (commit/rollback) belongs to the
service layer / Unit of Work (Phase 3).
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Generic, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class AbstractRepository(ABC, Generic[ModelT]):
    """Persistence contract for a single aggregate/entity type."""

    @abstractmethod
    async def add(self, entity: ModelT) -> ModelT: ...

    @abstractmethod
    async def get(self, entity_id: UUID) -> ModelT | None: ...

    @abstractmethod
    async def list(self) -> Sequence[ModelT]: ...


class SQLAlchemyRepository(AbstractRepository[ModelT]):
    """Generic async SQLAlchemy implementation. Subclasses set ``model``."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, entity: ModelT) -> ModelT:
        self.session.add(entity)
        await self.session.flush()
        return entity

    async def get(self, entity_id: UUID) -> ModelT | None:
        return await self.session.get(self.model, entity_id)

    async def list(self) -> Sequence[ModelT]:
        result = await self.session.execute(select(self.model))
        return result.scalars().all()
