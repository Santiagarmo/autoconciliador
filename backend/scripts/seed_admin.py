"""Seed an initial AUDITOR user (idempotent).

Run from the backend/ directory once migrations are applied:

    python -m scripts.seed_admin

Credentials come from env: SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD.
Opens its own session (independent of any request lifecycle).
"""
from __future__ import annotations

import asyncio
import os

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.domain.enums import RolUsuario
from app.models.user import Usuario
from app.repositories.user_repository import UserRepository


async def seed_admin() -> None:
    email = os.getenv("SEED_ADMIN_EMAIL", "admin@autoconciliador.local")
    password = os.getenv("SEED_ADMIN_PASSWORD", "Cambiar-Esta-Clave-123")

    async with AsyncSessionLocal() as session:
        repo = UserRepository(session)
        existing = await repo.get_by_email(email)
        if existing is not None:
            print(f"[seed] Usuario '{email}' ya existe (rol={existing.rol.value}).")
            return

        usuario = Usuario(
            email=email,
            hashed_password=hash_password(password),
            rol=RolUsuario.AUDITOR,
        )
        await repo.add(usuario)
        await session.commit()
        print(f"[seed] Auditor creado: '{email}'.")


if __name__ == "__main__":
    asyncio.run(seed_admin())
