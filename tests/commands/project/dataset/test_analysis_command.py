"""Tests for AnalysisCommand: segment alignment, existing target, refresh events."""

from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.commands.project.dataset.analysis_command import AnalysisCommand
from pandaplot.models.events.event_types import DatasetEvents, DatasetOperationEvents
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def ctx():
    project = Project(name="P")
    x = np.linspace(0.0, 10.0, 11)
    dataset = Dataset(id="ds-1", name="Data", data=pd.DataFrame({"x": x, "y": x ** 2}))
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, project, dataset, app_state.event_bus


def _emitted(event_bus, event_name):
    """Return payloads emitted for a given event name."""
    return [
        call.args[1]
        for call in event_bus.emit.call_args_list
        if call.args and call.args[0] == event_name
    ]


class TestAnalysisCommand:
    def test_full_length_derivative_added(self, ctx):
        app_context, _, dataset, event_bus = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is True
        assert "dydx" in dataset.data.columns
        # d/dx of x^2 = 2x; check away from the noisy endpoints.
        assert dataset.data["dydx"].iloc[5] == pytest.approx(10.0, abs=0.1)
        assert dataset.data["dydx"].notna().all()

        added = _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)
        assert added and added[0]["column_positions"] == [2]

    def test_segment_result_aligns_to_source_rows(self, ctx):
        app_context, _, dataset, _ = ctx
        # Integrate only rows 3..7 (inclusive of 3, exclusive of 8).
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "integral", "x_column": "x", "y_column": "y",
            "new_column_name": "cum", "parameters": {"start_index": 3, "end_index": 8},
        })
        assert command.execute() is True

        col = dataset.data["cum"]
        # Values land on the segment's own rows, NaN everywhere else.
        assert col.iloc[:3].isna().all()
        assert col.iloc[8:].isna().all()
        assert col.iloc[3:8].notna().all()
        # Cumulative integral starts at 0 on the first segment row.
        assert col.iloc[3] == pytest.approx(0.0)

    def test_replace_existing_emits_data_changed(self, ctx):
        app_context, _, dataset, event_bus = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "y", "replace_existing": True,
        })
        assert command.execute() is True
        # 'y' was overwritten in place; no new column.
        assert list(dataset.data.columns) == ["x", "y"]

        changed = _emitted(event_bus, DatasetEvents.DATASET_DATA_CHANGED)
        assert changed and changed[0]["start_index"][1] == 1  # column index of 'y'
        assert not _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_ADDED)

    def test_dataset_not_found_is_surfaced_to_the_user(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "missing-ds", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_dataset_with_no_data_is_surfaced_to_the_user(self, ctx):
        app_context, _, dataset, _ = ctx
        dataset.data = None
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_existing_target_without_replace_fails(self, ctx):
        app_context, _, _, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "y", "replace_existing": False,
        })
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_analysis_engine_failure_is_surfaced_to_the_user(self, ctx, monkeypatch):
        app_context, _, _, _ = ctx
        monkeypatch.setattr(
            "pandaplot.commands.project.dataset.analysis_command.AnalysisEngine.calculate_derivative",
            Mock(side_effect=ValueError("boom")),
        )
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()
        title, message = app_context.get_ui_controller.return_value.show_error_message.call_args.args
        assert "boom" in message

    def test_undo_removes_added_column_and_emits(self, ctx):
        app_context, _, dataset, event_bus = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "derivative", "x_column": "x", "y_column": "y",
            "new_column_name": "dydx",
        })
        command.execute()
        assert command.undo() is True
        assert "dydx" not in dataset.data.columns
        assert _emitted(event_bus, DatasetOperationEvents.DATASET_COLUMN_REMOVED)

    def test_arc_length_line_on_plot(self, ctx):
        app_context, _, dataset, _ = ctx
        command = AnalysisCommand(app_context, "ds-1", {
            "analysis_type": "arc_length", "x_column": "x", "y_column": "y",
            "new_column_name": "arc",
        })
        assert command.execute() is True
        # Arc length is monotonically increasing and starts at 0.
        arc = dataset.data["arc"]
        assert arc.iloc[0] == pytest.approx(0.0)
        assert (arc.diff().dropna() >= 0).all()
