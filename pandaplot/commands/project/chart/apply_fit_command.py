"""Command for applying a fit to a chart, plus a standalone fit report."""

import uuid
from typing import Optional, override

import numpy as np
import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.fit_style import FitStyle
from pandaplot.models.events import ChartEvents
from pandaplot.models.events.event_types import DatasetEvents, ProjectEvents
from pandaplot.models.project.items import Dataset, Note
from pandaplot.models.state import AppContext

# Maps a short fit-type name to its chart color. `fit_type` from the fit panel is a
# full descriptive string (e.g. "Linear (y = ax + b)"), so lookups use substring
# matching rather than exact-match, mirroring FitService._get_fit_func.
FIT_TYPE_COLORS = {
    "Linear": "#ff0000",       # Red
    "Quadratic": "#00aa00",    # Green
    "Exponential": "#0066cc",  # Blue
    "Power": "#cc00cc",        # Magenta
    "Logarithmic": "#ff6600",  # Orange
    "Custom": "#00cccc",       # Cyan
}


def _resolve_fit_style(fit_type: str) -> tuple[str, str]:
    """Return (short_name, color) for a fit_type string like 'Linear (y = ax + b)'."""
    for short_name, color in FIT_TYPE_COLORS.items():
        if short_name in fit_type:
            return short_name, color
    return fit_type, "#ff0000"


