"""Tests for ChartNoDatasetPage."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_no_dataset_page import ChartNoDatasetPage
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


def test_page_shows_step_2_of_3_with_no_next_or_empty_link():
    page = ChartNoDatasetPage(app_context=_fake_app_context())
    page.show()

    assert page.footer.step_label.text() == "Step 2 of 3"
    assert page.footer.next_button.isVisible() is False
    assert page.footer.finish_button.isVisible() is False
    assert page.footer.empty_link is None
    assert page.footer.back_button.isVisible() is True


def test_import_button_emits_import_requested():
    page = ChartNoDatasetPage(app_context=_fake_app_context())
    received = []
    page.importRequested.connect(lambda: received.append(True))

    page.import_button.click()

    assert received == [True]


def test_empty_button_emits_empty_requested():
    page = ChartNoDatasetPage(app_context=_fake_app_context())
    received = []
    page.emptyRequested.connect(lambda: received.append(True))

    page.empty_button.click()

    assert received == [True]
