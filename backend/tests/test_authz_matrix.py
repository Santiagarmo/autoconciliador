"""Matriz de autorización: cada endpoint x {anónimo, ASESOR, AUDITOR}.

Complementa ``test_auth.py`` (que ya cubre login/JWT/roles caso por caso) con
una tabla exhaustiva por endpoint, y las ramas sin cubrir de
``get_current_user`` (token expirado, usuario inactivo, ``sub`` no-UUID).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from jose import jwt

from app.core.config import settings
from app.core.security import hash_password
from app.domain.enums import RolUsuario
from tests.conftest import make_pedido, make_usuario


def _token_for(user_id, rol: str, *, expira_en: timedelta = timedelta(minutes=60)) -> str:
    payload = {
        "sub": str(user_id),
        "rol": rol,
        "exp": datetime.now(timezone.utc) + expira_en,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


# --- Matriz por endpoint -----------------------------------------------------
# (metodo, path_builder, body_builder, status_anonimo, status_asesor, status_auditor)

@pytest.mark.parametrize(
    "metodo,path,expect_anon,expect_asesor,expect_auditor",
    [
        ("GET", "/api/pedidos", 401, 200, 200),
        ("GET", "/api/pagos", 401, 200, 200),
        ("GET", "/api/movimientos", 401, 200, 200),
        ("GET", "/api/conciliaciones", 401, 200, 200),
        ("POST", "/api/conciliaciones/run", 401, 403, 200),
    ],
)
async def test_matriz_roles_endpoints_get(
    client, as_role, metodo, path, expect_anon, expect_asesor, expect_auditor
) -> None:
    anon_resp = await client.request(metodo, path)
    assert anon_resp.status_code == expect_anon, f"{metodo} {path} anonimo"

    as_role(RolUsuario.ASESOR)
    asesor_resp = await client.request(metodo, path)
    assert asesor_resp.status_code == expect_asesor, f"{metodo} {path} asesor"

    as_role(RolUsuario.AUDITOR)
    auditor_resp = await client.request(metodo, path)
    assert auditor_resp.status_code == expect_auditor, f"{metodo} {path} auditor"


async def test_post_auth_users_solo_auditor(client, as_role) -> None:
    payload = {"email": f"nuevo-{uuid4().hex[:8]}@test.local", "password": "Passw0rd!"}

    anon = await client.post("/api/auth/users", json=payload)
    assert anon.status_code == 401

    as_role(RolUsuario.ASESOR)
    asesor = await client.post("/api/auth/users", json={**payload, "email": f"a-{uuid4().hex[:8]}@test.local"})
    assert asesor.status_code == 403

    as_role(RolUsuario.AUDITOR)
    auditor = await client.post("/api/auth/users", json={**payload, "email": f"b-{uuid4().hex[:8]}@test.local"})
    assert auditor.status_code == 201


async def test_patch_pedido_despacho_solo_auditor(client, as_role, session) -> None:
    from app.repositories.pedido_repository import PedidoRepository

    pedido = await PedidoRepository(session).add(make_pedido())

    as_role(RolUsuario.ASESOR)
    resp = await client.patch(
        f"/api/pedidos/{pedido.id}", json={"estado_pedido": "LISTO_PARA_DESPACHO"}
    )
    assert resp.status_code == 403

    resp = await client.patch(
        f"/api/pedidos/{pedido.id}", json={"estado_pedido": "DESPACHADO"}
    )
    assert resp.status_code == 403

    as_role(RolUsuario.AUDITOR)
    resp = await client.patch(
        f"/api/pedidos/{pedido.id}", json={"estado_pedido": "LISTO_PARA_DESPACHO"}
    )
    assert resp.status_code == 200


async def test_patch_pedido_otros_campos_permitido_a_asesor(client, as_role, session) -> None:
    """Non-restricted PATCH fields (e.g. cliente_whatsapp) work for any role —
    only the dispatch-adjacent estados are auditor-gated."""
    from app.repositories.pedido_repository import PedidoRepository

    pedido = await PedidoRepository(session).add(make_pedido())
    as_role(RolUsuario.ASESOR)
    resp = await client.patch(
        f"/api/pedidos/{pedido.id}", json={"cliente_whatsapp": "+573000000000"}
    )
    assert resp.status_code == 200


async def test_ingesta_permitida_a_asesor_decision_de_diseno(client, as_role, monkeypatch) -> None:
    """POST /movimientos/ingesta has NO auditor gate. Confirmed with the user
    to be INTENTIONAL (advisors do upload bank statements) — this test pins
    that behavior so it reads as a documented decision, not an oversight.
    See docs/QA-INTEGRAL-2026-07.md."""
    import app.api.movimientos as mv

    async def _noop(banco: str, content: bytes) -> None:
        return None

    monkeypatch.setattr(mv, "_ingest_and_reconcile", _noop)

    as_role(RolUsuario.ASESOR)
    resp = await client.post(
        "/api/movimientos/ingesta",
        data={"banco": "BANCOLOMBIA"},
        files={"archivo": ("x.pdf", b"data", "application/pdf")},
    )
    assert resp.status_code == 202  # intentional: not 403


# --- get_current_user edge branches -----------------------------------------

async def test_token_expirado_401(client, session) -> None:
    user = make_usuario(RolUsuario.AUDITOR, hashed_password=hash_password("x"))
    session.add(user)
    await session.flush()

    token = _token_for(user.id, user.rol.value, expira_en=timedelta(minutes=-5))
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate") == "Bearer"


async def test_token_usuario_inactivo_401(client, session) -> None:
    user = make_usuario(RolUsuario.ASESOR, hashed_password=hash_password("x"), activo=False)
    session.add(user)
    await session.flush()

    token = _token_for(user.id, user.rol.value)
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_token_sub_no_uuid_401(client) -> None:
    payload = {
        "sub": "not-a-uuid",
        "rol": "ASESOR",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_token_usuario_inexistente_401(client) -> None:
    token = _token_for(uuid4(), "ASESOR")
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401


async def test_token_firma_invalida_401(client) -> None:
    payload = {
        "sub": str(uuid4()),
        "rol": "AUDITOR",
        "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
    }
    token = jwt.encode(payload, "clave-incorrecta", algorithm=settings.ALGORITHM)
    resp = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 401
