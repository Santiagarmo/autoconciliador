"""Movimientos router: ingest an official bank statement PDF and auto-reconcile.

Parsing runs in ``BackgroundTasks`` (spec: never block the event loop). Because
that task runs *after* the response — when the request-scoped session is already
closed — the background function opens its OWN session via ``AsyncSessionLocal``
and never touches the request session.
"""
from __future__ import annotations

import logging
import traceback

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
    VerificacionExtractoRepositoryDep,
)
from app.db.session import AsyncSessionLocal
from app.models.movimiento_bancario import MovimientoBancario
from app.models.verificacion_extracto import VerificacionExtracto
from app.domain.enums import ResultadoVerificacion
from app.repositories import (
    ConciliacionRepository,
    MovimientoBancarioRepository,
    PagoDeclaradoRepository,
    PedidoRepository,
)
from app.schemas.movimiento_bancario import MovimientoBancarioRead
from app.schemas.verificacion_extracto import VerificacionExtractoRead
from app.services.pdf_ingestion_service import PDFIngestionService
from app.services.reconciliation_service import ReconciliationService
from app.workers.factory import get_parser

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/movimientos", tags=["movimientos"])


async def _ingest_and_reconcile(banco: str, content: bytes) -> None:
    """Background job: parse+persist the statement, then run reconciliation.

    Opens a dedicated session so it is independent of the request lifecycle.
    An exception here used to die silently in server logs — invisible to any
    client, since FastAPI already returned 202 (docs/QA-INTEGRAL-2026-07.md,
    bug #2). It's re-raised (so existing tests asserting it propagates still
    pass, and so it still surfaces in logs/process supervision) but now also
    leaves a durable, queryable ``VerificacionExtracto(resultado=ERROR)`` row
    — a NEW session, since the one that failed may be poisoned.
    """
    parser = get_parser(banco)
    try:
        async with AsyncSessionLocal() as session:
            ingestion = PDFIngestionService(session, parser)
            ingest_summary = await ingestion.ingest(content)
            verificacion = ingest_summary.verificacion
            logger.info(
                "Ingesta %s: %d insertados, %d omitidos, resultado=%s (%d hallazgos).",
                banco,
                ingest_summary.insertados,
                ingest_summary.omitidos,
                verificacion.resultado if verificacion else "N/A",
                len(verificacion.hallazgos) if verificacion else 0,
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
    except Exception:
        logger.exception("Ingesta %s falló en background.", banco)
        async with AsyncSessionLocal() as error_session:
            error_session.add(
                VerificacionExtracto(
                    banco=banco,
                    resultado=ResultadoVerificacion.ERROR,
                    error=traceback.format_exc(),
                )
            )
            await error_session.commit()
        raise


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


@router.get("/verificaciones", response_model=list[VerificacionExtractoRead])
async def listar_verificaciones(
    repo: VerificacionExtractoRepositoryDep,
    _current: CurrentUserDep,
    limit: int = 20,
) -> list[VerificacionExtracto]:
    """Últimas ingestas y su veredicto — el asesor que sube un extracto debe
    poder ver si su carga salió limpia sin tener que leer logs del servidor."""
    return list(await repo.list_recientes(limit))
