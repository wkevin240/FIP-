from unittest.mock import AsyncMock, Mock

import pytest

from app.repositories.customer_repository import CustomerRepository


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
