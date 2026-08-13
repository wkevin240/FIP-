import pytest
from app.domain.payroll.lifecycle.rules import PayrollLifecycleRules


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("DRAFT", "CALCULATED"),
        ("CALCULATED", "VALIDATED"),
        ("VALIDATED", "LOCKED"),
        ("LOCKED", "POSTED"),
    ],
)
def test_allows_explicit_payroll_period_transitions(
    current_status: str, target_status: str
) -> None:
    PayrollLifecycleRules.validate_period_transition(current_status, target_status)


@pytest.mark.parametrize(
    ("current_status", "target_status"),
    [
        ("DRAFT", "VALIDATED"),
        ("CALCULATED", "LOCKED"),
        ("VALIDATED", "POSTED"),
        ("POSTED", "LOCKED"),
    ],
)
def test_rejects_skipped_or_reversed_payroll_period_transitions(
    current_status: str, target_status: str
) -> None:
    with pytest.raises(ValueError, match="cannot transition"):
        PayrollLifecycleRules.validate_period_transition(current_status, target_status)


@pytest.mark.parametrize(
    "period_status", ["CALCULATED", "VALIDATED", "LOCKED", "POSTED"]
)
def test_rejects_input_mutation_after_calculation(period_status: str) -> None:
    with pytest.raises(ValueError, match="only be modified while the period is DRAFT"):
        PayrollLifecycleRules.validate_input_mutation(period_status)


@pytest.mark.parametrize("slip_status", ["DRAFT", "CALCULATED", "CORRECTED"])
def test_rejects_correction_before_validation_or_after_correction(
    slip_status: str,
) -> None:
    with pytest.raises(ValueError, match="Only validated, locked or posted"):
        PayrollLifecycleRules.validate_correction_source(slip_status)
