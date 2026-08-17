from decimal import Decimal


class BankReconciliationRules:
    @staticmethod
    def validate_match(bank_amount: Decimal, ledger_amount: Decimal) -> None:
        if bank_amount == 0 or ledger_amount == 0:
            raise ValueError("Bank and ledger amounts must be non-zero")
        if bank_amount * ledger_amount < 0:
            raise ValueError("Bank and ledger amounts must have the same direction")
        if abs(bank_amount) != abs(ledger_amount):
            raise ValueError("Bank and ledger amounts must match exactly")

    @staticmethod
    def validate_allocation(
        bank_amount: Decimal,
        bank_allocated: Decimal,
        ledger_amount: Decimal,
        ledger_allocated: Decimal,
        matched_amount: Decimal,
    ) -> None:
        if matched_amount <= 0:
            raise ValueError("Reconciliation allocation amount must be positive")
        if bank_amount == 0 or ledger_amount == 0:
            raise ValueError("Bank and ledger amounts must be non-zero")
        if bank_amount * ledger_amount < 0:
            raise ValueError("Bank and ledger amounts must have the same direction")
        if bank_allocated + matched_amount > abs(bank_amount):
            raise ValueError(
                "Reconciliation allocation exceeds bank transaction remainder"
            )
        if ledger_allocated + matched_amount > abs(ledger_amount):
            raise ValueError("Reconciliation allocation exceeds ledger entry remainder")