class ApplyFitCommand(Command):
    """Command to apply fitted data to an existing chart, and generate a
    standalone fit report (a Note plus a Dataset of fitted values) as part
    of the same undoable action (see issue #95)."""

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        fit_results,
        source_dataset_id: str,
        source_x_column_id: str,
        source_y_column_id: str,
        source_x_column: str = "",
        source_y_column: str = "",
        label: str = "",
        fixed_parameters: Optional[str] = None,
    ):
        super().__init__()

        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.fit_results = fit_results

        self.source_dataset_id = source_dataset_id
        self.source_x_column_id = source_x_column_id
        self.source_y_column_id = source_y_column_id
        self.source_x_column = source_x_column
        self.source_y_column = source_y_column
        self.label = label
        self.fixed_parameters = fixed_parameters

        self.added_index: Optional[int] = None

        # State for undo/redo of the report items. The Note/Dataset objects
        # (and their ids) are created once on the first execute() and then
        # re-added as-is on redo(), so a redo doesn't mint new identities
        # that later commands (e.g. an edit to the generated note) can't
        # find by their originally-recorded id -- see CreateNoteCommand.redo().
        self.report_note_id: Optional[str] = None
        self.result_dataset_id: Optional[str] = None
        self._report_note: Optional[Note] = None
        self._result_dataset: Optional[Dataset] = None
        self._chart_finder = ChartFinder(app_context)

    def _source_path(self) -> str:
        """Full "Folder / Subfolder / DatasetName" path of the source dataset."""
        app_state = self.app_context.get_app_state()
        project = app_state.current_project
        if project is None:
            return self.source_dataset_id

        source = project.find_item(self.source_dataset_id)
        name = source.name if source is not None else self.source_dataset_id
        return " / ".join([*project.get_folder_path(self.source_dataset_id), name])

    def _parameter_lines(self) -> list[str]:
        """Fitted parameters as mathtext bullet lines, e.g. '- $a = 2.0 \\pm 0.1$'."""
        results = self.fit_results
        fixed_params = {}
        if self.fixed_parameters:
            for item in self.fixed_parameters.split(","):
                if "=" in item:
                    key, val = item.split("=", 1)
                    fixed_params[key.strip()] = float(val)

        lines = []
        free_index = 0
        for name in results.param_names:
            value = results.params[name]
            if name in fixed_params:
                lines.append(f"- ${name} = {value:.6g}$ (fixed)")
            else:
                error = results.errors[free_index]
                if np.isinf(error) or np.isnan(error):
                    lines.append(f"- ${name} = {value:.6g}$ (no error estimate)")
                else:
                    lines.append(f"- ${name} = {value:.6g} \\pm {error:.6g}$")
                free_index += 1
        return lines

    def _report_text(self) -> str:
        results = self.fit_results

        lines = [
            f"# Fit Report: {results.fit_type}",
            "",
            "## Equation",
            "",
            f"$${results.equation or 'Unknown equation'}$$",
            "",
            "## Parameters",
            "",
            *self._parameter_lines(),
            "",
        ]

        if results.r_squared is not None:
            lines += [f"$R^2 = {results.r_squared:.6f}$", ""]

        lines += [
            "## Data",
            "",
            f"- **Source:** {self._source_path()}",
            f"- **X column:** {self.source_x_column or '?'}",
            f"- **Y column:** {self.source_y_column or '?'}",
            f"- **Fit range:** {results.x_fit.min():.6g} to {results.x_fit.max():.6g}",
            f"- **Data points:** {len(results.x_data)}",
            f"- **Fit points:** {len(results.x_fit)}",
        ]

        return "\n".join(lines)

    def _fit_dataframe(self) -> pd.DataFrame:
        results = self.fit_results
        data = {"x": results.x_fit, "y": results.y_fit}
        if results.confidence_lower is not None:
            data["y_lower"] = results.confidence_lower
        if results.confidence_upper is not None:
            data["y_upper"] = results.confidence_upper
        return pd.DataFrame(data)

    def _create_report(self, project, folder_id: Optional[str], short_fit_name: str) -> None:
        """Add the report Note and fit-data Dataset alongside the source dataset.

        The objects are built once (first execute()) and cached; a later
        redo() re-adds the very same objects instead of minting fresh ids,
        so anything that recorded the original ids (e.g. an edit to the
        note) keeps working after an undo/redo round-trip.
        """
        if self._result_dataset is None:
            self.result_dataset_id = str(uuid.uuid4())
            self._result_dataset = Dataset(
                id=self.result_dataset_id,
                name=f"{short_fit_name} Fit Data",
                data=self._fit_dataframe(),
                source_file=None,
            )
        dataset = self._result_dataset

        project.add_item(dataset, parent_id=folder_id)
        self.app_context.event_bus.emit(DatasetEvents.DATASET_CREATED, {
            "project": project,
            "dataset_id": self.result_dataset_id,
            "dataset_name": dataset.name,
            "folder_id": folder_id,
            "dataset_data": dataset.data,
        })

        if self._report_note is None:
            self.report_note_id = str(uuid.uuid4())
            self._report_note = Note(
                id=self.report_note_id,
                name=f"{short_fit_name} Fit Report",
                content=self._report_text(),
            )
        note = self._report_note

        project.add_item(note, parent_id=folder_id)
        self.app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_ADDED, {
            "project": project,
            "item_id": self.report_note_id,
            "note_id": self.report_note_id,
            "note_name": note.name,
            "folder_id": folder_id,
            "note": note,
        })

    def _remove_report(self, project) -> None:
        if self.report_note_id:
            note = project.find_item(self.report_note_id)
            if note:
                project.remove_item(note)
                self.app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                    "project": project,
                    "item_id": self.report_note_id,
                    "note_id": self.report_note_id,
                    "note": note,
                })

        if self.result_dataset_id:
            dataset = project.find_item(self.result_dataset_id)
            if dataset:
                project.remove_item(dataset)
                self.app_context.event_bus.emit(DatasetEvents.DATASET_DELETED, {
                    "project": project,
                    "dataset_id": self.result_dataset_id,
                    "dataset_name": dataset.name,
                })
                # DATASET_DELETED deliberately doesn't bubble to
                # project.item_removed (its payload has no generic
                # "item_id"), so an open tab for this dataset wouldn't
                # otherwise close -- publish that explicitly too.
                self.app_context.event_bus.emit(ProjectEvents.PROJECT_ITEM_REMOVED, {
                    "project": project,
                    "item_id": self.result_dataset_id,
                    "dataset_id": self.result_dataset_id,
                })

    @override
    def execute(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)

        if chart is None:
            self.logger.warning(
                "ApplyFitCommand.execute: chart '%s' not found or not a Chart",
                self.chart_id,
            )
            self.ui_controller.show_error_message(
                "Apply Fit Error", f"Chart '{self.chart_id}' not found."
            )
            return CommandResult.FAILURE

        results = self.fit_results

        short_fit_name, fit_color = _resolve_fit_style(results.fit_type)
        label = self.label or f"{short_fit_name} Fit: ({results.equation})"

        chart.add_fit_data(
            source_dataset_id=self.source_dataset_id,
            source_x_column_id=self.source_x_column_id,
            source_y_column_id=self.source_y_column_id,
            fit_type=results.fit_type,
            x_data=results.x_fit,
            y_data=results.y_fit,
            source_x_column=self.source_x_column,
            source_y_column=self.source_y_column,
            label=label,
            style=FitStyle(color=fit_color, line_style="dashed", line_width=2.0),
            fit_params=results.params,
            fit_stats={
                "r_squared": results.r_squared,
            },
            confidence_lower=results.confidence_lower,
            confidence_upper=results.confidence_upper,
        )

        self.added_index = len(chart.fit_data) - 1

        self.app_context.event_bus.emit(
            ChartEvents.CHART_UPDATED,
            {
                "chart_id": self.chart_id,
                "update_type": "fit_added",
                "chart": chart,
            },
        )

        app_state = self.app_context.get_app_state()
        project = app_state.current_project
        source = project.find_item(self.source_dataset_id)
        folder_id = source.parent_id if source else None
        self._create_report(project, folder_id, short_fit_name)

        return CommandResult.SUCCESS

    @override
    def undo(self) -> CommandResult:
        chart = self._chart_finder.find(self.chart_id)

        if chart is None or self.added_index is None:
            self.logger.warning(
                "ApplyFitCommand.undo: cannot undo for chart '%s' (chart found=%s, added_index set=%s)",
                self.chart_id, chart is not None, self.added_index is not None,
            )
            return CommandResult.FAILURE

        chart.remove_fit_data(self.added_index)

        self.app_context.event_bus.emit(
            ChartEvents.CHART_UPDATED,
            {
                "chart_id": self.chart_id,
                "update_type": "fit_removed",
                "chart": chart,
            },
        )

        app_state = self.app_context.get_app_state()
        project = app_state.current_project
        if project is not None:
            self._remove_report(project)

        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        return self.execute()

    @override
    def cleanup(self) -> None:
        """Release the insertion-index and report-id bookkeeping held for
        undo once this command is dropped from the stacks for good (see
        Command.cleanup)."""
        self.added_index = None
        self.report_note_id = None
        self.result_dataset_id = None
        self._report_note = None
        self._result_dataset = None
