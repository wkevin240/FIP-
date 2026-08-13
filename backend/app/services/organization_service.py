from sqlalchemy.ext.asyncio import AsyncSession

from app.models.organization import Organization
from app.repositories.organization_repository import OrganizationRepository
from app.schemas.organization import OrganizationCreate


class OrganizationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = OrganizationRepository(session)

    async def create(self, data: OrganizationCreate) -> Organization:
        name = data.name.strip()
        if await self.repository.get_by_name(name):
            raise ValueError("Organization name already exists")
        organization = await self.repository.create(Organization(name=name))
        await self.session.commit()
        await self.session.refresh(organization)
        return organization
