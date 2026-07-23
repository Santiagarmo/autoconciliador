"""Fase 2 — ConciliacionRepository integration tests."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.conciliacion import Conciliacion
from app.repositories.conciliacion_repository import ConciliacionRepository
from app.repositories.movimiento_bancario_repository import (
    MovimientoBancarioRepository,
)
from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
from app.repositories.pedido_repository import PedidoRepository
from tests.conftest import make_movimiento, make_pago, make_pedido


async def _pago_y_movimiento(session):
    pedido = await PedidoRepository(session).add(make_pedido())
    pago = await PagoDeclaradoRepository(session).add(make_pago(pedido.id))
    mov = await MovimientoBancarioRepository(session).add(make_movimiento())
    return pago, mov


async def test_add_and_get_by_pago(session):
    repo = ConciliacionRepository(session)
    pago, mov = await _pago_y_movimiento(session)
    await repo.add(
        Conciliacion(pago_declarado_id=pago.id, movimiento_bancario_id=mov.id)
    )

    found = await repo.get_by_pago(pago.id)
    assert found is not None
    assert found.movimiento_bancario_id == mov.id


async def test_pago_reconciled_once(session):
    """UNIQUE FK: a payment cannot appear in two reconciliations."""
    repo = ConciliacionRepository(session)
    pago, mov = await _pago_y_movimiento(session)
    otro_mov = await MovimientoBancarioRepository(session).add(make_movimiento())
    await repo.add(
        Conciliacion(pago_declarado_id=pago.id, movimiento_bancario_id=mov.id)
    )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repo.add(
                Conciliacion(
                    pago_declarado_id=pago.id,
                    movimiento_bancario_id=otro_mov.id,
                )
            )


async def test_movimiento_reconciled_once(session):
    """UNIQUE FK: a bank movement cannot appear in two reconciliations."""
    repo = ConciliacionRepository(session)
    pago, mov = await _pago_y_movimiento(session)
    pedido2 = await PedidoRepository(session).add(make_pedido())
    otro_pago = await PagoDeclaradoRepository(session).add(make_pago(pedido2.id))
    await repo.add(
        Conciliacion(pago_declarado_id=pago.id, movimiento_bancario_id=mov.id)
    )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repo.add(
                Conciliacion(
                    pago_declarado_id=otro_pago.id,
                    movimiento_bancario_id=mov.id,
                )
            )
