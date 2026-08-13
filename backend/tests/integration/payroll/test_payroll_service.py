from datetime import date
from decimal import Decimal

import pytest
from app.core.enums.accounting import (
    FiscalPeriodStatus,
    FiscalYearStatus,
    JournalEntryStatus,
)
from app.models.accounting.account import Account
from app.models.accounting.fiscal_period import FiscalPeriod
from app.models.accounting.fiscal_year import FiscalYear
from app.models.organization import Organization
from app.schemas.accounting.journal import JournalCreate
from app.schemas.payroll.configuration import (
    ContributionRuleCreate,
    PayrollAccountingProfileCreate,
    PayrollPeriodCreate,
    PayrollRuleSetCreate,
    TaxBracketCreate,
)
from app.schemas.payroll.employee import (
    EmployeeCreate,
    EmploymentContractCreate,
    EmploymentContractUpdate,
)
from app.schemas.payroll.payroll import PayrollCorrectionCreate, PayrollInputCreate
from app.services.accounting.journal_service import JournalService
from app.services.payroll.configuration_service import PayrollConfigurationService
from app.services.payroll.employee_service import EmployeeService
from app.services.payroll.payroll_service import PayrollService
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession


async def _create_payroll_context(
    session: AsyncSession,
) -> tuple[Organization, PayrollService, str, str]:
    organization = Organization(name="Payroll test organization")
    session.add(organization)
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
    fiscal_period = FiscalPeriod(
        organization_id=organization.id,
        fiscal_year_id=fiscal_year.id,
        name="January 2026",
        start_date=date(2026, 1, 1),
        end_date=date(2026, 1, 31),
        status=FiscalPeriodStatus.OPEN,
    )
    account_specs = [
        ("661100", "Salary expense", "EXPENSE"),
        ("661200", "Employer social charge", "EXPENSE"),
        ("421100", "Employee payable", "LIABILITY"),
        ("442100", "Tax payable", "LIABILITY"),
        ("431100", "Social payable", "LIABILITY"),
        ("427100", "Other deductions payable", "LIABILITY"),
    ]
    accounts = []
    for code, name, account_type in account_specs:
        account = Account(
            organization_id=organization.id,
            code=code,
            name=name,
            account_type=account_type,
            level=1,
            path=f"/{code}/",
            is_active=True,
        )
        accounts.append(account)
    session.add_all([fiscal_period, *accounts])
    await session.commit()

    journal = await JournalService(session).create_journal(
        organization.id, JournalCreate(code="PAY", name="Payroll journal")
    )
    employee_service = EmployeeService(session)
    employee = await employee_service.create_employee(
        organization.id,
        "payroll-actor",
        EmployeeCreate(
            employee_code="EMP-001",
            first_name="Ada",
            last_name="Pay",
            hire_date=date(2025, 1, 1),
        ),
    )
    contract = await employee_service.create_contract(
        organization.id,
        "payroll-actor",
        employee.id,
        EmploymentContractCreate(
            contract_number="CON-001",
            title="Financial analyst",
            start_date=date(2025, 1, 1),
            base_salary=Decimal("1000.00"),
        ),
    )
    await employee_service.update_contract(
        organization.id,
        "payroll-actor",
        contract.id,
        EmploymentContractUpdate(status="ACTIVE"),
    )

    configuration_service = PayrollConfigurationService(session)
    rule_set = await configuration_service.create_rule_set(
        organization.id,
        "payroll-actor",
        PayrollRuleSetCreate(
            code="CM-2026-01",
            name="Configurable Cameroon reference set",
            effective_from=date(2026, 1, 1),
            professional_expense_rate=Decimal("0.000000"),
            annual_tax_allowance=Decimal("0.00"),
            local_surtax_rate=Decimal("0.000000"),
            contribution_rules=[
                ContributionRuleCreate(
                    code="EMP-SOCIAL",
                    name="Employee social contribution",
                    direction="EMPLOYEE",
                    rate=Decimal("4.200000"),
                    cap_amount=Decimal("750000.00"),
                    sort_order=1,
                ),
                ContributionRuleCreate(
                    code="ER-SOCIAL",
                    name="Employer social contribution",
                    direction="EMPLOYER",
                    rate=Decimal("7.000000"),
                    cap_amount=Decimal("750000.00"),
                    sort_order=2,
                ),
            ],
            tax_brackets=[
                TaxBracketCreate(
                    lower_bound=Decimal("0.00"),
                    upper_bound=None,
                    rate=Decimal("10.000000"),
                    sort_order=1,
                )
            ],
        ),
    )
    profile = await configuration_service.create_accounting_profile(
        organization.id,
        "payroll-actor",
        PayrollAccountingProfileCreate(
            profile_code="PAY-DEFAULT",
            name="Default payroll accounting",
            journal_id=journal.id,
            salary_expense_account_id=accounts[0].id,
            employer_charge_account_id=accounts[1].id,
            employee_payable_account_id=accounts[2].id,
            tax_payable_account_id=accounts[3].id,
            social_payable_account_id=accounts[4].id,
            other_deduction_payable_account_id=accounts[5].id,
        ),
    )
    payroll_service = PayrollService(session)
    payroll_period = await payroll_service.create_period(
        organization.id,
        "payroll-actor",
        PayrollPeriodCreate(
            period_code="PAY-2026-01",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 1, 31),
            payment_date=date(2026, 1, 31),
            fiscal_period_id=fiscal_period.id,
            rule_set_id=rule_set.id,
            accounting_profile_id=profile.id,
        ),
    )
    return organization, payroll_service, payroll_period.id, employee.id


