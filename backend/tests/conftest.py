"""Pytest fixtures: DB session isolated per test via an outer transaction.

Each test runs against the real Postgres (migrated schema) but inside an outer
transaction that is rolled back at teardown, so tests never persist data and
don't fight each other. ``join_transaction_mode="create_savepoint"`` makes the
session use a SAVEPOINT as its root, so service code calling ``commit()`` /
``begin_nested()`` releases savepoints instead of the real transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

import app.models  # noqa: F401 — register ORM metadata
from app.core.config import settings
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.models.pedido import Pedido
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.workers.base import BankParserStrategy


@pytest_asyncio.fixture
async def engine():
    eng = create_async_engine(settings.DATABASE_URL)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as s:
            yield s
        await conn.rollback()


# --- Object factories (unique data so tests never collide) -----------------

def make_pedido(**overrides) -> Pedido:
    data = dict(
        codigo_pedido=f"PED-{uuid4().hex[:8].upper()}",
        cliente_whatsapp="+573001112233",
        monto_total=Decimal("100000.00"),
    )
    data.update(overrides)
    return Pedido(**data)


def make_pago(pedido_id, **overrides) -> PagoDeclarado:
    data = dict(
        pedido_id=pedido_id,
        banco_destino="NEQUI",
        monto_declarado=Decimal("100000.00"),
        numero_referencia=f"REF{uuid4().hex[:10].upper()}",
        ultimos_4_digitos=None,
    )
    data.update(overrides)
    return PagoDeclarado(**data)


def make_movimiento(**overrides) -> MovimientoBancario:
    data = dict(
        banco_origen="NEQUI",
        fecha_movimiento=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        monto_real=Decimal("100000.00"),
        saldo_posterior=Decimal("500000.00"),
        numero_referencia=None,
        descripcion_concepto="TRANSFERENCIA RECIBIDA",
        hash_idempotencia=uuid4().hex,
    )
    data.update(overrides)
    return MovimientoBancario(**data)


# --- Test-only parser strategy (no real PDF needed) ------------------------

class StubParser(BankParserStrategy):
    """Returns a fixed list of parsed rows — decouples ingestion from PDFs."""

    banco = "STUB"

    def __init__(self, rows: list[MovimientoBancarioParsed]) -> None:
        self._rows = rows

    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        return list(self._rows)
