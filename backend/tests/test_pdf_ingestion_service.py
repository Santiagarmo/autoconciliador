"""Fase 3 — PDFIngestionService: hash idempotency, skip-duplicates."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from app.domain.enums import EstadoMovimiento
from app.repositories.movimiento_bancario_repository import (
    MovimientoBancarioRepository,
)
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.services.pdf_ingestion_service import PDFIngestionService
from tests.conftest import StubParser


def _row(descripcion: str, monto="100000.00", ref=None) -> MovimientoBancarioParsed:
    return MovimientoBancarioParsed(
        banco_origen="NEQUI",
        fecha_movimiento=datetime(2026, 7, 20, 9, 0, tzinfo=timezone.utc),
        monto_real=Decimal(monto),
        saldo_posterior=Decimal("900000.00"),
        numero_referencia=ref,
        descripcion_concepto=descripcion,
    )


async def test_first_ingest_inserts_all(session):
    rows = [_row("PAGO PEDIDO PED-1"), _row("PAGO PEDIDO PED-2")]
    svc = PDFIngestionService(session, StubParser(rows))

    summary = await svc.ingest(b"pdf-bytes")
    assert summary.insertados == 2
    assert summary.omitidos == 0

    disponibles = await MovimientoBancarioRepository(session).list_disponibles()
    assert len(disponibles) == 2
    assert all(
        m.estado_movimiento == EstadoMovimiento.DISPONIBLE for m in disponibles
    )


async def test_reingest_is_idempotent(session):
    rows = [_row("PAGO PEDIDO PED-1"), _row("PAGO PEDIDO PED-2")]

    first = await PDFIngestionService(session, StubParser(rows)).ingest(b"x")
    assert first.insertados == 2

    # Same statement re-ingested → nothing new, all skipped.
    second = await PDFIngestionService(session, StubParser(rows)).ingest(b"x")
    assert second.insertados == 0
    assert second.omitidos == 2

    disponibles = await MovimientoBancarioRepository(session).list_disponibles()
    assert len(disponibles) == 2


async def test_duplicate_row_within_batch_skipped(session):
    dup = _row("PAGO DUPLICADO")
    rows = [dup, _row("PAGO UNICO"), dup]
    summary = await PDFIngestionService(session, StubParser(rows)).ingest(b"x")

    # 2 unique hashes inserted, the repeated row skipped — run never aborts.
    assert summary.insertados == 2
    assert summary.omitidos == 1


async def test_normalization_collapses_whitespace(session):
    # Same content, different spacing/case → same hash → deduped.
    rows = [_row("PAGO   recibido"), _row("pago Recibido")]
    summary = await PDFIngestionService(session, StubParser(rows)).ingest(b"x")
    assert summary.insertados == 1
    assert summary.omitidos == 1
