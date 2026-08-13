from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MONEY_QUANTUM = Decimal("0.01")
ONE_HUNDRED = Decimal(100)
MONTHS_PER_YEAR = Decimal(12)


@dataclass(frozen=True)
class ContributionRuleInput:
    code: str
    name: str
    direction: str
    base_type: str
    rate: Decimal
    cap_amount: Decimal | None
    sort_order: int


@dataclass(frozen=True)
class TaxBracketInput:
    lower_bound: Decimal
    upper_bound: Decimal | None
    rate: Decimal
    sort_order: int


@dataclass(frozen=True)
class VariableInput:
    code: str
    description: str
    input_type: str
    amount: Decimal
    taxable: bool
    contribution_eligible: bool


@dataclass(frozen=True)
class PayrollCalculationLine:
    line_type: str
    rule_code: str
    description: str
    base_amount: Decimal
    rate: Decimal
    cap_amount: Decimal | None
    amount: Decimal
    sort_order: int


@dataclass(frozen=True)
class PayrollCalculation:
    variable_earning_total: Decimal
    gross_salary: Decimal
    employee_contribution_total: Decimal
    employer_contribution_total: Decimal
    income_tax: Decimal
    other_deduction_total: Decimal
    net_salary: Decimal
    lines: list[PayrollCalculationLine]


