"""Smoke tests for FitPanel construction.

FitPanel moved its `apply_button`/`fit_button`/`clear_button` `.clicked.connect(...)`
calls into the constructor via PButton's `on_click=`/`enabled=` params. That made
construction order matter: `fit_button` is built with `enabled=self.scipy_available`,
which requires `self.scipy_available` to already be assigned before
`_create_action_buttons` runs. Nothing previously constructed FitPanel in tests, so a
future construction-order regression (e.g. reordering the scipy check after UI setup)
would go unnoticed. These tests just build the panel and check the buttons exist.
"""
from unittest.mock import Mock

import numpy as np
import pandas as pd
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.commands.base_command import CommandResult
from pandaplot.commands.project.chart.apply_fit_command import ApplyFitCommand
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.sidebar.fit.fit_panel import CUSTOM_SERIES_SENTINEL, FitPanel
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.items.dataset import Dataset
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.fit.fit_service import FitResult


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def app_context():
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    return ctx


@pytest.fixture
def fit_panel(app_context):
    return FitPanel(app_context)


def test_fit_panel_constructs_with_expected_buttons(fit_panel):
    assert isinstance(fit_panel.fit_button, PButton)
    assert isinstance(fit_panel.apply_button, PButton)
    assert isinstance(fit_panel.clear_button, PButton)


def test_fit_button_enabled_state_matches_scipy_availability(app_context):
    # Directly covers the construction-order-sensitive `enabled=self.scipy_available`
    # retrofit: fit_button's enabled state must reflect scipy_available as computed
    # at construction time, not some later/default value.
    #
    # A valid series with enough data points must be loaded first: the fit
    # button is also gated on data availability (see
    # test_fit_button_disabled_when_data_is_insufficient), so with no chart
    # loaded the button is disabled regardless of scipy_available.
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    assert panel.fit_button.isEnabled() == panel.scipy_available


def test_fit_button_disabled_when_data_is_insufficient(fit_panel):
    assert fit_panel.fit_button.isEnabled() is False


def test_apply_button_starts_disabled(fit_panel):
    assert fit_panel.apply_button.isEnabled() is False


def test_clear_button_click_invokes_clear_results(app_context):
    panel = FitPanel(app_context)
    panel.results_text.setPlainText("some results")

    panel.clear_button.click()

    assert panel.results_text.toPlainText() == ""


def _make_dataset_and_chart_with_id_only_series():
    """Build a Dataset + Chart whose series references columns only via ids.

    This mirrors what the wizard / "+Add series" actually produce: the
    legacy ``x_column``/``y_column`` name fields are left empty, and only
    ``x_column_id``/``y_column_id`` are populated.
    """
    df = pd.DataFrame({"time": [1, 2, 3, 4], "value": [10, 20, 30, 40]})
    dataset = Dataset(id="ds-1", name="dataset", data=df)
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("value")
    assert x_id is not None
    assert y_id is not None

    chart = Chart(id="chart-1", name="chart")
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id)
    return dataset, chart


def _make_fake_fit_result():
    return FitResult(
        fit_type="Linear",
        parameters=np.array([1.0, 0.0]),
        errors=np.array([0.1, 0.1]),
        param_names=["a", "b"],
        params={"a": 1.0, "b": 0.0},
        r_squared=0.99,
        x_fit=np.array([1.0, 2.0]),
        y_fit=np.array([1.0, 2.0]),
        x_data=np.array([1.0, 2.0]),
        y_data=np.array([1.0, 2.0]),
        covariance=np.eye(2),
    )


def test_get_current_data_resolves_id_only_series(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    result = panel.get_current_data()

    assert result is not None
    df, mask, x_data, y_data, series = result
    assert len(x_data) == 4
    assert len(y_data) == 4


def test_load_chart_object_clears_stale_fit_results_across_charts(app_context):
    dataset, chart_a = _make_dataset_and_chart_with_id_only_series()
    _, chart_b = _make_dataset_and_chart_with_id_only_series()
    chart_b.id = "chart-2"

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart_a)

    panel.fit_results = _make_fake_fit_result()
    panel.apply_button.setEnabled(True)

    panel.load_chart_object(chart_b)

    assert panel.fit_results is None
    assert panel.apply_button.isEnabled() is False


