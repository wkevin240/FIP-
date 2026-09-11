from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.domain.calculation.contracts import CalculationContext
from app.schemas.accounting.profitability import (
    CalculationSourceResponse,
    ProfitabilityReportResponse,
    ProfitabilityResultResponse,
)
from app.services.accounting.ledger_service import LedgerService
from app.services.accounting.profitability_service import (
    LedgerProfitabilityIntegrityError,
    LedgerProfitabilityService,
    ProfitabilityMappingAmbiguityError,
)
from app.repositories.accounting.profitability_mapping_repository import ProfitabilityMappingRepository

router = APIRouter()


def get_profitability_service(db: AsyncSession = Depends(get_db)) -> LedgerProfitabilityService:
    return LedgerProfitabilityService(
        LedgerService(db),
        ProfitabilityMappingRepository(db),
    )


@router.get("/p-and-l", response_model=ProfitabilityReportResponse)
async def profitability_report(
    start_date: date = Query(...),
    end_date: date = Query(...),
    fiscal_period_id: str | None = Query(default=None),
    rule_version: str = Query(default="1", min_length=1),
    tenant: CurrentTenant = Depends(require_permission("ledger:read")),
    service: LedgerProfitabilityService = Depends(get_profitability_service),
):
    # Direct function calls in unit tests do not pass FastAPI's Query default;
    # normalize that framework object at the application boundary.
    effective_rule_version = rule_version if isinstance(rule_version, str) else "1"
    context = CalculationContext(
        organization_id=tenant.organization_id,
        period_start=start_date,
        period_end=end_date,
        rule_version=effective_rule_version,
    )
    try:
        results = await service.calculate_from_persisted_mappings(
            context,
            fiscal_period_id=fiscal_period_id,
        )
    except ProfitabilityMappingAmbiguityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "AMBIGUOUS_PROFITABILITY_MAPPING", "account_ids": list(exc.account_ids)},
        ) from exc
    except LedgerProfitabilityIntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "LEDGER_NOT_RECONCILED", "message": str(exc)},
        ) from exc

    return ProfitabilityReportResponse(
        organization_id=tenant.organization_id,
        fiscal_period_id=fiscal_period_id,
        start_date=start_date,
        end_date=end_date,
        rule_version=effective_rule_version,
        results=[
            ProfitabilityResultResponse(
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
