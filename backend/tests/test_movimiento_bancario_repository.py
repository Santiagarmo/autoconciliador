"""Fase 2 — MovimientoBancarioRepository integration tests."""
from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError

from app.domain.enums import EstadoMovimiento
from app.repositories.movimiento_bancario_repository import (
    MovimientoBancarioRepository,
)
from tests.conftest import make_movimiento


async def test_get_by_hash(session):
    repo = MovimientoBancarioRepository(session)
    mov = await repo.add(make_movimiento(hash_idempotencia="HASH-XYZ"))

    found = await repo.get_by_hash("HASH-XYZ")
    assert found is not None
    assert found.id == mov.id
    assert await repo.get_by_hash("HASH-NO-EXISTE") is None


async def test_list_disponibles(session):
    repo = MovimientoBancarioRepository(session)
    disponible = await repo.add(make_movimiento())
    await repo.add(
        make_movimiento(estado_movimiento=EstadoMovimiento.NO_OPERATIVO)
    )

    ids = {m.id for m in await repo.list_disponibles()}
    assert disponible.id in ids
    assert all(
        m.estado_movimiento == EstadoMovimiento.DISPONIBLE
        for m in await repo.list_disponibles()
    )


async def test_list_disponibles_for_update(session):
    """for_update=True must return the same rows (SELECT ... FOR UPDATE)."""
    repo = MovimientoBancarioRepository(session)
    mov = await repo.add(make_movimiento())

    locked = await repo.list_disponibles(for_update=True)
    assert mov.id in {m.id for m in locked}


async def test_hash_idempotencia_unique(session):
    repo = MovimientoBancarioRepository(session)
    await repo.add(make_movimiento(hash_idempotencia="HASH-DUP"))

    with pytest.raises(IntegrityError):
        async with session.begin_nested():
            await repo.add(make_movimiento(hash_idempotencia="HASH-DUP"))
