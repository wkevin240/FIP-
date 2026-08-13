from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, organization_id: str) -> Organization | None:
        return await self.session.scalar(select(Organization).where(Organization.id == organization_id))

    async def get_by_name(self, name: str) -> Organization | None:
        return await self.session.scalar(select(Organization).where(Organization.name == name))

    async def create(self, organization: Organization) -> Organization:
        self.session.add(organization)
        await self.session.flush()
        return organization
