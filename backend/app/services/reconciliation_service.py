"""ReconciliationService — match declared payments to bank movements.

Servicio 2 del spec. Cruza ``pagos_declarados`` en estado REGISTRADO contra
``movimientos_bancarios`` DISPONIBLE. Match = monto exacto Y al menos una
condición de metadatos (referencia / código de pedido / últimos 4 dígitos).
Usa ``with_for_update(skip_locked=True)`` para concurrencia y aplica cada
cruce como una unidad atómica (Unit of Work).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from app.domain.enums import (
    EstadoMovimiento,
    EstadoPago,
    EstadoPedido,
    TipoConciliacion,
)
from app.models.conciliacion import Conciliacion
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.repositories.conciliacion_repository import IConciliacionRepository
from app.repositories.movimiento_bancario_repository import (
    IMovimientoBancarioRepository,
)
from app.repositories.pago_declarado_repository import IPagoDeclaradoRepository
from app.repositories.pedido_repository import IPedidoRepository

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReconSummary:
    conciliados: int


def _contains(needle: str | None, haystack: str | None) -> bool:
    """Case-insensitive substring check; False if either side is empty."""
    if not needle or not haystack:
        return False
    return needle.upper() in haystack.upper()


class ReconciliationService:
    def __init__(
        self,
        session,
        pago_repo: IPagoDeclaradoRepository,
        movimiento_repo: IMovimientoBancarioRepository,
        conciliacion_repo: IConciliacionRepository,
        pedido_repo: IPedidoRepository,
    ) -> None:
        self.session = session
        self.pago_repo = pago_repo
        self.movimiento_repo = movimiento_repo
        self.conciliacion_repo = conciliacion_repo
        self.pedido_repo = pedido_repo

    async def _matches(
        self, pago: PagoDeclarado, movimiento: MovimientoBancario
    ) -> bool:
        # Amount must match exactly first — cheapest and mandatory filter.
        if pago.monto_declarado != movimiento.monto_real:
            return False

        # L1 (fuerte): payment reference inside bank reference or description.
        if _contains(pago.numero_referencia, movimiento.numero_referencia) or _contains(
            pago.numero_referencia, movimiento.descripcion_concepto
        ):
            return True

        # L2 (fuerte): order code inside the bank description.
        pedido = await self.pedido_repo.get(pago.pedido_id)
        if pedido is not None and _contains(
            pedido.codigo_pedido, movimiento.descripcion_concepto
        ):
            return True

        # L3 (medio): last 4 phone digits inside the bank description.
        if _contains(pago.ultimos_4_digitos, movimiento.descripcion_concepto):
            return True

        return False

    async def run(self) -> ReconSummary:
        pagos = await self.pago_repo.list_by_estado(EstadoPago.REGISTRADO)
        # Lock available movements so concurrent runs never grab the same row.
        movimientos = list(
            await self.movimiento_repo.list_disponibles(for_update=True)
        )

        conciliados = 0
        for pago in pagos:
            match = None
            for movimiento in movimientos:
                if await self._matches(pago, movimiento):
                    match = movimiento
                    break
            if match is None:
                continue

            try:
                # Unit of Work: the four writes are one atomic savepoint.
                async with self.session.begin_nested():
                    self.session.add(
                        Conciliacion(
                            pago_declarado_id=pago.id,
                            movimiento_bancario_id=match.id,
                            tipo_conciliacion=TipoConciliacion.AUTOMATICA,
                        )
                    )
                    pago.estado_pago = EstadoPago.CONCILIADO
                    match.estado_movimiento = EstadoMovimiento.CONCILIADO
                    pedido = await self.pedido_repo.get(pago.pedido_id)
                    if pedido is not None:
                        pedido.estado_pedido = EstadoPedido.LISTO_PARA_DESPACHO
            except IntegrityError:
                # Race: this payment/movement was reconciled elsewhere. Skip.
                logger.info(
                    "Conciliación en carrera omitida (pago=%s, movimiento=%s)",
                    pago.id,
                    match.id,
                )
                continue

            # Consume the movement so it is not reused in this run.
            movimientos.remove(match)
            conciliados += 1

        await self.session.commit()
        return ReconSummary(conciliados=conciliados)
