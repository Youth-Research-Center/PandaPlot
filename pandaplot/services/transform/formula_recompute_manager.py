"""Live recompute of formula columns (issue #154).

Registered once at app-context build time, this manager listens on the event
bus for "a dataset's data changed" events and recomputes the *live* formula
columns that transitively depend on whatever changed.

Doing it here rather than inside each command matters for two reasons:

* Every command that mutates a dataset already announces itself on the bus
  (EditCommand, EditBatchCommand, AddRowsCommand, PreprocessColumnCommand, ...),
  so live recompute works for all of them without touching any of them -- and
  can't be forgotten by the next command someone adds.
* Undo/redo needs no special casing: ``EditCommand.undo()`` restores the old
  value and emits the same event, so the dependent formula column recomputes
  back to its old value on the way out too.
"""

import logging
from typing import Any

import pandas as pd

from pandaplot.models.events.event_bus import EventBus
from pandaplot.models.events.event_data import DatasetDataChangedData
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_state import AppState
from pandaplot.services.transform import formula_engine


class FormulaRecomputeManager:
    """Recomputes live formula columns when their sources change."""

    def __init__(self, event_bus: EventBus, app_state: AppState):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._event_bus = event_bus
        self._app_state = app_state
        # Dataset ids currently being recomputed. The recompute writes to the
        # dataset and emits data-changed events of its own; without this the
        # listener would immediately process its own emissions and cascade
        # forever.
        self._recomputing: set[str] = set()

        for event_type in (
            DatasetEvents.DATASET_DATA_CHANGED,
            DatasetOperationEvents.DATASET_COLUMN_ADDED,
            DatasetOperationEvents.DATASET_COLUMN_REMOVED,
            DatasetOperationEvents.DATASET_ROW_ADDED,
            DatasetOperationEvents.DATASET_ROW_REMOVED,
        ):
            event_bus.subscribe(event_type, self._on_dataset_changed)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def _on_dataset_changed(self, event_data: dict[str, Any]) -> None:
        dataset_id = (event_data or {}).get("dataset_id")
        if not dataset_id or dataset_id in self._recomputing:
            return

        dataset = self._find_dataset(dataset_id)
        if dataset is None or dataset.data is None or not dataset.formula_columns:
            return

        changed_ids = self._changed_column_ids(dataset, event_data)
        try:
            self._recomputing.add(dataset_id)
            self.recompute(dataset, changed_column_ids=changed_ids)
        finally:
            self._recomputing.discard(dataset_id)

    def _find_dataset(self, dataset_id: str) -> Dataset | None:
        project = self._app_state.current_project
        if project is None:
            return None
        item = project.find_item(dataset_id)
        return item if isinstance(item, Dataset) else None

    def _changed_column_ids(self, dataset: Dataset, event_data: dict[str, Any]) -> set[str] | None:
        """Column ids the event says changed, or None for "assume everything".

        Row events and column removals carry no usable column identity (a
        removal's positions already refer to a layout that no longer exists),
        so those fall back to recomputing every live formula column.
        """
        columns = list(dataset.column_ids.keys())

        start = event_data.get("start_index")
        end = event_data.get("end_index")
        if start is not None and end is not None:
            first, last = int(start[1]), int(end[1])
            return {columns[i] for i in range(first, last + 1) if 0 <= i < len(columns)}

        positions = event_data.get("column_positions")
        if positions:
            resolved = {columns[i] for i in positions if 0 <= i < len(columns)}
            # A removal's positions are stale -- if they don't all resolve,
            # fall back to recomputing everything live.
            return resolved if len(resolved) == len(positions) else None

        return None

    # ------------------------------------------------------------------
    # Recompute
    # ------------------------------------------------------------------
    def recompute(self, dataset: Dataset, changed_column_ids: set[str] | None = None) -> list[str]:
        """Recompute the live formula columns affected by a change.

        Args:
            dataset: The dataset to recompute in place.
            changed_column_ids: Ids of the columns that changed, or None to
                recompute every live formula column.

        Returns:
            The names of the columns that were recomputed, in cascade order.
        """
        order = self._cascade_order(dataset, changed_column_ids)
        if not order:
            return []

        df = dataset.data.copy()
        safe_globals = formula_engine.build_formula_globals()
        recomputed: list[str] = []

        for column_id in order:
            spec = dataset.formula_column(column_id)
            name = dataset.column_name(column_id)
            if spec is None or name is None or name not in df.columns:
                continue
            source_names = [dataset.column_name(cid) for cid in spec.source_column_ids]
            if any(source is None for source in source_names):
                self._logger.warning(
                    "Skipping live recompute of '%s': a source column no longer exists", name,
                )
                continue
            try:
                series = formula_engine.evaluate_formula(
                    df,
                    expression=spec.expression,
                    transform_type=spec.transform_type,
                    source_columns=[str(source) for source in source_names],
                    safe_globals=safe_globals,
                )
            except Exception as e:  # noqa: BLE001 -- a user-authored expression can raise anything; one bad formula must not abort the rest of the cascade
                self._logger.error("Live recompute of column '%s' failed: %s", name, e)
                continue
            df[name] = series
            recomputed.append(str(name))

        if not recomputed:
            return []

        dataset.set_data(df)
        self._emit_recomputed(dataset, df, recomputed)
        return recomputed

    def _cascade_order(self, dataset: Dataset, changed_column_ids: set[str] | None) -> list[str]:
        """Live formula column ids to recompute, dependencies first.

        Only *live* columns participate: a plain formula column is static data
        until its transform is re-run by hand, so nothing propagates through
        it either.
        """
        live = {cid: spec for cid, spec in dataset.formula_columns.items() if spec.live}
        if not live:
            return []

        dependencies = {cid: spec.source_column_ids for cid, spec in live.items()}
        try:
            topological = formula_engine.resolve_recompute_order(live.keys(), dependencies)
        except formula_engine.CircularFormulaDependencyError as e:
            # Cycles are rejected when a formula is created, so reaching this
            # means a hand-edited or otherwise corrupted project file.
            self._logger.error("Refusing to recompute dataset '%s': %s", dataset.id, e)
            return []

        if changed_column_ids is None:
            return topological

        # A column that was itself just edited stays as edited -- it's the
        # input to this cascade, not an output of it. Only what reads from it
        # (transitively) is recomputed.
        dirty = set(changed_column_ids)
        order: list[str] = []
        for cid in topological:
            if cid in dirty:
                continue
            if any(source in dirty for source in dependencies[cid]):
                dirty.add(cid)
                order.append(cid)
        return order

    def _emit_recomputed(self, dataset: Dataset, df: pd.DataFrame, columns: list[str]) -> None:
        last_row = max(len(df) - 1, 0)
        for name in columns:
            col = int(df.columns.get_loc(name))
            self._event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED,
                DatasetDataChangedData(
                    dataset_id=dataset.id,
                    start_index=(0, col),
                    end_index=(last_row, col),
                ).to_dict(),
            )
