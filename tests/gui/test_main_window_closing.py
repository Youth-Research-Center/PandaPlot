"""Tests for PandaMainWindow.on_app_closing_event's re-entrancy guard.

Regression: `_is_closing` used to be reset to False in a `finally` block
*before* `self.close()` was called, so the guard flag provided no actual
protection during the one call (`close()`) that could plausibly re-enter
this handler synchronously. The fix keeps `_is_closing` True for the full
duration of `close()`.
"""
from unittest.mock import Mock

from pandaplot.gui.main_window import PandaMainWindow


def _window():
    window = PandaMainWindow.__new__(PandaMainWindow)
    window.logger = Mock()
    window._is_closing = False
    return window


def test_is_closing_stays_true_for_the_duration_of_close():
    window = _window()

    def _fake_close():
        # This is the crux of the regression: at the moment close() actually
        # runs, the guard flag must still be True.
        assert window._is_closing is True

    window.close = Mock(side_effect=_fake_close)

    window.on_app_closing_event({})

    window.close.assert_called_once()
    # After the handler completes, the flag is cleared again.
    assert window._is_closing is False


def test_ignores_event_when_close_already_in_progress():
    window = _window()
    window._is_closing = True
    window.close = Mock()

    window.on_app_closing_event({})

    window.close.assert_not_called()


def test_close_is_still_called_and_flag_cleared_when_cleanup_raises():
    """If a cleanup step raises, close() must still run (in the finally
    block) so the app doesn't stay open despite the "forcing application
    exit" log message, and the guard flag must still be released afterward
    so the app isn't stuck refusing to close."""
    window = _window()
    window.close = Mock()

    def _raise_on_cleanup_completed(msg, *args, **kwargs):
        if msg == "Application cleanup completed successfully":
            raise RuntimeError("boom")

    window.logger.info.side_effect = _raise_on_cleanup_completed

    window.on_app_closing_event({})

    window.close.assert_called_once()
    assert window._is_closing is False
    window.logger.error.assert_called_once()
