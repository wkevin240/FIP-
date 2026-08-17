from app.models.inventory.accounting import (
    InventoryAccountingPosting,
    InventoryAccountingProfile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class InventoryAccountingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(self, organization_id: str, for_update: bool = False):
        statement = select(InventoryAccountingProfile).where(
            InventoryAccountingProfile.organization_id == organization_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def create_profile(self, organization_id: str, values: dict[str, object]):
        profile = InventoryAccountingProfile(organization_id=organization_id, **values)
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_posting(self, organization_id: str, movement_id: str):
        return await self.session.scalar(
            select(InventoryAccountingPosting).where(
                InventoryAccountingPosting.organization_id == organization_id,
                InventoryAccountingPosting.source_id == movement_id,
            )
        )

    async def create_posting(
        self, organization_id: str, movement_type: str, movement_id: str, entry_id: str
    ):
        posting = InventoryAccountingPosting(
            organization_id=organization_id,
            source_type=movement_type,
            source_id=movement_id,
            journal_entry_id=entry_id,
        )
        self.session.add(posting)
        await self.session.flush()
        return posting
