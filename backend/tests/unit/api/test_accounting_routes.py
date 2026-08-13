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
    assert "post" in paths["/api/v1/accounting/journals/"]
    assert "post" in paths["/api/v1/accounting/journal-entries/{journal_entry_id}/post"]
    assert (
        "post" in paths["/api/v1/accounting/period-closings/periods/{fiscal_period_id}"]
    )
