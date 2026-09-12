from fastapi import APIRouter

from app.api.v1.accounting.accounts import router as accounts_router
from app.api.v1.accounting.balance_sheet import router as balance_sheet_router
from app.api.v1.accounting.balance_sheet_mappings import router as balance_sheet_mappings_router
from app.api.v1.accounting.fiscal_years import router as fy_router
from app.api.v1.accounting.fiscal_periods import router as fp_router
from app.api.v1.accounting.journal_entries import router as journal_entries_router
from app.api.v1.accounting.ledger import router as ledger_router
from app.api.v1.accounting.profitability import router as profitability_router
from app.api.v1.accounting.profitability_mappings import router as profitability_mappings_router
from app.api.v1.audit import router as audit_router

api_router = APIRouter()
api_router.include_router(accounts_router, prefix="/accounting/accounts", tags=["Accounting - Accounts"])
api_router.include_router(fy_router, prefix="/accounting/fiscal-years", tags=["Accounting - Fiscal Years"])
api_router.include_router(fp_router, prefix="/accounting/fiscal-periods", tags=["Accounting - Fiscal Periods"])
api_router.include_router(journal_entries_router, prefix="/accounting/journal-entries", tags=["Accounting - Journal Entries"])
api_router.include_router(ledger_router, prefix="/accounting/ledger", tags=["Accounting - Ledger"])
api_router.include_router(profitability_router, prefix="/accounting/profitability", tags=["Accounting - Profitability"])
api_router.include_router(profitability_mappings_router, prefix="/accounting/profitability/mappings", tags=["Accounting - Profitability Mappings"])
api_router.include_router(balance_sheet_router, prefix="/accounting/balance-sheet", tags=["Accounting - Balance Sheet"])
api_router.include_router(balance_sheet_mappings_router, prefix="/accounting/balance-sheet/mappings", tags=["Accounting - Balance Sheet Mappings"])
api_router.include_router(audit_router, prefix="/accounting/audit", tags=["Accounting - Audit"])
