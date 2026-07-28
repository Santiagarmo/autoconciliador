"""VerificacionExtracto repository: abstract interface + SQLAlchemy impl."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence

from sqlalchemy import select

from app.models.verificacion_extracto import VerificacionExtracto
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IVerificacionExtractoRepository(AbstractRepository[VerificacionExtracto]):
    @abstractmethod
    async def list_recientes(
        self, limit: int = 20
    ) -> Sequence[VerificacionExtracto]: ...


class VerificacionExtractoRepository(
    SQLAlchemyRepository[VerificacionExtracto], IVerificacionExtractoRepository
):
    model = VerificacionExtracto

    async def list_recientes(
        self, limit: int = 20
    ) -> Sequence[VerificacionExtracto]:
        stmt = (
            select(VerificacionExtracto)
            .order_by(VerificacionExtracto.created_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()
