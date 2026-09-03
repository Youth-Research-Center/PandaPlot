"""Tests for TransformChartSeriesCommand (expression transform on chart series)."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.transform_chart_series_command import (
    TransformChartSeriesCommand,
)
from pandaplot.models.chart.chart_type import ChartType
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.events.event_types import ProjectEvents
from pandaplot.models.project.items.chart import Chart, YAxis
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.items.folder import Folder
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")
    t = np.linspace(0.0, 10.0, 11)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"t": t, "sq": t ** 2}))
    project.add_item(dataset)

    chart = Chart(id="chart-1", name="C")
    x_id = dataset.column_id("t")
    y_id = dataset.column_id("sq")
    chart.add_data_series(dataset_id="ds-1", x_column_id=x_id, y_column_id=y_id,
                          x_column="t", y_column="sq", label="Squared")
    chart.add_fit_data(source_dataset_id="ds-1", fit_type="quadratic",
                       x_data=t, y_data=t ** 2, label="Quadratic Fit", source_x_column="t")
    project.add_item(chart)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, project


def _cmd(ctx, **kw):
    app_context, _ = ctx
    kw.setdefault("source_kind", "series")
    kw.setdefault("source_index", 0)
    kw.setdefault("target", "y")
    kw.setdefault("expression", "y * 2")
    return TransformChartSeriesCommand(app_context, "chart-1", **kw)


class TestTransformChartSeriesCommand:
    def test_transform_y_on_data_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, target="y", expression="y * 2")
        assert command.execute() is CommandResult.SUCCESS
        result = project.find_item(command.result_dataset_id)
        assert "t" in result.data.columns
        transformed_col = [c for c in result.data.columns if c != "t"][0]
        assert result.data[transformed_col].tolist() == pytest.approx((result.data["t"] ** 2 * 2).tolist())

    def test_untouched_non_numeric_axis_round_trips_unchanged(self, ctx):
        """Transforming Y on a series whose X column holds categorical
        strings must leave those strings alone in the result dataset --
        not rewrite them to NaN via numeric coercion."""
        _, project = ctx
        dataset = project.find_item("ds-1")
        labels = ["cat", "dog", "bird", "fish", "ant", "bee", "cow", "pig", "rat", "owl", "fox"]
        dataset.data["t"] = labels

        command = _cmd(ctx, target="y", expression="y * 2")
        assert command.execute() is CommandResult.SUCCESS

        result = project.find_item(command.result_dataset_id)
        assert result.data["t"].tolist() == labels

    def test_transform_x_on_data_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, target="x", expression="x + 1")
        assert command.execute() is CommandResult.SUCCESS
        result = project.find_item(command.result_dataset_id)
        assert "Squared" in result.data.columns
        transformed_col = [c for c in result.data.columns if c != "Squared"][0]
        assert transformed_col == "t (transformed)"
        assert result.data[transformed_col].iloc[0] == pytest.approx(1.0)

    def test_transformed_column_name_disambiguates_from_a_colliding_untouched_label(self, ctx):
        """If the source series' label (used as the y column name) happens
        to equal what the transformed x column would be named, the two
        DataFrame({...}) keys would otherwise collide and pandas would
        silently keep only one of the two columns."""
        _, project = ctx
        chart = project.find_item("chart-1")
        chart.data_series[0].label = "t (transformed)"  # collides with x_label + " (transformed)"

        command = _cmd(ctx, target="x", expression="x + 1")
        assert command.execute() is CommandResult.SUCCESS

        result = project.find_item(command.result_dataset_id)
        assert len(result.data.columns) == 2
        assert "t (transformed)" in result.data.columns
        assert "t (transformed) (2)" in result.data.columns

    def test_transform_on_fit_series(self, ctx):
        _, project = ctx
        command = _cmd(ctx, source_kind="fit", target="y", expression="np.sqrt(y)")
        assert command.execute() is CommandResult.SUCCESS
        result = project.find_item(command.result_dataset_id)
        transformed_col = [c for c in result.data.columns if c != "t"][0]
        assert result.data[transformed_col].iloc[-1] == pytest.approx(10.0)

    def test_custom_result_name(self, ctx):
        _, project = ctx
        command = _cmd(ctx, result_name="My Transform")
        assert command.execute() is CommandResult.SUCCESS
        assert project.find_item(command.result_dataset_id).name == "My Transform"

    def test_undo_removes_dataset(self, ctx):
        _, project = ctx
        command = _cmd(ctx)
        command.execute()
        new_id = command.result_dataset_id
        assert project.find_item(new_id) is not None
        assert command.undo() is CommandResult.SUCCESS
        assert project.find_item(new_id) is None

    def test_redo_recreates_the_dataset(self, ctx):
        _, project = ctx
        command = _cmd(ctx)
        command.execute()
        command.undo()
        assert command.redo() is CommandResult.SUCCESS
        assert project.find_item(command.result_dataset_id) is not None

    def test_invalid_source_index_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, source_kind="fit", source_index=9)
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_invalid_series_source_index_fails_with_the_friendly_message(self, ctx):
        """Regression: _resolve_result_series_type used to index
        chart.data_series[source_index] directly, before run_transform()'s
        own bounds check ran -- an out-of-range series index raised a raw
        IndexError instead of this same friendly message."""
        app_context, _ = ctx
        command = _cmd(ctx, source_kind="series", source_index=9)
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
        assert "no longer exists" in message

    def test_expression_returning_a_wrong_length_array_fails_with_the_friendly_message(self, ctx):
        """A raw array/list result (not a pd.Series) of the wrong length
        used to hit pandas' own construction error (assigning a mismatched
        index) before the code's own length check got a chance to produce
        this message."""
        app_context, _ = ctx
        command = _cmd(ctx, expression="np.array([1.0, 2.0, 3.0])")
        assert command.execute() is CommandResult.FAILURE
        _title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
        assert "Expression returned 3 values" in message

    def test_unsafe_expression_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, expression="__import__('os')")
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_empty_expression_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, expression="")
        assert command.execute() is CommandResult.FAILURE

    def test_expression_referencing_unknown_name_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, expression="not_a_real_variable")
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_expression_that_changes_result_length_fails(self, ctx):
        app_context, _ = ctx
        command = _cmd(ctx, expression="y[y > 5]")
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_series_type_that_does_not_support_transform_fails(self, ctx):
        app_context, project = ctx
        chart = project.find_item("chart-1")
        chart.data_series[0].series_type = SeriesType.BAR
        command = _cmd(ctx, source_kind="series", source_index=0)
        assert command.execute() is CommandResult.FAILURE

    def test_execute_surfaces_no_project_loaded_to_the_user(self, ctx):
        app_context, _ = ctx
        app_context.get_app_state.return_value.has_project = False
        app_context.get_app_state.return_value.current_project = None
        command = _cmd(ctx)
        assert command.execute() is CommandResult.FAILURE
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_run_transform_does_not_touch_the_project(self, ctx):
        _, project = ctx
        command = _cmd(ctx)
        df, name = command.run_transform()
        assert len(df) == 11
        assert isinstance(name, str)
        assert command.result_dataset_id is None

    def test_new_series_copies_the_source_series_type_style_and_opacity(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        source_series = chart.data_series[0]
        source_series.series_type = SeriesType.SCATTER
        source_series.style = SERIES_TYPE_SPECS[SeriesType.SCATTER].style_cls()
        source_series.style.marker.marker_color = "#ff00ff"
        source_series.alpha = 0.4

        command = _cmd(ctx, source_kind="series", source_index=0)
        assert command.execute() is CommandResult.SUCCESS

        new_series = chart.data_series[command.added_series_index]
        assert new_series.series_type == SeriesType.SCATTER
        assert new_series.style.marker.marker_color == "#ff00ff"
        assert new_series.alpha == 0.4
        # A copy, not the same object -- editing one must not edit the other.
        assert new_series.style is not source_series.style

    def test_new_series_does_not_copy_stale_error_bar_column_bindings(self, ctx):
        """The source series' error-bar column ids/names point at columns of
        its OWN dataset, which the result dataset (only the two axis
        columns) doesn't have -- copying them verbatim would leave a
        reference to a nonexistent column, or worse, silently resolve
        against a same-named column that means something else entirely."""
        _, project = ctx
        chart = project.find_item("chart-1")
        source_series = chart.data_series[0]
        source_series.style.error_bars.y_error_column_id = "err-col-id"
        source_series.style.error_bars.y_error_column = "sq_err"
        source_series.style.error_bars.error_color = "#00ff00"  # pure styling, should survive

        command = _cmd(ctx, source_kind="series", source_index=0)
        assert command.execute() is CommandResult.SUCCESS

        new_series = chart.data_series[command.added_series_index]
        assert new_series.style.error_bars.y_error_column_id == ""
        assert new_series.style.error_bars.y_error_column == ""
        assert new_series.style.error_bars.error_color == "#00ff00"
        # The source series' own bindings must be untouched too.
        assert source_series.style.error_bars.y_error_column_id == "err-col-id"

    def test_new_series_from_a_fit_source_uses_default_style(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        command = _cmd(ctx, source_kind="fit", source_index=0)
        assert command.execute() is CommandResult.SUCCESS
        new_series = chart.data_series[command.added_series_index]
        assert new_series.series_type == SeriesType.LINE

    def test_fit_source_uses_line_type_even_on_a_chart_whose_default_needs_more_columns(self, ctx):
        """A vector chart's own default series_type (SeriesType.VECTOR)
        needs U/V columns this command's plain two-column result dataset
        doesn't have -- a fit-derived series must not default to it just
        because it happens to be the chart's type."""
        _, project = ctx
        chart = project.find_item("chart-1")
        chart.chart_type = ChartType.VECTOR
        command = _cmd(ctx, source_kind="fit", source_index=0)
        assert command.execute() is CommandResult.SUCCESS
        new_series = chart.data_series[command.added_series_index]
        assert new_series.series_type == SeriesType.LINE

    def test_fit_source_uses_scatter_type_on_a_chart_that_does_not_allow_line(self, ctx):
        """A bar chart allows BAR/SCATTER but not LINE -- the fit-derived
        series must fall through to the next chart-compatible type
        instead of defaulting to LINE unconditionally."""
        _, project = ctx
        chart = project.find_item("chart-1")
        chart.chart_type = ChartType.BAR
        command = _cmd(ctx, source_kind="fit", source_index=0)
        assert command.execute() is CommandResult.SUCCESS
        new_series = chart.data_series[command.added_series_index]
        assert new_series.series_type == SeriesType.SCATTER

    def test_fit_source_fails_on_a_chart_type_with_no_compatible_series_type(self, ctx):
        """A histogram chart's only allowed series type (HIST) isn't an
        (x, y) pair type at all -- the transform must be rejected before
        anything is created, not fail partway through with an orphaned
        dataset or an invalid series."""
        app_context, project = ctx
        chart = project.find_item("chart-1")
        chart.chart_type = ChartType.HIST
        datasets_before = [item for item in project.get_all_items() if isinstance(item, Dataset)]
        command = _cmd(ctx, source_kind="fit", source_index=0)

        assert command.execute() is CommandResult.FAILURE

        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        datasets_after = [item for item in project.get_all_items() if isinstance(item, Dataset)]
        assert datasets_after == datasets_before
        assert command.result_dataset_id is None

    def test_new_series_preserves_the_source_series_y_axis(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        chart.data_series[0].y_axis = YAxis.SECONDARY
        command = _cmd(ctx, source_kind="series", source_index=0)
        assert command.execute() is CommandResult.SUCCESS
        new_series = chart.data_series[command.added_series_index]
        assert new_series.y_axis == YAxis.SECONDARY

    def test_execute_adds_a_new_series_to_the_chart(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        series_count_before = len(chart.data_series)
        command = _cmd(ctx, target="y", expression="y * 2")
        assert command.execute() is CommandResult.SUCCESS
        assert len(chart.data_series) == series_count_before + 1
        assert command.added_series_index == series_count_before

    def test_added_series_points_at_the_new_dataset_and_its_columns(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        command = _cmd(ctx, target="y", expression="y * 2")
        command.execute()
        new_series = chart.data_series[command.added_series_index]
        new_dataset = project.find_item(command.result_dataset_id)
        assert new_series.dataset_id == command.result_dataset_id
        assert new_series.x_column_id == new_dataset.column_id(new_series.x_column)
        assert new_series.y_column_id == new_dataset.column_id(new_series.y_column)
        assert new_series.label == new_dataset.name

    def test_undo_removes_the_added_series_as_well_as_the_dataset(self, ctx):
        _, project = ctx
        chart = project.find_item("chart-1")
        series_count_before = len(chart.data_series)
        command = _cmd(ctx)
        command.execute()
        assert len(chart.data_series) == series_count_before + 1
        assert command.undo() is CommandResult.SUCCESS
        assert len(chart.data_series) == series_count_before

    def test_execute_emits_the_generic_project_item_added_event(self, ctx):
        """The project explorer tree and other item-type-agnostic listeners
        (e.g. tab_container's item-removed tab closer) key off the generic
        ProjectEvents, not the narrower DatasetEvents.DATASET_CREATED/DELETED
        -- see import_data_command.py's TODO(#219) migration note."""
        app_context, project = ctx
        command = _cmd(ctx)
        command.execute()
        new_dataset = project.find_item(command.result_dataset_id)
        app_context.get_app_state.return_value.event_bus.emit.assert_any_call(
            ProjectEvents.PROJECT_ITEM_ADDED,
            {
                "project": project,
                "item_id": command.result_dataset_id,
                "item_type": "dataset",
                "item_name": new_dataset.name,
                "item": new_dataset,
                "folder_id": None,
            },
        )

    def test_undo_emits_the_generic_project_item_removed_event(self, ctx):
        app_context, project = ctx
        command = _cmd(ctx)
        command.execute()
        dataset_name = project.find_item(command.result_dataset_id).name
        command.undo()
        app_context.get_app_state.return_value.event_bus.emit.assert_any_call(
            ProjectEvents.PROJECT_ITEM_REMOVED,
            {
                "project": project,
                "item_id": command.result_dataset_id,
                "item_type": "dataset",
                "item_name": dataset_name,
            },
        )

    def test_dataset_is_created_in_the_given_folder(self, ctx):
        app_context, project = ctx
        folder = Folder(id="folder-1", name="Charts")
        project.add_item(folder)
        chart = project.find_item("chart-1")
        project.remove_item(chart)
        chart.parent_id = None
        project.add_item(chart, parent_id="folder-1")
        command = TransformChartSeriesCommand(
            app_context, "chart-1", source_kind="series", source_index=0,
            target="y", expression="y * 2", folder_id="folder-1",
        )
        assert command.execute() is CommandResult.SUCCESS
        new_dataset = project.find_item(command.result_dataset_id)
        assert new_dataset.parent_id == "folder-1"

    def test_emitted_folder_id_falls_back_to_none_when_the_requested_folder_is_gone(self, ctx):
        """project.add_item() silently places the dataset at the project
        root if folder_id no longer resolves to a real folder (e.g. the
        folder was deleted between an undo and a redo) -- the emitted
        event must report that as folder_id=None (the "no folder"
        convention), not the stale, now-nonexistent folder id."""
        app_context, project = ctx
        command = TransformChartSeriesCommand(
            app_context, "chart-1", source_kind="series", source_index=0,
            target="y", expression="y * 2", folder_id="no-such-folder",
        )
        assert command.execute() is CommandResult.SUCCESS
        new_dataset = project.find_item(command.result_dataset_id)
        assert new_dataset.parent_id != "no-such-folder"
        app_context.get_app_state.return_value.event_bus.emit.assert_any_call(
            ProjectEvents.PROJECT_ITEM_ADDED,
            {
                "project": project,
                "item_id": command.result_dataset_id,
                "item_type": "dataset",
                "item_name": new_dataset.name,
                "item": new_dataset,
                "folder_id": None,
            },
        )

    def test_dataset_name_gets_a_counter_suffix_when_it_collides(self, ctx):
        """Re-running the same transform twice (e.g. re-applying the panel
        with unchanged inputs) must not produce two indistinguishable
        datasets with the exact same name in the project explorer."""
        _, project = ctx
        first = _cmd(ctx, result_name="Doubled")
        assert first.execute() is CommandResult.SUCCESS
        second = _cmd(ctx, result_name="Doubled")
        assert second.execute() is CommandResult.SUCCESS

        first_dataset = project.find_item(first.result_dataset_id)
        second_dataset = project.find_item(second.result_dataset_id)
        assert first_dataset.name == "Doubled"
        assert second_dataset.name == "Doubled (2)"

    def test_dataset_name_counter_skips_names_already_taken(self, ctx):
        _, project = ctx
        project.add_item(Dataset(id="pre-existing-1", name="Doubled", data=pd.DataFrame({"a": [1]})))
        project.add_item(Dataset(id="pre-existing-2", name="Doubled (2)", data=pd.DataFrame({"a": [1]})))
        command = _cmd(ctx, result_name="Doubled")
        assert command.execute() is CommandResult.SUCCESS
        new_dataset = project.find_item(command.result_dataset_id)
        assert new_dataset.name == "Doubled (3)"

    def test_dataset_name_uniqueness_is_scoped_to_the_target_folder(self, ctx):
        """A same-named dataset in a *different* folder isn't a collision --
        only siblings of the newly created dataset are checked."""
        _, project = ctx
        folder = Folder(id="folder-1", name="Other Folder")
        project.add_item(folder)
        project.add_item(Dataset(id="elsewhere", name="Doubled", data=pd.DataFrame({"a": [1]})), parent_id="folder-1")
        command = _cmd(ctx, result_name="Doubled")
        assert command.execute() is CommandResult.SUCCESS
        new_dataset = project.find_item(command.result_dataset_id)
        assert new_dataset.name == "Doubled"
