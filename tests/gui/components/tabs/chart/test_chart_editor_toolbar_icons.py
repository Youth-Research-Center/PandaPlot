"""The chart editor's preview toolbar shows theme-tinted bundled icons instead of emoji prefixes."""

import re
from typing import Any

import pandas as pd
import pytest
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QToolBar

from pandaplot.app import build_app_context
from pandaplot.gui.components.tabs.chart.chart_editor import ChartEditorWidget
from pandaplot.gui.resources.icon_library import build_icon
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import Chart
from pandaplot.models.project.project import Project
from pandaplot.models.state.config import Theme
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.icon_testing import assert_tinted, strongest_pixel
from tests.gui.theme_testing import design_tokens

LIGHT_TOKENS = design_tokens(Theme.LIGHT)
DARK_TOKENS = design_tokens(Theme.DARK)

ICON_SIZE = 16
NON_ASCII = re.compile(r"[^\x00-\x7f]")

EXPECTED_ICONS = {
    "Refresh": "arrows-clockwise",
    "Reset": "arrow-counter-clockwise",
    "Reset Zoom": "magnifying-glass-minus",
    "Swap X/Y": "arrows-left-right",
}

# QAction falls back to its text when no tooltip is set.
EXPECTED_TOOLTIPS = {
    "Refresh": "Reload data from the datasets and redraw the chart",
    "Reset": "Reset",
    "Reset Zoom": "Reset chart zoom to fit all data",
    "Swap X/Y": "Swap the X and Y axes, including their titles, scales and ranges",
}


@pytest.fixture
def tokens() -> dict[str, Any]:
    return dict(LIGHT_TOKENS)


@pytest.fixture
def editor(qapp, monkeypatch, tokens):
    app_context = build_app_context()
    theme_manager = app_context.get_manager(ThemeManager)
    monkeypatch.setattr(theme_manager, "get_design_tokens", lambda: dict(tokens))
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


def _toolbar_actions(editor: ChartEditorWidget) -> dict[str, QAction]:
    return {action.text(): action for action in editor.preview_toolbar.actions() if not action.isSeparator()}


def _pixels(action: QAction):
    return action.icon().pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def test_toolbar_labels_match_the_expected_mapping_and_have_no_emoji(editor):
    actions = _toolbar_actions(editor)

    assert set(actions) == set(EXPECTED_ICONS)
    for text in actions:
        assert NON_ASCII.search(text) is None, f"{text!r} contains emoji or non-ASCII text"


@pytest.mark.parametrize(("label", "icon_name"), list(EXPECTED_ICONS.items()), ids=list(EXPECTED_ICONS))
def test_toolbar_action_uses_the_intended_icon(editor, label, icon_name):
    action = _toolbar_actions(editor)[label]
    expected = build_icon(icon_name, LIGHT_TOKENS["text_primary"], size=ICON_SIZE, disabled_color=LIGHT_TOKENS["text_disabled"])

    assert not action.icon().isNull()
    assert _pixels(action) == expected.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


@pytest.mark.parametrize(("label", "tooltip"), list(EXPECTED_TOOLTIPS.items()), ids=list(EXPECTED_TOOLTIPS))
def test_tooltips_are_unchanged(editor, label, tooltip):
    assert _toolbar_actions(editor)[label].toolTip() == tooltip


def test_toolbar_shows_icons_beside_text_at_16px(editor):
    toolbar: QToolBar = editor.preview_toolbar

    assert toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    assert toolbar.iconSize() == QSize(ICON_SIZE, ICON_SIZE)


def _expected_pixels(icon_name: str, palette: dict[str, Any]):
    icon = build_icon(icon_name, palette["text_primary"], size=ICON_SIZE, disabled_color=palette["text_disabled"])
    return icon.pixmap(QSize(ICON_SIZE, ICON_SIZE)).toImage()


def test_icons_are_retinted_when_the_theme_changes(editor, tokens):
    actions = _toolbar_actions(editor)
    for action in actions.values():
        assert_tinted(strongest_pixel(action.icon()), LIGHT_TOKENS["text_primary"])
    light_pixels = {label: _pixels(action) for label, action in actions.items()}

    tokens.update(DARK_TOKENS)
    editor._apply_theme()

    # The same actions are re-tinted in place (not replaced), and every icon is now exactly the dark-theme rendering.
    assert _toolbar_actions(editor) == actions
    for label, action in actions.items():
        assert_tinted(strongest_pixel(action.icon()), DARK_TOKENS["text_primary"])
        assert _pixels(action) == _expected_pixels(EXPECTED_ICONS[label], DARK_TOKENS)
        assert _pixels(action) != light_pixels[label]
