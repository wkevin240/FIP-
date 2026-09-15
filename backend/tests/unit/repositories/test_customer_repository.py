from unittest.mock import AsyncMock, Mock

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.customer_repository import CustomerRepository


@pytest.mark.asyncio
async def test_get_for_update_is_tenant_scoped_and_locks_customer_row() -> None:
    session = AsyncMock()
    session.scalar.return_value = None

    repository = CustomerRepository(session)
    result = await repository.get_for_update("org-1", "customer-1")

    assert result is None
    statement = session.scalar.await_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    assert "customers.organization_id" in sql
    assert "customers.id" in sql
    assert "FOR UPDATE" in sql


@pytest.mark.asyncio
async def test_list_adds_active_filter_when_requested() -> None:
    session = AsyncMock()
    scalars_result = Mock()
    scalars_result.all.return_value = []
    session.scalars.return_value = scalars_result

    repository = CustomerRepository(session)
    result = await repository.list("org-1", is_active=False)

    assert result == []
    statement = session.scalars.await_args.args[0]
    sql = str(statement)
    assert "customers.organization_id" in sql
    assert "customers.is_active" in sql


@pytest.mark.asyncio
async def test_list_does_not_add_active_filter_by_default() -> None:
    session = AsyncMock()
    scalars_result = Mock()
    scalars_result.all.return_value = []
    session.scalars.return_value = scalars_result

    repository = CustomerRepository(session)
    result = await repository.list("org-1")

    assert result == []
    statement = session.scalars.await_args.args[0]
    sql = str(statement)
    assert "customers.organization_id" in sql
    assert "customers.is_active" not in sql
