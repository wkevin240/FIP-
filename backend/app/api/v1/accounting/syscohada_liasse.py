from datetime import date

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.syscohada_liasse import SyscohadaLiasseResponse
from app.services.accounting.syscohada_liasse_service import SyscohadaLiasseService
from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_liasse_service(
    session: AsyncSession = Depends(get_db),
) -> SyscohadaLiasseService:
    return SyscohadaLiasseService(session)


@router.get("/export.json", response_class=Response)
async def export_syscohada_liasse(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: SyscohadaLiasseService = Depends(get_liasse_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> Response:
    content = await service.export_json(
        tenant.organization_id, tenant.user_id, start_date, end_date
    )
    return Response(
        content=content,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=syscohada-liasse.json"},
    )


@router.get("/", response_model=SyscohadaLiasseResponse)
async def get_syscohada_liasse(
    start_date: date = Query(...),
    end_date: date = Query(...),
    service: SyscohadaLiasseService = Depends(get_liasse_service),
    tenant: CurrentTenant = Depends(require_permission("professional_reporting:read")),
) -> SyscohadaLiasseResponse:
    return await service.get_liasse(tenant.organization_id, start_date, end_date)
