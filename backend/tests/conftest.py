"""Pytest fixtures: DB session isolated per test via an outer transaction.

Each test runs against the real Postgres (migrated schema) but inside an outer
transaction that is rolled back at teardown, so tests never persist data and
don't fight each other. ``join_transaction_mode="create_savepoint"`` makes the
session use a SAVEPOINT as its root, so service code calling ``commit()`` /
``begin_nested()`` releases savepoints instead of the real transaction.
"""
from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

import app.models  # noqa: F401 — register ORM metadata
from app.api.deps import get_current_user
from app.core.config import settings
from app.db.session import get_session
from app.domain.enums import RolUsuario
from app.main import app
from app.models.movimiento_bancario import MovimientoBancario
from app.models.pago_declarado import PagoDeclarado
from app.models.pedido import Pedido
from app.models.user import Usuario
from app.schemas.movimiento_bancario import MovimientoBancarioParsed
from app.services.llm_reviewer import (
    StatementReviewer,
    StatementReviewRequest,
    StatementReviewVerdict,
)
from app.workers.base import BankParserStrategy


@pytest_asyncio.fixture
async def engine():
    # Dedicated test DB (see TEST_DATABASE_URL) — never the dev database, so
    # tests that commit for real (committing_session) can't pollute demo data
    # seeded via scripts/seed_demo.py, and a stray `--reset` there can't wipe
    # a test in flight.
    eng = create_async_engine(settings.TEST_DATABASE_URL)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncSession:
    async with engine.connect() as conn:
        await conn.begin()
        async with AsyncSession(
            bind=conn,
            expire_on_commit=False,
            join_transaction_mode="create_savepoint",
        ) as s:
            yield s
        await conn.rollback()


@pytest_asyncio.fixture
async def committing_session():
    """A plain, really-commits session against the test DB.

    Use this (instead of ``session``) for tests that must exercise code
    opening its own ``AsyncSessionLocal`` — e.g. the ingesta background task —
    since that code can't see the outer-transaction savepoint the ``session``
    fixture relies on. Rows are truncated at teardown so tests stay isolated
    despite committing for real.
    """
    test_engine = create_async_engine(settings.TEST_DATABASE_URL)
    session_factory = async_sessionmaker(
        bind=test_engine, expire_on_commit=False
    )
    try:
        async with session_factory() as s:
            yield s
    finally:
        async with test_engine.begin() as conn:
            await conn.execute(
                text(
                    "TRUNCATE conciliaciones, movimientos_bancarios, "
                    "pagos_declarados, pedidos, verificaciones_extracto "
                    "RESTART IDENTITY CASCADE"
                )
            )
        await test_engine.dispose()


