from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.membership import OrganizationMembership
from app.models.user import User


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_email(self, email: str) -> User | None:
        return await self.session.scalar(
            select(User).where(User.email == email.lower())
        )

    async def get_by_id(self, user_id: str) -> User | None:
        return await self.session.scalar(select(User).where(User.id == user_id))

    async def get_membership(
        self, user_id: str, organization_id: str
    ) -> OrganizationMembership | None:
        return await self.session.scalar(
            select(OrganizationMembership).where(
                OrganizationMembership.user_id == user_id,
                OrganizationMembership.organization_id == organization_id,
            )
        )

    async def create(self, user: User) -> User:
        self.session.add(user)
        await self.session.flush()
        return user
