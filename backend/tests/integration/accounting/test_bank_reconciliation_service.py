from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
from app.core.enums.accounting import FiscalPeriodStatus, FiscalYearStatus
from app.models.accounting.account import Account
from app.models.accounting.bank_reconciliation_allocation import (
    BankReconciliationAllocation,
    BankReconciliationBatch,
)
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.audit.audit_event import AuditEvent
from app.models.organization import Organization
from app.models.user import User
from app.schemas.accounting.bank_reconciliation import (
    AutomaticReconciliationRequest,
    BankTransactionCreate,
    ReconcileBankTransactionsRequest,
    ReconciliationAllocationCreate,
)
from app.schemas.accounting.journal import JournalCreate
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.services.accounting.automatic_bank_reconciliation_service import (
    AutomaticBankReconciliationService,
)
from app.services.accounting.bank_reconciliation_service import (
    BankReconciliationService,
)
from app.services.accounting.journal_entry_service import JournalEntryService
from app.services.accounting.journal_service import JournalService
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_reconciliation_context(
    session: AsyncSession,
) -> tuple[Organization, User, FiscalPeriod, dict[str, Account], str]:
    suffix = uuid4().hex[:12]
    organization = Organization(name=f"Bank reconciliation test organization {suffix}")
    user = User(
        email=f"reconciler-{suffix}@example.test",
        hashed_password="not-used-by-test",
        is_active=True,
    )
    session.add_all([organization, user])
    await session.flush()

    fiscal_year = FiscalYear(
        organization_id=organization.id,
        name="FY 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        status=FiscalYearStatus.OPEN,
    )
    session.add(fiscal_year)
    await session.flush()
    period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    accounts = {
        "bank": Account(
            organization_id=organization.id,
            code="512000",
            name="Bank account",
            account_type="ASSET",
            level=1,
            path="/512000/",
        ),
        "revenue": Account(
            organization_id=organization.id,
            code="701000",
            name="Sales revenue",
            account_type="REVENUE",
            level=1,
            path="/701000/",
        ),
        "expense": Account(
            organization_id=organization.id,
            code="611000",
            name="Supplies expense",
            account_type="EXPENSE",
            level=1,
            path="/611000/",
        ),
    }
    session.add_all([period, *accounts.values()])
    await session.commit()
    journal = await JournalService(session).create_journal(
        organization.id,
        JournalCreate(code="BQ", name="Bank journal"),
    )
    return organization, user, period, accounts, journal.id


async def _create_posted_entry(
    session: AsyncSession,
    organization_id: str,
    period_id: str,
    journal_id: str,
    entry_number: str,
    entry_date: date,
    lines: list[JournalEntryLineCreate],
) -> str:
    entry = await JournalEntryService(session).create_entry(
        organization_id,
        JournalEntryCreate(
            journal_id=journal_id,
            fiscal_period_id=period_id,
            entry_number=entry_number,
            entry_date=entry_date,
            description=entry_number,
            lines=lines,
        ),
    )
    posted = await JournalEntryService(session).post_entry(organization_id, entry.id)
    return posted.id


@pytest.mark.asyncio
async def test_exact_candidate_and_reconciliation_of_incoming_transaction(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0001",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("500.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("500.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transaction = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 16),
            amount=Decimal("500.00"),
            description="Customer transfer",
            external_id="BANK-001",
        ),
    )

    candidates = await service.candidate_entries(organization.id, transaction.id)
    reconciliation = await service.reconcile(
        organization.id, transaction.id, entry_id, user.id
    )

    assert [candidate.journal_entry_id for candidate in candidates] == [entry_id]
    assert reconciliation.matched_amount == Decimal("500.00")
    assert reconciliation.match_method == "MANUAL"
    assert await service.candidate_entries(organization.id, transaction.id) == []


