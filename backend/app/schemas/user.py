"""Pydantic DTOs for Usuario and JWT auth (Phase 4)."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import RolUsuario


class UserCreate(BaseModel):
    """Input DTO to create an operator (auditor-only endpoint).

    ``email`` is a plain string: operator accounts use internal domains
    (e.g. ``admin@autoconciliador.local``) that strict RFC email validation
    rejects as reserved TLDs.
    """

    email: str = Field(..., min_length=3)
    password: str = Field(..., min_length=8)
    rol: RolUsuario = RolUsuario.ASESOR


class UserRead(BaseModel):
    """Output DTO — never exposes the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: str
    rol: RolUsuario
    activo: bool
    created_at: datetime


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
