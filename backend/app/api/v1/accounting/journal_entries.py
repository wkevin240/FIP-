from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.journal_entry import (
    JournalEntryCreate,
    JournalEntryResponse,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> JournalEntryService:
    return JournalEntryService(session)


@router.post(
    "/", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED
)
async def create_journal_entry(
    data: JournalEntryCreate,
    service: JournalEntryService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal_entry:create")),
) -> JournalEntryResponse:
    return await service.create_entry(tenant.organization_id, data)


@router.get("/", response_model=list[JournalEntryResponse])
async def list_journal_entries(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    service: JournalEntryService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal_entry:read")),
) -> list[JournalEntryResponse]:
    return await service.get_all_entries(tenant.organization_id, skip, limit)


@router.get("/{journal_entry_id}", response_model=JournalEntryResponse)
async def get_journal_entry(
    journal_entry_id: str,
    service: JournalEntryService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal_entry:read")),
) -> JournalEntryResponse:
    return await service.get_entry(tenant.organization_id, journal_entry_id)


@router.post("/{journal_entry_id}/post", response_model=JournalEntryResponse)
async def post_journal_entry(
    journal_entry_id: str,
    service: JournalEntryService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("journal_entry:post")),
) -> JournalEntryResponse:
    return await service.post_entry(tenant.organization_id, journal_entry_id)
