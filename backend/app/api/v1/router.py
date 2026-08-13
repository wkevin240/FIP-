from fastapi import APIRouter

from app.api.v1.accounting.accounts import router as accounts_router
from app.api.v1.accounting.fiscal_periods import router as fiscal_periods_router
from app.api.v1.accounting.fiscal_years import router as fiscal_years_router
from app.api.v1.accounting.journal_entries import router as journal_entries_router
from app.api.v1.accounting.journals import router as journals_router

api_router = APIRouter()
api_router.include_router(
    accounts_router, prefix="/accounting/accounts", tags=["Accounting - Accounts"]
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
    journals_router, prefix="/accounting/journals", tags=["Accounting - Journals"]
)
api_router.include_router(
    journal_entries_router,
    prefix="/accounting/journal-entries",
    tags=["Accounting - Journal Entries"],
)
