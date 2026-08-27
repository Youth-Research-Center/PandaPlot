"""Command that opens the chart creation wizard and builds the resulting
Chart item — the single path every chart-creation entry point uses.

The wizard is opened non-blocking (`show()`, not `exec()`): `execute()` returns
as soon as the wizard is on screen, and the chart is built later in
`_on_wizard_finished`, driven by the wizard's `finished(int)` signal.
"""

from typing import Optional, override

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog

from pandaplot.commands.base_command import Command
from pandaplot.commands.project.chart.create_chart_command import CreateChartCommand
from pandaplot.commands.project.require_project import ensure_project_or_offer_create
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.project.items.dataset import dataset_display_options
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.config.config_manager import ConfigManager

# Same default palette data_tab.py's "+Add series" cycles through -- keeps
# wizard-created series visually distinguishable instead of all landing on
# the style class's own single hardcoded default color.
_DEFAULT_SERIES_COLORS = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
    "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf",
]


class CreateChartFromWizardCommand(Command):
    """Opens `ChartWizard` non-blocking; on acceptance builds a `Chart` from it."""

    def __init__(self, app_context: AppContext, dataset_id: Optional[str] = None,
                 preselected_column_ids: Optional[list[str]] = None):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.created_chart_id: Optional[str] = None
        self.created_chart: Optional[Chart] = None
        self._resolved_parent_id: Optional[str] = None
        self.dataset_id: Optional[str] = dataset_id
        self.preselected_column_ids: list[str] = preselected_column_ids or []
        self._dialog: Optional[QDialog] = None

    def _dataset_options(self, project) -> list[tuple[str, str]]:
        return dataset_display_options(project)

    def _columns_provider(self, project):
        def provider(dataset_id: str) -> list[tuple[str, str]]:
            dataset = project.find_item(dataset_id)
            if not isinstance(dataset, Dataset) or dataset.data is None:
                return []
            return [(dataset.column_id(name) or "", name) for name in dataset.data.columns]
        return provider

    def _default_series_label(self, project, series_config: dict) -> str:
        """Default label for a wizard-created series: "{dataset name}:{Y column name}".

        Matches the convention already used elsewhere in the app (e.g. the
        dataset properties panel). Histogram series need no special case:
        their picked "Values" column already lands in `y_column_id` via the
        wizard's own role mapping. Falls back to just the dataset name if the
        Y column can't be resolved (shouldn't normally happen for a complete
        series).
        """
        dataset = project.find_item(series_config["dataset_id"])
        dataset_name = dataset.name if isinstance(dataset, Dataset) else series_config["dataset_id"]
        y_column_name = ""
        y_column_id = series_config["y_column_id"]
        if isinstance(dataset, Dataset) and y_column_id:
            y_column_name = dataset.column_name(y_column_id) or ""
        if y_column_name:
            return f"{dataset_name}:{y_column_name}"
        return dataset_name

    def _resolve_parent_id(self, project, series_configs: list[dict]) -> Optional[str]:
        """Folder for the new chart: the shared folder of every dataset its
        series use, or the project root if they don't share one.

        An empty-plot chart has no series to derive this from, so it falls
        back to `self.dataset_id` (the entry point's originating dataset, if
        any) -- e.g. "Create empty plot" from a dataset's own context menu
        still places the chart in that dataset's folder.
        """
        dataset_ids = {config["dataset_id"] for config in series_configs if config.get("dataset_id")}
        if not dataset_ids and self.dataset_id:
            dataset_ids = {self.dataset_id}

        parent_ids = set()
        for dataset_id in dataset_ids:
            dataset = project.find_item(dataset_id)
            if dataset is not None:
                parent_ids.add(dataset.parent_id)

        if len(parent_ids) == 1:
            return next(iter(parent_ids))
        return None

    def _default_chart_name(self, project) -> str:
        """Name for the new chart, derived from the originating dataset.

        Computed *before* `Chart(...)` construction on purpose: `Chart.__init__`
        snapshots `config["title"] = self.name`, so a name assigned after
        construction would leave the rendered title permanently empty.
        """
        if self.dataset_id:
            dataset = project.find_item(self.dataset_id)
            if isinstance(dataset, Dataset):
                return f"Chart from {dataset.name}"
        return "New Chart"

    @override
    def occupies_undo_slot(self) -> bool:
        """This command only opens the wizard; the real, undoable effect is
        CreateChartCommand, executed separately once the wizard finishes
        (see _on_wizard_finished). Exempting this command from the stacks
        is what fixes #185/#186: there is no "wizard opened but nothing
        happened yet" state sitting on undo_stack to desync."""
        return False

    @override
    def execute(self) -> bool:
        from pandaplot.gui.dialogs.chart.chart_wizard import ChartWizard

        try:
            self.logger.info("Executing CreateChartFromWizardCommand")

            if not self.app_state.has_project or not self.app_state.current_project:
                self.logger.warning("CreateChartFromWizardCommand.execute: no project is currently loaded")
                if not ensure_project_or_offer_create(
                    self.app_context, "Create Chart",
                    "Creating a chart requires a project. Create a new project to continue?",
                ):
                    return False
            project = self.app_state.current_project

            dialog = ChartWizard(
                self.app_context,
                parent=self.ui_controller.parent_widget,
                initial_dataset_id=self.dataset_id,
                initial_column_ids=self.preselected_column_ids,
                initial_title=self._default_chart_name(project),
                datasets=self._dataset_options(project),
                columns_provider=self._columns_provider(project),
                project=project,
            )
            # Qt does not delete a `.show()`'d top-level widget on close by
            # default (that's only implicit for `exec()`'d modal dialogs);
            # without this, the dialog survives as a hidden top-level widget
            # for as long as the (parent) main window is alive. This also
            # lets the `finished` closure below release its references to
            # `dialog`/`self` once the C++ object is actually destroyed.
            dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
            # Keep a strong reference so the dialog isn't garbage-collected while
            # open.
            self._dialog = dialog
            # Use a lambda closure, not the bound method `self._on_wizard_finished`:
            # PySide treats bound-method slots as weak references, so it wouldn't
            # keep this command alive. This command never occupies an undo slot
            # (see occupies_undo_slot()), so it isn't held by any stack either --
            # the closure's strong references to `self` and `dialog` are the only
            # thing keeping both alive for as long as the wizard is open. `dialog`
            # is captured explicitly rather than read from
            # `self._dialog` at emit time, so a replaced `self._dialog` can't make
            # the wrong wizard's state build the chart.
            dialog.finished.connect(lambda result: self._on_wizard_finished(result, dialog))
            # `exec()` used to make the wizard application-modal implicitly;
            # `show()` does not, so set it explicitly to keep the project from
            # being edited underneath a half-configured wizard.
            dialog.setModal(True)
            dialog.show()
            dialog.raise_()
            dialog.activateWindow()
            return True

        except Exception as e:
            error_msg = f"Failed to open chart wizard: {str(e)}"
            self.logger.error(f"CreateChartFromWizardCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Create Chart Error", error_msg)
            return False

    def _on_wizard_finished(self, result: int, dialog: Optional[QDialog] = None) -> None:
        """Runs once the user actually finishes the wizard (Finish or Cancel).

        `execute()` returning True now only means "the wizard opened
        successfully" -- the chart itself is created here, asynchronously, once
        the wizard's `finished` signal fires. A cancelled/closed wizard never
        emits `QDialog.DialogCode.Accepted`, so it simply never creates a chart
        (no error, matching the old blocking behaviour's early return on
        `Rejected`).

        `dialog` is the wizard that actually emitted the signal, captured by the
        connected closure in `execute()`; it is preferred over `self._dialog`,
        which could in principle point at a different (newer) wizard.
        """
        dialog = dialog if dialog is not None else self._dialog
        if dialog is None or result != QDialog.DialogCode.Accepted:
            self._dialog = None
            return
        if self.created_chart is not None:
            # A chart was already created for this command instance; guard
            # against a stray double-fire of `finished` creating a duplicate.
            return

        try:
            if not self.app_state.has_project or not self.app_state.current_project:
                return
            project = self.app_state.current_project

            chart = Chart(name=self._default_chart_name(project), chart_type=dialog.get_chart_type())
            # Reported live: "when creating chart through wizard, the
            # chart is too small (it didn't use app default size)."
            # Leaving width_cm/height_cm as None routes a new chart
            # through ChartEditorWidget's auto-fit-to-viewport path,
            # which races the still-settling layout of a just-opened tab
            # and can permanently bake in an undersized result. Setting
            # the app's configured defaults explicitly here skips that
            # racy path for every wizard-created chart.
            width_cm, height_cm, dpi = 20.0, 15.0, 100
            try:
                cfg_manager = self.app_context.get_manager(ConfigManager)
                chart_display = getattr(getattr(cfg_manager, "config", None), "chart_display", None)
                if chart_display:
                    width_cm = getattr(chart_display, "default_width_cm", width_cm) or width_cm
                    height_cm = getattr(chart_display, "default_height_cm", height_cm) or height_cm
                    dpi = getattr(chart_display, "dpi", dpi) or dpi
            except Exception:
                pass
            chart.config["width_cm"] = width_cm
            chart.config["height_cm"] = height_cm
            chart.config["dpi"] = dpi
            series_configs = [] if dialog.is_empty() else dialog.get_series_configs()
            if not dialog.is_empty():
                chart.set_labels(
                    title=dialog.get_title() or None,
                    x_label=dialog.get_x_label() or None,
                    y_label=dialog.get_y_label() or None,
                )
                chart.config["subtitle"] = dialog.get_subtitle()
                chart.config["show_legend"] = dialog.get_show_legend()
                chart.config["show_grid_x"] = dialog.get_show_grid()
                chart.config["show_grid_y"] = dialog.get_show_grid()
                series_type = SeriesType(chart.chart_type)
                spec = SERIES_TYPE_SPECS[series_type]
                style_cls = spec.style_cls
                for index, series_config in enumerate(series_configs):
                    # Cycle through the same default palette data_tab.py's
                    # "+Add series" uses, so multiple wizard-created series
                    # aren't all left on the style class's own single
                    # hardcoded default color.
                    color = _DEFAULT_SERIES_COLORS[index % len(_DEFAULT_SERIES_COLORS)]
                    if spec.supports_error_bars:
                        style = style_cls(color=color, error_bars=ErrorBarConfig(
                            x_error_column_id=series_config["x_error_column_id"],
                            y_error_column_id=series_config["y_error_column_id"],
                            x_error_minus_column_id=series_config.get("x_error_minus_column_id", ""),
                            y_error_minus_column_id=series_config.get("y_error_minus_column_id", ""),
                            error_symmetric=series_config["error_symmetric"],
                        ))
                    elif series_type == SeriesType.VECTOR:
                        style = style_cls(
                            vector_color=color,
                            u_column_id=series_config.get("u_column_id", ""),
                            v_column_id=series_config.get("v_column_id", ""),
                            magnitude_column_id=series_config.get("magnitude_column_id", ""),
                        )
                    elif series_type in (SeriesType.COLORMAP, SeriesType.HEATMAP):
                        style = style_cls(z_column_id=series_config.get("z_column_id", ""))
                    else:
                        style = style_cls(color=color)
                    chart.add_data_series(
                        series_config["dataset_id"],
                        x_column_id=series_config["x_column_id"],
                        y_column_id=series_config["y_column_id"],
                        style=style,
                        label=self._default_series_label(project, series_config),
                    )

            self._resolved_parent_id = self._resolve_parent_id(project, series_configs)
            self.created_chart_id = chart.id
            self.created_chart = chart
            created = self.app_context.get_command_executor().execute_command(
                CreateChartCommand(self.app_context, chart, parent_id=self._resolved_parent_id)
            )
            if created:
                self.logger.info("CreateChartFromWizardCommand: created chart '%s'", chart.id)
            else:
                # CreateChartCommand already logged/handled its own failure; undo
                # the created_chart/created_chart_id bookkeeping above so the
                # double-fire guard above doesn't block a legitimate retry, and
                # surface the failure here since CreateChartCommand.execute()
                # only returns False -- it doesn't itself talk to the user.
                self.created_chart = None
                self.created_chart_id = None
                error_msg = f"Failed to create chart '{chart.name}'."
                self.logger.error(f"CreateChartFromWizardCommand Error: {error_msg}")
                self.ui_controller.show_error_message("Create Chart Error", error_msg)
        except Exception as e:
            error_msg = f"Failed to create chart: {str(e)}"
            self.logger.error(f"CreateChartFromWizardCommand Error: {error_msg}")
            self.ui_controller.show_error_message("Create Chart Error", error_msg)
        finally:
            # Drop the reference now that the wizard has finished; this command
            # is never on the undo/redo stacks, so nothing else would release it.
            self._dialog = None

    @override
    def undo(self):
        """Unreachable via CommandExecutor: occupies_undo_slot() is False, so
        this command is never pushed onto undo_stack/redo_stack, and the
        executor's undo()/redo() only ever act on stack contents. Undoing
        the chart's creation is CreateChartCommand's job. Kept as a no-op
        only to satisfy the abstract Command interface."""
        return

    @override
    def redo(self):
        """See undo() -- unreachable via CommandExecutor for the same reason."""
        return

    @override
    def cleanup(self) -> None:
        """Unreachable via CommandExecutor: occupies_undo_slot() is False, so
        this command is never pushed onto a stack for cleanup() to apply to.
        Kept as a documented no-op only to complete the Command interface."""
        return
