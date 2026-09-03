"""Command to transform a chart series' x or y values into a new dataset.

Chart series come in two flavours (see series_xy.resolve_series_xy): data
series (a live dataset column reference) and fit series (resampled arrays).
This command evaluates a transform expression -- the same expression syntax
the dataset Transform panel uses -- against one of a series' resolved axes,
and writes the result, alongside the untouched axis, to a new Dataset
project item, the same way AnalyzeChartSeriesCommand does for analysis
results (#268). It then also adds a new data series to the chart pointing at
that dataset, so the transform's effect is visible on the chart immediately
-- from there it's an ordinary series like any other (restylable, removable,
independently re-pointed at a different column via the Data tab). When the
source is a data series (not a fit), the new series copies its type,
style, opacity, and y-axis assignment, so a transformed line/scatter/etc.
looks and plots the same as what it was derived from instead of falling
back to the chart's defaults. A fit source has no series to copy from, so
it's given the first of LINE/SCATTER the current chart type actually
allows -- never the chart's own default type, which can require columns
(e.g. a vector chart's U/V) this command's plain two-column result
dataset doesn't have -- and the transform is refused up front if the
chart type allows neither (e.g. a pure histogram chart).
"""

import copy
from typing import Literal, Optional, override

import pandas as pd

from pandaplot.commands.base_command import Command, CommandResult
from pandaplot.commands.project.chart.series_xy import (
    SourceKind,
    create_result_dataset,
    remove_result_dataset,
    resolve_series_xy,
)
from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.events import ChartEvents
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.state import AppContext, AppState
from pandaplot.services.transform import expression_engine

Target = Literal["x", "y"]