class PayrollCalculationRules:
    @staticmethod
    def money(value: Decimal) -> Decimal:
        return Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)

    @classmethod
    def calculate(
        cls,
        base_salary: Decimal,
        inputs: list[VariableInput],
        contribution_rules: list[ContributionRuleInput],
        tax_brackets: list[TaxBracketInput],
        professional_expense_rate: Decimal,
        professional_expense_cap: Decimal | None,
        annual_tax_allowance: Decimal,
        local_surtax_rate: Decimal,
    ) -> PayrollCalculation:
        base_salary = cls.money(base_salary)
        if base_salary < 0:
            raise ValueError("Base salary cannot be negative")
        if not Decimal(0) <= Decimal(professional_expense_rate) <= ONE_HUNDRED:
            raise ValueError("Professional expense rate must be between 0 and 100")
        if not Decimal(0) <= Decimal(local_surtax_rate) <= ONE_HUNDRED:
            raise ValueError("Local surtax rate must be between 0 and 100")
        if Decimal(annual_tax_allowance) < 0:
            raise ValueError("Annual tax allowance cannot be negative")
        if (
            professional_expense_cap is not None
            and Decimal(professional_expense_cap) < 0
        ):
            raise ValueError("Professional expense cap cannot be negative")

        lines = [
            PayrollCalculationLine(
                line_type="BASE_SALARY",
                rule_code="BASE_SALARY",
                description="Base salary",
                base_amount=base_salary,
                rate=Decimal("0.000000"),
                cap_amount=None,
                amount=base_salary,
                sort_order=1,
            )
        ]
        variable_earnings = Decimal("0.00")
        other_deductions = Decimal("0.00")
        taxable_variable_earnings = Decimal("0.00")
        contribution_variable_earnings = Decimal("0.00")
        next_order = 2
        for item in inputs:
            amount = cls.money(item.amount)
            if amount < 0:
                raise ValueError("Payroll input amount cannot be negative")
            if item.input_type not in {"EARNING", "DEDUCTION"}:
                raise ValueError("Payroll input type must be EARNING or DEDUCTION")
            if item.input_type == "EARNING":
                variable_earnings += amount
                if item.taxable:
                    taxable_variable_earnings += amount
                if item.contribution_eligible:
                    contribution_variable_earnings += amount
                line_type = "VARIABLE_EARNING"
            else:
                other_deductions += amount
                line_type = "OTHER_DEDUCTION"
            lines.append(
                PayrollCalculationLine(
                    line_type=line_type,
                    rule_code=item.code,
                    description=item.description,
                    base_amount=amount,
                    rate=Decimal("0.000000"),
                    cap_amount=None,
                    amount=amount,
                    sort_order=next_order,
                )
            )
            next_order += 1

        gross_salary = cls.money(base_salary + variable_earnings)
        taxable_gross = cls.money(base_salary + taxable_variable_earnings)
        contribution_gross = cls.money(base_salary + contribution_variable_earnings)
        employee_contributions = Decimal("0.00")
        employer_contributions = Decimal("0.00")
        for rule in sorted(contribution_rules, key=lambda current: current.sort_order):
            if rule.direction not in {"EMPLOYEE", "EMPLOYER"}:
                raise ValueError("Contribution direction must be EMPLOYEE or EMPLOYER")
            if rule.base_type not in {"GROSS", "TAXABLE_GROSS"}:
                raise ValueError("Contribution base type is invalid")
            if not Decimal(0) <= Decimal(rule.rate) <= ONE_HUNDRED:
                raise ValueError("Contribution rate must be between 0 and 100")
            if rule.cap_amount is not None and Decimal(rule.cap_amount) < 0:
                raise ValueError("Contribution cap cannot be negative")
            basis = contribution_gross if rule.base_type == "GROSS" else taxable_gross
            cap = Decimal(rule.cap_amount) if rule.cap_amount is not None else None
            applied_base = min(basis, cap) if cap is not None else basis
            amount = cls.money(applied_base * Decimal(rule.rate) / ONE_HUNDRED)
            line_type = (
                "EMPLOYEE_CONTRIBUTION"
                if rule.direction == "EMPLOYEE"
                else "EMPLOYER_CONTRIBUTION"
            )
            lines.append(
                PayrollCalculationLine(
                    line_type=line_type,
                    rule_code=rule.code,
                    description=rule.name,
                    base_amount=applied_base,
                    rate=Decimal(rule.rate),
                    cap_amount=cap,
                    amount=amount,
                    sort_order=next_order,
                )
            )
            next_order += 1
            if rule.direction == "EMPLOYEE":
                employee_contributions += amount
            else:
                employer_contributions += amount

        annual_taxable_income = taxable_gross * MONTHS_PER_YEAR
        professional_expense = (
            annual_taxable_income * Decimal(professional_expense_rate) / ONE_HUNDRED
        )
        if professional_expense_cap is not None:
            professional_expense = min(
                professional_expense, Decimal(professional_expense_cap)
            )
        annual_tax_base = max(
            Decimal("0.00"),
            annual_taxable_income
            - professional_expense
            - employee_contributions * MONTHS_PER_YEAR
            - Decimal(annual_tax_allowance),
        )
        annual_tax = cls._progressive_tax(annual_tax_base, tax_brackets)
        monthly_tax = cls.money(annual_tax / MONTHS_PER_YEAR)
        local_surtax = cls.money(monthly_tax * Decimal(local_surtax_rate) / ONE_HUNDRED)
        income_tax = cls.money(monthly_tax + local_surtax)
        lines.append(
            PayrollCalculationLine(
                line_type="INCOME_TAX",
                rule_code="INCOME_TAX",
                description="Income tax withholding",
                base_amount=cls.money(annual_tax_base / MONTHS_PER_YEAR),
                rate=Decimal("0.000000"),
                cap_amount=None,
                amount=income_tax,
                sort_order=next_order,
            )
        )
        net_salary = cls.money(
            gross_salary - employee_contributions - income_tax - other_deductions
        )
        if net_salary < 0:
            raise ValueError("Net salary cannot be negative")
        return PayrollCalculation(
            variable_earning_total=cls.money(variable_earnings),
            gross_salary=gross_salary,
            employee_contribution_total=cls.money(employee_contributions),
            employer_contribution_total=cls.money(employer_contributions),
            income_tax=income_tax,
            other_deduction_total=cls.money(other_deductions),
            net_salary=net_salary,
            lines=lines,
        )

    @classmethod
    def _progressive_tax(
        cls, annual_tax_base: Decimal, brackets: list[TaxBracketInput]
    ) -> Decimal:
        previous_upper = Decimal("0.00")
        annual_tax = Decimal("0.00")
        for bracket in sorted(brackets, key=lambda current: current.sort_order):
            lower = Decimal(bracket.lower_bound)
            upper = (
                Decimal(bracket.upper_bound)
                if bracket.upper_bound is not None
                else None
            )
            rate = Decimal(bracket.rate)
            if lower != previous_upper:
                raise ValueError("Tax brackets must be contiguous and ordered")
            if upper is not None and upper <= lower:
                raise ValueError("Tax bracket upper bound must exceed lower bound")
            if not Decimal(0) <= rate <= ONE_HUNDRED:
                raise ValueError("Tax bracket rate must be between 0 and 100")
            taxable_slice = max(Decimal("0.00"), annual_tax_base - lower)
            if upper is not None:
                taxable_slice = min(taxable_slice, upper - lower)
            annual_tax += taxable_slice * rate / ONE_HUNDRED
            if upper is None:
                previous_upper = annual_tax_base
                break
            previous_upper = upper
        return cls.money(annual_tax)
