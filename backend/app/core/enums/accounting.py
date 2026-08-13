from enum import Enum

class FiscalYearStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"

class FiscalPeriodStatus(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    LOCKED = "LOCKED"