def test_load_chart_object_calls_get_current_data_exactly_once(app_context):
    """Regression test (PR review): populating series_combo in
    load_chart_object() used to fire currentIndexChanged mid-update (via
    clear()/addItem()), triggering get_current_data() multiple times for
    the same load and producing duplicate/misleading log warnings for one
    state change. blockSignals() fixed it; this pins the fix down so a
    regression (e.g. removing blockSignals, or moving the explicit
    _on_series_changed() call back inside an `if count() > 0` guard) fails
    a test instead of silently reintroducing the duplicate calls."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    call_count = 0
    original_get_current_data = panel.get_current_data

    def _counting_get_current_data():
        nonlocal call_count
        call_count += 1
        return original_get_current_data()

    panel.get_current_data = _counting_get_current_data

    panel.load_chart_object(chart)

    assert call_count == 1


def test_current_project_reflects_app_state_without_explicit_sync(app_context):
    """`current_project` must be a live read of app_state, not a cache that
    needs an explicit setter call to stay in sync (see issue #246 follow-up:
    every real call site was already re-deriving the same value moments
    later via load_chart_object, making the old set_project() cache
    write-only and pointless)."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    project_a = Mock()
    project_a.find_item = Mock(return_value=dataset)
    project_b = Mock()
    project_b.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project_a
    panel.load_chart_object(chart)

    assert panel.current_project is project_a

    # Swap the project directly on app_state, with no set_project() call.
    panel.app_context.app_state.current_project = project_b

    assert panel.current_project is project_b


def test_get_current_data_returns_none_when_project_goes_away(app_context):
    """A project that disappears out from under an already-loaded chart
    (e.g. project closed) must make get_current_data() return None, even
    though series_combo still has a selected series -- proving there's no
    stale cached project keeping stale data usable."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    assert panel.get_current_data() is not None  # sanity check: data loads fine first

    panel.app_context.app_state.current_project = None

    assert panel.series_combo.currentData() is not None  # series selection untouched
    assert panel.get_current_data() is None


def test_apply_fit_resolves_id_only_series_columns(app_context):
    """`_apply_fit` must resolve the id-only series' columns via
    `resolve_series_column` (not read the empty legacy name fields directly),
    and must carry the raw column ids through to the `ApplyFitCommand` it
    executes alongside the resolved names, so downstream axis/series pairing
    in chart_editor (which matches by column name) doesn't misattribute the
    fit to the wrong series when several id-only series share empty legacy
    names.
    """
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    series = chart.data_series[0]

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.fit_results = _make_fake_fit_result()

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    panel._apply_fit()

    command = executed["command"]
    assert isinstance(command, ApplyFitCommand)
    assert command.source_dataset_id == series.dataset_id
    assert command.source_x_column == "time"
    assert command.source_y_column == "value"
    assert command.source_x_column_id == series.x_column_id
    assert command.source_y_column_id == series.y_column_id


def test_on_tab_changed_skips_work_while_panel_not_visible(app_context):
    """Regression test for issue #246: FitPanel must not do get_current_data()
    work (via load_chart_object) on tab-change events while it isn't the
    visible sidebar panel."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: chart if item_id == chart.id else dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    assert panel.isVisible() is False

    panel._on_tab_changed({"tab_type": "chart", "tab_id": chart.id})

    assert panel.current_chart is None
    assert panel.series_combo.count() == 0


def test_on_tab_changed_resyncs_when_panel_becomes_visible(app_context):
    """The tab-change event skipped while hidden must be replayed once the
    panel is shown again, so its context catches up."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: chart if item_id == chart.id else dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    panel._on_tab_changed({"tab_type": "chart", "tab_id": chart.id})
    assert panel.current_chart is None

    panel.show()
    QApplication.processEvents()

    assert panel.current_chart is not None
    assert panel.current_chart.id == chart.id
    # +1 for the always-present "Custom..." sentinel entry.
    assert panel.series_combo.count() == len(chart.data_series) + 1

    panel.close()


def test_on_chart_updated_skips_work_while_panel_not_visible(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    assert panel.isVisible() is False

    panel._on_chart_updated({"chart": chart})

    assert panel.current_chart is None
    assert panel.series_combo.count() == 0


def test_reshowing_panel_without_new_tab_change_preserves_fit_results(app_context):
    """Regression test: showEvent must not replay a tab-change event that
    was already applied while the panel was visible -- otherwise switching
    to another sidebar panel and back would silently wipe completed fit
    results even though nothing changed while the Fit panel was hidden."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: chart if item_id == chart.id else dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    panel.show()
    QApplication.processEvents()

    panel._on_tab_changed({"tab_type": "chart", "tab_id": chart.id})
    panel.fit_results = _make_fake_fit_result()
    panel.apply_button.setEnabled(True)

    # Simulate switching to another sidebar panel and back -- no new
    # tab-change event occurs in between.
    panel.hide()
    QApplication.processEvents()
    panel.show()
    QApplication.processEvents()

    assert panel.fit_results is not None
    assert panel.apply_button.isEnabled() is True

    panel.close()


