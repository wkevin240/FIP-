from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.payroll.configuration import (
    PayrollAccountingProfileCreate,
    PayrollAccountingProfileResponse,
    PayrollRuleSetCreate,
    PayrollRuleSetResponse,
)
from app.services.payroll.configuration_service import PayrollConfigurationService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(
    session: AsyncSession = Depends(get_db),
) -> PayrollConfigurationService:
    return PayrollConfigurationService(session)


@router.post(
    "/rule-sets",
    response_model=PayrollRuleSetResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_rule_set(
    data: PayrollRuleSetCreate,
    service: PayrollConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_rule_set:create")),
) -> PayrollRuleSetResponse:
    return await service.create_rule_set(tenant.organization_id, tenant.user_id, data)


@router.get("/rule-sets/{rule_set_id}", response_model=PayrollRuleSetResponse)
async def get_rule_set(
    rule_set_id: str,
    service: PayrollConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_rule_set:read")),
) -> PayrollRuleSetResponse:
    return await service.get_rule_set(tenant.organization_id, rule_set_id)


@router.post(
    "/accounting-profiles",
    response_model=PayrollAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_accounting_profile(
    data: PayrollAccountingProfileCreate,
    service: PayrollConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_rule_set:create")),
) -> PayrollAccountingProfileResponse:
    return await service.create_accounting_profile(
        tenant.organization_id, tenant.user_id, data
    )


@router.get(
    "/accounting-profiles/{profile_id}", response_model=PayrollAccountingProfileResponse
)
async def get_accounting_profile(
    profile_id: str,
    service: PayrollConfigurationService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("payroll_rule_set:read")),
) -> PayrollAccountingProfileResponse:
    return await service.get_accounting_profile(tenant.organization_id, profile_id)
