from datetime import date
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

Money = Annotated[Decimal, Field(max_digits=18, decimal_places=2, ge=Decimal("0.00"))]


class SupplierCreate(BaseModel):
    supplier_code: str = Field(min_length=1, max_length=64)
    legal_name: str = Field(min_length=1, max_length=255)
    tax_id: str | None = Field(default=None, max_length=64)
    address: str | None = None
    currency: str = Field(default="XOF", min_length=3, max_length=3)


class SupplierResponse(SupplierCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    is_active: bool


class PurchaseInvoiceLineCreate(BaseModel):
    expense_account_id: str = Field(min_length=1)
    description: str = Field(min_length=1, max_length=500)
    quantity: Decimal = Field(gt=Decimal(0), max_digits=18, decimal_places=3)
    unit_price: Decimal = Field(ge=Decimal(0), max_digits=18, decimal_places=2)
    tax_rate: Decimal = Field(
        ge=Decimal(0), le=Decimal(100), max_digits=5, decimal_places=2
    )

    @property
    def line_subtotal(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))

    @property
    def tax_amount(self) -> Decimal:
        return (self.line_subtotal * self.tax_rate / Decimal(100)).quantize(
            Decimal("0.01")
        )

    @property
    def line_total(self) -> Decimal:
        return self.line_subtotal + self.tax_amount


class PurchaseInvoiceCreate(BaseModel):
    supplier_id: str
    purchase_order_id: str | None = None
    invoice_number: str = Field(min_length=1, max_length=64)
    invoice_date: date
    due_date: date | None = None
    currency: str = Field(default="XOF", min_length=3, max_length=3)
    lines: list[PurchaseInvoiceLineCreate] = Field(min_length=1)
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.due_date is not None and self.due_date < self.invoice_date:
            raise ValueError("due_date must not precede invoice_date")
        return self


class PurchaseInvoiceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    supplier_id: str
    purchase_order_id: str | None
    invoice_number: str
    invoice_date: date
    due_date: date | None
    currency: str
    status: str
    subtotal: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    paid_amount: Decimal


class ProcurementAccountingProfileCreate(BaseModel):
    journal_id: str
    payable_account_id: str
    deductible_vat_account_id: str | None = None
    settlement_account_id: str


class ProcurementAccountingProfileResponse(ProcurementAccountingProfileCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    is_active: bool


class SupplierPaymentCreate(BaseModel):
    invoice_id: str | None = None
    payment_date: date
    amount: Decimal = Field(gt=Decimal(0), max_digits=18, decimal_places=2)
    method: str = Field(min_length=1, max_length=32)
    external_reference: str = Field(min_length=1, max_length=128)
    notes: str | None = None


class SupplierPaymentResponse(SupplierPaymentCreate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str


class AccountingPostingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    organization_id: str
    source_id: str
    journal_entry_id: str
    idempotency_key: str
    status: str
