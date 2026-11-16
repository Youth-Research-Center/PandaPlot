"""Tests for ChartNoDatasetPage."""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_no_dataset_page import ChartNoDatasetPage
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.theme_testing import design_tokens


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _fake_app_context():
    app_context = Mock()
    app_context.event_bus = Mock()

    theme_manager = Mock()
    theme_manager.get_design_tokens.return_value = design_tokens()

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
