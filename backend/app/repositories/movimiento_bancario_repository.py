"""MovimientoBancario repository: abstract interface + SQLAlchemy impl."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence

from sqlalchemy import select

from app.domain.enums import EstadoMovimiento
from app.models.movimiento_bancario import MovimientoBancario
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IMovimientoBancarioRepository(AbstractRepository[MovimientoBancario]):
    @abstractmethod
    async def get_by_hash(
        self, hash_idempotencia: str
    ) -> MovimientoBancario | None: ...

    @abstractmethod
    async def list_disponibles(
        self, *, for_update: bool = False
    ) -> Sequence[MovimientoBancario]: ...


class MovimientoBancarioRepository(
    SQLAlchemyRepository[MovimientoBancario], IMovimientoBancarioRepository
):
    model = MovimientoBancario

    async def get_by_hash(
        self, hash_idempotencia: str
    ) -> MovimientoBancario | None:
        result = await self.session.execute(
            select(MovimientoBancario).where(
                MovimientoBancario.hash_idempotencia == hash_idempotencia
            )
        )
        return result.scalar_one_or_none()

    async def list_disponibles(
        self, *, for_update: bool = False
    ) -> Sequence[MovimientoBancario]:
        stmt = select(MovimientoBancario).where(
            MovimientoBancario.estado_movimiento == EstadoMovimiento.DISPONIBLE
        )
        if for_update:
            # Concurrency guard for the reconciliation engine (Phase 3):
            # each worker grabs its own rows, never blocks on locked ones.
            stmt = stmt.with_for_update(skip_locked=True)
        result = await self.session.execute(stmt)
        return result.scalars().all()
