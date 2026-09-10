from collections.abc import Callable, Mapping
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation

from app.domain.calculation.contracts import (
    CalculationContext,
    CalculationDefinition,
    CalculationResult,
    CalculationStatus,
)


Operation = Callable[[tuple[Decimal, ...]], Decimal]

_STATUS_PRIORITY = {
    CalculationStatus.READY: 0,
    CalculationStatus.INCOMPLETE: 1,
    CalculationStatus.NOT_READY: 2,
    CalculationStatus.ERROR: 3,
}


@dataclass(frozen=True, slots=True)
class CalculationNode:
    definition: CalculationDefinition
    operation: Operation


class CalculationGraphError(ValueError):
    """Raised when a calculation graph is structurally invalid."""


class CalculationContextError(ValueError):
    """Raised when inputs do not belong to the execution context."""


class CalculationEngine:
    """Small deterministic DAG executor used by all FIP calculation branches.

    The engine deliberately knows nothing about accounting, tax, banking or finance.
    Branch engines supply definitions and typed operations; the kernel resolves
    dependencies, propagates the worst dependency status and never substitutes
    missing values.
    """

    def __init__(self, nodes: tuple[CalculationNode, ...]) -> None:
        self._nodes = {node.definition.code: node for node in nodes}
        if len(self._nodes) != len(nodes):
            raise CalculationGraphError("calculation node codes must be unique")
        self._validate_dependencies()

    def _validate_dependencies(self) -> None:
        for node in self._nodes.values():
            unknown = set(node.definition.dependencies) - self._nodes.keys()
            if unknown:
                raise CalculationGraphError(
                    f"{node.definition.code} depends on unknown calculations: "
                    + ", ".join(sorted(unknown))
                )
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(code: str) -> None:
            if code in visiting:
                raise CalculationGraphError(f"calculation cycle detected at {code}")
            if code in visited:
                return
            visiting.add(code)
            for dependency in self._nodes[code].definition.dependencies:
                visit(dependency)
            visiting.remove(code)
            visited.add(code)

        for code in self._nodes:
            visit(code)

    @staticmethod
    def _validate_context(
        context: CalculationContext,
        inputs: Mapping[str, CalculationResult],
    ) -> None:
        for code, result in inputs.items():
            source_context = result.context
            if source_context.organization_id != context.organization_id:
                raise CalculationContextError(
                    f"input {code} belongs to organization "
                    f"{source_context.organization_id}, expected {context.organization_id}"
                )
            if (
                source_context.period_start != context.period_start
                or source_context.period_end != context.period_end
            ):
                raise CalculationContextError(
                    f"input {code} belongs to period "
                    f"{source_context.period_start}..{source_context.period_end}, "
                    f"expected {context.period_start}..{context.period_end}"
                )
            if (
                source_context.dimension_id != context.dimension_id
                or source_context.dimension_value_id != context.dimension_value_id
            ):
                raise CalculationContextError(
                    f"input {code} has an incompatible analytical dimension context"
                )
            if source_context.currency != context.currency:
                raise CalculationContextError(
                    f"input {code} has currency {source_context.currency!r}, "
                    f"expected {context.currency!r}"
                )
            if source_context.rule_version != context.rule_version:
                raise CalculationContextError(
                    f"input {code} uses rule version {source_context.rule_version!r}, "
                    f"expected {context.rule_version!r}"
                )

    def execute(
        self,
        context: CalculationContext,
        inputs: Mapping[str, CalculationResult],
    ) -> dict[str, CalculationResult]:
        self._validate_context(context, inputs)
        results = dict(inputs)
        for code in self._topological_order():
            if code in results:
                continue
            node = self._nodes[code]
            dependencies = tuple(results[key] for key in node.definition.dependencies)
            sources = tuple(
                source
                for result in dependencies
                for source in result.sources
            )
            blocked = self._worst_dependency(dependencies)
            if blocked is not None:
                results[code] = CalculationResult(
                    definition=node.definition,
                    context=context,
                    status=blocked.status,
                    reason=f"Dependency {blocked.definition.code}: {blocked.reason}",
                    sources=sources,
                )
                continue
            try:
                values = tuple(result.value for result in dependencies)
                if any(value is None for value in values):
                    raise CalculationGraphError("READY dependency has no value")
                value = node.operation(values)  # type: ignore[arg-type]
                if not isinstance(value, Decimal):
                    raise TypeError("calculation operations must return Decimal")
            except (ArithmeticError, InvalidOperation, DivisionByZero) as exc:
                results[code] = CalculationResult.error(
                    node.definition, context, f"{type(exc).__name__}: {exc}", sources=sources
                )
                continue
            except (TypeError, ValueError) as exc:
                results[code] = CalculationResult.error(
                    node.definition, context, f"{type(exc).__name__}: {exc}", sources=sources
                )
                continue
            results[code] = CalculationResult.ready(
                node.definition, context, value, sources=sources
            )
        return results

    @staticmethod
    def _worst_dependency(
        dependencies: tuple[CalculationResult, ...],
    ) -> CalculationResult | None:
        blocked = [
            result
            for result in dependencies
            if result.status is not CalculationStatus.READY
        ]
        if not blocked:
            return None
        return max(blocked, key=lambda result: _STATUS_PRIORITY[result.status])

    def _topological_order(self) -> tuple[str, ...]:
        order: list[str] = []
        visited: set[str] = set()

        def visit(code: str) -> None:
            if code in visited:
                return
            for dependency in self._nodes[code].definition.dependencies:
                visit(dependency)
            visited.add(code)
            order.append(code)

        for code in self._nodes:
            visit(code)
        return tuple(order)
