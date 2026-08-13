from decimal import Decimal

import pytest
from app.domain.payroll.calculation.rules import (
    ContributionRuleInput,
    PayrollCalculationRules,
    TaxBracketInput,
    VariableInput,
)


def _contribution(
    code: str,
    direction: str,
    rate: str,
    cap: str | None = None,
    sort_order: int = 1,
) -> ContributionRuleInput:
    return ContributionRuleInput(
        code=code,
        name=code,
        direction=direction,
        base_type="GROSS",
        rate=Decimal(rate),
        cap_amount=Decimal(cap) if cap is not None else None,
        sort_order=sort_order,
    )


def _bracket(lower: str, upper: str | None, rate: str, order: int) -> TaxBracketInput:
    return TaxBracketInput(
        lower_bound=Decimal(lower),
        upper_bound=Decimal(upper) if upper is not None else None,
        rate=Decimal(rate),
        sort_order=order,
    )


def test_calculation_keeps_all_intermediate_totals_and_snapshots() -> None:
    calculation = PayrollCalculationRules.calculate(
        base_salary=Decimal("1000.00"),
        inputs=[
            VariableInput(
                code="BONUS",
                description="Performance bonus",
                input_type="EARNING",
                amount=Decimal("100.00"),
                taxable=True,
                contribution_eligible=True,
            ),
            VariableInput(
                code="LOAN",
                description="Loan repayment",
                input_type="DEDUCTION",
                amount=Decimal("50.00"),
                taxable=False,
                contribution_eligible=False,
            ),
        ],
        contribution_rules=[
            _contribution("EMP_SOCIAL", "EMPLOYEE", "10.000000", "100.00"),
            _contribution("ER_SOCIAL", "EMPLOYER", "5.000000", None, 2),
        ],
        tax_brackets=[_bracket("0.00", None, "10.000000", 1)],
        professional_expense_rate=Decimal("0.000000"),
        professional_expense_cap=None,
        annual_tax_allowance=Decimal("0.00"),
        local_surtax_rate=Decimal("0.000000"),
    )

    assert calculation.variable_earning_total == Decimal("100.00")
    assert calculation.gross_salary == Decimal("1100.00")
    assert calculation.employee_contribution_total == Decimal("10.00")
    assert calculation.employer_contribution_total == Decimal("55.00")
    assert calculation.income_tax == Decimal("109.00")
    assert calculation.other_deduction_total == Decimal("50.00")
    assert calculation.net_salary == Decimal("931.00")
    assert [(line.line_type, line.rule_code) for line in calculation.lines] == [
        ("BASE_SALARY", "BASE_SALARY"),
        ("VARIABLE_EARNING", "BONUS"),
        ("OTHER_DEDUCTION", "LOAN"),
        ("EMPLOYEE_CONTRIBUTION", "EMP_SOCIAL"),
        ("EMPLOYER_CONTRIBUTION", "ER_SOCIAL"),
        ("INCOME_TAX", "INCOME_TAX"),
    ]


def test_progressive_tax_is_computed_from_ordered_annual_brackets() -> None:
    calculation = PayrollCalculationRules.calculate(
        base_salary=Decimal("100000.00"),
        inputs=[],
        contribution_rules=[],
        tax_brackets=[
            _bracket("0.00", "1000000.00", "10.000000", 1),
            _bracket("1000000.00", None, "20.000000", 2),
        ],
        professional_expense_rate=Decimal("0.000000"),
        professional_expense_cap=None,
        annual_tax_allowance=Decimal("0.00"),
        local_surtax_rate=Decimal("0.000000"),
    )

    assert calculation.income_tax == Decimal("11666.67")
    assert calculation.net_salary == Decimal("88333.33")


def test_rounds_contributions_half_up_at_the_cent() -> None:
    calculation = PayrollCalculationRules.calculate(
        base_salary=Decimal("1.00"),
        inputs=[],
        contribution_rules=[_contribution("ROUND", "EMPLOYEE", "0.500000")],
        tax_brackets=[],
        professional_expense_rate=Decimal("0.000000"),
        professional_expense_cap=None,
        annual_tax_allowance=Decimal("0.00"),
        local_surtax_rate=Decimal("0.000000"),
    )

    assert calculation.employee_contribution_total == Decimal("0.01")
    assert calculation.net_salary == Decimal("0.99")


@pytest.mark.parametrize(
    ("inputs", "brackets", "error"),
    [
        (
            [
                VariableInput(
                    code="NEG",
                    description="Invalid",
                    input_type="EARNING",
                    amount=Decimal("-1.00"),
                    taxable=True,
                    contribution_eligible=True,
                )
            ],
            [],
            "Payroll input amount cannot be negative",
        ),
        (
            [],
            [_bracket("1.00", None, "10.000000", 1)],
            "Tax brackets must be contiguous and ordered",
        ),
    ],
)
def test_rejects_invalid_inputs_and_brackets(
    inputs: list[VariableInput], brackets: list[TaxBracketInput], error: str
) -> None:
    with pytest.raises(ValueError, match=error):
        PayrollCalculationRules.calculate(
            base_salary=Decimal("100.00"),
            inputs=inputs,
            contribution_rules=[],
            tax_brackets=brackets,
            professional_expense_rate=Decimal("0.000000"),
            professional_expense_cap=None,
            annual_tax_allowance=Decimal("0.00"),
            local_surtax_rate=Decimal("0.000000"),
        )
