"""Pedidos router: order registration and state management."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import CurrentUserDep, PedidoRepositoryDep, SessionDep
from app.domain.enums import EstadoPedido, RolUsuario
from app.models.pedido import Pedido
from app.schemas.pedido import PedidoCreate, PedidoRead, PedidoUpdate

router = APIRouter(prefix="/pedidos", tags=["pedidos"])


@router.post("", response_model=PedidoRead, status_code=status.HTTP_201_CREATED)
async def crear_pedido(
    payload: PedidoCreate,
    repo: PedidoRepositoryDep,
    session: SessionDep,
    _current: CurrentUserDep,
) -> Pedido:
    pedido = Pedido(
        codigo_pedido=payload.codigo_pedido,
        cliente_whatsapp=payload.cliente_whatsapp,
        monto_total=payload.monto_total,
    )
    try:
        await repo.add(pedido)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un pedido con código '{payload.codigo_pedido}'.",
        )
    return pedido


@router.get("", response_model=list[PedidoRead])
async def listar_pedidos(
    repo: PedidoRepositoryDep,
    _current: CurrentUserDep,
    estado: EstadoPedido | None = Query(default=None),
) -> list[Pedido]:
    pedidos = await repo.list()
    if estado is not None:
        pedidos = [p for p in pedidos if p.estado_pedido == estado]
    return list(pedidos)


@router.get("/{pedido_id}", response_model=PedidoRead)
async def obtener_pedido(
    pedido_id: UUID,
    repo: PedidoRepositoryDep,
    _current: CurrentUserDep,
) -> Pedido:
    pedido = await repo.get(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado."
        )
    return pedido


@router.patch("/{pedido_id}", response_model=PedidoRead)
async def actualizar_pedido(
    pedido_id: UUID,
    payload: PedidoUpdate,
    repo: PedidoRepositoryDep,
    session: SessionDep,
    current: CurrentUserDep,
) -> Pedido:
    pedido = await repo.get(pedido_id)
    if pedido is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Pedido no encontrado."
        )

    # LISTO_PARA_DESPACHO is set by the reconciliation engine (or an auditor
    # doing a manual match); DESPACHADO is the physical dispatch decision.
    # Advisors must never flip either — that would bypass the anti-fraud
    # crosscheck this whole system exists for.
    _ESTADOS_RESTRINGIDOS = {
        EstadoPedido.LISTO_PARA_DESPACHO,
        EstadoPedido.DESPACHADO,
    }
    if (
        payload.estado_pedido in _ESTADOS_RESTRINGIDOS
        and current.rol != RolUsuario.AUDITOR
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Solo un auditor puede liberar o despachar un pedido "
                f"({payload.estado_pedido.value})."
            ),
        )

    if payload.cliente_whatsapp is not None:
        pedido.cliente_whatsapp = payload.cliente_whatsapp
    if payload.estado_pedido is not None:
        pedido.estado_pedido = payload.estado_pedido

    await session.commit()
    await session.refresh(pedido)
    return pedido
