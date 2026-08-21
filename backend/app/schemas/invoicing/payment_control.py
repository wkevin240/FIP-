from datetime import date
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class PaymentAllocationCreate(BaseModel):
    payment_id: str
    invoice_id: str
    allocated_amount: Decimal = Field(
        ..., gt=Decimal("0.00"), max_digits=18, decimal_places=2
    )
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    allocation_reference: str | None = Field(default=None, max_length=255)


class SupplierPaymentAllocationCreate(BaseModel):
    supplier_payment_id: str
    purchase_invoice_id: str
    allocated_amount: Decimal = Field(
        ..., gt=Decimal("0.00"), max_digits=18, decimal_places=2
    )
    idempotency_key: str = Field(..., min_length=1, max_length=128)
    allocation_reference: str | None = Field(default=None, max_length=255)


class PaymentAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    payment_id: str
    invoice_id: str
    allocated_amount: Decimal
    idempotency_key: str
    allocation_reference: str | None


class SupplierPaymentAllocationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    supplier_payment_id: str
    purchase_invoice_id: str
    allocated_amount: Decimal
    idempotency_key: str
    allocation_reference: str | None


class PaymentControlResponse(BaseModel):
    organization_id: str
    payment_id: str
    payment_amount: Decimal
    allocated_amount: Decimal
    unapplied_amount: Decimal
    status: str
    allocations: list[PaymentAllocationResponse]
    blockers: list[str]


class SupplierPaymentControlResponse(BaseModel):
    organization_id: str
    supplier_payment_id: str
    payment_amount: Decimal
    allocated_amount: Decimal
    unapplied_amount: Decimal
    status: str
    allocations: list[SupplierPaymentAllocationResponse]
    blockers: list[str]


class PaymentReconciliationResponse(BaseModel):
    organization_id: str
    as_of: date
    status: str
    customer_unapplied_payments: Decimal
    supplier_unapplied_payments: Decimal
    payment_without_bank_transaction: int
    bank_transaction_without_payment: int
    amount_differences: Decimal
    blockers: list[str]