def test_chart_updated_while_hidden_refreshes_chart_on_show(app_context):
    """A chart update skipped while the panel is hidden -- with no
    tab-change event at all in this scenario, pending or otherwise -- must
    still be picked up once the panel becomes visible again. Seeds context
    via load_chart_object() directly (not _on_tab_changed) so this only
    exercises the chart-refresh path, not the tab-change-replay path."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: chart if item_id == chart.id else dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    panel.load_chart_object(chart)
    panel.show()
    QApplication.processEvents()
    panel.hide()
    QApplication.processEvents()

    # Chart gains a second series while the panel is hidden; find_item
    # keeps returning the same (mutated) chart object.
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("value")
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id, label="second series")

    panel._on_chart_updated({"chart": chart})
    # +1 for the always-present "Custom..." sentinel entry.
    assert panel.series_combo.count() == 2  # not yet refreshed while hidden

    panel.show()
    QApplication.processEvents()

    assert panel.series_combo.count() == 3

    panel.close()


def test_chart_updated_for_unrelated_chart_while_hidden_does_not_trigger_refresh(app_context):
    """Regression test: a CHART_UPDATED event for some *other* chart while
    the Fit panel is hidden must not mark a refresh as owed -- otherwise an
    unrelated chart edit elsewhere would cause the panel to reload its own
    chart (wiping fit results) the next time it's shown, for no reason."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    _, other_chart = _make_dataset_and_chart_with_id_only_series()
    other_chart.id = "chart-2"

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: chart if item_id == chart.id else dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    panel.load_chart_object(chart)
    panel.fit_results = _make_fake_fit_result()
    panel.apply_button.setEnabled(True)

    panel.show()
    QApplication.processEvents()
    panel.hide()
    QApplication.processEvents()

    panel._on_chart_updated({"chart": other_chart})
    assert panel._needs_chart_refresh is False

    panel.show()
    QApplication.processEvents()

    assert panel.fit_results is not None
    assert panel.apply_button.isEnabled() is True

    panel.close()


def test_on_series_changed_clears_stale_fit_results_within_same_chart(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("value")
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id, label="second series")

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.fit_results = _make_fake_fit_result()
    panel.apply_button.setEnabled(True)

    panel.series_combo.setCurrentIndex(1)

    assert panel.fit_results is None
    assert panel.apply_button.isEnabled() is False


def test_range_controls_start_in_auto_mode(fit_panel):
    # isHidden() reflects each widget's own explicit hide state, unlike
    # isVisible() which is always False for a widget whose top-level
    # ancestor has never been shown -- so this works without panel.show().
    assert fit_panel.range_auto_check.isChecked() is True
    assert fit_panel.range_min_spin.isHidden() is True
    assert fit_panel.range_max_spin.isHidden() is True
    assert fit_panel.range_min_value_label.isHidden() is False
    assert fit_panel.range_max_value_label.isHidden() is False


def test_unchecking_auto_enables_range_spinboxes_and_seeds_data_range(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.range_auto_check.setChecked(False)

    assert panel.range_min_spin.isHidden() is False
    assert panel.range_max_spin.isHidden() is False
    assert panel.range_min_value_label.isHidden() is True
    assert panel.range_max_value_label.isHidden() is True
    assert panel.range_min_spin.value() == 1.0  # min of the "time" column [1, 2, 3, 4]
    assert panel.range_max_spin.value() == 4.0  # max of the "time" column


def test_changing_series_resets_range_to_auto(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("value")
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id, label="second series")

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(-5.0)
    panel.range_max_spin.setValue(10.0)

    panel.series_combo.setCurrentIndex(1)

    assert panel.range_auto_check.isChecked() is True
    assert panel.range_min_spin.isHidden() is True
    assert panel.range_max_spin.isHidden() is True


def test_loading_a_new_chart_resets_range_to_auto(app_context):
    dataset, chart_a = _make_dataset_and_chart_with_id_only_series()
    _, chart_b = _make_dataset_and_chart_with_id_only_series()
    chart_b.id = "chart-2"

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart_a)

    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(-5.0)
    panel.range_max_spin.setValue(10.0)

    panel.load_chart_object(chart_b)

    assert panel.range_auto_check.isChecked() is True
    assert panel.range_min_spin.isHidden() is True
    assert panel.range_max_spin.isHidden() is True


