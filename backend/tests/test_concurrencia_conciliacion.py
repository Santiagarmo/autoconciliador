"""Dos corridas concurrentes de ReconciliationService no deben duplicar.

``ReconciliationService.run()`` usa ``list_disponibles(for_update=True)`` ->
``SELECT ... FOR UPDATE SKIP LOCKED``, precisamente para que dos ejecuciones
simultáneas (ej. dos requests a ``POST /conciliaciones/run``, o una ingesta en
background solapada con un run manual) no concilien el mismo pago dos veces.
Los tests de servicio existentes (``test_reconciliation_service.py``) sólo
prueban esto con un ``StubParser`` de una corrida; aquí se lanzan dos
instancias reales, cada una con su propia sesión, contra el mismo par
pago/movimiento.
"""
from __future__ import annotations

import asyncio
from decimal import Decimal
from uuid import uuid4

from app.domain.enums import EstadoPago
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.models.pedido import Pedido
from app.repositories.conciliacion_repository import ConciliacionRepository
from app.repositories.movimiento_bancario_repository import MovimientoBancarioRepository
from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
from app.repositories.pedido_repository import PedidoRepository
from app.services.pdf_ingestion_service import compute_hash
from app.services.reconciliation_service import ReconciliationService


def _service_for(session) -> ReconciliationService:
    return ReconciliationService(
        session,
        PagoDeclaradoRepository(session),
        MovimientoBancarioRepository(session),
        ConciliacionRepository(session),
        PedidoRepository(session),
    )


async def test_dos_runs_concurrentes_no_duplican(committing_session, real_async_session_local) -> None:
    """Two ReconciliationService instances, each on its own AsyncSessionLocal
    session, racing against one shared matching pago+movimiento. Exactly one
    must win; the other must find nothing left (SKIP LOCKED) or hit the
    UNIQUE-FK IntegrityError guard — either way, total conciliados == 1."""
    ref = f"CONC{uuid4().hex[:8].upper()}"
    monto = Decimal("64000.00")

    pedido = Pedido(
        codigo_pedido=f"PED-CONC-{uuid4().hex[:6].upper()}",
        cliente_whatsapp="+573001112233",
        monto_total=monto,
    )
    committing_session.add(pedido)
    await committing_session.flush()

    pago = PagoDeclarado(
        pedido_id=pedido.id, banco_destino="BANCOLOMBIA",
        monto_declarado=monto, numero_referencia=ref,
    )
    committing_session.add(pago)

    descripcion = f"TRANSFERENCIA RECIBIDA REF {ref}"
    from app.services.pdf_ingestion_service import _normalize_descripcion
    import datetime as _dt
    fecha_mov = _dt.datetime(2026, 7, 20, 12, 0, tzinfo=_dt.timezone.utc)
    saldo = Decimal("900000.00")
    mov = MovimientoBancario(
        banco_origen="BANCOLOMBIA",
        fecha_movimiento=fecha_mov,
        monto_real=monto,
        saldo_posterior=saldo,
        descripcion_concepto=descripcion,
        hash_idempotencia=compute_hash(
            fecha_movimiento=fecha_mov,
            monto_real=monto,
            saldo_posterior=saldo,
            descripcion_limpia=_normalize_descripcion(descripcion),
        ),
    )
    committing_session.add(mov)
    await committing_session.commit()

    # Two independent sessions from the (test-DB-repointed) global factory —
    # simulates two separate requests/background tasks racing each other.
    from app.db.session import AsyncSessionLocal as TestAsyncSessionLocal

    async def _run_once() -> int:
        async with TestAsyncSessionLocal() as s:
            summary = await _service_for(s).run()
            return summary.conciliados

    results = await asyncio.gather(_run_once(), _run_once())

    assert sum(results) == 1, (
        f"exactamente una corrida debe conciliar (resultados: {results})"
    )

    await committing_session.refresh(pago)
    assert pago.estado_pago == EstadoPago.CONCILIADO

    conc_repo = ConciliacionRepository(committing_session)
    conciliaciones = await conc_repo.list()
    matching = [c for c in conciliaciones if c.pago_declarado_id == pago.id]
    assert len(matching) == 1, "no debe existir más de una conciliacion para el mismo pago"
