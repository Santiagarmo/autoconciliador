"""Fase 4 — Ingesta API: upload contract (202), validation, no event-loop block.

The heavy ingest+reconcile work runs in a background task with its OWN session,
so here we patch it to a no-op and assert only the HTTP contract. The actual
ingest/reconcile wiring is covered by the Phase-3 service tests.
"""
from __future__ import annotations

import app.api.movimientos as mv
from app.domain.enums import RolUsuario


async def test_ingesta_acepta_202(client, as_role, monkeypatch) -> None:
    as_role(RolUsuario.ASESOR)

    async def _noop(banco: str, content: bytes) -> None:
        return None

    monkeypatch.setattr(mv, "_ingest_and_reconcile", _noop)

    resp = await client.post(
        "/api/movimientos/ingesta",
        data={"banco": "BANCOLOMBIA"},
        files={"archivo": ("extracto.pdf", b"%PDF-fake-bytes", "application/pdf")},
    )
    assert resp.status_code == 202


async def test_ingesta_banco_no_soportado_400(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.post(
        "/api/movimientos/ingesta",
        data={"banco": "NEQUI"},  # deferred parser, not registered
        files={"archivo": ("x.pdf", b"data", "application/pdf")},
    )
    assert resp.status_code == 400


async def test_ingesta_archivo_vacio_400(client, as_role) -> None:
    as_role(RolUsuario.ASESOR)
    resp = await client.post(
        "/api/movimientos/ingesta",
        data={"banco": "BANCOLOMBIA"},
        files={"archivo": ("x.pdf", b"", "application/pdf")},
    )
    assert resp.status_code == 400


async def test_ingesta_requiere_auth(client) -> None:
    resp = await client.post(
        "/api/movimientos/ingesta",
        data={"banco": "BANCOLOMBIA"},
        files={"archivo": ("x.pdf", b"data", "application/pdf")},
    )
    assert resp.status_code == 401
