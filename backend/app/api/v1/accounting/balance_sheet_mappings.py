from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.audit.audit_context import AuditContext
from app.audit.audit_service import AuditService
from app.db.session import get_db
from app.repositories.accounting.balance_sheet_mapping_repository import (
    BalanceSheetMappingConflictError,
    BalanceSheetMappingRepository,
)
from app.schemas.accounting.balance_sheet_mapping import (
    BalanceSheetMappingCreateRequest,
    BalanceSheetMappingResponse,
)

router = APIRouter()


def get_repository(db: AsyncSession = Depends(get_db)) -> BalanceSheetMappingRepository:
    return BalanceSheetMappingRepository(db)


def get_audit_service() -> type[AuditService]:
    return AuditService


def _response(mapping) -> BalanceSheetMappingResponse:
    return BalanceSheetMappingResponse(
        id=mapping.id,
        organization_id=mapping.organization_id,
        account_id=mapping.account_id,
        category=mapping.category,
        rule_version=mapping.rule_version,
        effective_from=mapping.effective_from,
        effective_to=mapping.effective_to,
    )


@router.get("", response_model=list[BalanceSheetMappingResponse])
async def list_mappings(
    rule_version: str = Query(..., min_length=1),
    period_start: date = Query(...),
    period_end: date = Query(...),
    tenant: CurrentTenant = Depends(require_permission("balance_sheet_mapping:read")),
    repository: BalanceSheetMappingRepository = Depends(get_repository),
):
    try:
        mappings = await repository.list_for_period(
            tenant.organization_id, rule_version, period_start, period_end
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return [_response(mapping) for mapping in mappings]


@router.post("", response_model=BalanceSheetMappingResponse, status_code=status.HTTP_201_CREATED)
async def create_mapping(
    payload: BalanceSheetMappingCreateRequest,
    tenant: CurrentTenant = Depends(require_permission("balance_sheet_mapping:create")),
    repository: BalanceSheetMappingRepository = Depends(get_repository),
    audit_service: type[AuditService] = Depends(get_audit_service),
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
    except BalanceSheetMappingConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    audit_service.record(
        AuditContext(
            organization_id=tenant.organization_id,
            actor_id=tenant.user_id,
            action="BALANCE_SHEET_MAPPING_CREATED",
        ),
        entity_type="BalanceSheetAccountMapping",
        entity_id=mapping.id,
        payload={
            "account_id": mapping.account_id,
            "category": mapping.category,
            "rule_version": mapping.rule_version,
            "effective_from": mapping.effective_from.isoformat(),
            "effective_to": (
                mapping.effective_to.isoformat() if mapping.effective_to is not None else None
            ),
        },
    )
    return _response(mapping)
