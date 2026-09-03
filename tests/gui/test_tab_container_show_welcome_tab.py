"""Tests for TabContainer.show_welcome_tab (Help > Welcome): focus an
already-open Welcome tab instead of opening a second one, since WelcomeTab
instances aren't tracked in `self.tabs` like project-item tabs are; and
select/activate a newly created one even when the target pane already had
other tabs open (QTabWidget.addTab only auto-selects into an empty pane).
"""
from unittest.mock import Mock

import pytest
from PySide6.QtWidgets import QApplication, QTabWidget

from pandaplot.gui.components.tabs.tab_container import TabContainer
from pandaplot.gui.components.tabs.tab_container_command_manager import TabContainerCommandManager
from pandaplot.gui.components.tabs.welcome_tab import WelcomeTab


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _make_container():
    container = TabContainer.__new__(TabContainer)
    container.app_context = Mock()
    container.command_manager = Mock(spec=TabContainerCommandManager)
    container._active_pane = QTabWidget()
    container.panes = [container._active_pane]
    # Plain QTabWidget panes lack CustomTabWidget.set_active, which the real
    # _activate_pane needs -- these tests aren't about that indicator, so
    # stub it out and assert on how/whether it was called instead.
    container._activate_pane = Mock()
    return container


def test_show_welcome_tab_creates_and_selects_one_when_none_open():
    container = _make_container()

    container.show_welcome_tab()

    pane = container.panes[0]
    assert pane.count() == 1
    assert isinstance(pane.widget(pane.currentIndex()), WelcomeTab)
    container._activate_pane.assert_called_once_with(pane)


def test_show_welcome_tab_selects_new_tab_even_when_pane_already_has_other_tabs():
    container = _make_container()
    pane = container.panes[0]
    # Simulates the active pane already showing project tabs -- the bug this
    # guards against: addTab() alone wouldn't switch to the new tab here.
    pane.addTab(QTabWidget(), "Other Tab")
    pane.setCurrentIndex(0)

    container.show_welcome_tab()

    assert pane.count() == 2
    assert isinstance(pane.widget(pane.currentIndex()), WelcomeTab)
    container._activate_pane.assert_called_once_with(pane)


def test_show_welcome_tab_focuses_existing_one_instead_of_creating_a_second():
    container = _make_container()
    pane = container.panes[0]
    pane.addTab(QTabWidget(), "Other Tab")
    container.create_welcome_tab()
    assert pane.count() == 2
    pane.setCurrentIndex(0)
    container._activate_pane.reset_mock()

    container.show_welcome_tab()

    assert pane.count() == 2  # no duplicate created
    assert isinstance(pane.widget(pane.currentIndex()), WelcomeTab)
    container._activate_pane.assert_called_once_with(pane)


def test_show_welcome_tab_activates_the_pane_containing_the_existing_tab():
    container = _make_container()
    other_pane = QTabWidget()
    container.create_welcome_tab(pane=other_pane)
    container.panes.append(other_pane)
    container._activate_pane.reset_mock()

    container.show_welcome_tab()

    container._activate_pane.assert_called_once_with(other_pane)
