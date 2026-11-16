"""Tests for the help ("?") buttons and F1 shortcut of ChartWizard."""
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_wizard import ChartWizard
from pandaplot.models.events.event_types import UIEvents
from pandaplot.services.help.help_types import (
    WIZARD_TOPIC_DATA,
    WIZARD_TOPIC_LABELS,
    WIZARD_TOPIC_NO_DATASET,
    WIZARD_TOPIC_TYPE,
)
from pandaplot.services.theme.theme_manager import ThemeManager
from tests.gui.theme_testing import design_tokens, surface_palette


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _fake_app_context():
    app_context = Mock()
    app_context.event_bus = Mock()

    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = surface_palette()
    theme_manager.get_design_tokens.return_value = design_tokens()

    def _get_manager(manager_type, *args, **kwargs):
        if manager_type is ThemeManager:
            return theme_manager
        return Mock()

    app_context.get_manager.side_effect = _get_manager
    return app_context


def _columns_for(dataset_id: str):
    return [("col-date", "Date"), ("col-rev", "Revenue")]


def _make_wizard(*, datasets=(("ds-1", "Sales"),)) -> ChartWizard:
    return ChartWizard(app_context=_fake_app_context(), datasets=list(datasets), columns_provider=_columns_for)


def _help_topics(wizard: ChartWizard) -> list[str]:
    emit: Mock = wizard.app_context.event_bus.emit  # ty: ignore[invalid-assignment]
    return [call.args[1]["topic_id"] for call in emit.call_args_list if call.args[0] == UIEvents.HELP_REQUESTED]


def _show_active(qtbot, wizard: ChartWizard) -> None:
    qtbot.addWidget(wizard)
    wizard.show()
    assert QTest.qWaitForWindowActive(wizard)


def test_page_topics_come_from_the_wizard_constants(qtbot):
    wizard = _make_wizard()
    qtbot.addWidget(wizard)

    assert wizard.type_page.help_topic == WIZARD_TOPIC_TYPE
    assert wizard.data_page.help_topic == WIZARD_TOPIC_DATA
    assert wizard.labels_page.help_topic == WIZARD_TOPIC_LABELS
    assert wizard.no_dataset_page.help_topic == WIZARD_TOPIC_NO_DATASET


@pytest.mark.parametrize("page_name", ["type_page", "data_page", "labels_page", "no_dataset_page"])
def test_footer_help_button_publishes_the_page_topic(qtbot, page_name):
    wizard = _make_wizard()
    qtbot.addWidget(wizard)
    page = getattr(wizard, page_name)

    assert page.footer.help_button is not None
    page.footer.help_button.click()

    assert _help_topics(wizard) == [page.help_topic]


@pytest.mark.skipif(sys.platform == "darwin", reason="F1 is Cmd+? on macOS, so QKeySequence.HelpContents differs")
@pytest.mark.parametrize(
    ("step", "topic"),
    [(0, WIZARD_TOPIC_TYPE), (1, WIZARD_TOPIC_DATA), (2, WIZARD_TOPIC_LABELS)],
)
def test_f1_publishes_the_current_pages_topic(qtbot, step, topic):
    wizard = _make_wizard()
    _show_active(qtbot, wizard)
    wizard._jump_to_step(step)

    QTest.keyClick(wizard, Qt.Key.Key_F1)

    assert _help_topics(wizard) == [topic]


@pytest.mark.skipif(sys.platform == "darwin", reason="F1 is Cmd+? on macOS, so QKeySequence.HelpContents differs")
def test_f1_works_with_focus_in_a_line_edit(qtbot):
    from PySide6.QtWidgets import QLineEdit

    wizard = _make_wizard()
    _show_active(qtbot, wizard)
    wizard._jump_to_step(2)
    edit = wizard.labels_page.findChild(QLineEdit)
    assert edit is not None
    edit.setFocus()

    QTest.keyClick(edit, Qt.Key.Key_F1)

    assert _help_topics(wizard) == [WIZARD_TOPIC_LABELS]


@pytest.mark.skipif(sys.platform == "darwin", reason="F1 is Cmd+? on macOS, so QKeySequence.HelpContents differs")
def test_f1_on_the_no_dataset_page(qtbot):
    wizard = _make_wizard(datasets=())
    _show_active(qtbot, wizard)
    wizard.next()
    assert wizard.currentId() == wizard._no_dataset_page_id

    QTest.keyClick(wizard, Qt.Key.Key_F1)

    assert _help_topics(wizard) == [WIZARD_TOPIC_NO_DATASET]


def test_help_shortcut_without_page_topic_does_nothing(qtbot):
    wizard = _make_wizard()
    qtbot.addWidget(wizard)
    del wizard.type_page.help_topic
    assert wizard.currentPage() is wizard.type_page

    wizard._on_help_shortcut()

    assert _help_topics(wizard) == []


def test_help_window_search_field_is_not_restyled_by_the_wizard_stylesheet(qtbot):
    from PySide6.QtWidgets import QLineEdit, QWidget

    from pandaplot.gui.dialogs.help.help_window import HelpWindow

    wizard = _make_wizard()
    qtbot.addWidget(wizard)
    wizard.show()
    plain_parent = QWidget()
    qtbot.addWidget(plain_parent)

    under_plain = HelpWindow(wizard.app_context, plain_parent)
    under_wizard = HelpWindow(wizard.app_context, wizard)

    assert under_wizard.search_edit.sizeHint() == under_plain.search_edit.sizeHint()
    assert isinstance(wizard.labels_page.findChild(QLineEdit), QLineEdit)
