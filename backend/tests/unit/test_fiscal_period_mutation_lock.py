from sqlalchemy.dialects import postgresql

from app.services.accounting.journal_entry_service import JournalEntryService


def test_fiscal_period_mutation_query_is_row_locked():
    statement = JournalEntryService._fiscal_period_lock("org-1", "period-1")
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "fiscal_periods.organization_id" in sql
    assert "fiscal_periods.id" in sql
