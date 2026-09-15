from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.customer_service import CustomerService


def test_customer_update_audit_action_defaults_to_update() -> None:
    customer = SimpleNamespace(is_active=True)

    assert CustomerService._update_audit_action(customer, {"legal_name": "Acme SA"}) == "CUSTOMER_UPDATED"


def test_customer_update_audit_action_tracks_deactivation() -> None:
    customer = SimpleNamespace(is_active=True)

    assert CustomerService._update_audit_action(customer, {"is_active": False}) == "CUSTOMER_DEACTIVATED"


def test_customer_update_audit_action_tracks_reactivation() -> None:
    customer = SimpleNamespace(is_active=False)

    assert CustomerService._update_audit_action(customer, {"is_active": True}) == "CUSTOMER_ACTIVATED"


def test_customer_update_audit_action_does_not_claim_transition_when_state_is_unchanged() -> None:
    customer = SimpleNamespace(is_active=False)

    assert CustomerService._update_audit_action(customer, {"is_active": False}) == "CUSTOMER_UPDATED"


@pytest.mark.asyncio
async def test_customer_list_forwards_active_state_filter() -> None:
    service = CustomerService.__new__(CustomerService)
    service.repository = SimpleNamespace(list=AsyncMock(return_value=[]))

    result = await service.list("org-1", skip=10, limit=25, is_active=False)

    assert result == []
    service.repository.list.assert_awaited_once_with(
        "org-1",
        skip=10,
        limit=25,
        is_active=False,
    )
