"""Fase 2 — PedidoRepository integration tests."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.repositories.pedido_repository import PedidoRepository
from tests.conftest import make_pedido


async def test_add_and_get(session):
    repo = PedidoRepository(session)
    pedido = await repo.add(make_pedido())

    fetched = await repo.get(pedido.id)
    assert fetched is not None
    assert fetched.id == pedido.id


async def test_get_by_codigo(session):
    repo = PedidoRepository(session)
    pedido = await repo.add(make_pedido(codigo_pedido="PED-CODIGO-1"))

    found = await repo.get_by_codigo("PED-CODIGO-1")
    assert found is not None
    assert found.id == pedido.id

    assert await repo.get_by_codigo("PED-NO-EXISTE") is None


async def test_codigo_pedido_unique(session):
    repo = PedidoRepository(session)
    await repo.add(make_pedido(codigo_pedido="PED-DUP"))

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repo.add(make_pedido(codigo_pedido="PED-DUP"))
