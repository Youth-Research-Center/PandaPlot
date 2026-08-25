"""Tests for SignalAnalysisCommand."""

import logging
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest

from pandaplot.analysis import SignalAnalysisType
from pandaplot.commands.project.dataset.signal_analysis_command import SignalAnalysisCommand
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state import AppContext, AppState


@pytest.fixture
def app_context_with_project():
    fs = 1000

    t = np.linspace(
        0,
        1,
        fs,
        endpoint=False,
    )

    signal = np.sin(
        2 * np.pi * 50 * t
    )

    project = Project(name="P")

    dataset = Dataset(
        id="ds-1",
        name="Signal Data",
        data=pd.DataFrame(
            {
                "signal": signal,
            }
        ),
    )

    project.add_item(dataset)

    app_context = Mock(spec=AppContext)

    app_state = Mock(spec=AppState)
    app_state.has_project = True
    app_state.current_project = project
    app_state.event_bus = Mock()

    app_context.get_app_state.return_value = app_state
    app_context.event_bus = Mock()

    return app_context, project


class TestSignalAnalysisCommand:

    def test_execute_adds_fft_results_dataset(
        self,
        app_context_with_project,
    ):
        app_context, project = app_context_with_project

        command = SignalAnalysisCommand(
            app_context,
            "ds-1",
            SignalAnalysisType.FFT,
            "signal",
            sampling_rate=1000,
        )

        assert command.execute() is True

        results = project.find_item(
            command.result_dataset_id
        )

        assert results is not None

        assert "Frequency (Hz)" in results.data.columns
        assert "Amplitude" in results.data.columns


    def test_undo_removes_results_dataset(
        self,
        app_context_with_project,
    ):
        app_context, project = app_context_with_project

        command = SignalAnalysisCommand(
            app_context,
            "ds-1",
            SignalAnalysisType.PEAKS,
            "signal",
        )

        assert command.execute() is True

        new_id = command.result_dataset_id

        assert project.find_item(new_id) is not None

        assert command.undo() is True

        assert project.find_item(new_id) is None


    def test_missing_column_fails_gracefully(
        self,
        app_context_with_project,
    ):
        app_context, _ = app_context_with_project

        command = SignalAnalysisCommand(
            app_context,
            "ds-1",
            SignalAnalysisType.FFT,
            ["missing"],
            sampling_rate=1000,
        )

        assert command.execute() is False

        assert command.result_dataset_id is None
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()

    def test_undo_logs_a_warning_when_nothing_to_undo(
        self,
        app_context_with_project,
        caplog,
    ):
        app_context, _ = app_context_with_project

        command = SignalAnalysisCommand(
            app_context,
            "ds-1",
            SignalAnalysisType.PEAKS,
            "signal",
        )
        # undo() called without a prior successful execute(): result_dataset_id is None.

        with caplog.at_level(logging.WARNING):
            assert command.undo() is False
        assert "SignalAnalysisCommand.undo" in caplog.text

    def test_execute_surfaces_no_project_loaded_to_the_user(self):
        app_context = Mock(spec=AppContext)
        app_state = Mock(spec=AppState)
        app_state.has_project = False
        app_state.current_project = None
        app_context.get_app_state.return_value = app_state

        command = SignalAnalysisCommand(
            app_context, "ds-1", SignalAnalysisType.FFT, "signal", sampling_rate=1000,
        )
        assert command.execute() is False
        app_context.get_ui_controller.return_value.show_error_message.assert_called_once()