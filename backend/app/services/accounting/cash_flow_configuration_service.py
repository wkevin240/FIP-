from app.models.accounting.account import Account
from app.repositories.accounting.cash_flow_account_mapping_repository import (
    CashFlowAccountMappingRepository,
)
from app.schemas.accounting.cash_flow import CashFlowAccountMappingCreate
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class CashFlowConfigurationService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = CashFlowAccountMappingRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        organization_id: str,
        actor_user_id: str,
        data: CashFlowAccountMappingCreate,
    ):
        account = await self.session.scalar(
            select(Account).where(
                Account.organization_id == organization_id,
                Account.id == data.account_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active account in the current organization is required",
            )
        if data.is_cash_account and account.account_type != "ASSET":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Cash-flow cash accounts must be ASSET accounts",
            )
        if await self.repository.get_by_account(organization_id, data.account_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account already has a cash-flow mapping",
            )
        try:
            mapping = await self.repository.create(organization_id, data)
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="CASH_FLOW_ACCOUNT_MAPPING_CREATED",
                resource_type="CashFlowAccountMapping",
                resource_id=mapping.id,
                new_value={
                    "account_id": mapping.account_id,
                    "is_cash_account": mapping.is_cash_account,
                    "cash_flow_category": mapping.cash_flow_category,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Cash-flow mapping conflicts with an existing mapping",
            ) from exc
        await self.session.refresh(mapping)
        return mapping

    async def list_active(self, organization_id: str):
        return await self.repository.list_active(organization_id)
