"""Formula-column evaluation and dependency ordering (issue #154).

Two concerns live here, both shared by the one-shot transform path
(:class:`~pandaplot.commands.project.dataset.transform_column_command.TransformColumnCommand`)
and the live-recompute path
(:class:`~pandaplot.services.transform.formula_recompute_manager.FormulaRecomputeManager`):

* :func:`evaluate_formula` -- turning an expression plus a transform type into a
  Series, so a formula column recomputes with exactly the semantics the
  transform that created it used.
* :func:`resolve_recompute_order` -- one topological sort used *both* to reject a
  circular formula at creation time and to order a recompute cascade, so the two
  can never disagree about what a cycle is.
"""

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import pandas as pd

from pandaplot.services.transform import expression_engine


class CircularFormulaDependencyError(ValueError):
    """Raised when formula columns would depend on each other in a cycle."""

    def __init__(self, cycle: Sequence[str]):
        self.cycle = list(cycle)
        super().__init__("Circular formula dependency: " + " -> ".join(self.cycle))


def build_formula_globals() -> dict[str, Any]:
    """Safe globals for a formula/transform expression.

    The shared transform environment plus the ``math`` module, which transform
    expressions have historically been able to reach.
    """
    safe_globals = expression_engine.build_safe_globals()
    safe_globals["math"] = math
    return safe_globals


def evaluate_formula(
    df: pd.DataFrame,
    *,
    expression: str,
    transform_type: str,
    source_columns: Sequence[str],
    safe_globals: dict[str, Any] | None = None,
) -> pd.Series:
    """Evaluate a transform/formula expression against ``df``.

    Args:
        df: The dataframe to read source columns from.
        expression: The expression to evaluate.
        transform_type: "column", "row" or "multi_column".
        source_columns: Source column *names* (already resolved from ids).
        safe_globals: Optional pre-built globals, to avoid rebuilding them per
            column when recomputing a cascade.

    Raises:
        ValueError: For an unknown transform type or missing source column.
        Exception: Whatever the expression itself raises -- callers are the
            command/service boundary that turns that into a user-facing error.
    """
    if safe_globals is None:
        safe_globals = build_formula_globals()

    missing = [name for name in source_columns if name not in df.columns]
    if missing:
        raise ValueError(f"Source columns not found: {missing}")

    if transform_type == "column":
        return _evaluate_column(df, expression, source_columns, safe_globals)
    if transform_type == "row":
        return _evaluate_row(df, expression, safe_globals)
    if transform_type == "multi_column":
        return _evaluate_multi_column(df, expression, source_columns, safe_globals)
    raise ValueError(f"Unknown transform type: {transform_type}")


def _as_series(result: Any, index: pd.Index) -> pd.Series:
    if isinstance(result, pd.Series):
        return result
    if pd.api.types.is_scalar(result):
        return pd.Series([result] * len(index), index=index)
    return pd.Series(result, index=index)


def _evaluate_column(df: pd.DataFrame, expression: str, source_columns: Sequence[str],
                     safe_globals: dict[str, Any]) -> pd.Series:
    if not source_columns:
        raise ValueError("A column transform needs a source column")
    source_column = source_columns[0]
    source_data = df[source_column]
    local_vars = {
        "value": source_data,
        "x": source_data,
        "column": source_data,
        "data": source_data,
        # Look up the column by its own real name (#203), e.g. cols["t"] for a
        # column named "t" -- a dict subscript rather than binding "t" as a
        # bare local variable, so it works for ANY column name (spaces,
        # leading digits, ...) and can never shadow a Python keyword or one of
        # safe_globals' bare names (sqrt/log/mean/std/...) the way a
        # same-named bound identifier would.
        "cols": {source_column: source_data},
    }
    result = expression_engine.evaluate_expression(expression, local_vars, safe_globals)
    return _as_series(result, source_data.index)


def _evaluate_row(df: pd.DataFrame, expression: str, safe_globals: dict[str, Any]) -> pd.Series:
    def row_transform(row):
        return expression_engine.evaluate_expression(expression, {"row": row, "r": row}, safe_globals)

    return df.apply(row_transform, axis=1)


def _evaluate_multi_column(df: pd.DataFrame, expression: str, source_columns: Sequence[str],
                           safe_globals: dict[str, Any]) -> pd.Series:
    selected_columns = df[list(source_columns)]
    local_vars = {
        "cols": selected_columns,
        "columns": selected_columns,
        "data": selected_columns,
    }
    result = expression_engine.evaluate_expression(expression, local_vars, safe_globals)
    return _as_series(result, df.index)


# ----------------------------------------------------------------------
# Dependency ordering
# ----------------------------------------------------------------------
def resolve_recompute_order(
    nodes: Iterable[str], dependencies: Mapping[str, Sequence[str]],
) -> list[str]:
    """Order ``nodes`` so every node follows the nodes it depends on.

    ``dependencies`` maps a node to the ids it reads from; ids that aren't
    themselves in ``nodes`` are plain (non-formula) columns and are simply
    ignored as graph leaves.

    Raises:
        CircularFormulaDependencyError: If the nodes form a cycle. A node that
            depends on itself counts as a cycle of length one.
    """
    node_set = set(nodes)
    order: list[str] = []
    visited: set[str] = set()
    on_stack: list[str] = []
    on_stack_set: set[str] = set()

    def visit(node: str) -> None:
        if node in visited:
            return
        if node in on_stack_set:
            cycle_start = on_stack.index(node)
            raise CircularFormulaDependencyError([*on_stack[cycle_start:], node])
        on_stack.append(node)
        on_stack_set.add(node)
        for dependency in dependencies.get(node, ()):
            if dependency in node_set:
                visit(dependency)
        on_stack.pop()
        on_stack_set.discard(node)
        visited.add(node)
        order.append(node)

    # Deterministic order for nodes that don't constrain each other, so a
    # cascade (and any error message) is reproducible.
    for node in sorted(node_set):
        visit(node)
    return order


def find_circular_dependency(dependencies: Mapping[str, Sequence[str]]) -> list[str] | None:
    """Return the cycle among ``dependencies``' keys, or None if there is none."""
    try:
        resolve_recompute_order(dependencies.keys(), dependencies)
    except CircularFormulaDependencyError as e:
        return e.cycle
    return None
