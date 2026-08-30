from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from app.services.accounting.closing_signoff_service import ClosingSignoffService
from fastapi import HTTPException


@pytest.mark.asyncio
async def test_signoff_rejects_non_ready_closing_without_mutation():
    session = SimpleNamespace(scalar=AsyncMock())
    session.scalar.return_value = None
    service = ClosingSignoffService(session)
    service.control.assess = AsyncMock(
        return_value=SimpleNamespace(
            status="INCOMPLETE",
            blockers=[
                SimpleNamespace(
                    model_dump=lambda mode=None: {
                        "code": "DRAFT_JOURNAL_ENTRIES",
                        "module": "ACCOUNTING",
                    }
                )
            ],
        )
    )

    with pytest.raises(HTTPException) as exc_info:
        await service.sign("org-real", "year-real", "period-real", "user-real")

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["code"] == "CLOSING_NOT_READY"
    assert service.control.assess.await_count == 1
    assert not hasattr(session, "add")


@pytest.mark.asyncio
async def test_signoff_is_idempotent_for_existing_signed_year():
    session = SimpleNamespace(scalar=AsyncMock())
    existing = SimpleNamespace(
        id="signoff-real",
        organization_id="org-real",
        fiscal_year_id="year-real",
        status="SIGNED",
        signed_by_user_id="user-first",
        signed_at=datetime(2026, 1, 31, 12, 0, 0, tzinfo=timezone.utc),
        control_hash="a" * 64,
        control_snapshot="{}",
        revoked_at=None,
        revoked_by_user_id=None,
    )
    session.scalar.return_value = existing
    service = ClosingSignoffService(session)

    result = await service.sign("org-real", "year-real", "period-real", "user-second")

    assert result.id == "signoff-real"
    assert result.signed_by_user_id == "user-first"
    assert result.control_hash == "a" * 64
