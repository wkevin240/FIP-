from app.main import create_application


def test_journal_and_entry_routes_are_published() -> None:
    application = create_application()
    paths = application.openapi()["paths"]

    assert "/api/v1/accounting/vat/rates" in paths
    assert "/api/v1/accounting/vat/declarations" in paths
    assert "/api/v1/accounting/vat/declarations/{declaration_id}/submit" in paths
    assert "/api/v1/accounting/vat/declarations/{declaration_id}/export.json" in paths
    assert "/api/v1/accounting/journal-entries/" in paths
    assert "/api/v1/accounting/journal-entries/{journal_entry_id}/post" in paths
    assert "/api/v1/accounting/journal-entries/{journal_entry_id}/reverse" in paths
    assert "/api/v1/accounting/journal-entries/{journal_entry_id}/correct" in paths
    assert (
        "/api/v1/accounting/period-closings/periods/{fiscal_period_id}/preview" in paths
    )
    assert "/api/v1/accounting/period-closings/periods/{fiscal_period_id}" in paths
    assert "/api/v1/accounting/reports/balance-sheet" in paths
    assert "/api/v1/accounting/reports/income-statement" in paths
    assert "/api/v1/accounting/reports/trial-balance" in paths
    assert "/api/v1/accounting/reports/general-ledger/{account_id}" in paths
    assert "/api/v1/accounting/reports/comparative-balance" in paths
    assert "/api/v1/accounting/professional-reports/mappings" in paths
    assert "/api/v1/accounting/professional-reports/trial-balance" in paths
    assert "/api/v1/accounting/professional-reports/trial-balance/export.csv" in paths
    assert (
        "/api/v1/accounting/professional-reports/statements/{statement_code}" in paths
    )
    assert "/api/v1/accounting/professional-reports/reconciliation" in paths
    assert (
        "/api/v1/accounting/professional-reports/exports/syscohada-package.json"
        in paths
    )
    assert "/api/v1/accounting/cash-flow/mappings" in paths
    assert "/api/v1/accounting/syscohada-liasse/" in paths
    assert "/api/v1/accounting/syscohada-liasse/export.json" in paths
    assert "/api/v1/accounting/cash-flow/statement" in paths
    assert "/api/v1/accounting/bank-reconciliation/transactions" in paths
    assert "/api/v1/accounting/bank-reconciliation/automatic/preview" in paths
    assert "/api/v1/accounting/bank-reconciliation/automatic/apply" in paths
    assert (
        "/api/v1/accounting/bank-reconciliation/transactions/{transaction_id}/candidates"
        in paths
    )
    assert (
        "/api/v1/accounting/bank-reconciliation/transactions/{transaction_id}/match"
        in paths
    )
    assert "/api/v1/inventory/products/" in paths
    assert "/api/v1/inventory/warehouses/" in paths
    assert "/api/v1/inventory/stock/receipts" in paths
    assert "/api/v1/inventory/stock/transfers" in paths
    assert "/api/v1/invoicing/invoices/" in paths
    assert "/api/v1/invoicing/invoices/{invoice_id}/issue" in paths
    assert "/api/v1/invoicing/credit-notes/" in paths
    assert "/api/v1/invoicing/payments/" in paths
    assert "/api/v1/payroll/employees/" in paths
    assert "/api/v1/fixed-assets/configuration/accounting-profiles" in paths
    assert "/api/v1/fixed-assets/configuration/categories" in paths
    assert "/api/v1/fixed-assets/assets/" in paths
    assert "/api/v1/fixed-assets/assets/{asset_id}/acquire" in paths
    assert "/api/v1/fixed-assets/assets/{asset_id}/commission" in paths
    assert "/api/v1/fixed-assets/depreciation/assets/{asset_id}/plans" in paths
    assert "/api/v1/fixed-assets/disposals/assets/{asset_id}/dispose" in paths
    assert "/api/v1/payroll/configuration/rule-sets" in paths
    assert "/api/v1/payroll/configuration/accounting-profiles" in paths
    assert "/api/v1/payroll/periods" in paths
    assert "/api/v1/payroll/periods/{payroll_period_id}/calculate" in paths
    assert "/api/v1/payroll/periods/{payroll_period_id}/validate" in paths
    assert "/api/v1/payroll/periods/{payroll_period_id}/lock" in paths
    assert "/api/v1/payroll/periods/{payroll_period_id}/post" in paths
    assert "/api/v1/payroll/slips/{payroll_slip_id}/corrections" in paths
    assert "/api/v1/treasury/bank-accounts/" in paths
    assert "/api/v1/treasury/bank-accounts/{treasury_bank_account_id}/position" in paths
    assert "/api/v1/treasury/transactions/" in paths
    assert (
        "/api/v1/treasury/reconciliation/bank-accounts/{treasury_bank_account_id}/transactions/{transaction_id}/match"
        in paths
    )
    assert "post" in paths["/api/v1/accounting/vat/rates"]
    assert "post" in paths["/api/v1/accounting/bank-reconciliation/automatic/preview"]
    assert "post" in paths["/api/v1/accounting/bank-reconciliation/automatic/apply"]
    assert "post" in paths["/api/v1/accounting/vat/declarations"]
    assert "get" in paths["/api/v1/accounting/vat/declarations"]
    assert (
        "post" in paths["/api/v1/accounting/vat/declarations/{declaration_id}/submit"]
    )
    assert (
        "get"
        in paths["/api/v1/accounting/vat/declarations/{declaration_id}/export.json"]
    )
    assert "post" in paths["/api/v1/accounting/journal-entries/{journal_entry_id}/post"]
    assert "post" in paths["/api/v1/accounting/professional-reports/mappings"]
    assert (
        "get"
        in paths[
            "/api/v1/accounting/professional-reports/exports/syscohada-package.json"
        ]
    )
    assert "post" in paths["/api/v1/accounting/cash-flow/mappings"]
    assert "get" in paths["/api/v1/accounting/syscohada-liasse/"]
    assert "get" in paths["/api/v1/accounting/syscohada-liasse/export.json"]
    assert (
        "post" in paths["/api/v1/accounting/journal-entries/{journal_entry_id}/reverse"]
    )
    assert (
        "post" in paths["/api/v1/accounting/journal-entries/{journal_entry_id}/correct"]
    )
    assert (
        "post" in paths["/api/v1/accounting/period-closings/periods/{fiscal_period_id}"]
    )
    assert "post" in paths["/api/v1/inventory/products/"]
    assert "post" in paths["/api/v1/inventory/stock/receipts"]
    assert "post" in paths["/api/v1/invoicing/invoices/"]
    assert "post" in paths["/api/v1/invoicing/invoices/{invoice_id}/issue"]
    assert "post" in paths["/api/v1/invoicing/payments/"]
    assert "post" in paths["/api/v1/payroll/employees/"]
    assert "post" in paths["/api/v1/fixed-assets/configuration/categories"]
    assert "post" in paths["/api/v1/fixed-assets/assets/"]
    assert "post" in paths["/api/v1/fixed-assets/assets/{asset_id}/acquire"]
    assert "post" in paths["/api/v1/fixed-assets/assets/{asset_id}/commission"]
    assert "post" in paths["/api/v1/payroll/configuration/rule-sets"]
    assert "post" in paths["/api/v1/payroll/periods"]
    assert "post" in paths["/api/v1/payroll/periods/{payroll_period_id}/calculate"]
    assert "post" in paths["/api/v1/payroll/periods/{payroll_period_id}/validate"]
    assert "post" in paths["/api/v1/payroll/periods/{payroll_period_id}/lock"]
    assert "post" in paths["/api/v1/payroll/periods/{payroll_period_id}/post"]
    assert "post" in paths["/api/v1/treasury/bank-accounts/"]
    assert "post" in paths["/api/v1/treasury/transactions/"]
    assert (
        "post"
        in paths[
            "/api/v1/treasury/reconciliation/bank-accounts/{treasury_bank_account_id}/transactions/{transaction_id}/match"
        ]
    )
