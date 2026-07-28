"""Seed a realistic demo dataset (idempotent) for manual QA / frontend review.

Run from the backend/ directory once migrations are applied:

    python -m scripts.seed_demo               # upsert-style, safe to re-run
    python -m scripts.seed_demo --reset        # wipe pedidos/pagos/movimientos/
                                                # conciliaciones first (keeps usuarios)
    python -m scripts.seed_demo --users        # also create demo asesor/auditor logins

Opens its own session (independent of any request lifecycle), same pattern as
``scripts/seed_admin.py``. Deliberately does NOT touch ``usuarios`` on
``--reset`` so the seeded admin (and any other login) survives.

Scenario matrix (see docs/QA-INTEGRAL-2026-07.md for the full rationale):
pedidos 001-003 are designed to match on L1/L2/L3 respectively when
``POST /api/conciliaciones/run`` executes; 004 fails on the mandatory amount
gate despite a perfect reference; 005 is the anti-fraud sentinel — exact
amount, zero metadata overlap, must NOT match. 006/007 are orphans either
side. 008/009 are pre-reconciled (AUTOMATICA / MANUAL_AUDITOR). 010/011/012
cover the remaining estado values with no bank activity. Four standalone
movimientos add two debits (must never match), one NO_OPERATIVO, and one
filler credit.

Running the reconciliation engine against a freshly (--reset) seeded DB must
produce exactly 3 new conciliaciones (5 total, counting 008/009).
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import text

from app.core.config import settings
from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domain.enums import EstadoMovimiento, EstadoPago, EstadoPedido, RolUsuario, TipoConciliacion
from app.models.conciliacion import Conciliacion
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.models.pedido import Pedido
from app.models.user import Usuario
from app.repositories.pedido_repository import PedidoRepository
from app.repositories.user_repository import UserRepository
from app.services.pdf_ingestion_service import _normalize_descripcion, compute_hash

# Stable UUIDs so re-runs and browser screenshots stay comparable.
_NAMESPACE = uuid.UUID("6f6a1e2a-0000-4000-8000-000000000000")


def _stable_uuid(*parts: str) -> uuid.UUID:
    return uuid.uuid5(_NAMESPACE, ":".join(parts))


@dataclass
class Escenario:
    codigo_pedido: str
    monto_total: Decimal
    estado_pedido: EstadoPedido
    cliente_whatsapp: str = "+573001112233"
    pago: "PagoSpec | None" = None
    movimiento: "MovimientoSpec | None" = None
    conciliacion_previa: TipoConciliacion | None = None


@dataclass
class PagoSpec:
    banco_destino: str
    monto_declarado: Decimal
    numero_referencia: str
    ultimos_4_digitos: str | None = None
    estado_pago: EstadoPago = EstadoPago.REGISTRADO


@dataclass
class MovimientoSpec:
    banco_origen: str
    monto_real: Decimal
    saldo_posterior: Decimal
    descripcion_concepto: str
    numero_referencia: str | None = None
    estado_movimiento: EstadoMovimiento = EstadoMovimiento.DISPONIBLE
    fecha_movimiento: datetime = field(
        default_factory=lambda: datetime(2026, 7, 15, 9, 0, tzinfo=timezone.utc)
    )


ESCENARIOS: list[Escenario] = [
    # 1 — L1 match: numero_referencia is a substring of la descripción.
    Escenario(
        "PED-2026-001", Decimal("150000.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("BANCOLOMBIA", Decimal("150000.00"), "998877"),
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("150000.00"), Decimal("2150000.00"),
            "TRANSFERENCIA RECIBIDA REF 998877",
        ),
    ),
    # 2 — L2 match: codigo_pedido appears in the movimiento's descripción.
    Escenario(
        "PED-2026-002", Decimal("89900.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("BANCOLOMBIA", Decimal("89900.00"), "PSE-X1"),
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("89900.00"), Decimal("1999900.00"),
            "PAGO PSE PED-2026-002",
        ),
    ),
    # 3 — L3 match: ultimos_4_digitos appears in the descripción.
    Escenario(
        "PED-2026-003", Decimal("240000.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("NEQUI", Decimal("240000.00"), "NOMATCH1", ultimos_4_digitos="4477"),
        movimiento=MovimientoSpec(
            "NEQUI", Decimal("240000.00"), Decimal("759900.00"),
            "NEQUI ENVIO DESDE 4477",
        ),
    ),
    # 4 — mandatory amount gate fails despite a perfect reference match.
    Escenario(
        "PED-2026-004", Decimal("75000.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("BANCOLOMBIA", Decimal("75000.00"), "551122"),
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("74000.00"), Decimal("685900.00"),
            "TRANSFERENCIA REF 551122",
        ),
    ),
    # 5 — anti-fraud sentinel: exact amount, zero metadata overlap. Must NOT match.
    Escenario(
        "PED-2026-005", Decimal("120000.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("BANCOLOMBIA", Decimal("120000.00"), "ZZZ999"),
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("120000.00"), Decimal("805900.00"),
            "PAGO NOMINA JULIO",
        ),
    ),
    # 6 — declared payment, bank never received it (orphan pago).
    Escenario(
        "PED-2026-006", Decimal("310000.00"), EstadoPedido.PENDIENTE_PAGO,
        pago=PagoSpec("NEQUI", Decimal("310000.00"), "ORPHAN1"),
    ),
    # 7 — bank movement with no declared payment (orphan movimiento).
    Escenario(
        "PED-2026-007", Decimal("65000.00"), EstadoPedido.PENDIENTE_PAGO,
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("65000.00"), Decimal("870900.00"),
            "CONSIGNACION EFECTIVO",
        ),
    ),
    # 8 — already reconciled (AUTOMATICA). The run must leave this alone.
    Escenario(
        "PED-2026-008", Decimal("199000.00"), EstadoPedido.LISTO_PARA_DESPACHO,
        pago=PagoSpec(
            "BANCOLOMBIA", Decimal("199000.00"), "OLD-001",
            estado_pago=EstadoPago.CONCILIADO,
        ),
        movimiento=MovimientoSpec(
            "BANCOLOMBIA", Decimal("199000.00"), Decimal("1069900.00"),
            "TRANSFERENCIA REF OLD-001",
            estado_movimiento=EstadoMovimiento.CONCILIADO,
        ),
        conciliacion_previa=TipoConciliacion.AUTOMATICA,
    ),
    # 9 — already reconciled by an auditor manually (MANUAL_AUDITOR) — the
    # only way to make that enum value observable anywhere in the UI today.
    Escenario(
        "PED-2026-009", Decimal("88000.00"), EstadoPedido.DESPACHADO,
        pago=PagoSpec(
            "NEQUI", Decimal("88000.00"), "OLD-002",
            estado_pago=EstadoPago.CONCILIADO,
        ),
        movimiento=MovimientoSpec(
            "NEQUI", Decimal("88000.00"), Decimal("1157900.00"),
            "TRANSFERENCIA MANUAL VERIFICADA",
            estado_movimiento=EstadoMovimiento.CONCILIADO,
        ),
        conciliacion_previa=TipoConciliacion.MANUAL_AUDITOR,
    ),
    # 10-12 — remaining estado_pedido coverage, no bank activity involved.
    Escenario("PED-2026-010", Decimal("45000.00"), EstadoPedido.CANCELADO),
    Escenario(
        "PED-2026-011", Decimal("500000.00"), EstadoPedido.ALERTA_PAGO,
        pago=PagoSpec(
            "BANCOLOMBIA", Decimal("500000.00"), "ALERTA-1",
            estado_pago=EstadoPago.ALERTA_NO_ENCONTRADO,
        ),
    ),
    Escenario(
        "PED-2026-012", Decimal("33000.00"), EstadoPedido.EN_VERIFICACION,
        pago=PagoSpec(
            "BANCOLOMBIA", Decimal("33000.00"), "RECH-1",
            estado_pago=EstadoPago.RECHAZADO,
        ),
    ),
]

# Standalone movimientos, not tied to any pedido.
MOVIMIENTOS_SUELTOS: list[MovimientoSpec] = [
    MovimientoSpec("BANCOLOMBIA", Decimal("-50000.00"), Decimal("1119900.00"), "RETIRO CAJERO"),
    MovimientoSpec("BANCOLOMBIA", Decimal("-12000.00"), Decimal("1107900.00"), "COMISION MANEJO"),
    MovimientoSpec(
        "BANCOLOMBIA", Decimal("120000.00"), Decimal("1227900.00"), "ANULACION",
        estado_movimiento=EstadoMovimiento.NO_OPERATIVO,
    ),
    MovimientoSpec("BANCOLOMBIA", Decimal("1000000.00"), Decimal("2227900.00"), "SALDO INICIAL"),
]

DEMO_USERS = [
    ("asesor@demo.local", "Demo-1234", RolUsuario.ASESOR),
    ("auditor@demo.local", "Demo-1234", RolUsuario.AUDITOR),
]


def _movimiento_from_spec(spec: MovimientoSpec, key: str) -> MovimientoBancario:
    descripcion_limpia = _normalize_descripcion(spec.descripcion_concepto)
    return MovimientoBancario(
        id=_stable_uuid("movimiento", key),
        banco_origen=spec.banco_origen,
        fecha_movimiento=spec.fecha_movimiento,
        monto_real=spec.monto_real,
        saldo_posterior=spec.saldo_posterior,
        numero_referencia=spec.numero_referencia,
        descripcion_concepto=spec.descripcion_concepto,
        hash_idempotencia=compute_hash(
            fecha_movimiento=spec.fecha_movimiento,
            monto_real=spec.monto_real,
            saldo_posterior=spec.saldo_posterior,
            descripcion_limpia=descripcion_limpia,
        ),
        estado_movimiento=spec.estado_movimiento,
    )


async def _reset(session) -> None:
    print("[seed] --reset: truncando pedidos/pagos/movimientos/conciliaciones (usuarios se conserva)...")
    await session.execute(
        text(
            "TRUNCATE conciliaciones, movimientos_bancarios, "
            "pagos_declarados, pedidos RESTART IDENTITY CASCADE"
        )
    )
    await session.commit()


async def seed_demo(*, reset: bool, with_users: bool) -> None:
    if "prod" in settings.DATABASE_URL.lower():
        print("[seed] Rechazado: DATABASE_URL contiene 'prod'. Abortando por seguridad.")
        sys.exit(1)

    async with AsyncSessionLocal() as session:
        if reset:
            await _reset(session)

        pedido_repo = PedidoRepository(session)
        creados_pedidos = 0
        creados_pagos = 0
        creados_movimientos = 0
        creadas_conciliaciones = 0

        for esc in ESCENARIOS:
            pedido = await pedido_repo.get_by_codigo(esc.codigo_pedido)
            if pedido is None:
                pedido = Pedido(
                    id=_stable_uuid("pedido", esc.codigo_pedido),
                    codigo_pedido=esc.codigo_pedido,
                    cliente_whatsapp=esc.cliente_whatsapp,
                    monto_total=esc.monto_total,
                    estado_pedido=esc.estado_pedido,
                )
                session.add(pedido)
                await session.flush()
                creados_pedidos += 1
            else:
                pedido.estado_pedido = esc.estado_pedido

            pago = None
            if esc.pago is not None:
                pago_id = _stable_uuid("pago", esc.codigo_pedido)
                existing = await session.get(PagoDeclarado, pago_id)
                if existing is None:
                    pago = PagoDeclarado(
                        id=pago_id,
                        pedido_id=pedido.id,
                        banco_destino=esc.pago.banco_destino,
                        monto_declarado=esc.pago.monto_declarado,
                        numero_referencia=esc.pago.numero_referencia,
                        ultimos_4_digitos=esc.pago.ultimos_4_digitos,
                        estado_pago=esc.pago.estado_pago,
                    )
                    session.add(pago)
                    await session.flush()
                    creados_pagos += 1
                else:
                    pago = existing

            movimiento = None
            if esc.movimiento is not None:
                mov = _movimiento_from_spec(esc.movimiento, esc.codigo_pedido)
                existing_mov = await session.get(MovimientoBancario, mov.id)
                if existing_mov is None:
                    session.add(mov)
                    await session.flush()
                    movimiento = mov
                    creados_movimientos += 1
                else:
                    movimiento = existing_mov

            if esc.conciliacion_previa is not None and pago is not None and movimiento is not None:
                conc_id = _stable_uuid("conciliacion", esc.codigo_pedido)
                existing_conc = await session.get(Conciliacion, conc_id)
                if existing_conc is None:
                    session.add(
                        Conciliacion(
                            id=conc_id,
                            pago_declarado_id=pago.id,
                            movimiento_bancario_id=movimiento.id,
                            tipo_conciliacion=esc.conciliacion_previa,
                        )
                    )
                    creadas_conciliaciones += 1

        for i, spec in enumerate(MOVIMIENTOS_SUELTOS):
            mov = _movimiento_from_spec(spec, f"suelto-{i}")
            existing = await session.get(MovimientoBancario, mov.id)
            if existing is None:
                session.add(mov)
                creados_movimientos += 1

        await session.commit()

        if with_users:
            user_repo = UserRepository(session)
            creados_usuarios = 0
            for email, password, rol in DEMO_USERS:
                if await user_repo.get_by_email(email) is None:
                    session.add(
                        Usuario(
                            email=email,
                            hashed_password=hash_password(password),
                            rol=rol,
                        )
                    )
                    creados_usuarios += 1
            await session.commit()
            print(f"[seed] Usuarios demo: {creados_usuarios} creados (de {len(DEMO_USERS)}).")

        print(
            "[seed] Listo — "
            f"pedidos +{creados_pedidos}, pagos +{creados_pagos}, "
            f"movimientos +{creados_movimientos}, conciliaciones previas +{creadas_conciliaciones}."
        )
        print(
            "[seed] Ejecuta 'POST /api/conciliaciones/run' como auditor: "
            "sobre datos recién sembrados debe reportar exactamente 3 nuevas conciliaciones."
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--reset", action="store_true",
        help="TRUNCATE pedidos/pagos/movimientos/conciliaciones antes de sembrar (conserva usuarios).",
    )
    parser.add_argument(
        "--users", action="store_true",
        help="Crea asesor@demo.local / auditor@demo.local (password Demo-1234).",
    )
    args = parser.parse_args()
    asyncio.run(seed_demo(reset=args.reset, with_users=args.users))


if __name__ == "__main__":
    main()
