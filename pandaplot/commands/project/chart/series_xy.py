"""Shared (x, y) resolution for a chart's data/fit series, and the
materialize-a-result-as-a-new-dataset step both commands need afterward.

Used by any command that needs the live x/y values of whichever series or
fit the user picked -- AnalyzeChartSeriesCommand and (#268)
TransformChartSeriesCommand.
"""

import uuid
from typing import Literal, Optional

import numpy as np
import pandas as pd

from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart, resolve_series_column
from pandaplot.models.state import AppState

SourceKind = Literal["series", "fit"]


def resolve_series_xy(
    app_state: AppState, chart: Chart, source_kind: SourceKind, source_index: int,
    *, coerce_numeric: bool = True,
) -> tuple[pd.Series, pd.Series, str, str]:
    """Return (x, y, x_label, y_label) for chart's source_kind/source_index entry.

    Raises ValueError when the series/fit no longer exists, its series type
    has no meaningful ordered (x, y) curve, or its dataset/columns are
    unavailable.

    `coerce_numeric` (default True) converts both axes to numeric, turning
    anything that doesn't parse into NaN -- appropriate for
    AnalyzeChartSeriesCommand's inherently numeric operations (derivative,
    integral, ...), where a non-numeric axis is meaningless anyway. Pass
    False (TransformChartSeriesCommand does) to keep each axis's original
    dtype -- a transform may leave one axis untouched (categorical,
    datetime, zero-padded-string, ...) and must round-trip it unchanged,
    and a string-valued axis needs to stay a string for an expression like
    `x.str.upper()` to see actual text rather than NaN. Only the
    same-length pairwise-missing-value mask is dtype-agnostic and always
    applied.
    """
    if source_kind == "fit":
        if not (0 <= source_index < len(chart.fit_data)):
            raise ValueError("Selected fit no longer exists.")
        fit = chart.fit_data[source_index]
        dataset = app_state.current_project.find_item(fit.source_dataset_id)
        if not isinstance(dataset, Dataset):
            dataset = None
        x_label = resolve_series_column(dataset, fit.source_x_column_id, fit.source_x_column) or "x"
        x = pd.Series(np.asarray(fit.x_data), dtype="float64")
        y = pd.Series(np.asarray(fit.y_data), dtype="float64")
        return x, y, x_label, fit.label

    if not (0 <= source_index < len(chart.data_series)):
        raise ValueError("Selected series no longer exists.")
    series = chart.data_series[source_index]
    if not SERIES_TYPE_SPECS[series.series_type].supports_curve_analysis:
        # Operation-neutral wording: this resolver backs both analysis
        # (AnalyzeChartSeriesCommand) and transform (TransformChartSeriesCommand)
        # requests, so it can't say "analysis" without being wrong half the time.
        raise ValueError(
            f"'{series.series_type.value}' series aren't supported here "
            "(only line, scatter, and fitted curves have an ordered (x, y) curve)."
        )
    dataset = app_state.current_project.find_item(series.dataset_id)
    if not isinstance(dataset, Dataset) or dataset.data is None:
        raise ValueError("Series dataset is not available.")

    x_name = resolve_series_column(dataset, series.x_column_id, series.x_column)
    y_name = resolve_series_column(dataset, series.y_column_id, series.y_column)
    df = dataset.data
    if y_name is None or y_name not in df.columns:
        raise ValueError("Series y column not found.")

    if x_name and x_name in df.columns:
        x_full = df[x_name]
        x_label = x_name
    else:
        x_full = pd.Series(np.arange(len(df)), index=df.index)
        x_label = "index"
    y_full = df[y_name]

    mask = ~(pd.isna(x_full) | pd.isna(y_full))
    x = x_full[mask].reset_index(drop=True)
    y = y_full[mask].reset_index(drop=True)
    if coerce_numeric:
        x = pd.to_numeric(x, errors="coerce")
        y = pd.to_numeric(y, errors="coerce")
    label = series.label or y_name
    return x, y, x_label, label


def unique_sibling_name(project, folder_id: Optional[str], name: str) -> str:
    """Return `name`, or `name (N)` for the smallest N >= 2 not already used
    by a sibling in `folder_id` (or the project root when None).

    Used by both AnalyzeChartSeriesCommand and TransformChartSeriesCommand
    so re-running the same analysis/transform (or two that land on the
    same default name) doesn't produce two indistinguishable datasets
    sitting side by side in the project explorer.
    """
    parent = project.find_item(folder_id) if folder_id else None
    siblings = parent.get_items() if parent is not None else project.get_root_items()
    existing_names = {item.name for item in siblings}
    if name not in existing_names:
        return name
    counter = 2
    candidate = f"{name} ({counter})"
    while candidate in existing_names:
        counter += 1
        candidate = f"{name} ({counter})"
    return candidate


def create_result_dataset(
    app_state: AppState, folder_id: Optional[str], name: str, results_df: pd.DataFrame,
) -> Dataset:
    """Materialize `results_df` as a new, uniquely-named Dataset in the
    project, under `folder_id`, and announce it via the generic
    ProjectEvents.PROJECT_ITEM_ADDED (not the narrower, legacy
    DatasetEvents.DATASET_CREATED -- see import_data_command.py's
    TODO(#219)) -- what the project explorer tree and other
    item-type-agnostic listeners actually refresh on.

    Shared by AnalyzeChartSeriesCommand.execute() and
    TransformChartSeriesCommand.execute(): both compute a result
    DataFrame from a chart series, then need this exact same
    materialize-and-announce step.
    """
    project = app_state.current_project
    unique_name = unique_sibling_name(project, folder_id, name)
    dataset = Dataset(id=str(uuid.uuid4()), name=unique_name, data=results_df, source_file=None)
    project.add_item(dataset, parent_id=folder_id)
    # Report folder_id as None (the existing "no folder" convention) unless
    # it still resolves to a real folder: project.add_item() silently
    # places the dataset at the project root if folder_id no longer
    # resolves (e.g. the folder was deleted between an undo and a redo) --
    # note the root itself has a real internal id (dataset.parent_id, not
    # folder_id, would report *that* id even when no folder was asked for
    # at all), so re-checking the originally-requested folder_id is what
    # correctly collapses both "no folder requested" and "folder now gone"
    # to the same None the caller asked for.
    reported_folder_id = folder_id if folder_id is not None and project.find_item(folder_id) is not None else None
    app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
        "project": project,
        "item_id": dataset.id,
        "item_type": "dataset",
        "item_name": unique_name,
        "item": dataset,
        "folder_id": reported_folder_id,
    })
    return dataset


def remove_result_dataset(app_state: AppState, dataset_id: str) -> None:
    """Undo half of create_result_dataset(): remove `dataset_id` from the
    project (a no-op if it's already gone) and announce the removal via
    the generic ProjectEvents.PROJECT_ITEM_REMOVED.
    """
    project = app_state.current_project
    dataset = project.find_item(dataset_id)
    if dataset is None:
        return
    dataset_name = dataset.name
    project.remove_item(dataset)
    app_state.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
        "project": project,
        "item_id": dataset_id,
        "item_type": "dataset",
        "item_name": dataset_name,
    })
