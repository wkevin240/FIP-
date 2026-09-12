from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.accounting.journal_entry import JournalEntryCreate, JournalEntryResponse, JournalEntryReverse
from app.services.accounting.journal_entry_service import JournalEntryService

router = APIRouter()


def get_journal_entry_service(db: AsyncSession = Depends(get_db)) -> JournalEntryService:
    return JournalEntryService(db)


@router.post("/", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def create_journal_entry(
    entry_in: JournalEntryCreate,
    tenant: CurrentTenant = Depends(require_permission("journal_entry:create")),
    service: JournalEntryService = Depends(get_journal_entry_service),
):
    return await service.create(tenant.organization_id, tenant.user_id, entry_in)


@router.get("/{entry_id}", response_model=JournalEntryResponse)
async def read_journal_entry(
    entry_id: str,
    tenant: CurrentTenant = Depends(require_permission("journal_entry:read")),
    service: JournalEntryService = Depends(get_journal_entry_service),
):
    return await service.get(tenant.organization_id, entry_id)


@router.post("/{entry_id}/post", response_model=JournalEntryResponse)
async def post_journal_entry(
    entry_id: str,
    tenant: CurrentTenant = Depends(require_permission("journal_entry:post")),
    service: JournalEntryService = Depends(get_journal_entry_service),
):
    return await service.post(tenant.organization_id, entry_id, tenant.user_id)


@router.post("/{entry_id}/reverse", response_model=JournalEntryResponse, status_code=status.HTTP_201_CREATED)
async def reverse_journal_entry(
    entry_id: str,
    reverse_in: JournalEntryReverse,
    tenant: CurrentTenant = Depends(require_permission("journal_entry:reverse")),
    service: JournalEntryService = Depends(get_journal_entry_service),
):
    return await service.reverse(tenant.organization_id, entry_id, tenant.user_id, reverse_in)