@pytest_asyncio.fixture
async def real_async_session_local(monkeypatch):
    """Repoint ``app.db.session.AsyncSessionLocal`` at the test DB.

    ``app.db.session.engine``/``AsyncSessionLocal`` are built at import time
    from ``settings.DATABASE_URL`` (the dev DB) — that's what code like
    ``_ingest_and_reconcile`` uses via a bare ``AsyncSessionLocal()`` call, out
    of reach of the ``session``/``committing_session`` fixtures. Tests that
    exercise that code path (without monkeypatching the function itself) need
    the *global* factory swapped so it lands on the test DB.

    Deliberately does NOT truncate on teardown — always pair this with
    ``committing_session`` (which owns cleanup) in the same test. Fixture
    teardown is LIFO, so if this fixture also truncated, its cleanup could
    run *before* a still-open ``committing_session`` closes its own
    transaction, deadlocking on the lock it holds.
    """
    import app.api.movimientos as movimientos_module
    import app.db.session as session_module
    import scripts.seed_demo as seed_demo_module

    test_engine = create_async_engine(settings.TEST_DATABASE_URL)
    test_session_local = async_sessionmaker(
        bind=test_engine, expire_on_commit=False, autoflush=False
    )
    monkeypatch.setattr(session_module, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(movimientos_module, "AsyncSessionLocal", test_session_local)
    monkeypatch.setattr(seed_demo_module, "AsyncSessionLocal", test_session_local)
    try:
        yield test_session_local
    finally:
        await test_engine.dispose()


# --- Object factories (unique data so tests never collide) -----------------

def make_pedido(**overrides) -> Pedido:
    data = dict(
        codigo_pedido=f"PED-{uuid4().hex[:8].upper()}",
        cliente_whatsapp="+573001112233",
        monto_total=Decimal("100000.00"),
    )
    data.update(overrides)
    return Pedido(**data)


def make_pago(pedido_id, **overrides) -> PagoDeclarado:
    data = dict(
        pedido_id=pedido_id,
        banco_destino="NEQUI",
        monto_declarado=Decimal("100000.00"),
        numero_referencia=f"REF{uuid4().hex[:10].upper()}",
        ultimos_4_digitos=None,
    )
    data.update(overrides)
    return PagoDeclarado(**data)


def make_movimiento(**overrides) -> MovimientoBancario:
    data = dict(
        banco_origen="NEQUI",
        fecha_movimiento=datetime(2026, 7, 20, 10, 0, tzinfo=timezone.utc),
        monto_real=Decimal("100000.00"),
        saldo_posterior=Decimal("500000.00"),
        numero_referencia=None,
        descripcion_concepto="TRANSFERENCIA RECIBIDA",
        hash_idempotencia=uuid4().hex,
    )
    data.update(overrides)
    return MovimientoBancario(**data)


def make_usuario(rol: RolUsuario = RolUsuario.ASESOR, **overrides) -> Usuario:
    data = dict(
        email=f"{rol.value.lower()}-{uuid4().hex[:8]}@test.local",
        hashed_password="x",
        rol=rol,
    )
    data.update(overrides)
    return Usuario(**data)


# --- API test client (real ASGI app over the isolated test session) --------

@pytest_asyncio.fixture
async def client(session) -> AsyncClient:
    """HTTP client bound to the app, using the rolled-back test session.

    ``get_session`` is overridden so every request/dependency shares the same
    savepoint-isolated session, so endpoint ``commit()`` calls never persist.
    """
    app.dependency_overrides[get_session] = lambda: session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client_real_db(committing_session) -> AsyncClient:
    """HTTP client bound to ``committing_session`` — real commits, real JWTs.

    Unlike ``client``, this doesn't override ``get_current_user``: requests
    must carry a genuine ``Authorization: Bearer`` token from a real
    ``POST /auth/login``, so it's what full-path tests (login → ... →
    reconciliation) use to exercise the actual auth dependency instead of the
    ``as_role`` bypass.
    """
    app.dependency_overrides[get_session] = lambda: committing_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def as_role():
    """Return a setter that authenticates requests as a given role.

    Overrides ``get_current_user`` with a detached in-memory Usuario, so tests
    exercise ``require_role`` without issuing a real JWT. Cleared by the
    ``client`` fixture teardown.
    """

    def _set(rol: RolUsuario) -> Usuario:
        user = make_usuario(rol)
        app.dependency_overrides[get_current_user] = lambda: user
        return user

    return _set


# --- Test-only parser strategy (no real PDF needed) ------------------------

class StubParser(BankParserStrategy):
    """Returns a fixed list of parsed rows — decouples ingestion from PDFs."""

    banco = "STUB"

    def __init__(self, rows: list[MovimientoBancarioParsed]) -> None:
        self._rows = rows

    async def parse(self, source: bytes | str) -> list[MovimientoBancarioParsed]:
        return list(self._rows)


# --- Test-only reviewer strategy (no LLM endpoint needed) -------------------

class StubReviewer(StatementReviewer):
    """Records every call and returns a canned verdict — same idiom as
    ``StubParser``. Lets a test assert the tier-2 escalation path is called
    exactly once on DISCREPANCIA and zero times on OK, with no model."""

    def __init__(self, verdict: StatementReviewVerdict | None = None) -> None:
        self.verdict = verdict or StatementReviewVerdict(
            veredicto="INDETERMINADO", confianza=0.0, explicacion="stub"
        )
        self.calls: list[StatementReviewRequest] = []

    async def review(
        self, request: StatementReviewRequest
    ) -> StatementReviewVerdict | None:
        self.calls.append(request)
        return self.verdict
