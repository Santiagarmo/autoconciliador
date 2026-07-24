"""Fase 4 — Conciliaciones API: manual trigger and listing."""
from __future__ import annotations

from app.domain.enums import RolUsuario


async def test_run_como_auditor(client, as_role) -> None:
    as_role(RolUsuario.AUDITOR)
    resp = await client.post("/api/conciliaciones/run")
    assert resp.status_code == 200
    assert "conciliados" in resp.json()


async def test_run_forbidden_asesor(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.post("/api/conciliaciones/run")
    assert resp.status_code == 403


async def test_listar_conciliaciones(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.get("/api/conciliaciones")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
