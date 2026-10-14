"""Formula-column specification (issue #154).

A formula column is a dataset column whose values are *defined* by a transform
expression over other columns rather than being static data. The spec below is
what a :class:`~pandaplot.models.project.items.dataset.Dataset` stores per
formula column so the expression survives a save/load cycle and can be
re-evaluated later.

Sources are referenced by stable column *id* rather than by name: a column's
name is user-editable, and a rename must not silently detach a dependent
formula (see Dataset.column_ids / Dataset.rename_column).
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FormulaColumnSpec:
    """How to recompute one formula column.

    Attributes:
        expression: The transform expression, in the same dialect the
            Transform panel already uses (``x``/``value``/``cols[...]``/``row``).
        transform_type: One of "column", "row", "multi_column" -- selects which
            variables the expression is evaluated against.
        source_column_ids: Stable ids of the columns the expression reads.
        live: When True the column is recomputed automatically whenever one of
            its sources changes. Off by default: a plain formula column keeps
            its last computed values until the transform is re-run manually.
        source_aliases: The names those columns had when the expression was
            written, parallel to ``source_column_ids``. The expression refers
            to its sources by these names (``cols["a"]``), so they stay valid
            after a source column is renamed. Empty means "use the current
            names" (specs saved before aliases existed).
    """

    expression: str
    transform_type: str = "column"
    source_column_ids: list[str] = field(default_factory=list)
    live: bool = False
    source_aliases: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "expression": self.expression,
            "transform_type": self.transform_type,
            "source_column_ids": list(self.source_column_ids),
            "live": self.live,
            "source_aliases": list(self.source_aliases),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormulaColumnSpec":
        return cls(
            expression=data.get("expression", ""),
            transform_type=data.get("transform_type", "column"),
            source_column_ids=list(data.get("source_column_ids") or []),
            live=bool(data.get("live", False)),
            source_aliases=[str(alias) for alias in data.get("source_aliases") or []],
        )
