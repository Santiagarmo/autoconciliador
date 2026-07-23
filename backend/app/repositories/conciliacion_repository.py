"""Conciliacion repository: abstract interface + SQLAlchemy implementation."""
from __future__ import annotations

from abc import abstractmethod
from uuid import UUID

from sqlalchemy import select

from app.models.conciliacion import Conciliacion
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IConciliacionRepository(AbstractRepository[Conciliacion]):
    @abstractmethod
    async def get_by_pago(
        self, pago_declarado_id: UUID
    ) -> Conciliacion | None: ...


class ConciliacionRepository(
    SQLAlchemyRepository[Conciliacion], IConciliacionRepository
):
    model = Conciliacion

    async def get_by_pago(
        self, pago_declarado_id: UUID
    ) -> Conciliacion | None:
        result = await self.session.execute(
            select(Conciliacion).where(
                Conciliacion.pago_declarado_id == pago_declarado_id
            )
        )
        return result.scalar_one_or_none()
