from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Mapping


class CalculationStatus(str, Enum):
    READY = "READY"
    NOT_READY = "NOT_READY"
    INCOMPLETE = "INCOMPLETE"
    ERROR = "ERROR"


@dataclass(frozen=True, slots=True)
class CalculationContext:
    """Immutable execution context shared by deterministic FIP calculation engines."""

    organization_id: str
    period_start: date
    period_end: date
    currency: str | None = None
    dimension_id: str | None = None
    dimension_value_id: str | None = None
    rule_version: str = "1"

    def __post_init__(self) -> None:
        if not self.organization_id:
            raise ValueError("organization_id is required")
        if self.period_start > self.period_end:
            raise ValueError("period_start must be before or equal to period_end")
        if self.dimension_value_id and not self.dimension_id:
            raise ValueError("dimension_id is required with dimension_value_id")
        if self.currency is not None and not self.currency.strip():
            raise ValueError("currency cannot be blank")
        if not self.rule_version.strip():
            raise ValueError("rule_version cannot be blank")


@dataclass(frozen=True, slots=True)
class SourceReference:
    """Traceable reference to an input record used by a calculation."""

    record_type: str
    record_id: str
    module: str

    def __post_init__(self) -> None:
        if not self.record_type or not self.record_id or not self.module:
            raise ValueError("source references require type, id and module")


@dataclass(frozen=True, slots=True)
class CalculationDefinition:
    """Versioned, explainable definition owned by a business calculation engine."""

    code: str
    formula: str
    dependencies: tuple[str, ...] = ()
    rule_version: str = "1"

    def __post_init__(self) -> None:
        if not self.code.strip():
            raise ValueError("calculation code is required")
        if not self.formula.strip():
            raise ValueError("calculation formula is required")
        if not self.rule_version.strip():
            raise ValueError("rule_version is required")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("calculation dependencies must be unique")


@dataclass(frozen=True, slots=True)
class CalculationResult:
    """Immutable result with provenance and an explicit execution status."""

    definition: CalculationDefinition
    context: CalculationContext
    status: CalculationStatus
    value: Decimal | None = None
    reason: str | None = None
    sources: tuple[SourceReference, ...] = ()
    metadata: Mapping[str, str] = field(default_factory=dict)
    calculated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        if self.status == CalculationStatus.READY and self.value is None:
            raise ValueError("READY calculation results require a value")
        if self.status != CalculationStatus.READY and self.value is not None:
            raise ValueError("non-READY calculation results cannot expose a value")
        if self.status != CalculationStatus.READY and not self.reason:
            raise ValueError("non-READY calculation results require a reason")
        if self.calculated_at.tzinfo is None:
            raise ValueError("calculated_at must be timezone-aware")

    @classmethod
    def ready(
        cls,
        definition: CalculationDefinition,
        context: CalculationContext,
        value: Decimal,
        *,
        sources: tuple[SourceReference, ...] = (),
        metadata: Mapping[str, str] | None = None,
    ) -> "CalculationResult":
        if not isinstance(value, Decimal):
            raise TypeError("financial calculation values must use Decimal")
        return cls(
            definition=definition,
            context=context,
            status=CalculationStatus.READY,
            value=value,
            sources=sources,
            metadata=metadata or {},
        )

    @classmethod
    def not_ready(
        cls,
        definition: CalculationDefinition,
        context: CalculationContext,
        reason: str,
        *,
        sources: tuple[SourceReference, ...] = (),
    ) -> "CalculationResult":
        if not reason.strip():
            raise ValueError("reason is required")
        return cls(
            definition=definition,
            context=context,
            status=CalculationStatus.NOT_READY,
            reason=reason,
            sources=sources,
        )

    @classmethod
    def incomplete(
        cls,
        definition: CalculationDefinition,
        context: CalculationContext,
        reason: str,
        *,
        sources: tuple[SourceReference, ...] = (),
    ) -> "CalculationResult":
        if not reason.strip():
            raise ValueError("reason is required")
        return cls(
            definition=definition,
            context=context,
            status=CalculationStatus.INCOMPLETE,
            reason=reason,
            sources=sources,
        )

    @classmethod
    def error(
        cls,
        definition: CalculationDefinition,
        context: CalculationContext,
        reason: str,
        *,
        sources: tuple[SourceReference, ...] = (),
    ) -> "CalculationResult":
        if not reason.strip():
            raise ValueError("reason is required")
        return cls(
            definition=definition,
            context=context,
            status=CalculationStatus.ERROR,
            reason=reason,
            sources=sources,
        )
