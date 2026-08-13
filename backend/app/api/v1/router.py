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