@pytest.mark.asyncio
async def test_payroll_lifecycle_correction_and_accounting_posting(
    db_session: AsyncSession,
) -> None:
    (
        organization,
        payroll_service,
        payroll_period_id,
        employee_id,
    ) = await _create_payroll_context(db_session)
    organization_id = organization.id
    payroll_input = await payroll_service.create_input(
        organization_id,
        "payroll-actor",
        payroll_period_id,
        PayrollInputCreate(
            employee_id=employee_id,
            input_code="BONUS",
            description="Monthly bonus",
            input_type="EARNING",
            amount=Decimal("100.00"),
        ),
    )

    calculated = await payroll_service.calculate_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    slips = await payroll_service.list_slips(organization.id, payroll_period_id)

    assert payroll_input.amount == Decimal("100.00")
    assert calculated.status == "CALCULATED"
    assert calculated.gross_total == Decimal("1100.00")
    assert calculated.employee_contribution_total == Decimal("46.20")
    assert calculated.employer_contribution_total == Decimal("77.00")
    assert calculated.tax_total == Decimal("105.38")
    assert calculated.net_total == Decimal("948.42")
    assert len(slips) == 1
    slip_id = slips[0].id
    assert slips[0].net_salary == Decimal("948.42")
    assert slips[0].lines[-1].line_type == "INCOME_TAX"

    with pytest.raises(
        HTTPException, match="only be modified while the period is DRAFT"
    ):
        await payroll_service.create_input(
            organization_id,
            "payroll-actor",
            payroll_period_id,
            PayrollInputCreate(
                employee_id=slips[0].employee_id,
                input_code="LATE",
                description="Forbidden late input",
                input_type="EARNING",
                amount=Decimal("1.00"),
            ),
        )

    validated = await payroll_service.validate_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    assert validated.status == "VALIDATED"
    with pytest.raises(HTTPException, match="cannot transition"):
        await payroll_service.validate_period(
            organization_id, "payroll-actor", payroll_period_id
        )

    correction = await payroll_service.request_correction(
        organization_id,
        "payroll-actor",
        slip_id,
        PayrollCorrectionCreate(
            correction_number="CORR-001", reason="Approved salary correction request"
        ),
    )
    assert correction.status == "REQUESTED"
    locked = await payroll_service.lock_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    assert locked.status == "LOCKED"
    posted = await payroll_service.post_period(
        organization_id, "payroll-actor", payroll_period_id
    )

    assert posted.status == "POSTED"
    assert posted.journal_entry_id is not None
    entry = await payroll_service.journal_entries.get_entry(
        organization_id, posted.journal_entry_id
    )
    assert entry.status == JournalEntryStatus.POSTED
    assert sum(line.debit for line in entry.lines) == sum(
        line.credit for line in entry.lines
    )
    assert sum(line.debit for line in entry.lines) == Decimal("1177.00")
    audit_events = await payroll_service.list_audit_events(
        organization_id, payroll_period_id
    )
    assert {event.action for event in audit_events} >= {
        "PAYROLL_PERIOD_CREATED",
        "PAYROLL_PERIOD_CALCULATED",
        "PAYROLL_PERIOD_VALIDATED",
        "PAYROLL_PERIOD_LOCKED",
        "PAYROLL_PERIOD_POSTED",
        "PAYROLL_CORRECTION_REQUESTED",
    }


@pytest.mark.asyncio
async def test_payroll_period_is_tenant_scoped(db_session: AsyncSession) -> None:
    organization, payroll_service, payroll_period_id, _ = await _create_payroll_context(
        db_session
    )
    other_organization = Organization(name="Other payroll organization")
    db_session.add(other_organization)
    await db_session.commit()

    with pytest.raises(HTTPException, match="Payroll period not found"):
        await payroll_service.get_period(other_organization.id, payroll_period_id)
    assert organization.id != other_organization.id


@pytest.mark.asyncio
async def test_closed_fiscal_period_rejects_payroll_posting(
    db_session: AsyncSession,
) -> None:
    organization, payroll_service, payroll_period_id, _ = await _create_payroll_context(
        db_session
    )
    organization_id = organization.id
    await payroll_service.calculate_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    await payroll_service.validate_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    locked = await payroll_service.lock_period(
        organization_id, "payroll-actor", payroll_period_id
    )
    fiscal_period = await db_session.get(FiscalPeriod, locked.fiscal_period_id)
    assert fiscal_period is not None
    fiscal_period.status = FiscalPeriodStatus.CLOSED
    await db_session.commit()

    with pytest.raises(HTTPException, match="requires an open fiscal period"):
        await payroll_service.post_period(
            organization_id, "payroll-actor", payroll_period_id
        )
