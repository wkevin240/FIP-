import json
from collections import defaultdict
from datetime import datetime, timezone
from decimal import Decimal

from app.core.enums.accounting import FiscalPeriodStatus
from app.domain.payroll.calculation.rules import (
    ContributionRuleInput,
    PayrollCalculationRules,
    TaxBracketInput,
    VariableInput,
)
from app.domain.payroll.lifecycle.rules import PayrollLifecycleRules
from app.models.payroll.payroll import PayrollCorrection, PayrollInput, PayrollSlip
from app.models.payroll.payroll_period import PayrollPeriod
from app.repositories.accounting.fiscal_period_repository import FiscalPeriodRepository
from app.repositories.payroll.audit_repository import PayrollAuditRepository
from app.repositories.payroll.configuration_repository import (
    PayrollAccountingProfileRepository,
    PayrollRuleSetRepository,
)
from app.repositories.payroll.employee_repository import (
    EmployeeRepository,
    EmploymentContractRepository,
)
from app.repositories.payroll.payroll_repository import (
    PayrollInputRepository,
    PayrollPeriodRepository,
    PayrollSlipRepository,
)
from app.schemas.accounting.journal_entry import JournalEntryCreate
from app.schemas.accounting.journal_entry_line import JournalEntryLineCreate
from app.schemas.payroll.configuration import PayrollPeriodCreate
from app.schemas.payroll.payroll import PayrollCorrectionCreate, PayrollInputCreate
from app.services.accounting.journal_entry_service import JournalEntryService
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


