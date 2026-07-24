"""Conciliaciones router: manual reconciliation trigger and audit listing."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import (
    ConciliacionRepositoryDep,
    CurrentUserDep,
    ReconciliationServiceDep,
    require_role,
)
from app.domain.enums import RolUsuario
from app.models.conciliacion import Conciliacion
from app.schemas.conciliacion import ConciliacionRead, ReconSummaryRead

router = APIRouter(prefix="/conciliaciones", tags=["conciliaciones"])


@router.post(
    "/run",
    response_model=ReconSummaryRead,
    dependencies=[Depends(require_role(RolUsuario.AUDITOR))],
)
async def ejecutar_conciliacion(
    service: ReconciliationServiceDep,
) -> ReconSummaryRead:
    """Force a reconciliation run. Restricted to auditors."""
    summary = await service.run()
    return ReconSummaryRead(conciliados=summary.conciliados)


@router.get("", response_model=list[ConciliacionRead])
async def listar_conciliaciones(
    repo: ConciliacionRepositoryDep,
    _current: CurrentUserDep,
) -> list[Conciliacion]:
    return list(await repo.list())
