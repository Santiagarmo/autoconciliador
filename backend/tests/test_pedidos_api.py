"""Fase 4 — Pedidos API: CRUD and auditor-only dispatch."""
from __future__ import annotations

from uuid import uuid4

from app.domain.enums import RolUsuario


def _pedido_payload() -> dict:
    return {
        "codigo_pedido": f"PED-{uuid4().hex[:8].upper()}",
        "cliente_whatsapp": "+573001112233",
        "monto_total": "100000.00",
    }


async def test_crear_y_listar_pedido(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    created = await client.post("/api/pedidos", json=_pedido_payload())
    assert created.status_code == 201
    pedido_id = created.json()["id"]
    assert created.json()["estado_pedido"] == "PENDIENTE_PAGO"

    listed = await client.get("/api/pedidos")
    assert listed.status_code == 200
    assert any(p["id"] == pedido_id for p in listed.json())


async def test_codigo_duplicado_409(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    payload = _pedido_payload()
    assert (await client.post("/api/pedidos", json=payload)).status_code == 201
    dup = await client.post("/api/pedidos", json=payload)
    assert dup.status_code == 409


async def test_asesor_no_puede_despachar(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    created = await client.post("/api/pedidos", json=_pedido_payload())
    pedido_id = created.json()["id"]

    patch = await client.patch(
        f"/api/pedidos/{pedido_id}", json={"estado_pedido": "DESPACHADO"}
    )
    assert patch.status_code == 403


async def test_asesor_no_puede_liberar_para_despacho(client, as_role) -> None:
    """An advisor flipping estado_pedido to LISTO_PARA_DESPACHO would bypass
    the reconciliation engine — the core anti-fraud check. Must be blocked
    just like DESPACHADO."""
    as_role(RolUsuario.ASESOR)
    created = await client.post("/api/pedidos", json=_pedido_payload())
    pedido_id = created.json()["id"]

    patch = await client.patch(
        f"/api/pedidos/{pedido_id}",
        json={"estado_pedido": "LISTO_PARA_DESPACHO"},
    )
    assert patch.status_code == 403


async def test_auditor_puede_liberar_para_despacho(client, as_role) -> None:
    as_role(RolUsuario.AUDITOR)
    created = await client.post("/api/pedidos", json=_pedido_payload())
    pedido_id = created.json()["id"]

    patch = await client.patch(
        f"/api/pedidos/{pedido_id}",
        json={"estado_pedido": "LISTO_PARA_DESPACHO"},
    )
    assert patch.status_code == 200
    assert patch.json()["estado_pedido"] == "LISTO_PARA_DESPACHO"


async def test_auditor_puede_despachar(client, as_role) -> None:
    as_role(RolUsuario.AUDITOR)
    created = await client.post("/api/pedidos", json=_pedido_payload())
    pedido_id = created.json()["id"]

    patch = await client.patch(
        f"/api/pedidos/{pedido_id}", json={"estado_pedido": "DESPACHADO"}
    )
    assert patch.status_code == 200
    assert patch.json()["estado_pedido"] == "DESPACHADO"


async def test_pedido_inexistente_404(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.get(f"/api/pedidos/{uuid4()}")
    assert resp.status_code == 404


async def test_filtro_estado_devuelve_solo_ese_estado(client, as_role) -> None:
    """``?estado=`` is filtered in Python after ``repo.list()`` fetches every
    row (see app/api/pedidos.py:47-49), not in SQL — a perf smell at scale,
    but behaviorally it must still return exactly the matching subset. This
    pins that contract so a future move to SQL-side filtering is provably
    equivalent."""
    as_role(RolUsuario.ASESOR)
    pendiente = await client.post("/api/pedidos", json=_pedido_payload())
    pendiente_id = pendiente.json()["id"]

    otro = await client.post("/api/pedidos", json=_pedido_payload())
    as_role(RolUsuario.AUDITOR)
    await client.patch(f"/api/pedidos/{otro.json()['id']}", json={"estado_pedido": "DESPACHADO"})

    filtrado = await client.get("/api/pedidos", params={"estado": "PENDIENTE_PAGO"})
    assert filtrado.status_code == 200
    ids = {p["id"] for p in filtrado.json()}
    assert pendiente_id in ids
    assert otro.json()["id"] not in ids
    assert all(p["estado_pedido"] == "PENDIENTE_PAGO" for p in filtrado.json())
