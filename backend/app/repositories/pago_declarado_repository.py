"""PagoDeclarado repository: abstract interface + SQLAlchemy implementation."""
from __future__ import annotations

from abc import abstractmethod
from collections.abc import Sequence

from sqlalchemy import select

from app.domain.enums import EstadoPago
from app.models.pago_declarado import PagoDeclarado
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IPagoDeclaradoRepository(AbstractRepository[PagoDeclarado]):
    @abstractmethod
    async def get_by_banco_referencia(
        self, banco_destino: str, numero_referencia: str
    ) -> PagoDeclarado | None: ...

    @abstractmethod
    async def list_by_estado(
        self, estado: EstadoPago
    ) -> Sequence[PagoDeclarado]: ...


class PagoDeclaradoRepository(
    SQLAlchemyRepository[PagoDeclarado], IPagoDeclaradoRepository
):
    model = PagoDeclarado

    async def get_by_banco_referencia(
        self, banco_destino: str, numero_referencia: str
    ) -> PagoDeclarado | None:
        result = await self.session.execute(
            select(PagoDeclarado).where(
                PagoDeclarado.banco_destino == banco_destino,
                PagoDeclarado.numero_referencia == numero_referencia,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_estado(
        self, estado: EstadoPago
    ) -> Sequence[PagoDeclarado]:
        result = await self.session.execute(
            select(PagoDeclarado).where(PagoDeclarado.estado_pago == estado)
        )
        return result.scalars().all()
