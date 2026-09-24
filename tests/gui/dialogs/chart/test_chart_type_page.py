"""Tests for ChartTypePage."""
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_type_page import ChartTypePage
from pandaplot.services.theme.theme_manager import ThemeManager


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


_FAKE_TOKENS = {
    "text_primary": "#1C1E26", "text_secondary": "#3F4350",
    "text_muted": "#6B7280", "text_hint": "#9AA0AB",
    "border_panel": "#E5E6EA", "border_control": "#DCDEE4",
    "border_subtle": "#ECEEF2",
    "surface_white": "#FFFFFF", "surface_chrome": "#FBFBFC",
    "surface_inset": "#F4F5F8",
    "accent": "#4A56C6", "accent_active_text": "#3A45A8", "accent_disabled": "#AAB1E3",
    "accent_selected_bg": "#EEF0FB",
    "status_modified_dot": "#E09A1F", "status_modified_text": "#B06A00",
    "status_success": "#3FA46A",
    "y2_accent": "#8A4BB8", "y2_accent_bg": "#F5EEFB",
    "series_palette": ["#A01818", "#4A56C6", "#2B7A8C", "#3FA46A", "#E09A1F"],
    "radius_swatch": 4, "radius_control": 5, "radius_card": 6, "radius_chip": 12,
}


def _fake_app_context():
    app_context = Mock()
    app_context.event_bus = Mock()

    theme_manager = Mock()
    theme_manager.get_design_tokens.return_value = dict(_FAKE_TOKENS)

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    app_context.get_manager.side_effect = _get_manager
    return app_context


def test_line_is_selected_by_default():
    page = ChartTypePage(app_context=_fake_app_context())

    assert page.selected_chart_type() == "line"
    assert page.isComplete() is True


def test_selecting_histogram_updates_selected_chart_type():
    page = ChartTypePage(app_context=_fake_app_context())
    histogram_row = next(
        row for row in range(page.type_list.count())
        if page.type_list.item(row).data(Qt.ItemDataRole.UserRole) == "hist"
    )

    page.type_list.setCurrentRow(histogram_row)

    assert page.selected_chart_type() == "hist"


def test_empty_button_emits_empty_requested():
    page = ChartTypePage(app_context=_fake_app_context())
    received = []
    page.emptyRequested.connect(lambda: received.append(True))

    page.empty_button.click()

    assert received == [True]


def test_importing_chart_type_page_does_not_import_matplotlib():
    import subprocess
    import sys

    code = (
        "import sys; "
        "import pandaplot.gui.dialogs.chart.chart_type_page; "
        "assert 'matplotlib' not in sys.modules, 'matplotlib was imported eagerly'"
    )
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_type_rows_have_icons():
    page = ChartTypePage(app_context=_fake_app_context())

    for row in range(page.type_list.count()):
        assert not page.type_list.item(row).icon().isNull()


def test_page_exposes_a_step_rail_and_footer():
    page = ChartTypePage(app_context=_fake_app_context())

    assert page.step_rail is not None
    assert page.footer is not None
    assert page.footer.empty_link is not None  # step 1: empty-plot link is shown


def test_empty_button_is_the_footers_link():
    page = ChartTypePage(app_context=_fake_app_context())

    assert page.empty_button is page.footer.empty_link


def test_next_button_enabled_state_tracks_iscomplete():
    """Regression: after Task 3 removed QWizard's native buttons, nothing
    wired isComplete()/completeChanged to the footer's Next button, so users
    could advance past an incomplete page."""
    page = ChartTypePage(app_context=_fake_app_context())

    # A chart type is selected by default, so Type starts complete/enabled.
    assert page.isComplete() is True
    assert page.footer.next_button.isEnabled() is True


def test_selecting_a_different_type_refreshes_the_accent_colored_icon():
    """Regression: `_apply_tokens` only ran from theme-change events, so the
    accent-colored icon stayed stuck on whichever row was current at the
    last theme event, never updating when the user picked a new type."""
    page = ChartTypePage(app_context=_fake_app_context())
    page._apply_tokens(_FAKE_TOKENS)  # simulate a theme event, as _apply_theme would
    old_row = page.type_list.currentRow()

    bar_row = next(
        row for row in range(page.type_list.count())
        if page.type_list.item(row).data(Qt.ItemDataRole.UserRole) == "bar"
    )
    assert old_row != bar_row  # sanity: we actually switch rows

    # `_apply_tokens` regenerates every row's icon on each call, so if
    # selecting a new type re-applies tokens, both the old and new
    # current-row icons must be freshly created (different QIcon instances,
    # hence different cache keys) compared to right before the switch.
    old_row_icon_before = page.type_list.item(old_row).icon().cacheKey()
    bar_row_icon_before = page.type_list.item(bar_row).icon().cacheKey()

    page.type_list.setCurrentRow(bar_row)

    old_row_icon_after = page.type_list.item(old_row).icon().cacheKey()
    bar_row_icon_after = page.type_list.item(bar_row).icon().cacheKey()
    assert old_row_icon_after != old_row_icon_before
    assert bar_row_icon_after != bar_row_icon_before


def test_selecting_a_different_type_keeps_next_enabled_in_sync():
    page = ChartTypePage(app_context=_fake_app_context())
    histogram_row = next(
        row for row in range(page.type_list.count())
        if page.type_list.item(row).data(Qt.ItemDataRole.UserRole) == "hist"
    )

    page.type_list.setCurrentRow(histogram_row)

    assert page.isComplete() is True
    assert page.footer.next_button.isEnabled() is True
