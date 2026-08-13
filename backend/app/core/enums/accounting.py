from enum import Enum


class FiscalYearStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class FiscalPeriodStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"


class JournalType(str, Enum):
    GENERAL = "GENERAL"
    SALES = "SALES"
    PURCHASES = "PURCHASES"
    CASH = "CASH"
    BANK = "BANK"
    MISCELLANEOUS = "MISCELLANEOUS"


class JournalEntryStatus(str, Enum):
    DRAFT = "DRAFT"
    POSTED = "POSTED"
    VOIDED = "VOIDED"


class VATDirection(str, Enum):
    INPUT = "INPUT"
    OUTPUT = "OUTPUT"
