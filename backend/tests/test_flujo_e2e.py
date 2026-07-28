"""Flujo end-to-end: login real -> pedido -> pago -> extracto -> conciliación.

Unlike the phase-scoped tests (which use ``as_role`` to bypass JWT and the
rolled-back ``session`` fixture), these exercise the full HTTP path with a
real login and real commits against the test DB (``client_real_db`` /
``committing_session``), plus the matching matrix and the debit exclusion
that the reconciliation engine relies on for its anti-fraud guarantee.
"""
from __future__ import annotations

from datetime import date, timezone
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.security import hash_password
from app.domain.enums import EstadoMovimiento, EstadoPago, EstadoPedido, RolUsuario
from app.models.user import Usuario
from app.services.pdf_ingestion_service import PDFIngestionService
from app.workers.bancolombia_parser import BancolombiaParser
from tests.conftest import make_movimiento, make_pago, make_pedido
from tests.fixtures.bancolombia_pdf import StatementRow, build_bancolombia_pdf


async def _login(client, session, *, email: str, password: str, rol: RolUsuario) -> str:
    session.add(Usuario(email=email, hashed_password=hash_password(password), rol=rol))
    await session.flush()
    await session.commit()

    resp = await client.post(
        "/api/auth/login", data={"username": email, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_happy_path_completo(client_real_db, committing_session) -> None:
    """login (asesor) -> crea pedido -> declara pago -> auditor sube extracto
    real (PDF sintético) -> auditor ejecuta conciliación -> todo CONCILIADO /
    LISTO_PARA_DESPACHO."""
    client, session = client_real_db, committing_session

    suffix = uuid4().hex[:8]
    asesor_token = await _login(
        client, session, email=f"asesor.e2e.{suffix}@test.local", password="Pass1234", rol=RolUsuario.ASESOR
    )
    auditor_token = await _login(
        client, session, email=f"auditor.e2e.{suffix}@test.local", password="Pass1234", rol=RolUsuario.AUDITOR
    )

    pedido_resp = await client.post(
        "/api/pedidos",
        json={
            "codigo_pedido": f"PED-E2E-{suffix}",
            "cliente_whatsapp": "+573009998877",
            "monto_total": "150000.00",
        },
        headers=_auth(asesor_token),
    )
    assert pedido_resp.status_code == 201, pedido_resp.text
    pedido_id = pedido_resp.json()["id"]

    pago_resp = await client.post(
        "/api/pagos",
        json={
            "pedido_id": pedido_id,
            "banco_destino": "BANCOLOMBIA",
            "monto_declarado": "150000.00",
            "numero_referencia": "E2E998877",
        },
        headers=_auth(asesor_token),
    )
    assert pago_resp.status_code == 201, pago_resp.text

    # Real parse -> persist, going through PDFIngestionService directly
    # (not the HTTP upload endpoint, which backgrounds the work — that path
    # is covered separately in test_ingesta_background_e2e.py).
    pdf_bytes = build_bancolombia_pdf(
        rows=[
            StatementRow(
                10, 7, "TRANSFERENCIA RECIBIDA REF E2E998877",
                Decimal("150000.00"), Decimal("2000000.00"),
            )
        ],
        desde=date(2026, 7, 1),
        hasta=date(2026, 7, 31),
    )
    ingestion = PDFIngestionService(session, BancolombiaParser())
    ingest_summary = await ingestion.ingest(pdf_bytes)
    assert ingest_summary.insertados == 1

    run_resp = await client.post("/api/conciliaciones/run", headers=_auth(auditor_token))
    assert run_resp.status_code == 200, run_resp.text
    assert run_resp.json() == {"conciliados": 1}

    pedido_final = await client.get(f"/api/pedidos/{pedido_id}", headers=_auth(auditor_token))
    assert pedido_final.json()["estado_pedido"] == EstadoPedido.LISTO_PARA_DESPACHO.value

    pagos = (await client.get("/api/pagos", headers=_auth(auditor_token))).json()
    pago = next(p for p in pagos if p["pedido_id"] == pedido_id)
    assert pago["estado_pago"] == EstadoPago.CONCILIADO.value

    conciliaciones = (
        await client.get("/api/conciliaciones", headers=_auth(auditor_token))
    ).json()
    assert any(c["pago_declarado_id"] == pago["id"] for c in conciliaciones)


@pytest.mark.parametrize(
    "descripcion,pago_kwargs,mov_kwargs,should_match",
    [
        (
            "L1: numero_referencia en descripcion",
            dict(numero_referencia="998877"),
            dict(descripcion_concepto="TRANSFERENCIA RECIBIDA REF 998877"),
            True,
        ),
        (
            "L2: codigo_pedido en descripcion",
            dict(numero_referencia="PSE-X1"),
            dict(descripcion_concepto="PAGO PSE __CODIGO__"),
            True,
        ),
        (
            "L3: ultimos_4_digitos en descripcion",
            dict(numero_referencia="NOMATCH1", ultimos_4_digitos="4477"),
            dict(descripcion_concepto="NEQUI ENVIO DESDE 4477"),
            True,
        ),
        (
            "monto no coincide pese a referencia perfecta",
            dict(numero_referencia="551122"),
            dict(descripcion_concepto="TRANSFERENCIA REF 551122", monto_real=Decimal("74000.00")),
            False,
        ),
        (
            "centinela antifraude: monto exacto, cero metadata en comun",
            dict(numero_referencia="ZZZ999"),
            dict(descripcion_concepto="PAGO NOMINA JULIO"),
            False,
        ),
    ],
)
async def test_matriz_l1_l2_l3_y_no_match(
    session, descripcion, pago_kwargs, mov_kwargs, should_match
) -> None:
    from app.repositories.conciliacion_repository import ConciliacionRepository
    from app.repositories.movimiento_bancario_repository import MovimientoBancarioRepository
    from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
    from app.repositories.pedido_repository import PedidoRepository
    from app.services.reconciliation_service import ReconciliationService

    pedido_repo = PedidoRepository(session)
    pago_repo = PagoDeclaradoRepository(session)
    mov_repo = MovimientoBancarioRepository(session)

    pedido = await pedido_repo.add(make_pedido(codigo_pedido="PED-2026-002", monto_total=Decimal("89900.00")))
    if "__CODIGO__" in mov_kwargs.get("descripcion_concepto", ""):
        mov_kwargs = {
            **mov_kwargs,
            "descripcion_concepto": mov_kwargs["descripcion_concepto"].replace(
                "__CODIGO__", pedido.codigo_pedido
            ),
        }
    # The pago always declares the pedido's real amount; the movimiento's
    # amount only differs when the scenario explicitly says so (the
    # "monto no coincide" case) — that mismatch is the point being tested.
    pago = await pago_repo.add(
        make_pago(pedido.id, monto_declarado=pedido.monto_total, **pago_kwargs)
    )
    mov_kwargs.setdefault("monto_real", pedido.monto_total)
    mov = await mov_repo.add(make_movimiento(**mov_kwargs))

    service = ReconciliationService(
        session, pago_repo, mov_repo, ConciliacionRepository(session), pedido_repo
    )
    summary = await service.run()

    if should_match:
        assert summary.conciliados == 1, descripcion
        assert pago.estado_pago == EstadoPago.CONCILIADO, descripcion
        assert mov.estado_movimiento == EstadoMovimiento.CONCILIADO, descripcion
        assert pedido.estado_pedido == EstadoPedido.LISTO_PARA_DESPACHO, descripcion
    else:
        assert summary.conciliados == 0, descripcion
        assert pago.estado_pago == EstadoPago.REGISTRADO, descripcion


async def test_debito_nunca_concilia(session) -> None:
    """A negative monto_real (a debit) must never match a declared payment —
    every monto_declarado is CHECK > 0, so a debit and a pago can never be
    numerically equal, but this pins that invariant explicitly."""
    from app.repositories.conciliacion_repository import ConciliacionRepository
    from app.repositories.movimiento_bancario_repository import MovimientoBancarioRepository
    from app.repositories.pago_declarado_repository import PagoDeclaradoRepository
    from app.repositories.pedido_repository import PedidoRepository
    from app.services.reconciliation_service import ReconciliationService

    pedido_repo = PedidoRepository(session)
    pago_repo = PagoDeclaradoRepository(session)
    mov_repo = MovimientoBancarioRepository(session)

    pedido = await pedido_repo.add(make_pedido(monto_total=Decimal("50000.00")))
    pago = await pago_repo.add(
        make_pago(pedido.id, monto_declarado=Decimal("50000.00"), numero_referencia="DEB1")
    )
    mov = await mov_repo.add(
        make_movimiento(
            monto_real=Decimal("-50000.00"),
            descripcion_concepto="RETIRO CAJERO DEB1",
        )
    )

    service = ReconciliationService(
        session, pago_repo, mov_repo, ConciliacionRepository(session), pedido_repo
    )
    summary = await service.run()

    assert summary.conciliados == 0
    assert pago.estado_pago == EstadoPago.REGISTRADO
    assert mov.estado_movimiento == EstadoMovimiento.DISPONIBLE
