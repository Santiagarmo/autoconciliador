"""Fase 2 — PagoDeclaradoRepository integration tests."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import EstadoPago
from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
from app.repositories.pedido_repository import PedidoRepository
from tests.conftest import make_pago, make_pedido


async def _pedido_id(session):
    pedido = await PedidoRepository(session).add(make_pedido())
    return pedido.id


async def test_get_by_banco_referencia(session):
    repo = PagoDeclaradoRepository(session)
    pid = await _pedido_id(session)
    await repo.add(
        make_pago(pid, banco_destino="NEQUI", numero_referencia="REF-ABC")
    )

    found = await repo.get_by_banco_referencia("NEQUI", "REF-ABC")
    assert found is not None
    assert found.numero_referencia == "REF-ABC"

    # Same reference, different bank → distinct payment, not found.
    assert await repo.get_by_banco_referencia("BANCOLOMBIA", "REF-ABC") is None


async def test_list_by_estado(session):
    repo = PagoDeclaradoRepository(session)
    pid = await _pedido_id(session)
    await repo.add(make_pago(pid, numero_referencia="REF-REG"))

    registrados = await repo.list_by_estado(EstadoPago.REGISTRADO)
    assert any(p.numero_referencia == "REF-REG" for p in registrados)
    assert all(p.estado_pago == EstadoPago.REGISTRADO for p in registrados)


async def test_unique_banco_referencia_anti_reuse(session):
    """Core anti-fraud rule: (banco_destino, numero_referencia) is unique."""
    repo = PagoDeclaradoRepository(session)
    pid = await _pedido_id(session)
    await repo.add(
        make_pago(pid, banco_destino="NEQUI", numero_referencia="REF-DUP")
    )

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repo.add(
                make_pago(pid, banco_destino="NEQUI", numero_referencia="REF-DUP")
            )
