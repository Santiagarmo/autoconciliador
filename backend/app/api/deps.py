"""FastAPI dependency providers (Dependency Inversion wiring).

Routers depend on services, services depend on these repository providers,
and repositories depend on the request-scoped ``AsyncSession``. The provider
return type is the abstract interface so callers never bind to a concrete
implementation.
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.repositories import (
    ConciliacionRepository,
    IConciliacionRepository,
    IMovimientoBancarioRepository,
    IPagoDeclaradoRepository,
    IPedidoRepository,
    MovimientoBancarioRepository,
    PagoDeclaradoRepository,
    PedidoRepository,
)

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_pedido_repository(session: SessionDep) -> IPedidoRepository:
    return PedidoRepository(session)


def get_pago_declarado_repository(
    session: SessionDep,
) -> IPagoDeclaradoRepository:
    return PagoDeclaradoRepository(session)


def get_movimiento_bancario_repository(
    session: SessionDep,
) -> IMovimientoBancarioRepository:
    return MovimientoBancarioRepository(session)


def get_conciliacion_repository(
    session: SessionDep,
) -> IConciliacionRepository:
    return ConciliacionRepository(session)


PedidoRepositoryDep = Annotated[
    IPedidoRepository, Depends(get_pedido_repository)
]
PagoDeclaradoRepositoryDep = Annotated[
    IPagoDeclaradoRepository, Depends(get_pago_declarado_repository)
]
MovimientoBancarioRepositoryDep = Annotated[
    IMovimientoBancarioRepository, Depends(get_movimiento_bancario_repository)
]
ConciliacionRepositoryDep = Annotated[
    IConciliacionRepository, Depends(get_conciliacion_repository)
]
