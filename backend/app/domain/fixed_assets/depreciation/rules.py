from calendar import monthrange
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

CENT = Decimal("0.01")
HUNDRED = Decimal(100)
TWELVE = Decimal(12)


@dataclass(frozen=True)
class DepreciationScheduleCalculation:
    sequence_number: int
    scheduled_date: date
    opening_net_book_value: Decimal
    depreciation_amount: Decimal
    accumulated_depreciation: Decimal
    closing_net_book_value: Decimal


class DepreciationRules:
    @staticmethod
    def money(value: Decimal) -> Decimal:
        return value.quantize(CENT, rounding=ROUND_HALF_UP)

    @classmethod
    def build_schedule(
        cls,
        acquisition_cost: Decimal,
        residual_value: Decimal,
        start_date: date,
        useful_life_months: int,
        method: str,
        declining_rate: Decimal | None = None,
    ) -> list[DepreciationScheduleCalculation]:
        cls._validate_inputs(
            acquisition_cost,
            residual_value,
            start_date,
            useful_life_months,
            method,
            declining_rate,
        )
        depreciable_base = cls.money(acquisition_cost - residual_value)
        if depreciable_base == Decimal("0.00"):
            return []
        end_date = cls._add_months(start_date, useful_life_months) - timedelta(days=1)
        segments = cls._monthly_segments(start_date, end_date)
        opening_value = cls.money(acquisition_cost)
        accumulated = Decimal("0.00")
        calculations: list[DepreciationScheduleCalculation] = []
        for sequence_number, (segment_start, segment_end) in enumerate(
            segments, start=1
        ):
            is_final_segment = sequence_number == len(segments)
            remaining = cls.money(depreciable_base - accumulated)
            if is_final_segment:
                depreciation_amount = remaining
            elif method == "STRAIGHT_LINE":
                month_fraction = cls._month_fraction(segment_start, segment_end)
                depreciation_amount = cls.money(
                    (depreciable_base / Decimal(useful_life_months)) * month_fraction
                )
                depreciation_amount = min(depreciation_amount, remaining)
            else:
                assert declining_rate is not None
                month_fraction = cls._month_fraction(segment_start, segment_end)
                depreciation_amount = cls.money(
                    opening_value * (declining_rate / HUNDRED) / TWELVE * month_fraction
                )
                depreciation_amount = min(depreciation_amount, remaining)
            accumulated = cls.money(accumulated + depreciation_amount)
            closing_value = cls.money(acquisition_cost - accumulated)
            if closing_value < residual_value:
                raise ValueError("Depreciation schedule cannot go below residual value")
            calculations.append(
                DepreciationScheduleCalculation(
                    sequence_number=sequence_number,
                    scheduled_date=segment_end,
                    opening_net_book_value=opening_value,
                    depreciation_amount=depreciation_amount,
                    accumulated_depreciation=accumulated,
                    closing_net_book_value=closing_value,
                )
            )
            opening_value = closing_value
        if accumulated != depreciable_base:
            raise ValueError(
                "Depreciation schedule must fully allocate depreciable base"
            )
        if calculations[-1].closing_net_book_value != cls.money(residual_value):
            raise ValueError("Depreciation schedule must end at residual value")
        return calculations

    @staticmethod
    def calculate_disposal(
        acquisition_cost: Decimal,
        accumulated_depreciation: Decimal,
        proceeds: Decimal,
    ) -> tuple[Decimal, Decimal, Decimal]:
        if acquisition_cost < 0 or accumulated_depreciation < 0 or proceeds < 0:
            raise ValueError("Disposal amounts cannot be negative")
        if accumulated_depreciation > acquisition_cost:
            raise ValueError("Accumulated depreciation cannot exceed asset cost")
        net_book_value = DepreciationRules.money(
            acquisition_cost - accumulated_depreciation
        )
        gain_amount = DepreciationRules.money(
            max(Decimal("0.00"), proceeds - net_book_value)
        )
        loss_amount = DepreciationRules.money(
            max(Decimal("0.00"), net_book_value - proceeds)
        )
        return net_book_value, gain_amount, loss_amount

    @staticmethod
    def _validate_inputs(
        acquisition_cost: Decimal,
        residual_value: Decimal,
        start_date: date,
        useful_life_months: int,
        method: str,
        declining_rate: Decimal | None,
    ) -> None:
        if acquisition_cost < 0:
            raise ValueError("Acquisition cost cannot be negative")
        if residual_value < 0 or residual_value > acquisition_cost:
            raise ValueError("Residual value must be between zero and acquisition cost")
        if not isinstance(start_date, date):
            raise TypeError("Depreciation start date must be a date")
        if useful_life_months <= 0:
            raise ValueError("Useful life must be strictly positive")
        if method not in {"STRAIGHT_LINE", "DECLINING_BALANCE"}:
            raise ValueError("Unsupported depreciation method")
        if method == "DECLINING_BALANCE" and (
            declining_rate is None or not Decimal(0) < declining_rate <= HUNDRED
        ):
            raise ValueError(
                "Declining balance method requires a rate between zero and 100"
            )

    @staticmethod
    def _add_months(value: date, months: int) -> date:
        month_index = value.month - 1 + months
        year = value.year + month_index // 12
        month = month_index % 12 + 1
        day = min(value.day, monthrange(year, month)[1])
        return date(year, month, day)

    @staticmethod
    def _monthly_segments(start_date: date, end_date: date) -> list[tuple[date, date]]:
        if end_date < start_date:
            raise ValueError("Depreciation end date cannot precede its start date")
        segments: list[tuple[date, date]] = []
        cursor = start_date
        while cursor <= end_date:
            last_day = date(
                cursor.year, cursor.month, monthrange(cursor.year, cursor.month)[1]
            )
            segment_end = min(last_day, end_date)
            segments.append((cursor, segment_end))
            cursor = segment_end + timedelta(days=1)
        return segments

    @staticmethod
    def _month_fraction(segment_start: date, segment_end: date) -> Decimal:
        days_in_segment = Decimal((segment_end - segment_start).days + 1)
        days_in_month = Decimal(monthrange(segment_start.year, segment_start.month)[1])
        return days_in_segment / days_in_month
