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
