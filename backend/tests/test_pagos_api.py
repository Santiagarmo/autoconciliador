"""Fase 4 — Pagos API: registration and anti-fraud duplicate rejection."""
from __future__ import annotations

from uuid import uuid4

from app.domain.enums import RolUsuario


async def _crear_pedido(client) -> str:
    payload = {
        "codigo_pedido": f"PED-{uuid4().hex[:8].upper()}",
        "cliente_whatsapp": "+573001112233",
        "monto_total": "100000.00",
    }
    resp = await client.post("/api/pedidos", json=payload)
    return resp.json()["id"]


async def test_registrar_pago(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    pedido_id = await _crear_pedido(client)
    pago = {
        "pedido_id": pedido_id,
        "banco_destino": "BANCOLOMBIA",
        "monto_declarado": "100000.00",
        "numero_referencia": f"REF-{uuid4().hex[:10].upper()}",
        "ultimos_4_digitos": "1234",
    }
    resp = await client.post("/api/pagos", json=pago)
    assert resp.status_code == 201
    assert resp.json()["estado_pago"] == "REGISTRADO"


async def test_comprobante_reutilizado_409(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    pedido_id = await _crear_pedido(client)
    ref = f"REF-{uuid4().hex[:10].upper()}"
    pago = {
        "pedido_id": pedido_id,
        "banco_destino": "BANCOLOMBIA",
        "monto_declarado": "100000.00",
        "numero_referencia": ref,
    }
    assert (await client.post("/api/pagos", json=pago)).status_code == 201
    dup = await client.post("/api/pagos", json=pago)
    assert dup.status_code == 409


async def test_pago_pedido_inexistente_404(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    pago = {
        "pedido_id": str(uuid4()),
        "banco_destino": "BANCOLOMBIA",
        "monto_declarado": "100000.00",
        "numero_referencia": f"REF-{uuid4().hex[:10].upper()}",
    }
    resp = await client.post("/api/pagos", json=pago)
    assert resp.status_code == 404
