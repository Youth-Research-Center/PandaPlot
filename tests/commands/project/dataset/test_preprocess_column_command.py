"""Tests for PreprocessColumnCommand."""

import logging
from unittest.mock import Mock

import pandas as pd
import pytest

from pandaplot.commands.project.dataset.preprocess_column_command import (
    PreprocessColumnCommand,
)
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def app_context_with_project():
    project = Project(name="P")
    dataset = Dataset(
        id="ds-1",
        name="Data",
        data=pd.DataFrame({"A": [1.0, 2.0, 3.0, 4.0], "B": [10.0, 20.0, 30.0, 40.0]}),
    )
    project.add_item(dataset)

    app_context = Mock(spec=AppContext)
    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()
    app_context.get_app_state.return_value = app_state
    return app_context, project, dataset


class TestPreprocessColumnCommand:
    def test_execute_adds_standardized_column(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "standardize", "source_columns": ["A"]},
        )

        assert command.execute() is True
        assert "A_zscore" in dataset.data.columns
        assert dataset.data["A_zscore"].mean() == pytest.approx(0.0)
        assert dataset.data["A_zscore"].std(ddof=0) == pytest.approx(1.0)

    def test_execute_multiple_columns(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "center", "source_columns": ["A", "B"]},
        )

        assert command.execute() is True
        assert "A_centered" in dataset.data.columns
        assert "B_centered" in dataset.data.columns
        assert dataset.data["A_centered"].mean() == pytest.approx(0.0)
        assert dataset.data["B_centered"].mean() == pytest.approx(0.0)

    def test_undo_removes_created_columns(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        original_columns = list(dataset.data.columns)
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "minmax", "source_columns": ["A", "B"]},
        )
        command.execute()
        assert "A_minmax" in dataset.data.columns

        assert command.undo() is True
        assert list(dataset.data.columns) == original_columns

    def test_replace_existing_overwrites_source(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "standardize", "source_columns": ["A"], "replace_existing": True},
        )

        assert command.execute() is True
        assert list(dataset.data.columns) == ["A", "B"]
        assert dataset.data["A"].mean() == pytest.approx(0.0)

    def test_undo_restores_replaced_source(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        original = dataset.data["A"].copy()
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "standardize", "source_columns": ["A"], "replace_existing": True},
        )
        command.execute()

        assert command.undo() is True
        pd.testing.assert_series_equal(dataset.data["A"], original, check_names=False)

    def test_minmax_params_passed_through(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {
                "method": "minmax",
                "source_columns": ["A"],
                "params": {"range_min": -1.0, "range_max": 1.0},
            },
        )

        assert command.execute() is True
        assert dataset.data["A_minmax"].min() == pytest.approx(-1.0)
        assert dataset.data["A_minmax"].max() == pytest.approx(1.0)

    def test_dataset_not_found_is_surfaced_to_the_user(self, app_context_with_project):
        app_context, _, _ = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "missing-ds",
            {"method": "center", "source_columns": ["A"]},
        )
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_missing_column_fails(self, app_context_with_project):
        app_context, _, _ = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "center", "source_columns": ["Missing"]},
        )
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_non_numeric_column_fails(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        dataset.data["label"] = ["a", "b", "c", "d"]
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "center", "source_columns": ["label"]},
        )
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_existing_target_without_replace_fails(self, app_context_with_project):
        app_context, _, dataset = app_context_with_project
        dataset.data["A_centered"] = 0.0
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "center", "source_columns": ["A"]},
        )
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_undo_logs_a_warning_when_nothing_to_undo(self, app_context_with_project, caplog):
        app_context, _, _ = app_context_with_project
        command = PreprocessColumnCommand(
            app_context, "ds-1",
            {"method": "center", "source_columns": ["A"]},
        )
        # undo() called without a prior successful execute(): self.dataset is None.

        with caplog.at_level(logging.WARNING):
            assert command.undo() is False
        assert "ds-1" in caplog.text


def test_cleanup_releases_the_undo_state():
    app_context = Mock(spec=AppContext)

    command = PreprocessColumnCommand(app_context, "ds-1", {
        "method": "standardize", "source_columns": ["A"],
    })
    command._undo_state = [("A_zscore", True, pd.Series([1.0, 2.0, 3.0]))]

    command.cleanup()

    assert command._undo_state == []