@pytest.mark.asyncio
async def test_outgoing_transaction_requires_same_negative_direction(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0002",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["expense"].id, debit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, credit=Decimal("100.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transaction = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("-100.00"),
            description="Supplier debit",
            external_id="BANK-002",
        ),
    )

    reconciliation = await service.reconcile(
        organization.id, transaction.id, entry_id, user.id
    )

    assert reconciliation.matched_amount == Decimal("100.00")


@pytest.mark.asyncio
async def test_mismatched_or_already_used_entry_is_rejected(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-2026-0003",
        date(2026, 1, 10),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("250.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("250.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    mismatch = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("200.00"),
            description="Wrong amount",
            external_id="BANK-003",
        ),
    )
    with pytest.raises(HTTPException, match="must match exactly") as exc_info:
        await service.reconcile(organization.id, mismatch.id, entry_id, user.id)
    assert exc_info.value.status_code == 422
    await db_session.refresh(organization)
    await db_session.refresh(user)
    await db_session.refresh(accounts["bank"])

    exact = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("250.00"),
            description="Exact amount",
            external_id="BANK-004",
        ),
    )
    await service.reconcile(organization.id, exact.id, entry_id, user.id)

    duplicate = await service.create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 10),
            amount=Decimal("250.00"),
            description="Duplicate candidate",
            external_id="BANK-005",
        ),
    )
    with pytest.raises(HTTPException, match="already reconciled") as exc_info:
        await service.reconcile(organization.id, duplicate.id, entry_id, user.id)
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_automatic_reconciliation_applies_only_unique_exact_matches_and_audits(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    exact_entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-AUTO-EXACT",
        date(2026, 1, 10),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("500.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("500.00")
            ),
        ],
    )
    for entry_number in ("BQ-AUTO-AMB-1", "BQ-AUTO-AMB-2"):
        await _create_posted_entry(
            db_session,
            organization.id,
            period.id,
            journal_id,
            entry_number,
            date(2026, 1, 12),
            [
                JournalEntryLineCreate(
                    account_id=accounts["bank"].id, debit=Decimal("300.00")
                ),
                JournalEntryLineCreate(
                    account_id=accounts["revenue"].id, credit=Decimal("300.00")
                ),
            ],
        )
    manual_service = BankReconciliationService(db_session)
    for external_id, amount, transaction_date in (
        ("BANK-AUTO-EXACT", Decimal("500.00"), date(2026, 1, 11)),
        ("BANK-AUTO-AMB", Decimal("300.00"), date(2026, 1, 12)),
        ("BANK-AUTO-NONE", Decimal("200.00"), date(2026, 1, 12)),
    ):
        await manual_service.create_transaction(
            organization.id,
            BankTransactionCreate(
                bank_account_id=accounts["bank"].id,
                transaction_date=transaction_date,
                amount=amount,
                description=external_id,
                external_id=external_id,
            ),
        )

    automatic_service = AutomaticBankReconciliationService(db_session)
    request = AutomaticReconciliationRequest(bank_account_id=accounts["bank"].id)
    preview = await automatic_service.preview(organization.id, request)
    statuses = {
        suggestion.external_id: suggestion.status for suggestion in preview.suggestions
    }
    assert statuses == {
        "BANK-AUTO-EXACT": "AUTO_ELIGIBLE",
        "BANK-AUTO-AMB": "AMBIGUOUS",
        "BANK-AUTO-NONE": "UNMATCHED",
    }

    applied = await automatic_service.apply(organization.id, user.id, request)
    assert len(applied.reconciliations) == 1
    assert applied.reconciliations[0].journal_entry_id == exact_entry_id
    assert applied.reconciliations[0].match_method == "AUTO_EXACT"
    audit_event = await db_session.scalar(
        select(AuditEvent).where(
            AuditEvent.organization_id == organization.id,
            AuditEvent.action == "BANK_TRANSACTION_RECONCILED",
            AuditEvent.resource_id == applied.reconciliations[0].id,
        )
    )
    assert audit_event is not None


