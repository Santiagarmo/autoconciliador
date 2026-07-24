"""Usuario repository: abstract interface + SQLAlchemy implementation."""
from __future__ import annotations

from abc import abstractmethod

from sqlalchemy import select

from app.models.user import Usuario
from app.repositories.base import AbstractRepository, SQLAlchemyRepository


class IUserRepository(AbstractRepository[Usuario]):
    @abstractmethod
    async def get_by_email(self, email: str) -> Usuario | None: ...


class UserRepository(SQLAlchemyRepository[Usuario], IUserRepository):
    model = Usuario

    async def get_by_email(self, email: str) -> Usuario | None:
        result = await self.session.execute(
            select(Usuario).where(Usuario.email == email)
        )
        return result.scalar_one_or_none()
