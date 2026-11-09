"""Command that opens the Add Series dialog and adds the configured series to a chart.

The dialog is opened non-blocking (`show()`, not `exec()`): `execute()` returns as soon as
it is on screen, and the series is added later in `_on_dialog_finished`, driven by the
dialog's `finished(int)` signal. The undoable edit is the `AddSeriesCommand` executed then.
"""

from typing import TYPE_CHECKING, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QWidget

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.add_series_command import AddSeriesCommand
from pandaplot.commands.project.chart.chart_finder import ChartFinder
from pandaplot.commands.project.chart.series_from_config import build_series_from_config
from pandaplot.commands.project.current_project import get_current_project
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.series_style_builder import default_series_color
from pandaplot.models.events import ChartEvents
from pandaplot.models.events.event_data import SeriesSelectedData
from pandaplot.models.project import Project
from pandaplot.models.project.items import Dataset
from pandaplot.models.state import AppContext

if TYPE_CHECKING:
    from pandaplot.gui.dialogs.chart.add_series_dialog import AddSeriesDialog

_TITLE = "Add Series"


class AddSeriesFromDialogCommand(Command):
    """Opens `AddSeriesDialog` for a chart; on acceptance adds the series via `AddSeriesCommand`."""

    def __init__(self, app_context: AppContext, chart_id: str, *, parent: QWidget | None = None) -> None:
        """Create the command.

        Args:
            app_context: Application context.
            chart_id: Id of the chart that receives the series.
            parent: Parent widget of the dialog; defaults to the main window.
        """
        super().__init__()
        self.app_context = app_context
        self.ui_controller: UIController = app_context.get_ui_controller()
        self.chart_id = chart_id
        self.parent = parent
        self._dialog: AddSeriesDialog | None = None
        self._project: Project | None = None

    @override
    def occupies_undo_slot(self) -> bool:
        """Only opens the dialog; the undoable effect is the `AddSeriesCommand` run on accept."""
        return False

    @override
    def marks_project_modified(self) -> bool:
        """A cancelled dialog must not flag the project as having unsaved changes."""
        return False

    @override
    def execute(self) -> CommandResult:
        from pandaplot.gui.dialogs.chart.add_series_dialog import AddSeriesDialog

        try:
            project = get_current_project(self.app_context)
            chart = ChartFinder(self.app_context).find(self.chart_id)
            if project is None or chart is None:
                self.logger.warning("AddSeriesFromDialogCommand.execute: no project or chart '%s'", self.chart_id)
                self.ui_controller.show_error_message(_TITLE, "The chart to add a series to could not be found.")
                return CommandResult.FAILURE

            if not any(isinstance(item, Dataset) for item in project.get_all_items()):
                self.ui_controller.show_info_message(
                    _TITLE, "This project has no datasets yet. Import a dataset (File > Import Data...), then add a series."
                )
                return CommandResult.NOOP

            self._project = project
            dialog = AddSeriesDialog(
                self.app_context,
                chart=chart,
                project=project,
                parent=self.parent if self.parent is not None else self.ui_controller.parent_widget,
            )
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            self._dialog = dialog
            # A lambda closure, not a bound method: PySide holds bound-method slots weakly, and this
            # command is on no undo stack, so the closure is what keeps the command alive while open.
            dialog.finished.connect(lambda result: self._on_dialog_finished(result, dialog))
            dialog.setModal(True)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            return CommandResult.SUCCESS

        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary: any failure must become FAILURE, not a crash
            error_msg = f"Failed to open the Add Series dialog: {e!s}"
            self.logger.error("AddSeriesFromDialogCommand Error: %s", error_msg)
            self.ui_controller.show_error_message("Add Series Error", error_msg)
            return CommandResult.FAILURE

    def _on_dialog_finished(self, result: int, dialog: "AddSeriesDialog | None" = None) -> None:
        """Add the series once the dialog is accepted; a cancelled dialog changes nothing."""
        dialog = dialog if dialog is not None else self._dialog
        try:
            if dialog is None or result != QDialog.DialogCode.Accepted:
                return

            project = get_current_project(self.app_context)
            if project is None or project is not self._project:
                self.logger.info("AddSeriesFromDialogCommand: project changed while the dialog was open; nothing added")
                return
            chart = ChartFinder(self.app_context).find(self.chart_id)
            if chart is None:
                self.logger.info("AddSeriesFromDialogCommand: chart '%s' is gone; nothing added", self.chart_id)
                return

            color = default_series_color(len(chart.data_series))
            series = build_series_from_config(project, chart.chart_type, dialog.series_config(), color=color)
            add_command = AddSeriesCommand(self.app_context, self.chart_id, series)
            if not self.app_context.get_command_executor().execute_command(add_command):
                return
            if add_command.added_index is not None:
                self.app_context.event_bus.emit(
                    ChartEvents.SERIES_SELECTED,
                    SeriesSelectedData(chart_id=self.chart_id, series_index=add_command.added_index, kind="series").to_dict(),
                )
        except Exception as e:  # noqa: BLE001 -- Command-pattern boundary: report instead of crashing from a Qt slot
            error_msg = f"Failed to add series: {e!s}"
            self.logger.error("AddSeriesFromDialogCommand Error: %s", error_msg)
            self.ui_controller.show_error_message("Add Series Error", error_msg)
        finally:
            self._dialog = None
            self._project = None

    @override
    def undo(self) -> CommandResult:
        """Unreachable via CommandExecutor (no undo slot); undoing is `AddSeriesCommand`'s job."""
        return CommandResult.SUCCESS

    @override
    def redo(self) -> CommandResult:
        """Unreachable via CommandExecutor (no undo slot); see `undo`."""
        return CommandResult.SUCCESS