class TransformChartSeriesCommand(Command):
    """Transform a chart series' x or y values via an expression, into a new dataset."""

    def __init__(
        self,
        app_context: AppContext,
        chart_id: str,
        source_kind: SourceKind,
        source_index: int,
        target: Target,
        expression: str,
        result_name: Optional[str] = None,
        folder_id: Optional[str] = None,
    ):
        super().__init__()
        self.app_context = app_context
        self.app_state: AppState = app_context.get_app_state()
        self.ui_controller: UIController = app_context.get_ui_controller()

        self.chart_id = chart_id
        self.source_kind = source_kind
        self.source_index = source_index
        self.target = target
        self.expression = expression
        self.result_name = result_name
        self.folder_id = folder_id

        # State for undo/redo.
        self.result_dataset_id: Optional[str] = None
        self.added_series_index: Optional[int] = None

    def _get_chart(self) -> Optional[Chart]:
        project = self.app_state.current_project
        if not project:
            return None
        item = project.find_item(self.chart_id)
        return item if isinstance(item, Chart) else None

    def run_transform(self) -> tuple[pd.DataFrame, str]:
        """Compute the transform and return (result dataframe, default name).

        Raises ValueError if the chart/series/expression is unavailable or
        invalid. Does not touch the project, so the UI can call it for a
        preview.
        """
        chart = self._get_chart()
        if chart is None:
            raise ValueError("Chart is not available.")

        x, y, x_label, y_label = resolve_series_xy(
            self.app_state, chart, self.source_kind, self.source_index, coerce_numeric=False,
        )
        if len(x) < 1:
            raise ValueError("Series has no points to transform.")

        is_valid, error_msg = expression_engine.validate_expression(self.expression)
        if not is_valid:
            raise ValueError(error_msg)

        target_series = x if self.target == "x" else y
        local_vars = {"x": x, "y": y}
        try:
            result = expression_engine.evaluate_expression(self.expression, local_vars)
        except Exception as e:
            raise ValueError(f"Expression failed: {e}") from e

        if not isinstance(result, pd.Series):
            if pd.api.types.is_scalar(result):
                result = pd.Series([result] * len(target_series), index=target_series.index)
            else:
                # No index yet: assigning target_series.index here would raise
                # pandas' own length-mismatch error before the check below
                # gets a chance to produce the friendlier message. Both `x`
                # and `y` already carry a plain reset (0..n-1) index (see
                # series_xy.resolve_series_xy), and results_df is built from
                # result.reset_index(drop=True) below regardless, so a
                # correctly-sized result still lines up positionally.
                result = pd.Series(result)

        if len(result) != len(target_series):
            raise ValueError(
                f"Expression returned {len(result)} values but the series has {len(target_series)} points."
            )

        untouched_label = y_label if self.target == "x" else x_label
        transformed_label = f"{x_label if self.target == 'x' else y_label} (transformed)"
        if transformed_label == untouched_label:
            # A collision here means the resulting DataFrame({...}) dict
            # literal would silently keep only one of the two columns
            # (Python dicts can't have duplicate keys) -- results_df would
            # end up with a single column, and execute()'s later
            # results_df.columns[1] lookup would then raise after the
            # dataset was already created, leaving an orphaned dataset.
            transformed_label = f"{transformed_label} (2)"
        if self.target == "x":
            results_df = pd.DataFrame({
                transformed_label: result.reset_index(drop=True),
                y_label: y.reset_index(drop=True),
            })
        else:
            results_df = pd.DataFrame({
                x_label: x.reset_index(drop=True),
                transformed_label: result.reset_index(drop=True),
            })
        default_name = f"{y_label} ({self.target} transformed)"
        return results_df, default_name

    @staticmethod
    def _copied_style_without_stale_error_columns(style):
        """Deep-copy `style`, clearing any error-bar column bindings.

        The result dataset only ever has the two axis columns -- an
        error-bar column id/name copied verbatim from the source series
        would point at a column that doesn't exist in it (or, worse,
        accidentally resolve against a same-named axis column that means
        something else entirely). ErrorBarConfig.without_column_bindings()
        keeps the rest of the error-bar config (color, symmetry, cap size),
        which is pure visual styling, not a data binding.
        """
        new_style = copy.deepcopy(style)
        error_bars = getattr(new_style, "error_bars", None)
        if error_bars is not None:
            new_style.error_bars = error_bars.without_column_bindings()
        return new_style

    def _resolve_result_series_type(self, chart: Chart) -> SeriesType:
        """Series type for the new series -- resolved before any project
        mutation, so an unsupported chart type fails without creating
        anything.

        A data-series source keeps its own type: resolve_series_xy's
        supports_curve_analysis check already guarantees it's a type that
        renders fine from a plain (x, y) result and is necessarily allowed
        on this chart (it's already one of the chart's own series) -- but
        that check runs later, inside run_transform(), so an out-of-range
        source_index is caught here explicitly rather than raising a raw
        IndexError. A fit source has no series to inherit a type from, and
        the chart's own default type can require columns this two-column
        result doesn't have (a vector chart's default SeriesType.VECTOR
        needs U/V; a histogram chart's only allowed type, SeriesType.HIST,
        isn't an (x, y) pair type at all) -- so pick the first
        curve-capable type (per SERIES_TYPE_SPECS, the same registry
        resolve_series_xy consults) this chart type actually allows, and
        raise if none is allowed (e.g. a pure histogram chart).
        """
        if self.source_kind == "series":
            if not (0 <= self.source_index < len(chart.data_series)):
                raise ValueError("Selected series no longer exists.")
            return chart.data_series[self.source_index].series_type
        allowed = CHART_TYPE_SPECS[chart.chart_type].allowed_series_types
        for candidate in SeriesType:
            if candidate in allowed and SERIES_TYPE_SPECS[candidate].supports_curve_analysis:
                return candidate
        raise ValueError(
            f"'{chart.chart_type.value}' charts can't take a new series from a fit-derived transform."
        )

    @override
    def execute(self) -> CommandResult:
        try:
            if not self.app_state.has_project or not self.app_state.current_project:
                message = "No project loaded; cannot transform chart series."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Transform Error", message)
                return CommandResult.FAILURE

            chart = self._get_chart()
            if chart is None:
                message = "Chart is not available."
                self.logger.warning(message)
                self.ui_controller.show_error_message("Chart Transform Error", message)
                return CommandResult.FAILURE

            # Resolved before touching the project: a chart type with no
            # compatible two-column series type for a fit-derived result
            # (e.g. a pure histogram chart) must fail before anything is
            # created, not after.
            result_series_type = self._resolve_result_series_type(chart)

            results_df, default_name = self.run_transform()
            dataset = create_result_dataset(
                self.app_state, self.folder_id, self.result_name or default_name, results_df,
            )
            self.result_dataset_id = dataset.id
            name = dataset.name

            # The result dataframe's columns are always (x column, y column),
            # in that order, regardless of which one was the transform target
            # -- see run_transform()'s two branches.
            x_column, y_column = results_df.columns[0], results_df.columns[1]
            style_kwargs: dict = {"series_type": result_series_type}
            if self.source_kind == "series":
                # Copy the source series' look (style, opacity, y-axis) so
                # the transformed series doesn't revert to the chart's
                # default styling or silently jump back to the primary axis.
                # DataSeries rejects a style/series_type pair from different
                # series types, but result_series_type IS this source
                # series' own type in this branch (see
                # _resolve_result_series_type), so the pairing is valid.
                source_series = chart.data_series[self.source_index]
                style_kwargs.update({
                    "style": self._copied_style_without_stale_error_columns(source_series.style),
                    "alpha": source_series.alpha,
                    "y_axis": source_series.y_axis,
                })
            chart.add_data_series(
                dataset_id=self.result_dataset_id,
                x_column_id=dataset.column_id(x_column) or "",
                y_column_id=dataset.column_id(y_column) or "",
                x_column=x_column,
                y_column=y_column,
                label=name,
                **style_kwargs,
            )
            # add_data_series() always appends, so the new series is the last
            # element -- found this way (not list.index(new_series)) since
            # DataSeries is a plain dataclass: two field-identical series
            # (possible if this command runs twice with the same inputs)
            # would make index() return the earlier, wrong one.
            self.added_series_index = len(chart.data_series) - 1

            self.app_state.event_bus.emit(ChartEvents.CHART_UPDATED, {
                "chart_id": self.chart_id,
                "update_type": "series_added",
                "chart": chart,
            })

            self.logger.info(
                "Created chart-transform dataset '%s' (%s) and added it as a series to chart '%s'",
                name, self.result_dataset_id, self.chart_id,
            )
            return CommandResult.SUCCESS

        except ValueError as e:
            self.logger.warning("Transform-chart-series failed: %s", e)
            self.ui_controller.show_error_message("Chart Transform Error", str(e))
            return CommandResult.FAILURE
        except Exception as e:
            self.logger.error("Transform-chart-series failed: %s", e, exc_info=True)
            self.ui_controller.show_error_message("Chart Transform Error", str(e))
            return CommandResult.FAILURE

    @override
    def undo(self) -> CommandResult:
        try:
            if not self.result_dataset_id or not self.app_state.current_project:
                return CommandResult.FAILURE

            chart = self._get_chart()
            if chart is not None and self.added_series_index is not None:
                chart.remove_data_series(self.added_series_index)
                self.app_state.event_bus.emit(ChartEvents.CHART_UPDATED, {
                    "chart_id": self.chart_id,
                    "update_type": "series_removed",
                    "chart": chart,
                })

            remove_result_dataset(self.app_state, self.result_dataset_id)
            return CommandResult.SUCCESS
        except Exception as e:
            self.logger.error("Failed to undo transform-chart-series: %s", e, exc_info=True)
            return CommandResult.FAILURE

    @override
    def redo(self) -> CommandResult:
        return self.execute()
