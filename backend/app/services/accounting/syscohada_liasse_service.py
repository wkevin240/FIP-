import json
from datetime import date

from app.repositories.accounting.syscohada_liasse_repository import (
    SyscohadaLiasseRepository,
)
from app.schemas.accounting.syscohada_liasse import (
    AnnexNoteResponse,
    LiasseReadinessResponse,
    LiasseReadinessStatus,
    SyscohadaLiasseResponse,
)
from app.services.accounting.cash_flow_service import CashFlowService
from app.services.accounting.reporting_service import ReportingService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class SyscohadaLiasseService:
    """Assemble a no-data-invention SYSCOHADA preparation package."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repository = SyscohadaLiasseRepository(session)
        self.reporting = ReportingService(session)
        self.cash_flow = CashFlowService(session)
        self.audit = AuditService(session)

    async def get_liasse(
        self, organization_id: str, start_date: date, end_date: date
    ) -> SyscohadaLiasseResponse:
        self._validate_range(start_date, end_date)
        posted_entry_count = await self.repository.posted_entry_count(
            organization_id, start_date, end_date
        )
        if posted_entry_count == 0:
            readiness = LiasseReadinessResponse(
                status=LiasseReadinessStatus.NOT_READY,
                reasons=["NO_POSTED_ENTRIES_FOR_PERIOD"],
                posted_entry_count=0,
            )
            return SyscohadaLiasseResponse(
                start_date=start_date,
                end_date=end_date,
                readiness=readiness,
                annex_notes=self._empty_notes(readiness.status),
            )

        reconciliation = await self.reporting.reconcile_reporting(
            organization_id, start_date, end_date
        )
        trial_balance = await self.reporting.professional_trial_balance(
            organization_id, start_date, end_date
        )
        balance_sheet = await self.reporting.professional_financial_statement(
            organization_id, "BALANCE_SHEET", end_date
        )
        income_statement = await self.reporting.professional_financial_statement(
            organization_id, "INCOME_STATEMENT", end_date, start_date
        )
        reasons: list[str] = []
        if not reconciliation.is_consistent:
            reasons.append("REPORTING_RECONCILIATION_FAILED")
        if balance_sheet.unmapped_account_codes:
            reasons.append("UNMAPPED_BALANCE_SHEET_ACCOUNTS")
        if income_statement.unmapped_account_codes:
            reasons.append("UNMAPPED_INCOME_STATEMENT_ACCOUNTS")

        cash_flow = None
        try:
            cash_flow = await self.cash_flow.statement(
                organization_id, start_date, end_date
            )
        except HTTPException:
            reasons.append("CASH_FLOW_NOT_CONFIGURED")
        else:
            if not cash_flow.is_reconciled:
                reasons.append("CASH_FLOW_RECONCILIATION_FAILED")
            if not cash_flow.is_complete:
                reasons.append("CASH_FLOW_CLASSIFICATION_INCOMPLETE")

        readiness = LiasseReadinessResponse(
            status=(
                LiasseReadinessStatus.READY
                if not reasons
                else LiasseReadinessStatus.INCOMPLETE
            ),
            reasons=reasons,
            posted_entry_count=posted_entry_count,
        )
        return SyscohadaLiasseResponse(
            start_date=start_date,
            end_date=end_date,
            readiness=readiness,
            reconciliation=reconciliation,
            professional_trial_balance=trial_balance,
            balance_sheet=balance_sheet,
            income_statement=income_statement,
            cash_flow=cash_flow,
            annex_notes=self._notes(
                readiness.status, balance_sheet, income_statement, cash_flow
            ),
        )

    async def export_json(
        self,
        organization_id: str,
        actor_user_id: str,
        start_date: date,
        end_date: date,
    ) -> str:
        liasse = await self.get_liasse(organization_id, start_date, end_date)
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SYSCOHADA_LIASSE_EXPORTED",
            resource_type="SYSCOHADALiasse",
            resource_id=f"{start_date.isoformat()}:{end_date.isoformat()}",
            context={"format": "json", "status": liasse.readiness.status.value},
        )
        await self.session.commit()
        return json.dumps(
            liasse.model_dump(mode="json"),
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )

    @staticmethod
    def _validate_range(start_date: date, end_date: date) -> None:
        if start_date > end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Start date must not be after end date",
            )

    @staticmethod
    def _empty_notes(status: LiasseReadinessStatus) -> list[AnnexNoteResponse]:
        return [
            AnnexNoteResponse(
                code=code,
                title=title,
                status=status,
                data={},
            )
            for code, title in (
                ("NOTE-BS", "Notes relatives au bilan"),
                ("NOTE-IS", "Notes relatives au compte de résultat"),
                ("NOTE-CF", "Notes relatives aux flux de trésorerie"),
            )
        ]

    @staticmethod
    def _notes(
        status: LiasseReadinessStatus,
        balance_sheet: object,
        income_statement: object,
        cash_flow: object | None,
    ) -> list[AnnexNoteResponse]:
        balance_sheet_data = balance_sheet.model_dump(mode="json")
        income_statement_data = income_statement.model_dump(mode="json")
        cash_flow_data = (
            cash_flow.model_dump(mode="json") if cash_flow is not None else {}
        )
        return [
            AnnexNoteResponse(
                code="NOTE-BS",
                title="Notes relatives au bilan",
                status=status,
                data={"statement": balance_sheet_data},
            ),
            AnnexNoteResponse(
                code="NOTE-IS",
                title="Notes relatives au compte de résultat",
                status=status,
                data={"statement": income_statement_data},
            ),
            AnnexNoteResponse(
                code="NOTE-CF",
                title="Notes relatives aux flux de trésorerie",
                status=(
                    status if cash_flow is not None else LiasseReadinessStatus.NOT_READY
                ),
                data={"statement": cash_flow_data},
            ),
        ]
