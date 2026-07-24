"""Fase 4 — Auth: password hashing, JWT login flow, role enforcement."""
from __future__ import annotations

from app.core.security import hash_password, verify_password
from app.domain.enums import RolUsuario
from app.models.user import Usuario


async def test_password_hash_roundtrip() -> None:
    hashed = hash_password("secret123")
    assert hashed != "secret123"
    assert verify_password("secret123", hashed)
    assert not verify_password("wrong-pass", hashed)


async def test_login_and_me(client, session) -> None:
    user = Usuario(
        email="auditor@test.local",
        hashed_password=hash_password("secret123"),
        rol=RolUsuario.AUDITOR,
    )
    session.add(user)
    await session.flush()

    login = await client.post(
        "/api/auth/login",
        data={"username": "auditor@test.local", "password": "secret123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
    )
    assert me.status_code == 200
    body = me.json()
    assert body["email"] == "auditor@test.local"
    assert body["rol"] == "AUDITOR"


async def test_login_wrong_password(client, session) -> None:
    user = Usuario(
        email="asesor@test.local",
        hashed_password=hash_password("secret123"),
        rol=RolUsuario.ASESOR,
    )
    session.add(user)
    await session.flush()

    resp = await client.post(
        "/api/auth/login",
        data={"username": "asesor@test.local", "password": "nope"},
    )
    assert resp.status_code == 401


async def test_me_requires_token(client) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_require_role_forbids_asesor(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.post("/api/conciliaciones/run")
    assert resp.status_code == 403


async def test_require_role_allows_auditor(client, as_role) -> None:
    as_role(RolUsuario.AUDITOR)
    resp = await client.post("/api/conciliaciones/run")
    assert resp.status_code == 200
    assert resp.json() == {"conciliados": 0}
