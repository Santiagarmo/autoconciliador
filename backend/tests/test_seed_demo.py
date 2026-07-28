"""scripts/seed_demo.py — idempotency and the reconciliation-count contract.

Runs the seeder's own async function directly (not the subprocess CLI)
against the test DB via ``real_async_session_local`` — same technique used
for the ingesta background-task tests, since ``seed_demo`` opens its own
``AsyncSessionLocal`` exactly like ``_ingest_and_reconcile`` does.
"""
from __future__ import annotations

from app.repositories.conciliacion_repository import ConciliacionRepository
from app.repositories.movimiento_bancario_repository import MovimientoBancarioRepository
from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
from app.repositories.pedido_repository import PedidoRepository
from app.services.reconciliation_service import ReconciliationService
from scripts.seed_demo import seed_demo


async def _counts(session) -> tuple[int, int, int, int]:
    pedidos = await PedidoRepository(session).list()
    pagos = await PagoDeclaradoRepository(session).list()
    movimientos = await MovimientoBancarioRepository(session).list()
    conciliaciones = await ConciliacionRepository(session).list()
    return len(pedidos), len(pagos), len(movimientos), len(conciliaciones)


async def test_seeder_es_idempotente(committing_session, real_async_session_local) -> None:
    await seed_demo(reset=True, with_users=False)
    first = await _counts(committing_session)

    await seed_demo(reset=False, with_users=False)
    second = await _counts(committing_session)

    assert first == second, "re-running the seeder without --reset must not change row counts"
    assert first == (12, 10, 12, 2), f"scenario matrix drifted: {first}"


async def test_dataset_produce_3_conciliaciones(committing_session, real_async_session_local) -> None:
    await seed_demo(reset=True, with_users=False)

    service = ReconciliationService(
        committing_session,
        PagoDeclaradoRepository(committing_session),
        MovimientoBancarioRepository(committing_session),
        ConciliacionRepository(committing_session),
        PedidoRepository(committing_session),
    )
    summary = await service.run()

    assert summary.conciliados == 3, (
        "the seeded matrix is designed so exactly pedidos 001/002/003 match "
        "(L1/L2/L3); a different count means the matrix or the matcher drifted"
    )
