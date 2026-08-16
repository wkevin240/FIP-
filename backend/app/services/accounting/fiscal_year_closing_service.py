from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.repositories.accounting.fiscal_year_closing_repository import (
    FiscalYearClosingRepository,
)
from app.schemas.accounting.fiscal_year_closing import (
    FiscalYearClosingPreviewResponse,
    FiscalYearClosingResponse,
)
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class FiscalYearClosingService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = FiscalYearClosingRepository(session)
        self.audit = AuditService(session)

    async def preview(
        self, organization_id: str, fiscal_year_id: str
    ) -> FiscalYearClosingPreviewResponse:
        fiscal_year = await self._get(organization_id, fiscal_year_id)
        periods = await self.repository.periods(organization_id, fiscal_year_id)
        draft_entry_count = await self.repository.draft_entry_count(
            organization_id, fiscal_year_id
        )
        open_period_count = sum(
            period.status == FiscalPeriodStatus.OPEN for period in periods
        )
        locked_period_count = sum(
            period.status == FiscalPeriodStatus.LOCKED for period in periods
        )
        blockers: list[str] = []
        if fiscal_year.status == FiscalYearStatus.CLOSED:
            blockers.append("FISCAL_YEAR_ALREADY_CLOSED")
        if not periods:
            blockers.append("NO_FISCAL_PERIODS")
        if open_period_count:
            blockers.append("OPEN_FISCAL_PERIODS")
        if locked_period_count:
            blockers.append("LOCKED_FISCAL_PERIODS")
        if draft_entry_count:
            blockers.append("DRAFT_JOURNAL_ENTRIES")
        return FiscalYearClosingPreviewResponse(
            fiscal_year_id=fiscal_year.id,
            start_date=fiscal_year.start_date,
            end_date=fiscal_year.end_date,
            current_status=fiscal_year.status,
            fiscal_period_count=len(periods),
            open_period_count=open_period_count,
            locked_period_count=locked_period_count,
            draft_entry_count=draft_entry_count,
            is_ready=not blockers,
            blockers=blockers,
        )

    async def close(
        self, organization_id: str, fiscal_year_id: str, actor_user_id: str
    ) -> FiscalYearClosingResponse:
        fiscal_year = await self.repository.get_fiscal_year(
            organization_id, fiscal_year_id, for_update=True
        )
        if fiscal_year is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Fiscal year not found"
            )
        preview = await self.preview(organization_id, fiscal_year_id)
        if not preview.is_ready:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "message": "Fiscal year is not ready for closing",
                    "blockers": preview.blockers,
                },
            )
        fiscal_year.status = FiscalYearStatus.CLOSED
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="FISCAL_YEAR_CLOSED",
            resource_type="FiscalYear",
            resource_id=fiscal_year.id,
            previous_value={"status": FiscalYearStatus.OPEN.value},
            new_value={"status": FiscalYearStatus.CLOSED.value},
        )
        await self.session.commit()
        await self.session.refresh(fiscal_year)
        return FiscalYearClosingResponse(
            **preview.model_dump(exclude={"current_status"}),
            current_status=FiscalYearStatus.OPEN,
            status=fiscal_year.status,
        )

    async def _get(self, organization_id: str, fiscal_year_id: str):
        fiscal_year = await self.repository.get_fiscal_year(
            organization_id, fiscal_year_id
        )
        if fiscal_year is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Fiscal year not found"
            )
        return fiscal_year
