"""Movimientos router: ingest an official bank statement PDF and auto-reconcile.

Parsing runs in ``BackgroundTasks`` (spec: never block the event loop). Because
that task runs *after* the response — when the request-scoped session is already
closed — the background function opens its OWN session via ``AsyncSessionLocal``
and never touches the request session.
"""
from __future__ import annotations

import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
    status,
)

from app.api.deps import (
    CurrentUserDep,
    MovimientoBancarioRepositoryDep,
)
from app.db.session import AsyncSessionLocal
from app.models.movimiento_bancario import MovimientoBancario
from app.repositories import (
    ConciliacionRepository,
    MovimientoBancarioRepository,
    PagoDeclaradoRepository,
    PedidoRepository,
)
from app.schemas.movimiento_bancario import MovimientoBancarioRead
from app.services.pdf_ingestion_service import PDFIngestionService
from app.services.reconciliation_service import ReconciliationService
from app.workers.factory import get_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


async def _ingest_and_reconcile(banco: str, content: bytes) -> None:
    """Background job: parse+persist the statement, then run reconciliation.

    Opens a dedicated session so it is independent of the request lifecycle.
    """
    parser = get_parser(banco)
    async with AsyncSessionLocal() as session:
        ingestion = PDFIngestionService(session, parser)
        ingest_summary = await ingestion.ingest(content)
        logger.info(
            "Ingesta %s: %d insertados, %d omitidos.",
            banco,
            ingest_summary.insertados,
            ingest_summary.omitidos,
        )

        reconciler = ReconciliationService(
            session,
            pago_repo=PagoDeclaradoRepository(session),
            movimiento_repo=MovimientoBancarioRepository(session),
            conciliacion_repo=ConciliacionRepository(session),
            pedido_repo=PedidoRepository(session),
        )
        recon_summary = await reconciler.run()
        logger.info("Conciliación tras ingesta: %d cruzados.", recon_summary.conciliados)


@router.post("/ingesta", status_code=status.HTTP_202_ACCEPTED)
async def ingestar_extracto(
    background_tasks: BackgroundTasks,
    _current: CurrentUserDep,
    banco: str = Form(...),
    archivo: UploadFile = File(...),
) -> dict[str, str]:
    """Upload an official statement PDF; ingestion + reconciliation run async."""
    # Validate the bank up front so the client gets immediate feedback.
    try:
        get_parser(banco)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )

    content = await archivo.read()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="El archivo está vacío.",
        )

    background_tasks.add_task(_ingest_and_reconcile, banco, content)
    return {
        "detail": (
            f"Extracto de '{banco}' recibido. La ingesta y conciliación "
            "se procesan en segundo plano."
        )
    }


@router.get("", response_model=list[MovimientoBancarioRead])
async def listar_movimientos(
    repo: MovimientoBancarioRepositoryDep,
    _current: CurrentUserDep,
) -> list[MovimientoBancario]:
    return list(await repo.list())