@pytest.mark.asyncio
async def test_automatic_reconciliation_does_not_reuse_one_ledger_entry(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-AUTO-ONE",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("120.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("120.00")
            ),
        ],
    )
    manual_service = BankReconciliationService(db_session)
    for external_id in ("BANK-AUTO-FIRST", "BANK-AUTO-SECOND"):
        await manual_service.create_transaction(
            organization.id,
            BankTransactionCreate(
                bank_account_id=accounts["bank"].id,
                transaction_date=date(2026, 1, 15),
                amount=Decimal("120.00"),
                description=external_id,
                external_id=external_id,
            ),
        )

    automatic_service = AutomaticBankReconciliationService(db_session)
    request = AutomaticReconciliationRequest(bank_account_id=accounts["bank"].id)
    preview = await automatic_service.preview(organization.id, request)
    assert [suggestion.status for suggestion in preview.suggestions] == [
        "AUTO_ELIGIBLE",
        "AMBIGUOUS",
    ]
    applied = await automatic_service.apply(organization.id, user.id, request)
    assert len(applied.reconciliations) == 1
    assert applied.suggestions[1].reason == "CANDIDATE_CLAIMED_BY_ANOTHER_TRANSACTION"


@pytest.mark.asyncio
async def test_automatic_reconciliation_never_reads_another_tenant_ledger(
    db_session: AsyncSession,
) -> None:
    (
        organization_a,
        _,
        _,
        accounts_a,
        _,
    ) = await _create_reconciliation_context(db_session)
    (
        organization_b,
        _,
        period_b,
        accounts_b,
        journal_b,
    ) = await _create_reconciliation_context(db_session)
    await _create_posted_entry(
        db_session,
        organization_b.id,
        period_b.id,
        journal_b,
        "BQ-OTHER-TENANT",
        date(2026, 1, 15),
        [
            JournalEntryLineCreate(
                account_id=accounts_b["bank"].id, debit=Decimal("400.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts_b["revenue"].id, credit=Decimal("400.00")
            ),
        ],
    )
    await BankReconciliationService(db_session).create_transaction(
        organization_a.id,
        BankTransactionCreate(
            bank_account_id=accounts_a["bank"].id,
            transaction_date=date(2026, 1, 15),
            amount=Decimal("400.00"),
            description="Cross tenant guard",
            external_id="BANK-TENANT-A",
        ),
    )

    preview = await AutomaticBankReconciliationService(db_session).preview(
        organization_a.id,
        AutomaticReconciliationRequest(bank_account_id=accounts_a["bank"].id),
    )

    assert len(preview.suggestions) == 1
    assert preview.suggestions[0].status == "UNMATCHED"
    assert preview.suggestions[0].reason == "NO_EXACT_CANDIDATE"


@pytest.mark.asyncio
async def test_grouped_bank_transaction_allocations_are_decimal_idempotent_and_audited(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_ids = []
    for entry_number, amount in (
        ("BQ-GROUP-60", Decimal("60.00")),
        ("BQ-GROUP-40", Decimal("40.00")),
    ):
        entry_ids.append(
            await _create_posted_entry(
                db_session,
                organization.id,
                period.id,
                journal_id,
                entry_number,
                date(2026, 1, 16),
                [
                    JournalEntryLineCreate(
                        account_id=accounts["bank"].id, debit=amount
                    ),
                    JournalEntryLineCreate(
                        account_id=accounts["revenue"].id, credit=amount
                    ),
                ],
            )
        )
    transaction = await BankReconciliationService(db_session).create_transaction(
        organization.id,
        BankTransactionCreate(
            bank_account_id=accounts["bank"].id,
            transaction_date=date(2026, 1, 16),
            amount=Decimal("100.00"),
            description="Grouped customer settlement",
            external_id="BANK-GROUP-100",
        ),
    )
    transaction_id = transaction.id
    request = ReconcileBankTransactionsRequest(
        bank_account_id=accounts["bank"].id,
        allocations=[
            ReconciliationAllocationCreate(
                bank_transaction_id=transaction_id,
                journal_entry_id=entry_ids[0],
                matched_amount=Decimal("60.00"),
            ),
            ReconciliationAllocationCreate(
                bank_transaction_id=transaction_id,
                journal_entry_id=entry_ids[1],
                matched_amount=Decimal("40.00"),
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    first = await service.reconcile_allocations(
        organization.id, user.id, "grouped-reconcile-001", request
    )
    repeated = await service.reconcile_allocations(
        organization.id, user.id, "grouped-reconcile-001", request
    )

    assert first.id == repeated.id
    assert first.allocated_total == Decimal("100.00")
    with pytest.raises(
        HTTPException, match="Idempotency key was already used with a different request"
    ) as conflicting_reuse:
        await service.reconcile_allocations(
            organization.id,
            user.id,
            "grouped-reconcile-001",
            ReconcileBankTransactionsRequest(
                bank_account_id=accounts["bank"].id,
                allocations=[
                    ReconciliationAllocationCreate(
                        bank_transaction_id=transaction_id,
                        journal_entry_id=entry_ids[0],
                        matched_amount=Decimal("59.00"),
                    )
                ],
            ),
        )
    assert conflicting_reuse.value.status_code == 409
    assert sorted(Decimal(item.matched_amount) for item in first.allocations) == [
        Decimal("40.00"),
        Decimal("60.00"),
    ]
    persisted_transaction = await service.repository.get_transaction(
        organization.id, transaction_id
    )
    assert persisted_transaction is not None
    assert persisted_transaction.reconciled_at is not None
    assert (
        await db_session.scalar(
            select(func.count(BankReconciliationBatch.id)).where(
                BankReconciliationBatch.organization_id == organization.id
            )
        )
        == 1
    )
    assert (
        await db_session.scalar(
            select(func.count(BankReconciliationAllocation.id)).where(
                BankReconciliationAllocation.organization_id == organization.id
            )
        )
        == 2
    )
    assert (
        await db_session.scalar(
            select(func.count(AuditEvent.id)).where(
                AuditEvent.organization_id == organization.id,
                AuditEvent.action == "BANK_RECONCILIATION_BATCH_APPLIED",
                AuditEvent.resource_id == first.id,
            )
        )
        == 1
    )


@pytest.mark.asyncio
async def test_grouped_transactions_can_fully_allocate_one_ledger_entry(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    entry_id = await _create_posted_entry(
        db_session,
        organization.id,
        period.id,
        journal_id,
        "BQ-GROUP-ENTRY-100",
        date(2026, 1, 18),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("100.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("100.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transactions = []
    for external_id, amount in (
        ("BANK-GROUP-ENTRY-40", Decimal("40.00")),
        ("BANK-GROUP-ENTRY-60", Decimal("60.00")),
    ):
        transactions.append(
            await service.create_transaction(
                organization.id,
                BankTransactionCreate(
                    bank_account_id=accounts["bank"].id,
                    transaction_date=date(2026, 1, 18),
                    amount=amount,
                    description=external_id,
                    external_id=external_id,
                ),
            )
        )
    transaction_ids = [transaction.id for transaction in transactions]
    batch = await service.reconcile_allocations(
        organization.id,
        user.id,
        "grouped-entry-001",
        ReconcileBankTransactionsRequest(
            bank_account_id=accounts["bank"].id,
            allocations=[
                ReconciliationAllocationCreate(
                    bank_transaction_id=transaction_ids[0],
                    journal_entry_id=entry_id,
                    matched_amount=Decimal("40.00"),
                ),
                ReconciliationAllocationCreate(
                    bank_transaction_id=transaction_ids[1],
                    journal_entry_id=entry_id,
                    matched_amount=Decimal("60.00"),
                ),
            ],
        ),
    )

    assert batch.allocated_total == Decimal("100.00")
    for transaction_id in transaction_ids:
        transaction = await service.repository.get_transaction(
            organization.id, transaction_id
        )
        assert transaction is not None and transaction.reconciled_at is not None


@pytest.mark.asyncio
async def test_partial_allocation_enforces_remainders_rolls_back_and_is_tenant_scoped(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        user,
        period,
        accounts,
        journal_id,
    ) = await _create_reconciliation_context(db_session)
    organization_id = organization.id
    user_id = user.id
    period_id = period.id
    bank_account_id = accounts["bank"].id
    first_entry_id = await _create_posted_entry(
        db_session,
        organization_id,
        period_id,
        journal_id,
        "BQ-PARTIAL-60",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("60.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("60.00")
            ),
        ],
    )
    second_entry_id = await _create_posted_entry(
        db_session,
        organization_id,
        period_id,
        journal_id,
        "BQ-PARTIAL-70",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=accounts["bank"].id, debit=Decimal("70.00")
            ),
            JournalEntryLineCreate(
                account_id=accounts["revenue"].id, credit=Decimal("70.00")
            ),
        ],
    )
    service = BankReconciliationService(db_session)
    transaction = await service.create_transaction(
        organization_id,
        BankTransactionCreate(
            bank_account_id=bank_account_id,
            transaction_date=date(2026, 1, 20),
            amount=Decimal("100.00"),
            description="Partial settlement",
            external_id="BANK-PARTIAL-100",
        ),
    )
    transaction_id = transaction.id
    first = await service.reconcile_allocations(
        organization_id,
        user_id,
        "partial-reconcile-001",
        ReconcileBankTransactionsRequest(
            bank_account_id=bank_account_id,
            allocations=[
                ReconciliationAllocationCreate(
                    bank_transaction_id=transaction_id,
                    journal_entry_id=first_entry_id,
                    matched_amount=Decimal("60.00"),
                )
            ],
        ),
    )
    assert first.allocated_total == Decimal("60.00")
    partially_reconciled = await service.repository.get_transaction(
        organization_id, transaction_id
    )
    assert partially_reconciled is not None
    assert partially_reconciled.reconciled_at is None

    with pytest.raises(
        HTTPException, match="exceeds bank transaction remainder"
    ) as overflow:
        await service.reconcile_allocations(
            organization_id,
            user_id,
            "partial-reconcile-overflow",
            ReconcileBankTransactionsRequest(
                bank_account_id=bank_account_id,
                allocations=[
                    ReconciliationAllocationCreate(
                        bank_transaction_id=transaction_id,
                        journal_entry_id=second_entry_id,
                        matched_amount=Decimal("41.00"),
                    )
                ],
            ),
        )
    assert overflow.value.status_code == 422
    assert (
        await db_session.scalar(
            select(func.count(BankReconciliationBatch.id)).where(
                BankReconciliationBatch.organization_id == organization_id
            )
        )
        == 1
    )

    (
        other_organization,
        _,
        other_period,
        other_accounts,
        other_journal_id,
    ) = await _create_reconciliation_context(db_session)
    foreign_entry_id = await _create_posted_entry(
        db_session,
        other_organization.id,
        other_period.id,
        other_journal_id,
        "BQ-OTHER-TENANT",
        date(2026, 1, 20),
        [
            JournalEntryLineCreate(
                account_id=other_accounts["bank"].id, debit=Decimal("40.00")
            ),
            JournalEntryLineCreate(
                account_id=other_accounts["revenue"].id, credit=Decimal("40.00")
            ),
        ],
    )
    with pytest.raises(
        HTTPException, match="Posted journal entry not found"
    ) as cross_tenant:
        await service.reconcile_allocations(
            organization_id,
            user_id,
            "partial-reconcile-tenant",
            ReconcileBankTransactionsRequest(
                bank_account_id=bank_account_id,
                allocations=[
                    ReconciliationAllocationCreate(
                        bank_transaction_id=transaction_id,
                        journal_entry_id=foreign_entry_id,
                        matched_amount=Decimal("40.00"),
                    )
                ],
            ),
        )
    assert cross_tenant.value.status_code == 422
