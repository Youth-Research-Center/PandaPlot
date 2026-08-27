from collections import OrderedDict
from dataclasses import dataclass
from typing import List, Union, override

from pandaplot.commands.base_command import Command
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.series_style.vector import VectorSeriesStyle
from pandaplot.models.events.event_data import DatasetColumnsAddedData, DatasetColumnsRemovedData
from pandaplot.models.events.event_types import ChartEvents, DatasetOperationEvents
from pandaplot.models.project.items import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


@dataclass
class ChartReferenceMatch:
    chart: Chart
    series_indices: List[int]
    fit_indices: List[int]
    error_only_indices: List[int]


def _error_field_targets(series):
    """Return (container, id_field, name_field) triples for a series'
    optional error/magnitude column references -- these now live on
    ``series.style.error_bars`` (x/y error + minus pairs) and, for a
    VECTOR series, ``series.style.magnitude_column*`` directly, rather
    than flatly on ``series`` itself."""
    targets = []
    error_bars = getattr(series.style, "error_bars", None)
    if error_bars is not None:
        targets.extend([
            (error_bars, "x_error_column_id", "x_error_column"),
            (error_bars, "y_error_column_id", "y_error_column"),
            (error_bars, "x_error_minus_column_id", "x_error_minus_column"),
            (error_bars, "y_error_minus_column_id", "y_error_minus_column"),
        ])
    if isinstance(series.style, VectorSeriesStyle):
        targets.append((series.style, "magnitude_column_id", "magnitude_column"))
    return targets


