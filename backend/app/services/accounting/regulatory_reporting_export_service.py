import json
from datetime import date

from app.services.accounting.reporting_service import ReportingService
from app.services.audit.audit_service import AuditService
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession


class RegulatoryReportingExportService:
    """Create a deterministic, auditable structured SYSCOHADA reporting package."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.reporting = ReportingService(session)
        self.audit = AuditService(session)

    async def export_syscohada_package(
        self,
        organization_id: str,
        actor_user_id: str,
        start_date: date,
        end_date: date,
    ) -> str:
        reconciliation = await self.reporting.reconcile_reporting(
            organization_id, start_date, end_date
        )
        balance_sheet = await self.reporting.professional_financial_statement(
            organization_id, "BALANCE_SHEET", end_date
        )
        income_statement = await self.reporting.professional_financial_statement(
            organization_id, "INCOME_STATEMENT", end_date, start_date
        )
        if (
            not reconciliation.is_consistent
            or balance_sheet.unmapped_account_codes
            or income_statement.unmapped_account_codes
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=(
                    "A complete and reconciled professional reporting mapping is "
                    "required before exporting a SYSCOHADA package"
                ),
            )
        trial_balance = await self.reporting.professional_trial_balance(
            organization_id, start_date, end_date
        )
        package = {
            "schema_version": "1.0",
            "framework": "SYSCOHADA",
            "organization_id": organization_id,
            "reporting_period": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
            },
            "controls": reconciliation.model_dump(mode="json"),
            "trial_balance": trial_balance.model_dump(mode="json"),
            "balance_sheet": balance_sheet.model_dump(mode="json"),
            "income_statement": income_statement.model_dump(mode="json"),
        }
        content = json.dumps(
            package,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        await self.audit.record(
            organization_id=organization_id,
            actor_user_id=actor_user_id,
            action="SYSCOHADA_REPORTING_PACKAGE_EXPORTED",
            resource_type="SYSCOHADAReportingPackage",
            resource_id=f"{start_date.isoformat()}:{end_date.isoformat()}",
            context={"format": "json", "schema_version": "1.0"},
        )
        await self.session.commit()
        return content
