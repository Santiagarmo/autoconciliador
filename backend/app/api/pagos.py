"""Pagos router: advisor registers a declared payment against an order.

The receipt arrives as a WhatsApp image; the advisor reads it and types the
reference here. The DB constraint ``uq_banco_referencia`` blocks re-using a
receipt (same bank + reference) — surfaced as HTTP 409.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    CurrentUserDep,
    PagoDeclaradoRepositoryDep,
    PedidoRepositoryDep,
    SessionDep,
)
from app.models.pago_declarado import PagoDeclarado
from app.schemas.pago_declarado import PagoDeclaradoCreate, PagoDeclaradoRead

router = APIRouter(prefix="/pagos", tags=["pagos"])


@router.post(
    "", response_model=PagoDeclaradoRead, status_code=status.HTTP_201_CREATED
)
async def registrar_pago(
    payload: PagoDeclaradoCreate,
    repo: PagoDeclaradoRepositoryDep,
    pedido_repo: PedidoRepositoryDep,
    session: SessionDep,
    _current: CurrentUserDep,
) -> PagoDeclarado:
    if await pedido_repo.get(payload.pedido_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="El pedido asociado no existe.",
        )

    pago = PagoDeclarado(
        pedido_id=payload.pedido_id,
        banco_destino=payload.banco_destino,
        monto_declarado=payload.monto_declarado,
        numero_referencia=payload.numero_referencia,
        ultimos_4_digitos=payload.ultimos_4_digitos,
    )
    try:
        await repo.add(pago)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Comprobante ya registrado: la referencia "
                f"'{payload.numero_referencia}' para el banco "
                f"'{payload.banco_destino}' ya existe."
            ),
        )
    return pago


@router.get("", response_model=list[PagoDeclaradoRead])
async def listar_pagos(
    repo: PagoDeclaradoRepositoryDep,
    _current: CurrentUserDep,
) -> list[PagoDeclarado]:
    return list(await repo.list())
