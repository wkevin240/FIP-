from fastapi import APIRouter

from app.api.v1.accounting.accounts import router as accounts_router
from app.api.v1.accounting.bank_reconciliation import (
    router as bank_reconciliation_router,
)
from app.api.v1.accounting.closing import router as closing_router
from app.api.v1.accounting.fiscal_periods import router as fiscal_periods_router
from app.api.v1.accounting.fiscal_years import router as fiscal_years_router
from app.api.v1.accounting.journal_entries import router as journal_entries_router
from app.api.v1.accounting.journals import router as journals_router
from app.api.v1.accounting.reporting import router as reporting_router
from app.api.v1.accounting.vat import router as vat_router
from app.api.v1.inventory.products import router as products_router
from app.api.v1.inventory.stock import router as stock_router
from app.api.v1.inventory.warehouses import router as warehouses_router
from app.api.v1.invoicing.credit_notes import router as credit_notes_router
from app.api.v1.invoicing.invoices import router as invoices_router
from app.api.v1.invoicing.payments import router as payments_router

api_router = APIRouter()
api_router.include_router(
    accounts_router, prefix="/accounting/accounts", tags=["Accounting - Accounts"]
)
api_router.include_router(
    bank_reconciliation_router,
    prefix="/accounting/bank-reconciliation",
    tags=["Accounting - Bank Reconciliation"],
)
api_router.include_router(
    fiscal_years_router,
    prefix="/accounting/fiscal-years",
    tags=["Accounting - Fiscal Years"],
)
api_router.include_router(
    fiscal_periods_router,
    prefix="/accounting/fiscal-periods",
    tags=["Accounting - Fiscal Periods"],
)
api_router.include_router(
    closing_router,
    prefix="/accounting/period-closings",
    tags=["Accounting - Period Closings"],
)
api_router.include_router(
    journals_router, prefix="/accounting/journals", tags=["Accounting - Journals"]
)
api_router.include_router(
    reporting_router,
    prefix="/accounting/reports",
    tags=["Accounting - Financial Reporting"],
)
api_router.include_router(
    vat_router, prefix="/accounting/vat", tags=["Accounting - VAT"]
)
api_router.include_router(
    journal_entries_router,
    prefix="/accounting/journal-entries",
    tags=["Accounting - Journal Entries"],
)
api_router.include_router(
    products_router, prefix="/inventory/products", tags=["Inventory - Products"]
)
api_router.include_router(
    warehouses_router,
    prefix="/inventory/warehouses",
    tags=["Inventory - Warehouses"],
)
api_router.include_router(
    stock_router, prefix="/inventory/stock", tags=["Inventory - Stock"]
)
api_router.include_router(
    invoices_router, prefix="/invoicing/invoices", tags=["Invoicing - Invoices"]
)
api_router.include_router(
    credit_notes_router,
    prefix="/invoicing/credit-notes",
    tags=["Invoicing - Credit Notes"],
)
api_router.include_router(
    payments_router, prefix="/invoicing/payments", tags=["Invoicing - Payments"]
)