def test_non_positive_min_invalid_for_logarithmic_fit(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.show()
    QApplication.processEvents()

    panel.fit_type_combo.setCurrentText("Logarithmic (y = a*ln(x) + b)")
    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(0.0)
    panel.range_max_spin.setValue(10.0)

    assert panel.fit_button.isEnabled() is False
    assert panel.range_warning_label.isVisible() is True

    panel.close()


def test_non_positive_min_valid_for_linear_fit(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.fit_type_combo.setCurrentText("Linear (y = ax + b)")
    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(-5.0)
    panel.range_max_spin.setValue(10.0)

    assert panel.fit_button.isEnabled() is True
    assert panel.range_warning_label.isVisible() is False


def test_invalid_range_disables_fit_button_and_shows_warning(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    # isVisible() only reflects the widget's own setVisible() flag once the
    # panel itself has actually been shown (Qt reports False for any
    # descendant of a never-shown top-level regardless of its own flag).
    panel.show()
    QApplication.processEvents()

    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(10.0)
    panel.range_max_spin.setValue(5.0)

    assert panel.fit_button.isEnabled() is False
    assert panel.range_warning_label.isVisible() is True

    panel.close()


def test_perform_fit_passes_custom_range_to_command(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(-5.0)
    panel.range_max_spin.setValue(10.0)

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    panel._perform_fit()

    command = executed["command"]
    assert command.x_min == -5.0
    assert command.x_max == 10.0


def test_perform_fit_passes_none_range_when_auto(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    panel._perform_fit()

    command = executed["command"]
    assert command.x_min is None
    assert command.x_max is None


def test_auto_range_labels_show_current_series_data_range(app_context):
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    assert panel.range_min_value_label.text() == "1"  # min of the "time" column [1, 2, 3, 4]
    assert panel.range_max_value_label.text() == "4"  # max of the "time" column


def test_auto_range_labels_refresh_on_series_change(app_context):
    """Regression test: the disabled spinboxes used before this feature's
    labels never refreshed once Auto was re-enabled (e.g. after applying a
    fit, or on a tab/series change) -- they just kept showing whatever
    value was last typed. The read-only labels must always reflect the
    currently selected series' real data range instead."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()
    y_id = dataset.column_id("value")
    dataset.set_data(dataset.data.assign(time2=[100, 200, 300, 400]))
    chart.add_data_series(dataset_id=dataset.id, x_column_id=dataset.column_id("time2"), y_column_id=y_id, label="second series")

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    assert panel.range_min_value_label.text() == "1"
    assert panel.range_max_value_label.text() == "4"

    panel.series_combo.setCurrentIndex(1)

    assert panel.range_min_value_label.text() == "100"
    assert panel.range_max_value_label.text() == "400"


def test_auto_range_labels_refresh_after_reapplying_tab_change(app_context):
    """Regression test: switching chart tabs (via _apply_tab_change ->
    load_chart_object) must refresh the Auto-mode range labels to the new
    chart's data, not leave the previous chart's range on screen."""
    dataset, chart_a = _make_dataset_and_chart_with_id_only_series()
    dataset.set_data(dataset.data.assign(time2=[100, 200, 300, 400]))
    y_id = dataset.column_id("value")
    chart_b = Chart(id="chart-2", name="chart-b")
    chart_b.add_data_series(dataset_id=dataset.id, x_column_id=dataset.column_id("time2"), y_column_id=y_id)

    project = Mock()
    project.find_item = Mock(side_effect=lambda item_id: {
        "chart-1": chart_a, "chart-2": chart_b,
    }.get(item_id, dataset))
    chart_a.id = "chart-1"

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project

    panel._apply_tab_change({"tab_type": "chart", "tab_id": "chart-1"})
    assert panel.range_min_value_label.text() == "1"
    assert panel.range_max_value_label.text() == "4"

    panel._apply_tab_change({"tab_type": "chart", "tab_id": "chart-2"})
    assert panel.range_min_value_label.text() == "100"
    assert panel.range_max_value_label.text() == "400"


def test_auto_range_label_resets_after_applying_fit(app_context):
    """Regression test: ApplyFitCommand emits CHART_UPDATED, which reloads
    the chart into the panel (resetting Auto per _on_series_changed). The
    Auto-mode labels must reflect the (possibly changed) data at that point
    too, not a stale value left over from before the reload."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.range_auto_check.setChecked(False)
    panel.range_min_spin.setValue(-5.0)
    panel.range_max_spin.setValue(10.0)

    # Simulate what ApplyFitCommand's CHART_UPDATED handler does: reload the
    # same chart object fresh, as _on_chart_updated -> load_chart_object would.
    panel.load_chart_object(chart)

    assert panel.range_auto_check.isChecked() is True
    assert panel.range_min_value_label.text() == "1"
    assert panel.range_max_value_label.text() == "4"


def _make_dataset_and_chart_with_all_nan_y():
    """Build a Dataset + Chart whose y column is entirely NaN, so
    get_current_data()'s NaN mask filters out every row -- x_data/y_data
    both come back empty (len 0)."""
    df = pd.DataFrame({"time": [1, 2, 3, 4], "value": [float("nan")] * 4})
    dataset = Dataset(id="ds-nan", name="dataset", data=df)
    x_id = dataset.column_id("time")
    y_id = dataset.column_id("value")

    chart = Chart(id="chart-nan", name="chart")
    chart.add_data_series(dataset_id=dataset.id, x_column_id=x_id, y_column_id=y_id)
    return dataset, chart


def test_unchecking_auto_with_no_valid_data_points_does_not_crash(app_context):
    """Regression test: get_current_data() can return an empty x_data array
    when every row is NaN-masked out. Unchecking Auto used to call
    x_data.min()/max() unconditionally, which raises ValueError on an empty
    numpy array and would crash the panel."""
    dataset, chart = _make_dataset_and_chart_with_all_nan_y()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    panel.range_auto_check.setChecked(False)  # must not raise

    assert panel.range_min_spin.isHidden() is False
    assert panel.range_max_spin.isHidden() is False


def _make_project_with_two_datasets_and_series_on_first():
    """A real Project with two datasets: `chart`'s only real series sources
    from `dataset_a`; `dataset_b` is never referenced by any series, so it
    only shows up in the Custom picker if that picker lists every dataset
    in the project (not just ones already on the chart -- see issue #274).
    """
    project = Project(name="Custom Source Project")

    df_a = pd.DataFrame({"time": [1, 2, 3, 4], "value": [10, 20, 30, 40]})
    dataset_a = Dataset(name="dataset-a", data=df_a)
    project.add_item(dataset_a)

    df_b = pd.DataFrame({"t2": [5, 6, 7, 8], "v2": [1.0, 2.0, 3.0, 4.0]})
    dataset_b = Dataset(name="dataset-b", data=df_b)
    project.add_item(dataset_b)

    chart = Chart(id="chart-1", name="chart")
    chart.add_data_series(
        dataset_id=dataset_a.id,
        x_column_id=dataset_a.column_id("time"),
        y_column_id=dataset_a.column_id("value"),
    )
    project.add_item(chart)

    return project, dataset_a, dataset_b, chart


def _select_custom_source(panel, dataset, x_column, y_column):
    """Select "Custom..." and configure its dataset/X/Y combos."""
    custom_index = panel.series_combo.findData(CUSTOM_SERIES_SENTINEL)
    panel.series_combo.setCurrentIndex(custom_index)

    dataset_index = panel.custom_dataset_combo.findData(dataset.id)
    panel.custom_dataset_combo.setCurrentIndex(dataset_index)

    x_index = panel.custom_x_column_combo.findData(dataset.column_id(x_column))
    panel.custom_x_column_combo.setCurrentIndex(x_index)

    y_index = panel.custom_y_column_combo.findData(dataset.column_id(y_column))
    panel.custom_y_column_combo.setCurrentIndex(y_index)


def test_series_combo_gets_custom_sentinel_entry_when_chart_loaded(app_context):
    project, _dataset_a, _dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    last_index = panel.series_combo.count() - 1
    assert panel.series_combo.itemData(last_index) == CUSTOM_SERIES_SENTINEL
    assert panel.series_combo.itemText(last_index) == "Custom..."


def test_no_chart_leaves_series_combo_empty(app_context):
    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = None
    panel.load_chart_object(None)

    assert panel.series_combo.count() == 0


def test_clearing_chart_after_custom_selected_hides_custom_widget(app_context):
    """Regression test (PR review): load_chart_object(None) clears the
    combo and returns early, before _on_series_changed() would normally run
    to hide custom_source_widget -- it must hide the widget itself instead,
    otherwise switching away from a chart tab with "Custom..." selected
    left the picker visible with no chart (or selection) backing it."""
    project, dataset_a, _dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    _select_custom_source(panel, dataset_a, "time", "value")
    assert panel.custom_source_widget.isHidden() is False

    panel.load_chart_object(None)

    assert panel.custom_source_widget.isHidden() is True


def test_custom_source_widget_hidden_until_custom_selected(app_context):
    project, dataset_a, _dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    assert panel.custom_source_widget.isHidden() is True

    _select_custom_source(panel, dataset_a, "time", "value")

    assert panel.custom_source_widget.isHidden() is False


def test_selecting_custom_populates_dataset_combo_with_every_project_dataset(app_context):
    project, dataset_a, dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    custom_index = panel.series_combo.findData(CUSTOM_SERIES_SENTINEL)
    panel.series_combo.setCurrentIndex(custom_index)

    dataset_ids = {
        panel.custom_dataset_combo.itemData(i)
        for i in range(panel.custom_dataset_combo.count())
    }
    assert dataset_ids == {dataset_a.id, dataset_b.id}


def test_get_current_data_uses_custom_source_when_selected(app_context):
    project, _dataset_a, dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    _select_custom_source(panel, dataset_b, "t2", "v2")

    result = panel.get_current_data()

    assert result is not None
    df, mask, x_data, y_data, series = result
    assert series.dataset_id == dataset_b.id
    assert list(x_data) == [5, 6, 7, 8]
    assert list(y_data) == [1.0, 2.0, 3.0, 4.0]


def test_resolve_selected_series_returns_none_when_custom_selection_incomplete(app_context):
    project, dataset_a, _dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    custom_index = panel.series_combo.findData(CUSTOM_SERIES_SENTINEL)
    panel.series_combo.setCurrentIndex(custom_index)
    # Dataset gets auto-selected by _populate_custom_dataset_combo, but X/Y
    # default to whatever _populate_custom_column_combos seeds (dataset_a's
    # own first two columns) -- clear them to simulate an incomplete pick.
    panel.custom_x_column_combo.setCurrentIndex(-1)
    panel.custom_y_column_combo.setCurrentIndex(-1)

    assert panel.get_current_data() is None


def test_apply_fit_uses_custom_source_dataset_and_columns(app_context):
    project, _dataset_a, dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    _select_custom_source(panel, dataset_b, "t2", "v2")

    panel.fit_results = _make_fake_fit_result()

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    panel._apply_fit()

    command = executed["command"]
    assert isinstance(command, ApplyFitCommand)
    assert command.source_dataset_id == dataset_b.id
    assert command.source_x_column == "t2"
    assert command.source_y_column == "v2"


def test_switching_back_to_real_series_hides_custom_widget(app_context):
    project, dataset_a, _dataset_b, chart = _make_project_with_two_datasets_and_series_on_first()

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    _select_custom_source(panel, dataset_a, "time", "value")
    assert panel.custom_source_widget.isHidden() is False

    panel.series_combo.setCurrentIndex(0)

    assert panel.custom_source_widget.isHidden() is True


def _build_panel_ready_to_fit(app_context):
    """Build a FitPanel loaded with a chart/series that has enough data
    points and a mocked `execute_command` that captures the dispatched
    `PerformFitCommand` and returns True (simulating a successful async
    dispatch)."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    return panel, executed


def test_perform_fit_discards_stale_result_after_chart_switch(app_context):
    """Regression test (PR review): chart/series navigation stays enabled
    while a fit computes in the background. If the user switches to a
    different chart/series before the result comes back, installing it into
    fit_results/apply_button would silently attach the wrong chart's fit
    data to whatever is now selected."""
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()
    command = executed["command"]

    # Switch to a different chart while the fit is still "running".
    other_dataset, other_chart = _make_dataset_and_chart_with_id_only_series()
    other_chart.id = "chart-2"
    panel.app_context.app_state.current_project.find_item = Mock(return_value=other_dataset)
    panel.load_chart_object(other_chart)

    command.result = _make_fake_fit_result()
    command.fixed_parameters = None
    command.on_complete(CommandResult.SUCCESS)

    # The stale result must not have been installed over the new context.
    assert panel.fit_results is None
    assert panel.apply_button.isEnabled() is False
    # But the panel isn't stuck busy either -- the fit did finish, just for
    # a context that's no longer current.
    assert panel.busy_spinner.is_running is False
    assert panel.fit_button.isEnabled() is True


def test_perform_fit_success_path_populates_results_and_stops_spinner(app_context):
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()

    command = executed["command"]
    assert panel.busy_spinner.is_running is True
    assert panel.fit_button.isEnabled() is False

    command.result = _make_fake_fit_result()
    command.fixed_parameters = None
    command.on_complete(CommandResult.SUCCESS)

    assert panel.busy_spinner.is_running is False
    assert panel.fit_button.isEnabled() is True
    assert panel.apply_button.isEnabled() is True
    assert panel.fit_results is command.result
    assert panel.equation_label.text() == (command.result.equation or "No equation")
    assert "Fit Type: Linear" in panel.results_text.toPlainText()


def test_perform_fit_is_a_no_op_while_a_fit_is_already_pending(app_context):
    """Regression test (PR review): update_data_points_display() (fired by
    unrelated range/series-change signals) re-enables fit_button based only
    on data validity, not on whether a fit is already running -- so a click
    reaching _perform_fit() must still be rejected while a fit is pending,
    even if the button looked clickable."""
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()
    first_command = executed["command"]
    assert panel._pending_fit_command is first_command

    # Simulate the button having been (incorrectly) re-enabled by an
    # unrelated handler while the first fit is still in flight.
    panel.fit_button.setEnabled(True)

    second_attempted = {}

    def _capture_second(command):
        second_attempted["command"] = command
        return True

    panel.app_context.get_command_executor.return_value.execute_command = _capture_second
    panel._perform_fit()

    assert "command" not in second_attempted  # no second dispatch happened
    assert panel._pending_fit_command is first_command  # first reference untouched


def test_update_data_points_display_keeps_fit_button_disabled_while_pending(app_context):
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()
    assert panel._pending_fit_command is not None

    panel.update_data_points_display()

    assert panel.fit_button.isEnabled() is False


def test_perform_fit_disables_apply_while_a_refit_is_in_flight(app_context):
    """Regression test (PR review): Apply must not stay enabled -- bound to
    the *previous* fit_results -- while a new fit is still computing in the
    background, or clicking it mid-flight would silently commit stale data."""
    panel, executed = _build_panel_ready_to_fit(app_context)

    # A previous fit already succeeded, so Apply starts out enabled and
    # fit_results points at the first result.
    panel._perform_fit()
    first_command = executed["command"]
    first_command.result = _make_fake_fit_result()
    first_command.fixed_parameters = None
    first_command.on_complete(CommandResult.SUCCESS)
    assert panel.apply_button.isEnabled() is True
    first_result = panel.fit_results

    # Trigger a second fit; while it's in flight, Apply must be disabled so
    # it can't commit `first_result` again under the user's belief they're
    # applying the fit they just requested.
    panel._perform_fit()

    assert panel.apply_button.isEnabled() is False
    assert panel.fit_results is first_result  # unchanged until the new fit completes


def test_perform_fit_sync_dispatch_failure_restores_previous_apply_state(app_context):
    """A dispatch failure (e.g. a fit already in progress) never reaches
    on_complete, so the previous fit is still valid -- Apply's enabled state
    must be restored to what it was, not left disabled."""
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()
    first_command = executed["command"]
    first_command.result = _make_fake_fit_result()
    first_command.fixed_parameters = None
    first_command.on_complete(CommandResult.SUCCESS)
    assert panel.apply_button.isEnabled() is True

    panel.app_context.get_command_executor.return_value.execute_command = lambda command: False

    panel._perform_fit()

    assert panel.apply_button.isEnabled() is True


def test_perform_fit_failure_path_shows_error_and_stops_spinner(app_context):
    panel, executed = _build_panel_ready_to_fit(app_context)

    panel._perform_fit()

    command = executed["command"]
    command.error_message = "Fit did not converge"
    command.on_complete(CommandResult.FAILURE)

    assert panel.busy_spinner.is_running is False
    assert panel.fit_button.isEnabled() is True
    assert panel.apply_button.isEnabled() is False
    assert panel.fit_results is None
    assert panel.results_text.toPlainText() == "Fit did not converge"
    assert panel.results_text.styleSheet() == "color: red;"


def test_perform_fit_sync_dispatch_failure_stops_spinner_without_on_complete(app_context):
    """When execute_command() returns False (e.g. a fit already in
    progress), on_complete never fires -- _perform_fit itself must undo the
    spinner/button state it set before dispatching."""
    dataset, chart = _make_dataset_and_chart_with_id_only_series()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)

    executed = {}

    def _capture_execute(command):
        executed["command"] = command
        return False

    panel.app_context.get_command_executor.return_value.execute_command = _capture_execute

    panel._perform_fit()

    command = executed["command"]
    assert panel.busy_spinner.is_running is False
    assert panel.fit_button.isEnabled() is True
    assert panel._pending_fit_command is None
    # on_complete's effects (populating fit_results, enabling apply_button)
    # must not have happened -- it was never invoked.
    assert panel.fit_results is None
    assert panel.apply_button.isEnabled() is False
    assert command.result is None


def test_range_labels_show_placeholder_when_no_valid_data_points(app_context):
    """Regression test: the Auto-mode range labels must not crash (and
    should fall back to a placeholder) when the current series has no valid
    (x, y) points left after NaN masking."""
    dataset, chart = _make_dataset_and_chart_with_all_nan_y()

    project = Mock()
    project.find_item = Mock(return_value=dataset)

    panel = FitPanel(app_context)
    panel.app_context.app_state = Mock()
    panel.app_context.app_state.current_project = project
    panel.load_chart_object(chart)  # must not raise

    assert panel.range_min_value_label.text() == "—"
    assert panel.range_max_value_label.text() == "—"


class TestFitPanelSeriesSelectedEvent:
    """Clicking a data series on the chart canvas or its legend (#341,
    #107) should also select it here as the fit source; a fitted-curve
    click is ignored, since a fit isn't itself a valid source for a new
    fit."""

    def _make_two_series_chart(self):
        df = pd.DataFrame({"time": [1, 2, 3, 4], "value": [10, 20, 30, 40]})
        dataset = Dataset(id="ds-1", name="dataset", data=df)
        chart = Chart(id="chart-1", name="chart")
        chart.add_data_series(dataset_id=dataset.id, x_column="time", y_column="value", label="First")
        chart.add_data_series(dataset_id=dataset.id, x_column="time", y_column="value", label="Second")
        return dataset, chart

    def test_series_click_selects_matching_combo_row(self, app_context):
        dataset, chart = self._make_two_series_chart()
        project = Mock()
        project.find_item = Mock(return_value=dataset)

        panel = FitPanel(app_context)
        panel.show()
        panel.app_context.app_state = Mock()
        panel.app_context.app_state.current_project = project
        panel.load_chart_object(chart)
        panel.series_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "series", "index": 1}
        )

        assert panel.series_combo.currentIndex() == 1
        assert panel.series_combo.currentData() is chart.data_series[1]

    def test_fit_click_is_ignored(self, app_context):
        """A fit isn't a valid source for a new fit -- selection must not
        change."""
        dataset, chart = self._make_two_series_chart()
        project = Mock()
        project.find_item = Mock(return_value=dataset)

        panel = FitPanel(app_context)
        panel.show()
        panel.app_context.app_state = Mock()
        panel.app_context.app_state.current_project = project
        panel.load_chart_object(chart)
        panel.series_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "fit", "index": 0}
        )

        assert panel.series_combo.currentIndex() == 0

    def test_ignores_event_while_panel_is_hidden(self, app_context):
        dataset, chart = self._make_two_series_chart()
        project = Mock()
        project.find_item = Mock(return_value=dataset)

        panel = FitPanel(app_context)
        panel.app_context.app_state = Mock()
        panel.app_context.app_state.current_project = project
        panel.load_chart_object(chart)
        panel.series_combo.setCurrentIndex(0)

        assert panel.isVisible() is False
        panel._on_series_selected_event(
            {"chart_id": "chart-1", "kind": "series", "index": 1}
        )

        assert panel.series_combo.currentIndex() == 0

    def test_ignores_event_for_a_different_chart(self, app_context):
        dataset, chart = self._make_two_series_chart()
        project = Mock()
        project.find_item = Mock(return_value=dataset)

        panel = FitPanel(app_context)
        panel.show()
        panel.app_context.app_state = Mock()
        panel.app_context.app_state.current_project = project
        panel.load_chart_object(chart)
        panel.series_combo.setCurrentIndex(0)

        panel._on_series_selected_event(
            {"chart_id": "some-other-chart", "kind": "series", "index": 1}
        )

        assert panel.series_combo.currentIndex() == 0
