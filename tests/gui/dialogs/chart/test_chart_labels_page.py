"""Tests for ChartLabelsPage."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_labels_page import ChartLabelsPage
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


def test_fields_start_empty():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_title() == ""
    assert page.get_x_label() == ""
    assert page.get_y_label() == ""


def test_set_defaults_populates_all_three_fields():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.set_defaults("Chart from Sales", "Date", "Revenue")

    assert page.get_title() == "Chart from Sales"
    assert page.get_x_label() == "Date"
    assert page.get_y_label() == "Revenue"


def test_fields_stay_editable_after_defaults_are_set():
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Chart from Sales", "Date", "Revenue")

    page.title_edit.setText("My custom title")
    page.y_label_edit.clear()

    assert page.get_title() == "My custom title"
    assert page.get_y_label() == ""
    assert page.get_x_label() == "Date"


def test_set_defaults_overwrites_previous_defaults():
    """Re-seeding (e.g. after a chart-type change) replaces stale defaults."""
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.set_defaults("New title", "New X", "New Y")

    assert page.get_title() == "New title"
    assert page.get_x_label() == "New X"
    assert page.get_y_label() == "New Y"


def test_set_defaults_overwrites_an_untouched_field_even_on_a_second_call():
    """Seeding itself must not mark a field as touched (regression guard for
    the blockSignals wiring in set_defaults)."""
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.set_defaults("Newer title", "Newer X", "Newer Y")

    assert page.get_title() == "Newer title"
    assert page.get_x_label() == "Newer X"
    assert page.get_y_label() == "Newer Y"


def test_a_field_touched_by_the_user_is_never_overwritten_again():
    page = ChartLabelsPage(app_context=_fake_app_context())
    page.set_defaults("Old title", "Old X", "Old Y")

    page.x_label_edit.setText("user typed this")  # simulates a real user edit
    page.set_defaults("New title", "New X", "New Y")

    assert page.get_x_label() == "user typed this"
    assert page.get_title() == "New title"
    assert page.get_y_label() == "New Y"


def test_subtitle_starts_empty():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_subtitle() == ""


def test_subtitle_is_directly_editable():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.subtitle_edit.setText("A closer look")

    assert page.get_subtitle() == "A closer look"


def test_legend_and_grid_default_on():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.get_show_legend() is True
    assert page.get_show_grid() is True


def test_legend_and_grid_toggles_are_independent():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.show_legend_toggle.setChecked(checked=False)

    assert page.get_show_legend() is False
    assert page.get_show_grid() is True


def test_page_exposes_a_step_rail_and_footer_with_no_empty_link():
    page = ChartLabelsPage(app_context=_fake_app_context())

    assert page.step_rail is not None
    assert page.footer is not None
    assert page.footer.empty_link is None  # step 3: no "Create empty plot" link


def test_refresh_preview_does_not_raise_with_no_project_or_series():
    page = ChartLabelsPage(app_context=_fake_app_context())

    page.refresh_preview(project=None, chart_type="line", series_configs=[])  # must not raise

    assert page.preview_canvas is not None
