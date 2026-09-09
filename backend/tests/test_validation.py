import pytest
from fastapi import HTTPException

from app.core.enums.users import MembershipRole
from app.core.validation import validate_pagination
from app.services.permission_service import PermissionService


def test_validate_pagination_accepts_normal_values() -> None:
    assert validate_pagination(0, 100) == (0, 100)


@pytest.mark.parametrize("skip,limit", [(-1, 10), (0, 0), (0, 501)])
def test_validate_pagination_rejects_invalid_values(skip: int, limit: int) -> None:
    with pytest.raises(HTTPException) as exc_info:
        validate_pagination(skip, limit)
    assert exc_info.value.status_code == 422


def test_accountant_can_manage_accounts_but_cannot_delete() -> None:
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "account:create")
    assert PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "account:update")
    assert not PermissionService.role_allows(MembershipRole.ACCOUNTANT.value, "account:delete")


def test_auditor_is_read_only_for_accounts() -> None:
    role = MembershipRole.AUDITOR.value
    assert PermissionService.role_allows(role, "account:read")
    assert not PermissionService.role_allows(role, "account:create")
    assert not PermissionService.role_allows(role, "account:update")
