from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.invoicing.credit_note import CreditNoteCreate, CreditNoteResponse
from app.services.invoicing.credit_note_service import CreditNoteService
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> CreditNoteService:
    return CreditNoteService(session)


@router.post(
    "/", response_model=CreditNoteResponse, status_code=status.HTTP_201_CREATED
)
async def create_credit_note(
    data: CreditNoteCreate,
    service: CreditNoteService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("credit_note:create")),
) -> CreditNoteResponse:
    return await service.create_credit_note(tenant.organization_id, data)


@router.get("/invoices/{invoice_id}", response_model=list[CreditNoteResponse])
async def list_credit_notes(
    invoice_id: str,
    service: CreditNoteService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("credit_note:read")),
) -> list[CreditNoteResponse]:
    return await service.list_credit_notes(tenant.organization_id, invoice_id)
