from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.repositories.accounting.balance_sheet_mapping_repository import BalanceSheetMappingRepository
from app.schemas.accounting.balance_sheet import BalanceSheetReportResponse, BalanceSheetResultResponse, CalculationSourceResponse
from app.services.accounting.balance_sheet_service import BalanceSheetMappingAmbiguityError, LedgerBalanceSheetService
from app.services.accounting.ledger_service import LedgerService

router = APIRouter()


def get_service(db: AsyncSession = Depends(get_db)) -> LedgerBalanceSheetService:
    return LedgerBalanceSheetService(LedgerService(db), BalanceSheetMappingRepository(db))


@router.get("", response_model=BalanceSheetReportResponse)
async def balance_sheet_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    fiscal_period_id: str | None = Query(default=None),
    rule_version: str = Query(default="1", min_length=1),
    tenant: CurrentTenant = Depends(require_permission("ledger:read")),
    service: LedgerBalanceSheetService = Depends(get_service),
):
    if start_date > end_date:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="start_date must be on or before end_date")
    from app.domain.calculation.contracts import CalculationContext

    context = CalculationContext(
        organization_id=tenant.organization_id,
        period_start=start_date,
        period_end=end_date,
        rule_version=rule_version,
    )
    try:
        results = await service.calculate_from_persisted_mappings(
            context,
            fiscal_period_id=fiscal_period_id,
        )
    except BalanceSheetMappingAmbiguityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AMBIGUOUS_BALANCE_SHEET_MAPPING", "account_ids": list(exc.account_ids)},
        ) from exc

    return BalanceSheetReportResponse(
        organization_id=tenant.organization_id,
        fiscal_period_id=fiscal_period_id,
        start_date=start_date,
        end_date=end_date,
        rule_version=rule_version,
        results=[
            BalanceSheetResultResponse(
                code=code,
                formula=result.definition.formula,
                rule_version=result.definition.rule_version,
                status=result.status.value,
                value=result.value,
                reason=result.reason,
                sources=[
                    CalculationSourceResponse(
                        record_type=source.record_type,
                        record_id=source.record_id,
                        module=source.module,
                    )
                    for source in result.sources
                ],
            )
            for code, result in results.items()
        ],
    )
