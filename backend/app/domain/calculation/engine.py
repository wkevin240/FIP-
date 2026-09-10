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


@dataclass(frozen=True, slots=True)
class CalculationNode:
    definition: CalculationDefinition
    operation: Operation


class CalculationGraphError(ValueError):
    """Raised when a calculation graph is structurally invalid."""


class CalculationEngine:
    """Small deterministic DAG executor used by all FIP calculation branches.

    The engine deliberately knows nothing about accounting, tax, banking or finance.
    Branch engines supply definitions and typed operations; the kernel resolves
    dependencies, propagates source status and never substitutes missing values.
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

    def execute(
        self,
        context: CalculationContext,
        inputs: Mapping[str, CalculationResult],
    ) -> dict[str, CalculationResult]:
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
            blocked = next(
                (result for result in dependencies if result.status != CalculationStatus.READY),
                None,
            )
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
