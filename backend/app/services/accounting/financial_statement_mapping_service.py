from app.models.accounting.account import Account
from app.models.accounting.financial_statement_mapping import FinancialStatementMapping
from app.repositories.accounting.financial_statement_mapping_repository import (
    FinancialStatementMappingRepository,
)
from app.schemas.accounting.professional_reporting import (
    FinancialStatementMappingCreate,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class FinancialStatementMappingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FinancialStatementMappingRepository(session)
        self.audit = AuditService(session)

    async def create(
        self,
        organization_id: str,
        actor_user_id: str,
        data: FinancialStatementMappingCreate,
    ) -> FinancialStatementMapping:
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
        expected_role = self._expected_presentation_role(
            account.account_type, data.statement_code
        )
        if expected_role != data.presentation_role:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "Presentation role is incompatible with the account type and statement"
                ),
            )
        if await self.repository.get_for_account_and_statement(
            organization_id, data.account_id, data.framework, data.statement_code
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Account already has a mapping for this financial statement",
            )
        try:
            mapping = await self.repository.create(organization_id, data)
            await self.audit.record(
                organization_id=organization_id,
                actor_user_id=actor_user_id,
                action="FINANCIAL_STATEMENT_MAPPING_CREATED",
                resource_type="FinancialStatementMapping",
                resource_id=mapping.id,
                new_value={
                    "account_id": mapping.account_id,
                    "framework": mapping.framework,
                    "statement_code": mapping.statement_code,
                    "presentation_role": mapping.presentation_role,
                    "section_code": mapping.section_code,
                    "line_code": mapping.line_code,
                },
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Financial statement mapping conflicts with an existing mapping",
            ) from exc
        await self.session.refresh(mapping)
        return mapping

    @staticmethod
    def _expected_presentation_role(account_type: str, statement_code: str) -> str:
        if statement_code == "BALANCE_SHEET":
            return "ASSETS" if account_type == "ASSET" else "LIABILITIES_EQUITY"
        if statement_code == "INCOME_STATEMENT" and account_type == "REVENUE":
            return "REVENUE"
        if statement_code == "INCOME_STATEMENT" and account_type == "EXPENSE":
            return "EXPENSE"
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Account type is incompatible with the requested financial statement",
        )

    async def list_active(
        self, organization_id: str, framework: str, statement_code: str
    ) -> list[FinancialStatementMapping]:
        return await self.repository.list_active(
            organization_id, framework, statement_code
        )
