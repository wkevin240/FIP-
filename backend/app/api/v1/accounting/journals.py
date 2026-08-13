from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.journal import JournalCreate, JournalResponse
from app.services.accounting.journal_service import JournalService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> JournalService:
    return JournalService(session)


@router.post("/", response_model=JournalResponse, status_code=status.HTTP_201_CREATED)
async def create_journal(
    data: JournalCreate,
    service: JournalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal:create")),
) -> JournalResponse:
    return await service.create_journal(tenant.organization_id, data)


@router.get("/", response_model=list[JournalResponse])
async def list_journals(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: JournalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal:read")),
) -> list[JournalResponse]:
    return await service.get_all_journals(tenant.organization_id, skip, limit)


@router.get("/{journal_id}", response_model=JournalResponse)
async def get_journal(
    journal_id: str,
    service: JournalService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal:read")),
) -> JournalResponse:
    return await service.get_journal(tenant.organization_id, journal_id)
