from fastapi import APIRouter

from app.api.v1.accounting.accounts import router as accounts_router

api_router = APIRouter()
api_router.include_router(
    accounts_router, prefix="/accounting/accounts", tags=["Accounting - Accounts"]
)
from app.api.v1.accounting.fiscal_periods import router as fp_router
from app.api.v1.accounting.fiscal_years import router as fy_router

api_router.include_router(
    fy_router, prefix="/accounting/fiscal-years", tags=["Accounting - Fiscal Years"]
)
api_router.include_router(
    fp_router, prefix="/accounting/fiscal-periods", tags=["Accounting - Fiscal Periods"]
)
