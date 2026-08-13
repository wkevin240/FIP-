from datetime import date
from decimal import Decimal

import pytest
from app.models.accounting.account import Account
from app.models.organization import Organization
from app.schemas.treasury.bank_account import (
    TreasuryBankAccountCreate,
    TreasuryBankAccountUpdate,
)
from app.schemas.treasury.transaction import TreasuryBankTransactionCreate
from app.services.treasury.bank_account_service import TreasuryBankAccountService
from app.services.treasury.transaction_service import TreasuryTransactionService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_organization_and_asset_account(
    session: AsyncSession,
) -> tuple[Organization, Account]:
    organization = Organization(name="Treasury test organization")
    session.add(organization)
    await session.commit()
    account = Account(
        organization_id=organization.id,
        code="512100",
        name="Primary bank",
        account_type="ASSET",
        level=1,
        path="/512100/",
        is_active=True,
    )
    session.add(account)
    await session.commit()
    return organization, account


def _bank_account_data(ledger_account_id: str) -> TreasuryBankAccountCreate:
    return TreasuryBankAccountCreate(
        ledger_account_id=ledger_account_id,
        bank_name="Example Bank",
        account_name="Operating Account",
        account_number="TG-001",
        currency="xof",
        opening_balance=Decimal("1000.00"),
        opening_date=date(2026, 1, 1),
    )


@pytest.mark.asyncio
async def test_bank_profile_transaction_facade_and_position(
    db_session: AsyncSession,
) -> None:
    organization, account = await _create_organization_and_asset_account(db_session)
    bank_account_service = TreasuryBankAccountService(db_session)
    transaction_service = TreasuryTransactionService(db_session)

    profile = await bank_account_service.create_bank_account(
        organization.id, _bank_account_data(account.id)
    )
    transaction = await transaction_service.create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=profile.id,
            transaction_date=date(2026, 1, 5),
            amount=Decimal("250.00"),
            description="Customer collection",
            external_id="statement-001",
        ),
    )
    transactions = await transaction_service.list_transactions(
        organization.id, profile.id
    )
    position = await bank_account_service.get_position(organization.id, profile.id)

    assert profile.currency == "XOF"
    assert transaction.bank_account_id == account.id
    assert len(transactions) == 1
    assert transactions[0].id == transaction.id
    assert position.statement_balance == Decimal("1250.00")
    assert position.ledger_balance == Decimal("1000.00")
    assert position.reconciliation_gap == Decimal("250.00")
    assert position.unreconciled_amount == Decimal("250.00")
    assert position.unreconciled_transaction_count == 1


@pytest.mark.asyncio
async def test_rejects_duplicate_profile_and_duplicate_bank_external_id(
    db_session: AsyncSession,
) -> None:
    organization, account = await _create_organization_and_asset_account(db_session)
    bank_account_service = TreasuryBankAccountService(db_session)
    transaction_service = TreasuryTransactionService(db_session)
    profile = await bank_account_service.create_bank_account(
        organization.id, _bank_account_data(account.id)
    )

    with pytest.raises(HTTPException, match="already exists") as duplicate_profile:
        await bank_account_service.create_bank_account(
            organization.id, _bank_account_data(account.id)
        )
    assert duplicate_profile.value.status_code == 409

    await transaction_service.create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=profile.id,
            transaction_date=date(2026, 1, 5),
            amount=Decimal("250.00"),
            description="Customer collection",
            external_id="statement-duplicate",
        ),
    )
    with pytest.raises(
        HTTPException, match="external ID already exists"
    ) as duplicate_id:
        await transaction_service.create_transaction(
            organization.id,
            TreasuryBankTransactionCreate(
                treasury_bank_account_id=profile.id,
                transaction_date=date(2026, 1, 6),
                amount=Decimal("125.00"),
                description="Repeated statement row",
                external_id="statement-duplicate",
            ),
        )
    assert duplicate_id.value.status_code == 409


@pytest.mark.asyncio
async def test_rejects_transaction_for_inactive_profile(
    db_session: AsyncSession,
) -> None:
    organization, account = await _create_organization_and_asset_account(db_session)
    bank_account_service = TreasuryBankAccountService(db_session)
    transaction_service = TreasuryTransactionService(db_session)
    profile = await bank_account_service.create_bank_account(
        organization.id, _bank_account_data(account.id)
    )
    await bank_account_service.update_bank_account(
        organization.id,
        profile.id,
        TreasuryBankAccountUpdate(is_active=False),
    )

    with pytest.raises(HTTPException, match="inactive") as inactive_profile:
        await transaction_service.create_transaction(
            organization.id,
            TreasuryBankTransactionCreate(
                treasury_bank_account_id=profile.id,
                transaction_date=date(2026, 1, 5),
                amount=Decimal("25.00"),
                description="Rejected import",
                external_id="statement-inactive",
            ),
        )
    assert inactive_profile.value.status_code == 422


@pytest.mark.asyncio
async def test_reconciliation_facade_rejects_transaction_from_another_profile(
    db_session: AsyncSession,
) -> None:
    organization, first_ledger_account = await _create_organization_and_asset_account(
        db_session
    )
    second_ledger_account = Account(
        organization_id=organization.id,
        code="512200",
        name="Secondary bank",
        account_type="ASSET",
        level=1,
        path="/512200/",
        is_active=True,
    )
    db_session.add(second_ledger_account)
    await db_session.commit()

    bank_account_service = TreasuryBankAccountService(db_session)
    transaction_service = TreasuryTransactionService(db_session)
    first_profile = await bank_account_service.create_bank_account(
        organization.id, _bank_account_data(first_ledger_account.id)
    )
    second_profile = await bank_account_service.create_bank_account(
        organization.id,
        _bank_account_data(second_ledger_account.id).model_copy(
            update={"account_number": "TG-002"}
        ),
    )
    transaction = await transaction_service.create_transaction(
        organization.id,
        TreasuryBankTransactionCreate(
            treasury_bank_account_id=first_profile.id,
            transaction_date=date(2026, 1, 5),
            amount=Decimal("25.00"),
            description="First account statement",
            external_id="statement-scope",
        ),
    )

    with pytest.raises(
        HTTPException, match="not found for treasury bank account"
    ) as scope:
        await transaction_service.candidate_entries(
            organization.id,
            second_profile.id,
            transaction.id,
        )
    assert scope.value.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("account_type", "is_active"),
    [("LIABILITY", True), ("ASSET", False)],
)
async def test_rejects_non_active_or_non_asset_ledger_account(
    db_session: AsyncSession,
    account_type: str,
    is_active: bool,
) -> None:
    organization = Organization(name="Invalid treasury account organization")
    db_session.add(organization)
    await db_session.commit()
    ledger_account = Account(
        organization_id=organization.id,
        code="512900",
        name="Invalid treasury ledger account",
        account_type=account_type,
        level=1,
        path="/512900/",
        is_active=is_active,
    )
    db_session.add(ledger_account)
    await db_session.commit()

    with pytest.raises(
        HTTPException, match="Active asset ledger account required"
    ) as error:
        await TreasuryBankAccountService(db_session).create_bank_account(
            organization.id, _bank_account_data(ledger_account.id)
        )
    assert error.value.status_code == 422
