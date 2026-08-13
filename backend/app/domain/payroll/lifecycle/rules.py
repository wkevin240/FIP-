from typing import ClassVar


class PayrollLifecycleRules:
    _PERIOD_TRANSITIONS: ClassVar[dict[str, frozenset[str]]] = {
        "DRAFT": frozenset({"CALCULATED"}),
        "CALCULATED": frozenset({"VALIDATED"}),
        "VALIDATED": frozenset({"LOCKED"}),
        "LOCKED": frozenset({"POSTED"}),
        "POSTED": frozenset(),
    }

    @classmethod
    def validate_period_transition(
        cls, current_status: str, target_status: str
    ) -> None:
        if target_status not in cls._PERIOD_TRANSITIONS.get(current_status, set()):
            raise ValueError(
                f"Payroll period cannot transition from {current_status} to {target_status}"
            )

    @staticmethod
    def validate_input_mutation(period_status: str) -> None:
        if period_status != "DRAFT":
            raise ValueError(
                "Payroll inputs can only be modified while the period is DRAFT"
            )

    @staticmethod
    def validate_correction_source(slip_status: str) -> None:
        if slip_status not in {"VALIDATED", "LOCKED", "POSTED"}:
            raise ValueError(
                "Only validated, locked or posted payroll slips can be corrected"
            )

    @staticmethod
    def validate_non_overlapping_contract(
        start_date: object, end_date: object, overlaps: bool
    ) -> None:
        if end_date is not None and end_date < start_date:
            raise ValueError("Contract end date cannot precede start date")
        if overlaps:
            raise ValueError("An overlapping active payroll contract already exists")
