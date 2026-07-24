"""Auth router: login (JWT), current user, and user creation (auditor-only)."""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.exc import IntegrityError

from app.api.deps import (
    CurrentUserDep,
    SessionDep,
    UserRepositoryDep,
    require_role,
)
from app.core.security import create_access_token, hash_password, verify_password
from app.domain.enums import RolUsuario
from app.models.user import Usuario
from app.schemas.user import Token, UserCreate, UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=Token)
async def login(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    user_repo: UserRepositoryDep,
) -> Token:
    """OAuth2 password flow: ``username`` is the email, returns a JWT."""
    user = await user_repo.get_by_email(form.username)
    if (
        user is None
        or not user.activo
        or not verify_password(form.password, user.hashed_password)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email o contraseña incorrectos.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = create_access_token(subject=str(user.id), rol=user.rol.value)
    return Token(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(current: CurrentUserDep) -> Usuario:
    return current


@router.post(
    "/users",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_role(RolUsuario.AUDITOR))],
)
async def create_user(
    payload: UserCreate,
    user_repo: UserRepositoryDep,
    session: SessionDep,
) -> Usuario:
    """Create an operator. Restricted to auditors."""
    usuario = Usuario(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        rol=payload.rol,
    )
    try:
        await user_repo.add(usuario)
        await session.commit()
    except IntegrityError:
        await session.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un usuario con el email '{payload.email}'.",
        )
    return usuario
