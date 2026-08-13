from enum import Enum


class StockUnit(str, Enum):
    UNIT = "UNIT"
    KILOGRAM = "KILOGRAM"
    LITER = "LITER"
    METER = "METER"


class StockMovementType(str, Enum):
    RECEIPT = "RECEIPT"
    ISSUE = "ISSUE"
    ADJUSTMENT_IN = "ADJUSTMENT_IN"
    ADJUSTMENT_OUT = "ADJUSTMENT_OUT"
    TRANSFER_IN = "TRANSFER_IN"
    TRANSFER_OUT = "TRANSFER_OUT"
