"""Fase 3 — ReconciliationService: matching, UoW state transitions."""
from __future__ import annotations

from decimal import Decimal

from app.domain.enums import (
    EstadoMovimiento,
    EstadoPago,
    EstadoPedido,
)
from app.repositories.conciliacion_repository import ConciliacionRepository
from app.repositories.movimiento_bancario_repository import (
    MovimientoBancarioRepository,
)
from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
from app.repositories.pedido_repository import PedidoRepository
from app.services.reconciliation_service import ReconciliationService
from tests.conftest import make_movimiento, make_pago, make_pedido


def _service(session) -> ReconciliationService:
    return ReconciliationService(
        session,
        PagoDeclaradoRepository(session),
        MovimientoBancarioRepository(session),
        ConciliacionRepository(session),
        PedidoRepository(session),
    )


async def _setup(session, *, pago_kwargs=None, mov_kwargs=None, pedido_kwargs=None):
    pedido = await PedidoRepository(session).add(make_pedido(**(pedido_kwargs or {})))
    pago = await PagoDeclaradoRepository(session).add(
        make_pago(pedido.id, **(pago_kwargs or {}))
    )
    mov = await MovimientoBancarioRepository(session).add(
        make_movimiento(**(mov_kwargs or {}))
    )
    return pedido, pago, mov


async def test_match_level1_reference(session):
    pedido, pago, mov = await _setup(
        session,
        pago_kwargs=dict(numero_referencia="REF98765"),
        mov_kwargs=dict(descripcion_concepto="TRANSF REF98765 EXITOSA"),
    )
    summary = await _service(session).run()

    assert summary.conciliados == 1
    assert pago.estado_pago == EstadoPago.CONCILIADO
    assert mov.estado_movimiento == EstadoMovimiento.CONCILIADO
    assert pedido.estado_pedido == EstadoPedido.LISTO_PARA_DESPACHO

    conc = await ConciliacionRepository(session).get_by_pago(pago.id)
    assert conc is not None
    assert conc.movimiento_bancario_id == mov.id


async def test_match_level2_codigo_pedido(session):
    pedido, pago, mov = await _setup(
        session,
        pedido_kwargs=dict(codigo_pedido="PED-55501"),
        pago_kwargs=dict(numero_referencia="NOMATCH"),
        mov_kwargs=dict(descripcion_concepto="ABONO PED-55501 CLIENTE"),
    )
    summary = await _service(session).run()

    assert summary.conciliados == 1
    assert pedido.estado_pedido == EstadoPedido.LISTO_PARA_DESPACHO


async def test_match_level3_ultimos_4(session):
    pedido, pago, mov = await _setup(
        session,
        pago_kwargs=dict(numero_referencia="NOMATCH", ultimos_4_digitos="4321"),
        mov_kwargs=dict(descripcion_concepto="TRANSFERENCIA CEL 4321"),
    )
    summary = await _service(session).run()

    assert summary.conciliados == 1
    assert pago.estado_pago == EstadoPago.CONCILIADO


async def test_amount_only_is_not_a_match(session):
    """Equal amount but zero metadata overlap → no reconciliation (fraud guard)."""
    pedido, pago, mov = await _setup(
        session,
        pago_kwargs=dict(numero_referencia="XXXX"),
        mov_kwargs=dict(descripcion_concepto="OTRA COSA SIN RELACION"),
    )
    summary = await _service(session).run()

    assert summary.conciliados == 0
    assert pago.estado_pago == EstadoPago.REGISTRADO
    assert mov.estado_movimiento == EstadoMovimiento.DISPONIBLE
    assert pedido.estado_pedido == EstadoPedido.PENDIENTE_PAGO


async def test_amount_mismatch_is_not_a_match(session):
    pedido, pago, mov = await _setup(
        session,
        pago_kwargs=dict(
            numero_referencia="REF111", monto_declarado=Decimal("100000.00")
        ),
        mov_kwargs=dict(
            descripcion_concepto="REF111", monto_real=Decimal("99000.00")
        ),
    )
    summary = await _service(session).run()
    assert summary.conciliados == 0


async def test_already_conciliado_movement_not_reused(session):
    pedido, pago, mov = await _setup(
        session,
        pago_kwargs=dict(numero_referencia="REF777"),
        mov_kwargs=dict(
            descripcion_concepto="REF777",
            estado_movimiento=EstadoMovimiento.CONCILIADO,
        ),
    )
    summary = await _service(session).run()

    assert summary.conciliados == 0
    assert pago.estado_pago == EstadoPago.REGISTRADO
