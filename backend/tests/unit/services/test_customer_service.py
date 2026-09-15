from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from app.schemas.customer import CustomerCreate, CustomerUpdate
from app.services.customer_service import CustomerService


@pytest.mark.asyncio
async def test_create_customer_is_tenant_scoped_and_audited() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    audit_repository = AsyncMock()
    service = CustomerService(session)
    service.repository = repository
    service.audit_repository = audit_repository

    repository.get_by_code.return_value = None
    repository.get_by_tax_id.return_value = None

    customer = await service.create(
        "org-1",
        "user-1",
        CustomerCreate(
            code=" c-001 ",
            legal_name="Example Customer",
            tax_id="CM-001",
            email="finance@example.com",
        ),
    )

    assert customer.organization_id == "org-1"
    assert customer.code == "C-001"
    assert customer.created_by == "user-1"
    assert customer.updated_by == "user-1"
    assert customer.is_active is True
    repository.get_by_code.assert_awaited_once_with("org-1", "C-001")
    repository.get_by_tax_id.assert_awaited_once_with("org-1", "CM-001")
    audit_repository.append.assert_awaited_once()
    session.flush.assert_awaited_once()
    session.commit.assert_awaited_once()
    session.refresh.assert_awaited_once_with(customer)


@pytest.mark.asyncio
async def test_create_customer_rejects_duplicate_code_without_mutation() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    service = CustomerService(session)
    service.repository = repository
    repository.get_by_code.return_value = object()

    with pytest.raises(HTTPException) as exc_info:
        await service.create(
            "org-1",
            "user-1",
            CustomerCreate(code="C-001", legal_name="Example Customer"),
        )

    assert exc_info.value.status_code == 409
    repository.add.assert_not_called()
    session.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_customer_locks_tenant_scoped_row_and_records_updater() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    audit_repository = AsyncMock()
    service = CustomerService(session)
    service.repository = repository
    service.audit_repository = audit_repository

    customer = type(
        "CustomerFixture",
        (),
        {
            "id": "customer-1",
            "organization_id": "org-1",
            "code": "C-001",
            "legal_name": "Old Name",
            "trade_name": None,
            "tax_id": "CM-001",
            "email": None,
            "phone": None,
            "address": None,
            "is_active": True,
            "updated_by": "user-1",
        },
    )()
    repository.get_for_update.return_value = customer
    repository.get_by_tax_id.return_value = customer

    result = await service.update(
        "org-1",
        "customer-1",
        "user-2",
        CustomerUpdate(legal_name="New Name", is_active=False),
    )

    assert result is customer
    assert customer.legal_name == "New Name"
    assert customer.is_active is False
    assert customer.updated_by == "user-2"
    repository.get_for_update.assert_awaited_once_with("org-1", "customer-1")
    repository.get_by_id.assert_not_awaited()
    audit_repository.append.assert_awaited_once()
    session.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_customer_creation() -> None:
    session = AsyncMock()
    repository = AsyncMock()
    audit_repository = AsyncMock()
    service = CustomerService(session)
    service.repository = repository
    service.audit_repository = audit_repository

    repository.get_by_code.return_value = None
    repository.get_by_tax_id.return_value = None
    audit_repository.append.side_effect = RuntimeError("audit unavailable")

    with pytest.raises(RuntimeError, match="audit unavailable"):
        await service.create(
            "org-1",
            "user-1",
            CustomerCreate(code="C-001", legal_name="Example Customer"),
        )

    session.rollback.assert_awaited_once()
    session.commit.assert_not_awaited()
