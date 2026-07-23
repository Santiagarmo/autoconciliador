"""Fase 2 — Pydantic schema validation (no DB)."""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.domain.enums import EstadoPedido
from app.schemas.pago_declarado import PagoDeclaradoCreate
from app.schemas.pedido import PedidoCreate, PedidoRead


def test_monto_must_be_positive():
    with pytest.raises(ValidationError):
        PedidoCreate(
            codigo_pedido="PED-1", cliente_whatsapp="+57300", monto_total=Decimal("0")
        )


def test_ultimos_4_digitos_max_length():
    pid = uuid4()
    with pytest.raises(ValidationError):
        PagoDeclaradoCreate(
            pedido_id=pid,
            banco_destino="NEQUI",
            monto_declarado=Decimal("1000"),
            numero_referencia="REF",
            ultimos_4_digitos="12345",  # 5 chars → invalid
        )
    # 4 chars is accepted
    ok = PagoDeclaradoCreate(
        pedido_id=pid,
        banco_destino="NEQUI",
        monto_declarado=Decimal("1000"),
        numero_referencia="REF",
        ultimos_4_digitos="1234",
    )
    assert ok.ultimos_4_digitos == "1234"


def test_pedido_read_from_attributes():
    class Row:
        id = uuid4()
        codigo_pedido = "PED-9"
        cliente_whatsapp = "+57300"
        monto_total = Decimal("5000.00")
        estado_pedido = EstadoPedido.PENDIENTE_PAGO
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)

    dto = PedidoRead.model_validate(Row())
    assert dto.codigo_pedido == "PED-9"
    assert dto.estado_pedido == EstadoPedido.PENDIENTE_PAGO
