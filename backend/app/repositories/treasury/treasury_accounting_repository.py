from app.models.treasury.accounting import (
    TreasuryAccountingPosting,
    TreasuryAccountingProfile,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


class TreasuryAccountingRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_profile(self, organization_id: str, for_update: bool = False):
        statement = select(TreasuryAccountingProfile).where(
            TreasuryAccountingProfile.organization_id == organization_id
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def create_profile(self, organization_id: str, journal_id: str):
        profile = TreasuryAccountingProfile(
            organization_id=organization_id, journal_id=journal_id
        )
        self.session.add(profile)
        await self.session.flush()
        return profile

    async def get_posting(self, organization_id: str, transaction_id: str):
        return await self.session.scalar(
            select(TreasuryAccountingPosting).where(
                TreasuryAccountingPosting.organization_id == organization_id,
                TreasuryAccountingPosting.source_id == transaction_id,
            )
        )

    async def create_posting(
        self,
        organization_id: str,
        transaction_id: str,
        journal_entry_id: str,
        counterpart_account_id: str,
    ):
        posting = TreasuryAccountingPosting(
            organization_id=organization_id,
            source_id=transaction_id,
            journal_entry_id=journal_entry_id,
            counterpart_account_id=counterpart_account_id,
        )
        self.session.add(posting)
        await self.session.flush()
        return posting
