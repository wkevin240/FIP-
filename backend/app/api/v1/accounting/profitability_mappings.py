from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.repositories.accounting.profitability_mapping_repository import (
    ProfitabilityMappingConflictError,
    ProfitabilityMappingNotFoundError,
    ProfitabilityMappingRepository,
)
from app.schemas.accounting.profitability import (
    ProfitabilityMappingCreateRequest,
    ProfitabilityMappingResponse,
)

router = APIRouter()


def get_mapping_repository(db: AsyncSession = Depends(get_db)) -> ProfitabilityMappingRepository:
    return ProfitabilityMappingRepository(db)


def _response(mapping) -> ProfitabilityMappingResponse:
    return ProfitabilityMappingResponse(
        id=mapping.id,
        organization_id=mapping.organization_id,
        account_id=mapping.account_id,
        category=mapping.category,
        rule_version=mapping.rule_version,
        effective_from=mapping.effective_from,
        effective_to=mapping.effective_to,
    )


@router.get("", response_model=list[ProfitabilityMappingResponse])
async def list_profitability_mappings(
    rule_version: str = Query(..., min_length=1),
    period_start: date = Query(...),
    period_end: date = Query(...),
    tenant: CurrentTenant = Depends(require_permission("profitability_mapping:read")),
    repository: ProfitabilityMappingRepository = Depends(get_mapping_repository),
):
    try:
        mappings = await repository.list_for_period(
            tenant.organization_id,
            rule_version,
            period_start,
            period_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return [_response(mapping) for mapping in mappings]


@router.post("", response_model=ProfitabilityMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_profitability_mapping(
    payload: ProfitabilityMappingCreateRequest,
    tenant: CurrentTenant = Depends(require_permission("profitability_mapping:create")),
    repository: ProfitabilityMappingRepository = Depends(get_mapping_repository),
):
    try:
        mapping = await repository.create(
            organization_id=tenant.organization_id,
            account_id=payload.account_id,
            category=payload.category,
            rule_version=payload.rule_version,
            effective_from=payload.effective_from,
            effective_to=payload.effective_to,
        )
    except ProfitabilityMappingConflictError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return _response(mapping)
