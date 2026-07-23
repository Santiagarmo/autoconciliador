"""Pedido repository: abstract interface + SQLAlchemy implementation."""
from __future__ import annotations

from abc import abstractmethod

from sqlalchemy import select

from app.models.pedido import Pedido
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IPedidoRepository(AbstractRepository[Pedido]):
    """Domain-specific contract for pedidos."""

    @abstractmethod
    async def get_by_codigo(self, codigo_pedido: str) -> Pedido | None: ...


class PedidoRepository(SQLAlchemyRepository[Pedido], IPedidoRepository):
    model = Pedido

    async def get_by_codigo(self, codigo_pedido: str) -> Pedido | None:
        result = await self.session.execute(
            select(Pedido).where(Pedido.codigo_pedido == codigo_pedido)
        )
        return result.scalar_one_or_none()
