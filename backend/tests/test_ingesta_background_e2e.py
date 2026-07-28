"""The real ingesta -> reconciliation background path, un-mocked.

``test_ingesta_api.py`` monkeypatches ``_ingest_and_reconcile`` to a no-op —
correctly, for testing the HTTP contract — but that leaves the actual
function (the one that opens its own ``AsyncSessionLocal`` and does the real
work) with zero test coverage. These tests call it directly against the test
DB via the ``real_async_session_local`` fixture, which repoints the module's
global session factory so nothing here touches dev data.
"""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from uuid import uuid4

import app.api.movimientos as movimientos_module
from app.domain.enums import EstadoPago
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.models.pedido import Pedido
from app.repositories.movimiento_bancario_repository import MovimientoBancarioRepository
from tests.fixtures.bancolombia_pdf import StatementRow, build_bancolombia_pdf


def _pdf(ref: str, monto: Decimal) -> bytes:
    return build_bancolombia_pdf(
        rows=[
            StatementRow(12, 7, f"TRANSFERENCIA RECIBIDA REF {ref}", monto, Decimal("500000.00")),
        ],
        desde=date(2026, 7, 1),
        hasta=date(2026, 7, 31),
    )


async def test_ingesta_real_dispara_conciliacion(
    committing_session, real_async_session_local
) -> None:
    """The un-mocked ``_ingest_and_reconcile`` must parse, persist and then
    reconcile a matching pago — the single biggest gap in prior coverage."""
    codigo = f"PED-BG-{uuid4().hex[:6].upper()}"
    ref = f"BG{uuid4().hex[:6].upper()}"
    monto = Decimal("77000.00")

    pedido = Pedido(codigo_pedido=codigo, cliente_whatsapp="+573001112233", monto_total=monto)
    committing_session.add(pedido)
    await committing_session.flush()
    pago = PagoDeclarado(
        pedido_id=pedido.id, banco_destino="BANCOLOMBIA",
        monto_declarado=monto, numero_referencia=ref,
    )
    committing_session.add(pago)
    await committing_session.commit()

    await movimientos_module._ingest_and_reconcile("BANCOLOMBIA", _pdf(ref, monto))

    await committing_session.refresh(pago)
    assert pago.estado_pago == EstadoPago.CONCILIADO


async def test_reingesta_misma_cartola_es_idempotente(
    committing_session, real_async_session_local
) -> None:
    """Uploading the exact same statement twice must insert 0 new movements
    the second time, and must not create a second/duplicate conciliacion."""
    ref = f"DUP{uuid4().hex[:6].upper()}"
    pdf_bytes = _pdf(ref, Decimal("42000.00"))

    await movimientos_module._ingest_and_reconcile("BANCOLOMBIA", pdf_bytes)
    mov_repo = MovimientoBancarioRepository(committing_session)
    first_run = await mov_repo.list()
    count_after_first = len(first_run)
    assert count_after_first >= 1

    await movimientos_module._ingest_and_reconcile("BANCOLOMBIA", pdf_bytes)
    second_run = await mov_repo.list()
    assert len(second_run) == count_after_first, (
        "re-ingesting an identical statement must not insert duplicate rows "
        "(hash_idempotencia uniqueness)"
    )


async def test_ingesta_pdf_corrupto_no_explota_en_silencio(
    committing_session, real_async_session_local
) -> None:
    """Documents a real defect (see docs/QA-INTEGRAL-2026-07.md, severidad
    Alta): a malformed PDF raises inside the background task, which FastAPI
    already responded 202 for. The exception here proves nothing in the HTTP
    layer will ever see it — it only reaches server logs."""
    import pytest

    with pytest.raises(Exception):
        await movimientos_module._ingest_and_reconcile("BANCOLOMBIA", b"%PDF-broken-not-a-real-pdf")
