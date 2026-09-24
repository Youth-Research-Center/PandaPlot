"""
Helpers for emitting the dataset events that keep the data-tab table and any
column-source selectors (analysis/transform/fit panels, chart data tab) in sync
after a command adds or overwrites columns.

The table model (:class:`PandasTableModel`) expects structured event payloads:
newly added columns must be announced with :class:`DatasetColumnsAddedData` so
it can insert them, while columns overwritten in place must be announced with
:class:`DatasetDataChangedData` so it repaints the affected cells. Panels that
show column lists key off the ``dataset_id`` in the same payloads.
"""


import pandas as pd

from pandaplot.models.events.event_data import (
    DatasetColumnsAddedData,
    DatasetDataChangedData,
)
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.state.app_context import AppContext


def emit_columns_changed(
    app_context: AppContext,
    dataset_id: str,
    df: pd.DataFrame,
    added_columns: list[str],
    replaced_columns: list[str],
) -> None:
    """Emit the appropriate events for columns added and/or overwritten.

    Args:
        app_context: Application context (used to reach the event bus).
        dataset_id: Target dataset id.
        df: The dataset's dataframe *after* the change (used to resolve the
            current column positions).
        added_columns: Names of columns that did not exist before.
        replaced_columns: Names of pre-existing columns whose values changed.
    """
    event_bus = app_context.get_app_state().event_bus

    if added_columns:
        positions = sorted(int(df.columns.get_loc(name)) for name in added_columns)
        event_bus.emit(
            DatasetOperationEvents.DATASET_COLUMN_ADDED,
            DatasetColumnsAddedData(
                dataset_id=dataset_id,
                column_positions=positions,
            ).to_dict(),
        )

    if replaced_columns:
        last_row = max(len(df) - 1, 0)
        for name in replaced_columns:
            col = int(df.columns.get_loc(name))
            event_bus.emit(
                DatasetEvents.DATASET_DATA_CHANGED,
                DatasetDataChangedData(
                    dataset_id=dataset_id,
                    start_index=(0, col),
                    end_index=(last_row, col),
                ).to_dict(),
            )
