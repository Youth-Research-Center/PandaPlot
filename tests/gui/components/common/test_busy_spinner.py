"""Tests for BusySpinner: start/stop drive visibility and the rotation timer."""

from pandaplot.gui.components.common.busy_spinner import BusySpinner


def test_starts_hidden_and_not_running(qtbot):
    spinner = BusySpinner()
    qtbot.addWidget(spinner)

    assert spinner.is_running is False
    assert spinner.isVisible() is False


def test_start_shows_and_marks_running(qtbot):
    spinner = BusySpinner()
    qtbot.addWidget(spinner)
    spinner.show()  # qtbot needs a shown top-level ancestor for isVisible() to be meaningful

    spinner.start()

    assert spinner.is_running is True
    assert spinner.isVisible() is True


def test_stop_hides_and_marks_not_running(qtbot):
    spinner = BusySpinner()
    qtbot.addWidget(spinner)
    spinner.show()

    spinner.start()
    spinner.stop()

    assert spinner.is_running is False
    assert spinner.isVisible() is False


def test_set_color_accepts_a_hex_string(qtbot):
    spinner = BusySpinner(color="#ff0000")
    qtbot.addWidget(spinner)

    spinner.set_color("#00ff00")  # must not raise


def test_advancing_the_timer_changes_the_angle(qtbot):
    spinner = BusySpinner()
    qtbot.addWidget(spinner)
    spinner.show()
    spinner.start()

    first_angle = spinner._angle
    spinner._advance()

    assert spinner._angle != first_angle


def test_has_an_accessible_name(qtbot):
    """Regression test (PR review): a purely custom-painted widget has no
    built-in accessible name -- screen readers would announce nothing when
    the spinner appears next to controls that just got disabled."""
    spinner = BusySpinner()
    qtbot.addWidget(spinner)

    assert spinner.accessibleName() != ""


def test_start_sets_an_accessible_description_stop_clears_it(qtbot):
    spinner = BusySpinner()
    qtbot.addWidget(spinner)
    spinner.show()

    spinner.start()
    assert spinner.accessibleDescription() != ""

    spinner.stop()
    assert spinner.accessibleDescription() == ""
