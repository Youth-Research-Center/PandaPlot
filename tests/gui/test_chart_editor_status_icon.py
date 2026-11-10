"""The chart editor status bar shows a check icon beside plain success messages instead of a trailing glyph."""

import pandas as pd
import pytest

from pandaplot.app import build_app_context
from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.icon_testing import ICON_TOKENS, assert_tinted, strongest_pixel

DARK_SUCCESS = "#3FB950"


@pytest.fixture
def tokens() -> dict[str, str]:
    return dict(ICON_TOKENS)


@pytest.fixture
def editor(qapp, monkeypatch, tokens):
    app_context = build_app_context()
    theme_manager = app_context.get_manager(ThemeManager)
    real_tokens = theme_manager.get_design_tokens
    monkeypatch.setattr(theme_manager, "get_design_tokens", lambda: {**real_tokens(), **tokens})
    project = Project(name="Test Project")
    dataset = Dataset(name="ds1", data=pd.DataFrame({"t": [1.0, 2.0, 3.0], "v": [10.0, 20.0, 30.0]}))
    project.add_item(dataset)
    chart = Chart(name="Test Chart", chart_type="line")
    chart.add_data_series(dataset.id, x_column="t", y_column="v", label="Series")
    project.add_item(chart)
    app_context.app_state.load_project(project)
    widget = ChartEditorWidget(app_context=app_context, chart=chart, parent=None)
    yield widget
    widget.deleteLater()


def test_status_icon_is_a_hidden_check_while_ready(editor):
    assert isinstance(editor.status_icon, IconLabel)
    assert editor.status_icon.icon_name == "check"
    assert editor.status_label.text() == "Ready"
    assert editor.status_icon.isHidden()


@pytest.mark.parametrize(
    ("action", "text"),
    [("_on_refresh", "Refreshed"), ("reset_chart", "Reset to defaults"), ("_on_swap_axes", "Swapped X and Y")],
)
def test_success_messages_are_plain_text_with_a_visible_check(editor, action, text):
    getattr(editor, action)()

    assert editor.status_label.text() == text
    assert not editor.status_icon.isHidden()


def test_check_is_hidden_again_when_the_status_returns_to_ready(editor):
    editor.update_status("Refreshed", success=True)
    assert not editor.status_icon.isHidden()

    editor.update_status("Ready")

    assert editor.status_icon.isHidden()


def test_non_success_status_hides_the_check(editor):
    editor.update_status("Refreshed", success=True)

    editor.update_status("Zoom reset")

    assert editor.status_icon.isHidden()


def test_status_icon_retints_when_the_theme_changes(editor, tokens):
    assert_tinted(strongest_pixel(editor.status_icon.pixmap().toImage()), ICON_TOKENS["status_success"])

    tokens["status_success"] = DARK_SUCCESS
    editor._apply_theme()

    assert_tinted(strongest_pixel(editor.status_icon.pixmap().toImage()), DARK_SUCCESS)
