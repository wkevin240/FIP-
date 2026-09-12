from sqlalchemy.dialects import postgresql

from app.services.accounting.journal_entry_service import JournalEntryService


def test_journal_entry_lock_query_is_scoped_and_row_locked():
    statement = JournalEntryService._journal_entry_lock("org-1", "entry-1")
    sql = str(statement.compile(dialect=postgresql.dialect()))

    assert "FOR UPDATE" in sql
    assert "journal_entries.organization_id" in sql
    assert "journal_entries.id" in sql
