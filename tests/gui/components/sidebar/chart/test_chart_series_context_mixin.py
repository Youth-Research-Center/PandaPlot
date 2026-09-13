"""Tests for ChartSeriesContextMixin."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QComboBox, QWidget

from pandaplot.gui.components.sidebar.chart.chart_series_context_mixin import (
    ChartSeriesContextMixin,
)
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project
from pandaplot.models.state.app_context import AppContext
from pandaplot.models.state.app_state import AppState


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


class _FakeContextPanel(SidebarPanel, ChartSeriesContextMixin):
    """Minimal concrete SidebarPanel + ChartSeriesContextMixin, for testing
    the mixin's event handlers in isolation from any real panel's UI."""

    def __init__(self, app_context):
        self.current_chart = None
        self.current_chart_id = None
        self.source_combo = QComboBox()
        self.populate_calls = 0
        self.refresh_calls = 0
        super().__init__(app_context=app_context)

    def _init_ui(self):
        self._init_panel_layout()
        self._set_title("Test")
        self._set_content(QWidget())

    def _apply_theme(self):
        pass

    def setup_event_subscriptions(self):
        self.setup_chart_series_context_subscriptions()

    def _populate_sources(self):
        self.populate_calls += 1

    def _refresh_chart_references(self):
        self.refresh_calls += 1


@pytest.fixture
def project():
    project = Project(name="P")
    project.add_item(Chart(id="chart-1", name="C"))
    project.add_item(Chart(id="chart-2", name="Other"))
    return project


@pytest.fixture
def app_context(project):
    ctx = Mock(spec=AppContext)
    ctx.event_bus = Mock()
    app_state = Mock(spec=AppState)
    app_state.current_project = project
    ctx.get_app_state.return_value = app_state
    return ctx


@pytest.fixture
def panel(app_context):
    return _FakeContextPanel(app_context)


class TestOnTabChanged:
    def test_switching_to_a_chart_tab_sets_current_chart_and_populates(self, panel, project):
        panel._on_tab_changed({"tab_type": "chart", "tab_id": "chart-1"})

        assert panel.current_chart is project.find_item("chart-1")
        assert panel.current_chart_id == "chart-1"
        assert panel.populate_calls == 1

    def test_switching_to_a_non_chart_tab_clears_current_chart(self, panel):
        panel._on_tab_changed({"tab_type": "chart", "tab_id": "chart-1"})

        panel._on_tab_changed({"tab_type": "dataset", "tab_id": "ds-1"})

        assert panel.current_chart is None
        assert panel.current_chart_id is None
        assert panel.populate_calls == 2


class TestOnChartUpdated:
    def test_update_for_the_current_chart_repopulates(self, panel, project):
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"

        panel._on_chart_updated({"chart": panel.current_chart})

        assert panel.populate_calls == 1
        assert panel.refresh_calls == 0

    def test_update_for_a_different_chart_refreshes_references_only(self, panel, project):
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"
        other = project.find_item("chart-2")

        panel._on_chart_updated({"chart": other})

        assert panel.populate_calls == 0
        assert panel.refresh_calls == 1

    def test_chart_id_only_payload_resolves_the_current_chart_from_the_project(self, panel, project):
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"

        panel._on_chart_updated({"chart_id": "chart-1"})

        assert panel.populate_calls == 1

    def test_chart_id_only_payload_for_a_different_chart_refreshes_references(self, panel, project):
        panel.current_chart = project.find_item("chart-1")
        panel.current_chart_id = "chart-1"

        panel._on_chart_updated({"chart_id": "chart-2"})

        assert panel.populate_calls == 0
        assert panel.refresh_calls == 1

    def test_no_chart_and_no_resolvable_chart_id_does_nothing(self, panel):
        panel._on_chart_updated({})

        assert panel.populate_calls == 0
        assert panel.refresh_calls == 0


class TestOnChartListChanged:
    def test_refreshes_chart_references(self, panel):
        panel._on_chart_list_changed({"item_id": "chart-2"})

        assert panel.refresh_calls == 1


class TestOnSeriesSelectedEvent:
    def test_selects_matching_combo_row(self, panel):
        panel.current_chart_id = "chart-1"
        panel.source_combo.addItem("Series 1", ("series", 0))
        panel.source_combo.addItem("Series 2", ("series", 1))
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event({"chart_id": "chart-1", "kind": "series", "index": 1})

        assert panel.source_combo.currentData() == ("series", 1)

    def test_ignores_event_for_a_different_chart(self, panel):
        panel.current_chart_id = "chart-1"
        panel.source_combo.addItem("Series 1", ("series", 0))
        panel.source_combo.setCurrentIndex(0)

        panel._on_series_selected_event({"chart_id": "other", "kind": "series", "index": 0})

        assert panel.source_combo.currentIndex() == 0