class PayrollService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.periods = PayrollPeriodRepository(session)
        self.inputs = PayrollInputRepository(session)
        self.slips = PayrollSlipRepository(session)
        self.employees = EmployeeRepository(session)
        self.contracts = EmploymentContractRepository(session)
        self.rule_sets = PayrollRuleSetRepository(session)
        self.accounting_profiles = PayrollAccountingProfileRepository(session)
        self.fiscal_periods = FiscalPeriodRepository(session)
        self.audit = PayrollAuditRepository(session)
        self.journal_entries = JournalEntryService(session)

    async def get_period(
        self, organization_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        payroll_period = await self.periods.get_by_id(
            organization_id, payroll_period_id
        )
        if payroll_period is None:
            raise HTTPException(status_code=404, detail="Payroll period not found")
        return payroll_period

    async def list_periods(
        self, organization_id: str, status_value: str | None, offset: int, limit: int
    ) -> list[PayrollPeriod]:
        return await self.periods.list(
            organization_id, status_value, max(offset, 0), min(max(limit, 1), 100)
        )

    async def create_period(
        self, organization_id: str, actor_user_id: str, data: PayrollPeriodCreate
    ) -> PayrollPeriod:
        if await self.periods.get_by_code(organization_id, data.period_code):
            raise HTTPException(
                status_code=409, detail="Payroll period code already exists"
            )
        rule_set = await self.rule_sets.get_by_id(organization_id, data.rule_set_id)
        if (
            rule_set is None
            or not rule_set.is_active
            or rule_set.effective_from > data.payment_date
            or (
                rule_set.effective_to is not None
                and rule_set.effective_to < data.payment_date
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active payroll rule set effective on the payment date is required",
            )
        accounting_profile = await self.accounting_profiles.get_by_id(
            organization_id, data.accounting_profile_id
        )
        if accounting_profile is None or not accounting_profile.is_active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="An active payroll accounting profile is required",
            )
        fiscal_period = await self.fiscal_periods.get_by_id(
            organization_id, data.fiscal_period_id
        )
        if (
            fiscal_period is None
            or data.payment_date < fiscal_period.start_date
            or data.payment_date > fiscal_period.end_date
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Payroll payment date must belong to the selected fiscal period",
            )
        try:
            payroll_period = await self.periods.create(organization_id, data)
            await self.audit.append(
                organization_id,
                actor_user_id,
                "PAYROLL_PERIOD_CREATED",
                "PayrollPeriod",
                payroll_period.id,
                payroll_period_id=payroll_period.id,
                new_value=json.dumps({"period_code": payroll_period.period_code}),
            )
            await self.session.commit()
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll period code already exists",
            ) from exc
        return await self.get_period(organization_id, payroll_period.id)

    async def create_input(
        self,
        organization_id: str,
        actor_user_id: str,
        payroll_period_id: str,
        data: PayrollInputCreate,
    ) -> PayrollInput:
        try:
            payroll_period = await self._locked_period(
                organization_id, payroll_period_id
            )
            PayrollLifecycleRules.validate_input_mutation(payroll_period.status)
            employee = await self.employees.get_by_id(organization_id, data.employee_id)
            if employee is None or not employee.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="An active payroll employee is required",
                )
            payroll_input = await self.inputs.create(
                organization_id, payroll_period.id, actor_user_id, data
            )
            await self.audit.append(
                organization_id,
                actor_user_id,
                "PAYROLL_INPUT_CREATED",
                "PayrollInput",
                payroll_input.id,
                payroll_period_id=payroll_period.id,
                new_value=json.dumps(
                    {
                        "employee_id": payroll_input.employee_id,
                        "input_code": payroll_input.input_code,
                        "amount": str(payroll_input.amount),
                    }
                ),
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        except IntegrityError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Payroll input conflicts with an existing source reference",
            ) from exc
        await self.session.refresh(payroll_input)
        return payroll_input

    async def calculate_period(
        self, organization_id: str, actor_user_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        try:
            payroll_period = await self._locked_period(
                organization_id, payroll_period_id
            )
            PayrollLifecycleRules.validate_period_transition(
                payroll_period.status, "CALCULATED"
            )
            rule_set = await self.rule_sets.get_by_id(
                organization_id, payroll_period.rule_set_id
            )
            if rule_set is None or not rule_set.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Payroll rule set is not active",
                )
            active_employees = await self.employees.list(organization_id, True, 0, 100)
            eligible_employees = [
                employee
                for employee in active_employees
                if employee.hire_date <= payroll_period.end_date
                and (
                    employee.termination_date is None
                    or employee.termination_date >= payroll_period.start_date
                )
            ]
            if not eligible_employees:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="No active payroll employees are eligible for this period",
                )
            inputs_by_employee: dict[str, list[VariableInput]] = defaultdict(list)
            for payroll_input in payroll_period.inputs:
                inputs_by_employee[payroll_input.employee_id].append(
                    self._variable_input(payroll_input)
                )
            contribution_rules = [
                ContributionRuleInput(
                    code=rule.code,
                    name=rule.name,
                    direction=rule.direction,
                    base_type=rule.base_type,
                    rate=Decimal(rule.rate),
                    cap_amount=(
                        Decimal(rule.cap_amount)
                        if rule.cap_amount is not None
                        else None
                    ),
                    sort_order=rule.sort_order,
                )
                for rule in rule_set.contribution_rules
                if rule.is_active
            ]
            tax_brackets = [
                TaxBracketInput(
                    lower_bound=Decimal(bracket.lower_bound),
                    upper_bound=(
                        Decimal(bracket.upper_bound)
                        if bracket.upper_bound is not None
                        else None
                    ),
                    rate=Decimal(bracket.rate),
                    sort_order=bracket.sort_order,
                )
                for bracket in rule_set.tax_brackets
            ]
            calculated_slips: list[PayrollSlip] = []
            for employee in eligible_employees:
                contract = await self.contracts.active_for_date(
                    organization_id, employee.id, payroll_period.payment_date
                )
                if contract is None:
                    raise HTTPException(
                        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                        detail=(
                            f"Active payroll contract required for employee "
                            f"{employee.employee_code}"
                        ),
                    )
                calculation = PayrollCalculationRules.calculate(
                    Decimal(contract.base_salary),
                    inputs_by_employee[employee.id],
                    contribution_rules,
                    tax_brackets,
                    Decimal(rule_set.professional_expense_rate),
                    (
                        Decimal(rule_set.professional_expense_cap)
                        if rule_set.professional_expense_cap is not None
                        else None
                    ),
                    Decimal(rule_set.annual_tax_allowance),
                    Decimal(rule_set.local_surtax_rate),
                )
                lines = [
                    {
                        "line_type": line.line_type,
                        "rule_code": line.rule_code,
                        "description": line.description,
                        "base_amount": line.base_amount,
                        "rate": line.rate,
                        "cap_amount": line.cap_amount,
                        "amount": line.amount,
                        "sort_order": line.sort_order,
                    }
                    for line in calculation.lines
                ]
                slip = await self.slips.build_slip(
                    {
                        "organization_id": organization_id,
                        "employee_id": employee.id,
                        "contract_id": contract.id,
                        "slip_number": f"{payroll_period.period_code}-{employee.employee_code}",
                        "correction_sequence": 0,
                        "status": "CALCULATED",
                        "currency": contract.currency,
                        "base_salary": Decimal(contract.base_salary),
                        "variable_earning_total": calculation.variable_earning_total,
                        "gross_salary": calculation.gross_salary,
                        "employee_contribution_total": calculation.employee_contribution_total,
                        "employer_contribution_total": calculation.employer_contribution_total,
                        "income_tax": calculation.income_tax,
                        "other_deduction_total": calculation.other_deduction_total,
                        "net_salary": calculation.net_salary,
                    },
                    lines,
                )
                calculated_slips.append(slip)
            await self.slips.replace_calculated_for_period(
                payroll_period, calculated_slips
            )
            self._apply_period_totals(payroll_period, calculated_slips)
            payroll_period.status = "CALCULATED"
            payroll_period.calculated_at = self._now()
            await self.audit.append(
                organization_id,
                actor_user_id,
                "PAYROLL_PERIOD_CALCULATED",
                "PayrollPeriod",
                payroll_period.id,
                payroll_period_id=payroll_period.id,
                previous_value=json.dumps({"status": "DRAFT"}),
                new_value=json.dumps(
                    {
                        "status": "CALCULATED",
                        "gross_total": str(payroll_period.gross_total),
                        "net_total": str(payroll_period.net_total),
                    }
                ),
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        return await self.get_period(organization_id, payroll_period_id)

    async def validate_period(
        self, organization_id: str, actor_user_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        return await self._transition_period(
            organization_id,
            actor_user_id,
            payroll_period_id,
            "VALIDATED",
            "PAYROLL_PERIOD_VALIDATED",
        )

    async def lock_period(
        self, organization_id: str, actor_user_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        return await self._transition_period(
            organization_id,
            actor_user_id,
            payroll_period_id,
            "LOCKED",
            "PAYROLL_PERIOD_LOCKED",
        )

    async def post_period(
        self, organization_id: str, actor_user_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        try:
            payroll_period = await self._locked_period(
                organization_id, payroll_period_id
            )
            PayrollLifecycleRules.validate_period_transition(
                payroll_period.status, "POSTED"
            )
            fiscal_period = await self.fiscal_periods.get_by_id(
                organization_id, payroll_period.fiscal_period_id, for_update=True
            )
            if fiscal_period is None or fiscal_period.status != FiscalPeriodStatus.OPEN:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Payroll posting requires an open fiscal period",
                )
            profile = await self.accounting_profiles.get_by_id(
                organization_id, payroll_period.accounting_profile_id
            )
            if profile is None or not profile.is_active:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                    detail="Payroll posting requires an active accounting profile",
                )
            accounting_lines = self._accounting_lines(payroll_period, profile)
            entry = await self.journal_entries.create_entry(
                organization_id,
                JournalEntryCreate(
                    journal_id=profile.journal_id,
                    fiscal_period_id=fiscal_period.id,
                    entry_number=f"PAY-{payroll_period.id[:24]}",
                    entry_date=payroll_period.payment_date,
                    description=f"Payroll posting {payroll_period.period_code}",
                    reference=payroll_period.period_code,
                    lines=accounting_lines,
                ),
            )
            posted_entry = await self.journal_entries.post_entry(
                organization_id, entry.id
            )
            payroll_period.status = "POSTED"
            payroll_period.posted_at = self._now()
            payroll_period.posted_by_user_id = actor_user_id
            payroll_period.journal_entry_id = posted_entry.id
            for slip in payroll_period.slips:
                slip.status = "POSTED"
                slip.posted_at = payroll_period.posted_at
            await self.audit.append(
                organization_id,
                actor_user_id,
                "PAYROLL_PERIOD_POSTED",
                "PayrollPeriod",
                payroll_period.id,
                payroll_period_id=payroll_period.id,
                previous_value=json.dumps({"status": "LOCKED"}),
                new_value=json.dumps(
                    {"status": "POSTED", "journal_entry_id": posted_entry.id}
                ),
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        return await self.get_period(organization_id, payroll_period_id)

    async def list_slips(
        self, organization_id: str, payroll_period_id: str
    ) -> list[PayrollSlip]:
        await self.get_period(organization_id, payroll_period_id)
        return await self.slips.list_for_period(organization_id, payroll_period_id)

    async def request_correction(
        self,
        organization_id: str,
        actor_user_id: str,
        payroll_slip_id: str,
        data: PayrollCorrectionCreate,
    ) -> PayrollCorrection:
        try:
            slip = await self.slips.get_by_id(organization_id, payroll_slip_id, True)
            if slip is None:
                raise HTTPException(status_code=404, detail="Payroll slip not found")
            PayrollLifecycleRules.validate_correction_source(slip.status)
            correction = await self.slips.create_correction(
                organization_id, slip.id, actor_user_id, data
            )
            await self.audit.append(
                organization_id,
                actor_user_id,
                "PAYROLL_CORRECTION_REQUESTED",
                "PayrollCorrection",
                correction.id,
                payroll_period_id=slip.payroll_period_id,
                previous_value=json.dumps({"slip_status": slip.status}),
                new_value=json.dumps({"status": correction.status}),
                reason=correction.reason,
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        await self.session.refresh(correction)
        return correction

    async def list_audit_events(
        self, organization_id: str, payroll_period_id: str
    ) -> list:
        await self.get_period(organization_id, payroll_period_id)
        return await self.audit.list_for_period(organization_id, payroll_period_id)

    async def _transition_period(
        self,
        organization_id: str,
        actor_user_id: str,
        payroll_period_id: str,
        target_status: str,
        action: str,
    ) -> PayrollPeriod:
        try:
            payroll_period = await self._locked_period(
                organization_id, payroll_period_id
            )
            previous_status = payroll_period.status
            PayrollLifecycleRules.validate_period_transition(
                previous_status, target_status
            )
            payroll_period.status = target_status
            now = self._now()
            if target_status == "VALIDATED":
                payroll_period.validated_at = now
                payroll_period.validated_by_user_id = actor_user_id
            if target_status == "LOCKED":
                payroll_period.locked_at = now
                payroll_period.locked_by_user_id = actor_user_id
            for slip in payroll_period.slips:
                slip.status = target_status
                if target_status == "VALIDATED":
                    slip.validated_at = now
                if target_status == "LOCKED":
                    slip.locked_at = now
            await self.audit.append(
                organization_id,
                actor_user_id,
                action,
                "PayrollPeriod",
                payroll_period.id,
                payroll_period_id=payroll_period.id,
                previous_value=json.dumps({"status": previous_status}),
                new_value=json.dumps({"status": target_status}),
            )
            await self.session.commit()
        except ValueError as exc:
            await self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
            ) from exc
        except HTTPException:
            await self.session.rollback()
            raise
        return await self.get_period(organization_id, payroll_period_id)

    async def _locked_period(
        self, organization_id: str, payroll_period_id: str
    ) -> PayrollPeriod:
        payroll_period = await self.periods.get_by_id(
            organization_id, payroll_period_id, for_update=True
        )
        if payroll_period is None:
            raise HTTPException(status_code=404, detail="Payroll period not found")
        return payroll_period

    @staticmethod
    def _variable_input(payroll_input: PayrollInput) -> VariableInput:
        return VariableInput(
            code=payroll_input.input_code,
            description=payroll_input.description,
            input_type=payroll_input.input_type,
            amount=Decimal(payroll_input.amount),
            taxable=payroll_input.taxable,
            contribution_eligible=payroll_input.contribution_eligible,
        )

    @staticmethod
    def _apply_period_totals(
        payroll_period: PayrollPeriod, slips: list[PayrollSlip]
    ) -> None:
        payroll_period.gross_total = PayrollCalculationRules.money(
            sum((Decimal(slip.gross_salary) for slip in slips), Decimal("0.00"))
        )
        payroll_period.employee_contribution_total = PayrollCalculationRules.money(
            sum(
                (Decimal(slip.employee_contribution_total) for slip in slips),
                Decimal("0.00"),
            )
        )
        payroll_period.employer_contribution_total = PayrollCalculationRules.money(
            sum(
                (Decimal(slip.employer_contribution_total) for slip in slips),
                Decimal("0.00"),
            )
        )
        payroll_period.tax_total = PayrollCalculationRules.money(
            sum((Decimal(slip.income_tax) for slip in slips), Decimal("0.00"))
        )
        payroll_period.other_deduction_total = PayrollCalculationRules.money(
            sum(
                (Decimal(slip.other_deduction_total) for slip in slips),
                Decimal("0.00"),
            )
        )
        payroll_period.net_total = PayrollCalculationRules.money(
            sum((Decimal(slip.net_salary) for slip in slips), Decimal("0.00"))
        )

    @staticmethod
    def _accounting_lines(
        payroll_period: PayrollPeriod, profile
    ) -> list[JournalEntryLineCreate]:
        debit_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        credit_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0.00"))
        debit_totals[profile.salary_expense_account_id] += Decimal(
            payroll_period.gross_total
        )
        debit_totals[profile.employer_charge_account_id] += Decimal(
            payroll_period.employer_contribution_total
        )
        credit_totals[profile.employee_payable_account_id] += Decimal(
            payroll_period.net_total
        )
        credit_totals[profile.tax_payable_account_id] += Decimal(
            payroll_period.tax_total
        )
        credit_totals[profile.social_payable_account_id] += Decimal(
            payroll_period.employee_contribution_total
        ) + Decimal(payroll_period.employer_contribution_total)
        credit_totals[profile.other_deduction_payable_account_id] += Decimal(
            payroll_period.other_deduction_total
        )
        lines = [
            JournalEntryLineCreate(
                account_id=account_id,
                description=f"Payroll {payroll_period.period_code}",
                debit=PayrollCalculationRules.money(amount),
            )
            for account_id, amount in sorted(debit_totals.items())
            if amount > 0
        ]
        lines.extend(
            JournalEntryLineCreate(
                account_id=account_id,
                description=f"Payroll {payroll_period.period_code}",
                credit=PayrollCalculationRules.money(amount),
            )
            for account_id, amount in sorted(credit_totals.items())
            if amount > 0
        )
        debit_total = sum((line.debit for line in lines), Decimal("0.00"))
        credit_total = sum((line.credit for line in lines), Decimal("0.00"))
        if debit_total != credit_total:
            raise ValueError("Payroll accounting entry totals must balance")
        if len(lines) < 2:
            raise ValueError("Payroll accounting entry requires at least two lines")
        return lines

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc).replace(tzinfo=None)
