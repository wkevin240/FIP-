from fastapi import APIRouter

from app.api.v1.accounting.accounts import router as accounts_router
from app.api.v1.accounting.analytical import router as analytical_router
from app.api.v1.accounting.bank_reconciliation import (
    router as bank_reconciliation_router,
)
from app.api.v1.accounting.budgets import router as budgets_router
from app.api.v1.accounting.cash_flow import router as cash_flow_router
from app.api.v1.accounting.cash_forecast import router as cash_forecast_router
from app.api.v1.accounting.closing import router as closing_router
from app.api.v1.accounting.fiscal_periods import router as fiscal_periods_router
from app.api.v1.accounting.fiscal_years import router as fiscal_years_router
from app.api.v1.accounting.forecasts import router as forecasts_router
from app.api.v1.accounting.journal_entries import router as journal_entries_router
from app.api.v1.accounting.journals import router as journals_router
from app.api.v1.accounting.kpis import router as kpis_router
from app.api.v1.accounting.professional_reporting import (
    router as professional_reporting_router,
)
from app.api.v1.accounting.reporting import router as reporting_router
from app.api.v1.accounting.scenarios import router as scenarios_router
from app.api.v1.accounting.syscohada_liasse import router as syscohada_liasse_router
from app.api.v1.accounting.vat import router as vat_router
from app.api.v1.audit.events import router as audit_events_router
from app.api.v1.fixed_assets.assets import router as fixed_assets_router
from app.api.v1.fixed_assets.configuration import (
    router as fixed_assets_configuration_router,
)
from app.api.v1.fixed_assets.depreciation import (
    router as fixed_assets_depreciation_router,
)
from app.api.v1.fixed_assets.disposal import router as fixed_assets_disposal_router
from app.api.v1.inventory.products import router as products_router
from app.api.v1.inventory.stock import router as stock_router
from app.api.v1.inventory.warehouses import router as warehouses_router
from app.api.v1.invoicing.collections import router as collections_router
from app.api.v1.invoicing.credit_notes import router as credit_notes_router
from app.api.v1.invoicing.invoices import router as invoices_router
from app.api.v1.invoicing.payments import router as payments_router
from app.api.v1.payroll.configuration import router as payroll_configuration_router
from app.api.v1.payroll.employees import router as payroll_employees_router
from app.api.v1.payroll.payroll import router as payroll_router
from app.api.v1.procurement import router as procurement_router
from app.api.v1.treasury.bank_accounts import router as treasury_bank_accounts_router
from app.api.v1.treasury.banking_control import router as banking_control_router
from app.api.v1.treasury.reconciliation import router as treasury_reconciliation_router
from app.api.v1.treasury.transactions import router as treasury_transactions_router

api_router = APIRouter()
api_router.include_router(audit_events_router, prefix="/audit", tags=["Audit"])
api_router.include_router(
    accounts_router, prefix="/accounting/accounts", tags=["Accounting - Accounts"]
)
api_router.include_router(
    bank_reconciliation_router,
    prefix="/accounting/bank-reconciliation",
    tags=["Accounting - Bank Reconciliation"],
)
api_router.include_router(
    budgets_router,
    prefix="/accounting/budgets",
    tags=["Accounting - Budgets"],
)
api_router.include_router(
    analytical_router,
    prefix="/accounting/analytical",
    tags=["Accounting - Analytical FP&A"],
)
api_router.include_router(
    scenarios_router,
    prefix="/accounting/scenarios",
    tags=["Accounting - FP&A Scenarios"],
)
api_router.include_router(
    forecasts_router,
    prefix="/accounting/forecasts",
    tags=["Accounting - FP&A Forecasts"],
)
api_router.include_router(
    kpis_router,
    prefix="/accounting/kpis",
    tags=["Accounting - FP&A KPIs"],
)
api_router.include_router(
    cash_flow_router,
    prefix="/accounting/cash-flow",
    tags=["Accounting - Cash Flow"],
)
api_router.include_router(
    cash_forecast_router,
    prefix="/accounting/cash-forecast",
    tags=["Accounting - Cash Forecast"],
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
    professional_reporting_router,
    prefix="/accounting/professional-reports",
    tags=["Accounting - Professional Reporting"],
)
api_router.include_router(
    syscohada_liasse_router,
    prefix="/accounting/syscohada-liasse",
    tags=["Accounting - SYSCOHADA Liasse"],
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
    collections_router,
    prefix="/invoicing/collections",
    tags=["Invoicing - Collections"],
)
api_router.include_router(
    payments_router, prefix="/invoicing/payments", tags=["Invoicing - Payments"]
)
api_router.include_router(
    procurement_router, prefix="/procurement", tags=["Procurement - Suppliers"]
)
api_router.include_router(
    fixed_assets_configuration_router,
    prefix="/fixed-assets/configuration",
    tags=["Fixed Assets - Configuration"],
)
api_router.include_router(
    fixed_assets_router, prefix="/fixed-assets/assets", tags=["Fixed Assets - Register"]
)
api_router.include_router(
    fixed_assets_depreciation_router,
    prefix="/fixed-assets/depreciation",
    tags=["Fixed Assets - Depreciation"],
)
api_router.include_router(
    fixed_assets_disposal_router,
    prefix="/fixed-assets/disposals",
    tags=["Fixed Assets - Disposals"],
)
api_router.include_router(
    payroll_employees_router, prefix="/payroll/employees", tags=["Payroll - Employees"]
)
api_router.include_router(
    payroll_configuration_router,
    prefix="/payroll/configuration",
    tags=["Payroll - Configuration"],
)
api_router.include_router(
    payroll_router, prefix="/payroll", tags=["Payroll - Operations"]
)
api_router.include_router(
    treasury_bank_accounts_router,
    prefix="/treasury/bank-accounts",
    tags=["Treasury - Bank Accounts"],
)
api_router.include_router(
    treasury_transactions_router,
    prefix="/treasury/transactions",
    tags=["Treasury - Transactions"],
)
api_router.include_router(
    banking_control_router,
    prefix="/treasury/banking-control",
    tags=["Treasury - Banking Control"],
)
api_router.include_router(
    treasury_reconciliation_router,
    prefix="/treasury/reconciliation",
    tags=["Treasury - Reconciliation"],
)
