"""FastAPI dependency providers (Dependency Inversion wiring).

Routers depend on services, services depend on these repository providers,
and repositories depend on the request-scoped ``AsyncSession``. The provider
return type is the abstract interface so callers never bind to a concrete
implementation.
"""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_session
from app.domain.enums import RolUsuario
from app.models.user import Usuario
from app.repositories import (
    ConciliacionRepository,
    IConciliacionRepository,
    IMovimientoBancarioRepository,
    IPagoDeclaradoRepository,
    IPedidoRepository,
    IUserRepository,
    IVerificacionExtractoRepository,
    MovimientoBancarioRepository,
    PagoDeclaradoRepository,
    PedidoRepository,
    UserRepository,
    VerificacionExtractoRepository,
)
from app.services.reconciliation_service import ReconciliationService

SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_pedido_repository(session: SessionDep) -> IPedidoRepository:
    return PedidoRepository(session)


def get_pago_declarado_repository(
    session: SessionDep,
) -> IPagoDeclaradoRepository:
    return PagoDeclaradoRepository(session)


def get_movimiento_bancario_repository(
    session: SessionDep,
) -> IMovimientoBancarioRepository:
    return MovimientoBancarioRepository(session)


def get_conciliacion_repository(
    session: SessionDep,
) -> IConciliacionRepository:
    return ConciliacionRepository(session)


def get_user_repository(session: SessionDep) -> IUserRepository:
    return UserRepository(session)


def get_verificacion_extracto_repository(
    session: SessionDep,
) -> IVerificacionExtractoRepository:
    return VerificacionExtractoRepository(session)


PedidoRepositoryDep = Annotated[
    IPedidoRepository, Depends(get_pedido_repository)
]
PagoDeclaradoRepositoryDep = Annotated[
    IPagoDeclaradoRepository, Depends(get_pago_declarado_repository)
]
MovimientoBancarioRepositoryDep = Annotated[
    IMovimientoBancarioRepository, Depends(get_movimiento_bancario_repository)
]
ConciliacionRepositoryDep = Annotated[
    IConciliacionRepository, Depends(get_conciliacion_repository)
]
UserRepositoryDep = Annotated[IUserRepository, Depends(get_user_repository)]
VerificacionExtractoRepositoryDep = Annotated[
    IVerificacionExtractoRepository,
    Depends(get_verificacion_extracto_repository),
]


# --- Service providers -----------------------------------------------------

def get_reconciliation_service(
    session: SessionDep,
    pago_repo: PagoDeclaradoRepositoryDep,
    movimiento_repo: MovimientoBancarioRepositoryDep,
    conciliacion_repo: ConciliacionRepositoryDep,
    pedido_repo: PedidoRepositoryDep,
) -> ReconciliationService:
    return ReconciliationService(
        session,
        pago_repo=pago_repo,
        movimiento_repo=movimiento_repo,
        conciliacion_repo=conciliacion_repo,
        pedido_repo=pedido_repo,
    )


ReconciliationServiceDep = Annotated[
    ReconciliationService, Depends(get_reconciliation_service)
]


# --- Authentication --------------------------------------------------------

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_credentials_exc = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Credenciales inválidas o expiradas.",
    headers={"WWW-Authenticate": "Bearer"},
)


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    user_repo: UserRepositoryDep,
) -> Usuario:
    claims = decode_token(token)
    if claims is None:
        raise _credentials_exc
    subject = claims.get("sub")
    if not subject:
        raise _credentials_exc
    try:
        user_id = UUID(subject)
    except ValueError:
        raise _credentials_exc
    user = await user_repo.get(user_id)
    if user is None or not user.activo:
        raise _credentials_exc
    return user


CurrentUserDep = Annotated[Usuario, Depends(get_current_user)]


def require_role(
    *roles: RolUsuario,
) -> Callable[[Usuario], Coroutine[Any, Any, Usuario]]:
    """Build a dependency that allows only the given roles (403 otherwise)."""

    async def _checker(current: CurrentUserDep) -> Usuario:
        if current.rol not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para esta acción.",
            )
        return current

    return _checker
