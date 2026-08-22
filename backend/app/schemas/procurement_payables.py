from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class PayableInvoiceResponse(BaseModel):
    invoice_id: str
    invoice_number: str
    supplier_id: str
    supplier_name: str
    supplier_tax_id: str | None
    invoice_date: date
    due_date: date | None
    total_amount: Decimal
    paid_amount: Decimal
    outstanding_amount: Decimal
    age_bucket: str | None
    overdue_amount: Decimal


class PayableSupplierBalanceResponse(BaseModel):
    supplier_id: str
    supplier_name: str
    supplier_tax_id: str | None
    outstanding_amount: Decimal
    overdue_amount: Decimal
    invoices: list[PayableInvoiceResponse]


class PayableStatementResponse(BaseModel):
    organization_id: str
    as_of_date: date
    supplier_id: str | None
    total_invoiced: Decimal
    total_paid: Decimal
    total_outstanding: Decimal
    total_overdue: Decimal
    suppliers: list[PayableSupplierBalanceResponse]
