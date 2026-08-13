from app.main import create_application


def test_journal_and_entry_routes_are_published() -> None:
    application = create_application()
    paths = application.openapi()["paths"]

    assert "/api/v1/accounting/journals/" in paths
    assert "/api/v1/accounting/journal-entries/" in paths
    assert "/api/v1/accounting/journal-entries/{journal_entry_id}/post" in paths
    assert (
        "/api/v1/accounting/period-closings/periods/{fiscal_period_id}/preview" in paths
    )
    assert "/api/v1/accounting/period-closings/periods/{fiscal_period_id}" in paths
    assert "/api/v1/accounting/reports/balance-sheet" in paths
    assert "/api/v1/accounting/reports/income-statement" in paths
    assert "/api/v1/accounting/bank-reconciliation/transactions" in paths
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
    assert "/api/v1/treasury/bank-accounts/" in paths
    assert "/api/v1/treasury/bank-accounts/{treasury_bank_account_id}/position" in paths
    assert "/api/v1/treasury/transactions/" in paths
    assert (
        "/api/v1/treasury/reconciliation/bank-accounts/{treasury_bank_account_id}/transactions/{transaction_id}/match"
        in paths
    )
    assert "post" in paths["/api/v1/accounting/journals/"]
    assert "post" in paths["/api/v1/accounting/journal-entries/{journal_entry_id}/post"]
    assert (
        "post" in paths["/api/v1/accounting/period-closings/periods/{fiscal_period_id}"]
    )
    assert "post" in paths["/api/v1/inventory/products/"]
    assert "post" in paths["/api/v1/inventory/stock/receipts"]
    assert "post" in paths["/api/v1/invoicing/invoices/"]
    assert "post" in paths["/api/v1/invoicing/invoices/{invoice_id}/issue"]
    assert "post" in paths["/api/v1/invoicing/payments/"]
    assert "post" in paths["/api/v1/treasury/bank-accounts/"]
    assert "post" in paths["/api/v1/treasury/transactions/"]
    assert (
        "post"
        in paths[
            "/api/v1/treasury/reconciliation/bank-accounts/{treasury_bank_account_id}/transactions/{transaction_id}/match"
        ]
    )