class DeleteColumnsCommand(Command):
    """
    Command to delete multiple columns from an existing dataset.
    Supports both column positions and column names for backward compatibility.
    """

    def __init__(self, app_context: AppContext, dataset_id: str, 
                 column_specs: Union[List[int], List[str]]):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()
        
        self.dataset_id = dataset_id
        self.column_specs = column_specs
        
        # These will be populated in execute() after we have access to the dataset
        self.column_names = []
        self.column_positions = []
        
        # Store state for undo
        self.original_data = None
        self.original_column_ids = None
        self.deleted_columns_data = None
        self.project = None
        self.dataset = None

        # chart_id -> {"series": [(index, DataSeries)], "fits": [(index, FitData)]}
        # populated when columns being deleted are referenced by chart series/fits
        self.removed_chart_refs = {}

        # chart_id -> [(series_index, old_x_error_column, old_y_error_column)]
        # populated when a deleted column is only referenced as an (optional)
        # error-bar column, so the series survives with error bars cleared
        # instead of being removed entirely
        self.cleared_error_refs = {}

    @override
    def execute(self) -> bool:
        """Execute the delete columns command."""
        try:
            self.logger.info(f"Executing DeleteColumnsCommand for {len(self.column_specs)} column specifications")
            
            # Validate input
            if not self.column_specs:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: no column specs provided"
                )
                self.ui_controller.show_warning_message(
                    "Delete Columns",
                    "No columns specified for deletion."
                )
                return False

            # Check if we have a project loaded
            if not self.app_state.has_project:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: no project open; cannot delete columns"
                )
                self.ui_controller.show_warning_message(
                    "Delete Columns",
                    "Please open or create a project first."
                )
                return False

            self.project = self.app_state.current_project
            if not self.project:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: has_project is True but current_project is None"
                )
                return False

            # Find the dataset
            found_item = self.project.find_item(self.dataset_id)
            if not found_item:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: dataset '%s' not found", self.dataset_id
                )
                self.ui_controller.show_error_message(
                    "Delete Columns",
                    f"Dataset with ID '{self.dataset_id}' not found."
                )
                return False

            if not isinstance(found_item, Dataset):
                self.logger.warning(
                    "DeleteColumnsCommand.execute: item '%s' is not a Dataset (got %s)",
                    self.dataset_id, type(found_item).__name__,
                )
                self.ui_controller.show_error_message(
                    "Delete Columns",
                    "Selected item is not a dataset."
                )
                return False

            self.dataset = found_item

            # Get current data
            if self.dataset.data is None or self.dataset.data.empty:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: dataset '%s' has no data to delete columns from",
                    self.dataset_id,
                )
                self.ui_controller.show_warning_message(
                    "Delete Columns",
                    "Cannot delete columns from empty dataset."
                )
                return False

            # Resolve column names and positions based on input type
            self._resolve_columns()

            # Validate resolved columns
            if not self.column_names:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: no valid columns resolved from specs %s for dataset '%s'",
                    self.column_specs, self.dataset_id,
                )
                self.ui_controller.show_warning_message(
                    "Delete Columns",
                    "No valid columns found for deletion."
                )
                return False

            # Check if all resolved columns exist
            existing_columns = set(self.dataset.data.columns)
            missing_columns = [col for col in self.column_names if col not in existing_columns]
            if missing_columns:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: columns %s not found in dataset '%s'",
                    missing_columns, self.dataset_id,
                )
                self.ui_controller.show_error_message(
                    "Delete Columns",
                    f"The following columns do not exist: {', '.join(missing_columns)}"
                )
                return False

            # Check for duplicate column names
            if len(set(self.column_names)) != len(self.column_names):
                self.logger.warning(
                    "DeleteColumnsCommand.execute: duplicate column names in deletion list %s for dataset '%s'",
                    self.column_names, self.dataset_id,
                )
                self.ui_controller.show_warning_message(
                    "Delete Columns",
                    "Duplicate column names found in the deletion list."
                )
                return False

            # Check if we're trying to delete all columns
            remaining_columns = len(self.dataset.data.columns) - len(self.column_names)
            if remaining_columns <= 0:
                self.logger.warning(
                    "DeleteColumnsCommand.execute: refusing to delete all %d columns from dataset '%s'",
                    len(self.dataset.data.columns), self.dataset_id,
                )
                self.ui_controller.show_error_message(
                    "Delete Columns",
                    "Cannot delete all columns from dataset. Dataset must have at least one column."
                )
                return False
            
            # Warn if any chart depends on the columns being deleted, since those
            # series/fit curves will be removed from the chart as part of this action
            references = self._find_chart_references(self.column_names)
            if references:
                details = "\n".join(
                    f"{match.chart.name}: " + ", ".join(
                        ([f"{len(match.series_indices)} series"] if match.series_indices else [])
                        + ([f"{len(match.fit_indices)} fit curve(s)"] if match.fit_indices else [])
                        + ([f"{len(match.error_only_indices)} series losing error bars"] if match.error_only_indices else [])
                    )
                    for match in references
                )
                proceed = self.ui_controller.show_confirmation(
                    "Delete Columns",
                    f"{len(self.column_names)} column(s) are used by {len(references)} "
                    "chart(s). Deleting them will remove the dependent series/fit "
                    "curves from those charts (series only using the column for "
                    "error bars will keep plotting, with error bars removed). Continue?",
                    details=details
                )
                if not proceed:
                    return False

            # Store original data + column-id registry for undo. Restoring the
            # registry keeps deleted columns' ids stable across delete/undo, so
            # series that reference them by id resolve again after undo (a plain
            # set_data would mint fresh ids for the reappearing columns).
            self.original_data = self.dataset.data.copy()
            self.original_column_ids = OrderedDict(self.dataset.column_ids)

            # Store the deleted columns data for potential restoration
            self.deleted_columns_data = {}
            for col_name in self.column_names:
                self.deleted_columns_data[col_name] = self.dataset.data[col_name].copy()

            self._perform_deletion(references)

            self.logger.info(f"Deleted {len(self.column_names)} columns from dataset '{self.dataset.name}' (ID: {self.dataset_id})")
            return True

        except Exception as e:
            error_msg = f"Failed to delete {len(self.column_specs) if self.column_specs else 0} columns: {str(e)}"
            self.logger.error(error_msg)
            self.ui_controller.show_error_message("Delete Columns Error", error_msg)
            return False

    def _find_chart_references(
        self, column_names: List[str]
    ) -> List[ChartReferenceMatch]:
        """Find charts whose series/fits reference this dataset's columns.

        Returns a list of (chart, data_series indices, fit_data indices,
        error-only data_series indices) for every chart with at least one
        matching reference. A series lands in error-only indices (instead of
        data_series indices) when the only matching reference is one of its
        optional columns (x_error_column/y_error_column/magnitude_column),
        since that series still
        renders fine without error bars and shouldn't be removed.
        """
        if not self.project:
            return []
        column_set = set(column_names)
        # Series/fits reference columns by stable id; resolve the names being
        # deleted to ids (the dataset still has them — deletion runs later) and
        # match by id, with a name fallback for legacy references.
        id_set = {
            cid for name in column_names
            if self.dataset and (cid := self.dataset.column_id(name))
        }

        def refs(id_value, name_value) -> bool:
            return (id_value in id_set and id_value) or name_value in column_set

        matches: List[ChartReferenceMatch] = []
        for item in self.project.get_all_items():
            if not isinstance(item, Chart):
                continue
            series_idx = [
                i for i, series in enumerate(item.data_series)
                if series.dataset_id == self.dataset_id
                and (refs(series.x_column_id, series.x_column)
                     or refs(series.y_column_id, series.y_column)
                     or (isinstance(series.style, VectorSeriesStyle)
                         and (refs(series.style.u_column_id, series.style.u_column)
                              or refs(series.style.v_column_id, series.style.v_column))))
            ]
            error_only_idx = [
                i for i, series in enumerate(item.data_series)
                if i not in series_idx and series.dataset_id == self.dataset_id
                and any(refs(getattr(container, id_field), getattr(container, name_field))
                        for container, id_field, name_field in _error_field_targets(series))
            ]
            fit_idx = [
                i for i, fit in enumerate(item.fit_data)
                if fit.source_dataset_id == self.dataset_id
                and (refs(fit.source_x_column_id, fit.source_x_column)
                     or refs(fit.source_y_column_id, fit.source_y_column))
            ]
            if series_idx or fit_idx or error_only_idx:
                matches.append(ChartReferenceMatch(item, series_idx, fit_idx, error_only_idx))
        return matches

    def _perform_deletion(
        self, references: List[ChartReferenceMatch]
    ) -> None:
        """Drop the columns from the dataset and remove dependent chart references."""
        # Resolve the deleted columns' stable ids *before* dropping (set_data
        # would drop them from the registry), so error-column references can be
        # cleared by id below.
        deleted_ids = {
            cid for name in self.column_names
            if (cid := self.dataset.column_id(name))
        }

        # Create new DataFrame with the columns removed
        new_data = self.dataset.data.drop(columns=self.column_names)

        # Update dataset
        self.dataset.set_data(new_data)

        # Emit event
        self.app_state.event_bus.emit(DatasetOperationEvents.DATASET_COLUMN_REMOVED,
                                      DatasetColumnsRemovedData(dataset_id=self.dataset_id, column_positions=self.column_positions).to_dict()
        )

        column_set = set(self.column_names)
        self.removed_chart_refs = {}
        self.cleared_error_refs = {}
        for match in references:
            chart = match.chart
            series_idx = match.series_indices
            fit_idx = match.fit_indices
            error_only_idx = match.error_only_indices
            removed_series = [(i, chart.data_series[i]) for i in series_idx]
            removed_fits = [(i, chart.fit_data[i]) for i in fit_idx]

            # Clear error-only references using original indices before any
            # deletion shifts the list, so `i` still points at the right series.
            # Match by stable id (deleted_ids) with a name fallback for legacy
            # references; clear both the id and the name field together.
            cleared_series = []
            for i in error_only_idx:
                series = chart.data_series[i]
                targets = _error_field_targets(series)
                old_values = [
                    (container, field, getattr(container, field))
                    for container, id_field, name_field in targets
                    for field in (id_field, name_field)
                ]
                for container, id_field, name_field in targets:
                    cid = getattr(container, id_field)
                    name = getattr(container, name_field)
                    if (cid and cid in deleted_ids) or name in column_set:
                        setattr(container, id_field, "")
                        setattr(container, name_field, "")
                cleared_series.append((i, old_values))

            for i in sorted(series_idx, reverse=True):
                del chart.data_series[i]
            for i in sorted(fit_idx, reverse=True):
                del chart.fit_data[i]

            if removed_series or removed_fits or cleared_series:
                chart.update_modified_time()
                if removed_series or removed_fits:
                    self.removed_chart_refs[chart.id] = {
                        "series": removed_series,
                        "fits": removed_fits,
                    }
                if cleared_series:
                    self.cleared_error_refs[chart.id] = cleared_series
                self.app_state.event_bus.emit(ChartEvents.CHART_UPDATED, {
                    "chart_id": chart.id,
                    "chart": chart,
                })

    def _restore_chart_references(self) -> None:
        """Re-insert chart series/fits removed by _perform_deletion, for undo."""
        if not self.project or not (self.removed_chart_refs or self.cleared_error_refs):
            return
        chart_ids = set(self.removed_chart_refs) | set(self.cleared_error_refs)
        for chart_id in chart_ids:
            chart = self.project.find_item(chart_id)
            if not isinstance(chart, Chart):
                continue
            removed = self.removed_chart_refs.get(chart_id, {"series": [], "fits": []})
            for i, series in sorted(removed["series"], key=lambda pair: pair[0]):
                chart.data_series.insert(i, series)
            for i, fit in sorted(removed["fits"], key=lambda pair: pair[0]):
                chart.fit_data.insert(i, fit)

            for i, old_values in self.cleared_error_refs.get(chart_id, []):
                if 0 <= i < len(chart.data_series):
                    for container, field, value in old_values:
                        setattr(container, field, value)

            if removed["series"] or removed["fits"] or chart_id in self.cleared_error_refs:
                chart.update_modified_time()
                self.app_state.event_bus.emit(ChartEvents.CHART_UPDATED, {
                    "chart_id": chart.id,
                    "chart": chart,
                })
        self.removed_chart_refs = {}
        self.cleared_error_refs = {}

    def _resolve_columns(self):
        """
        Resolve column names and positions based on the input specification.
        Supports both column positions (integers) and column names (strings).
        """
        if not self.column_specs or not self.dataset or self.dataset.data is None:
            return
        
        all_columns = list(self.dataset.data.columns)
        self.column_names = []
        self.column_positions = []
        
        for spec in self.column_specs:
            if isinstance(spec, int):
                # Position-based specification
                if 0 <= spec < len(all_columns):
                    column_name = all_columns[spec]
                    self.column_names.append(column_name)
                    self.column_positions.append(spec)
                else:
                    self.logger.warning(f"Column position {spec} is out of range (0-{len(all_columns)-1})")
            elif isinstance(spec, str):
                # Name-based specification (backward compatibility)
                if spec in all_columns:
                    position = all_columns.index(spec)
                    self.column_names.append(spec)
                    self.column_positions.append(position)
                else:
                    self.logger.warning(f"Column '{spec}' not found in dataset")
            else:
                self.logger.warning(f"Invalid column specification: {spec}")

    def undo(self):
        """Undo the delete columns command by restoring the original data and chart refs."""
        try:
            if self.dataset and self.original_data is not None and self.column_positions:
                # Restore original data, then the saved id registry so restored
                # columns keep their original ids (see execute()).
                self.dataset.set_data(self.original_data)
                if self.original_column_ids is not None:
                    self.dataset.column_ids = OrderedDict(self.original_column_ids)
                self._restore_chart_references()

                # Emit event
                self.app_state.event_bus.emit(
                    DatasetOperationEvents.DATASET_COLUMN_ADDED,
                    DatasetColumnsAddedData(dataset_id=self.dataset_id, column_positions=self.column_positions).to_dict())

                self.logger.info(f"Undid deleting {len(self.column_names)} columns from dataset '{self.dataset.name}'")
                return True
        except Exception as e:
            self.logger.error(f"DeleteColumnsCommand Undo Error: {e}")
            return False

    def redo(self):
        """Redo the delete columns command using the already-confirmed parameters."""
        try:
            if not (self.dataset and self.original_data is not None and self.column_names):
                return False
            references = self._find_chart_references(self.column_names)
            self._perform_deletion(references)
            self.logger.info(f"Redid deleting {len(self.column_names)} columns from dataset '{self.dataset.name}'")
            return True
        except Exception as e:
            error_msg = f"Failed to redo deleting {len(self.column_names)} columns: {e}"
            self.logger.error(f"DeleteColumnsCommand Redo Error: {error_msg}")
            self.ui_controller.show_error_message("Delete Columns Error", error_msg)
            return False

    @override
    def cleanup(self) -> None:
        """Release the undo snapshots held for undo once this command is
        dropped from the stacks for good (see Command.cleanup)."""
        self.original_data = None
        self.original_column_ids = None
        self.deleted_columns_data = None
        self.removed_chart_refs = {}
        self.cleared_error_refs = {}
