from typing import Annotated

from fastapi import APIRouter, Depends, Header, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import CurrentTenant, require_permission
from app.db.session import get_db
from app.schemas.procurement import (
    AccountingPostingResponse,
    ProcurementAccountingProfileCreate,
    ProcurementAccountingProfileResponse,
    PurchaseInvoiceCreate,
    PurchaseInvoiceResponse,
    SupplierCreate,
    SupplierPaymentCreate,
    SupplierPaymentResponse,
    SupplierResponse,
)
from app.schemas.procurement_approval import (
    PurchaseInvoiceApprovalDecision,
    PurchaseInvoiceApprovalResponse,
)
from app.schemas.procurement_flow import (
    GoodsReceiptCreate,
    GoodsReceiptResponse,
    PurchaseOrderCreate,
    PurchaseOrderResponse,
    PurchaseRequestCreate,
    PurchaseRequestResponse,
    ThreeWayMatchResponse,
)
from app.services.procurement_approval_service import ProcurementApprovalService
from app.services.procurement_flow_service import ProcurementFlowService
from app.services.procurement_service import ProcurementService

router = APIRouter()


async def get_service(session: AsyncSession = Depends(get_db)) -> ProcurementService:
    return ProcurementService(session)


async def get_approval_service(
    session: AsyncSession = Depends(get_db),
) -> ProcurementApprovalService:
    return ProcurementApprovalService(session)


async def get_flow_service(
    session: AsyncSession = Depends(get_db),
) -> ProcurementFlowService:
    return ProcurementFlowService(session)


@router.post(
    "/purchase-requests",
    response_model=PurchaseRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_request(
    data: PurchaseRequestCreate,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_request:create")),
):
    return await service.create_request(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/purchase-requests/{request_id}/{target}",
    response_model=PurchaseRequestResponse,
)
async def transition_purchase_request(
    request_id: str,
    target: str,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_request:approve")),
):
    return await service.transition_request(
        tenant.organization_id, tenant.user_id, request_id, target.upper()
    )


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_purchase_order(
    data: PurchaseOrderCreate,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_order:create")),
):
    return await service.create_order(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/purchase-orders/{order_id}/issue",
    response_model=PurchaseOrderResponse,
)
async def issue_purchase_order(
    order_id: str,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_order:issue")),
):
    return await service.issue_order(tenant.organization_id, tenant.user_id, order_id)


@router.post(
    "/goods-receipts",
    response_model=GoodsReceiptResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_goods_receipt(
    data: GoodsReceiptCreate,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("goods_receipt:create")),
):
    return await service.create_receipt(tenant.organization_id, tenant.user_id, data)


@router.get(
    "/invoices/{invoice_id}/three-way-match",
    response_model=ThreeWayMatchResponse,
)
async def three_way_match(
    invoice_id: str,
    service: ProcurementFlowService = Depends(get_flow_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:read")),
):
    return await service.three_way_match(tenant.organization_id, invoice_id)


@router.post(
    "/suppliers", response_model=SupplierResponse, status_code=status.HTTP_201_CREATED
)
async def create_supplier(
    data: SupplierCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier:create")),
):
    return await service.create_supplier(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/accounting-profile",
    response_model=ProcurementAccountingProfileResponse,
    status_code=status.HTTP_201_CREATED,
)
async def configure_profile(
    data: ProcurementAccountingProfileCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(
        require_permission("procurement:accounting:configure")
    ),
):
    return await service.configure_profile(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/invoices",
    response_model=PurchaseInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_invoice(
    data: PurchaseInvoiceCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:create")),
):
    return await service.create_invoice(tenant.organization_id, tenant.user_id, data)


@router.post("/invoices/{invoice_id}/validate", response_model=PurchaseInvoiceResponse)
async def validate_invoice(
    invoice_id: str,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:validate")),
):
    return await service.validate_invoice(
        tenant.organization_id, tenant.user_id, invoice_id
    )


@router.post(
    "/invoices/{invoice_id}/approval",
    response_model=PurchaseInvoiceApprovalResponse,
    status_code=status.HTTP_201_CREATED,
)
async def request_invoice_approval(
    invoice_id: str,
    service: ProcurementApprovalService = Depends(get_approval_service),
    tenant: CurrentTenant = Depends(
        require_permission("purchase_invoice:approval:request")
    ),
):
    return await service.request(tenant.organization_id, tenant.user_id, invoice_id)


@router.get(
    "/invoices/{invoice_id}/approval",
    response_model=PurchaseInvoiceApprovalResponse | None,
)
async def get_invoice_approval(
    invoice_id: str,
    service: ProcurementApprovalService = Depends(get_approval_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:read")),
):
    return await service.get(tenant.organization_id, invoice_id)


@router.post(
    "/invoices/{invoice_id}/approval/decision",
    response_model=PurchaseInvoiceApprovalResponse,
)
async def decide_invoice_approval(
    invoice_id: str,
    data: PurchaseInvoiceApprovalDecision,
    service: ProcurementApprovalService = Depends(get_approval_service),
    tenant: CurrentTenant = Depends(
        require_permission("purchase_invoice:approval:decide")
    ),
):
    return await service.decide(
        tenant.organization_id,
        tenant.user_id,
        invoice_id,
        data.decision,
        data.reason,
    )


@router.post(
    "/invoices/{invoice_id}/post-accounting", response_model=AccountingPostingResponse
)
async def post_invoice(
    invoice_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("purchase_invoice:post")),
):
    return await service.post_invoice(
        tenant.organization_id, tenant.user_id, invoice_id, idempotency_key
    )


@router.post(
    "/payments",
    response_model=SupplierPaymentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_payment(
    data: SupplierPaymentCreate,
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:create")),
):
    return await service.create_payment(tenant.organization_id, tenant.user_id, data)


@router.post(
    "/payments/{payment_id}/post-accounting", response_model=AccountingPostingResponse
)
async def post_payment(
    payment_id: str,
    idempotency_key: Annotated[
        str, Header(alias="Idempotency-Key", min_length=1, max_length=128)
    ],
    service: ProcurementService = Depends(get_service),
    tenant: CurrentTenant = Depends(require_permission("supplier_payment:post")),
):
    return await service.post_payment(
        tenant.organization_id, tenant.user_id, payment_id, idempotency_key
    )
