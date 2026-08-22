from datetime import date, datetime
from decimal import Decimal

from app.core.enums.invoicing import PaymentMethod
from pydantic import BaseModel, ConfigDict, Field


class PaymentCreate(BaseModel):
    invoice_id: str | None = None
    payment_date: date
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    method: PaymentMethod
    external_reference: str | None = Field(default=None, max_length=100)
    notes: str | None = Field(default=None, max_length=500)


class PaymentResponse(BaseModel):
    id: str
    organization_id: str
    invoice_id: str | None
    payment_date: date
    amount: Decimal
    method: PaymentMethod
    external_reference: str | None
    received_at: datetime
    notes: str | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class PaymentAllocationCreate(BaseModel):
    invoice_id: str = Field(min_length=1)
    amount: Decimal = Field(..., gt=0, max_digits=18, decimal_places=2)
    idempotency_key: str = Field(min_length=1, max_length=128)


class PaymentAllocationResponse(BaseModel):
    id: str
    organization_id: str
    payment_id: str
    invoice_id: str
    amount: Decimal
    allocated_at: str
    allocated_by_user_id: str | None
    model_config = ConfigDict(from_attributes=True)


class ReceivableInvoiceResponse(BaseModel):
    invoice_id: str
    invoice_number: str
    customer_name: str
    customer_tax_id: str | None
    invoice_date: date
    due_date: date | None
    total_amount: Decimal
    paid_amount: Decimal
    credited_amount: Decimal
    outstanding_amount: Decimal
    age_bucket: str | None
    overdue_amount: Decimal


class ReceivableCustomerBalanceResponse(BaseModel):
    customer_key: str
    customer_name: str
    customer_tax_id: str | None
    outstanding_amount: Decimal
    overdue_amount: Decimal
    invoices: list[ReceivableInvoiceResponse]


class ReceivableStatementResponse(BaseModel):
    organization_id: str
    as_of_date: date
    customer_key: str | None
    total_invoiced: Decimal
    total_paid: Decimal
    total_credited: Decimal
    total_outstanding: Decimal
    total_overdue: Decimal
    customers: list[ReceivableCustomerBalanceResponse]
