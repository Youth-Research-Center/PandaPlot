"""Tests for SidebarPanel._apply_title_theme (#188).

Every sidebar panel's _apply_theme() used to repeat the identical line
`self.title_label.setStyleSheet(self.title_stylesheet(base_fg, card_border))`
across 10 subclasses; this is the shared implementation they all call
instead now. Exercised against a lightweight stand-in (the unbound-method
pattern used elsewhere in this codebase, e.g. PandaMainWindow._update_
window_title) rather than constructing a real SidebarPanel, since the
method only reads/writes self.title_label and doesn't need a live
AppContext/QWidget.
"""
from pandaplot.gui.components.sidebar.panels.sidebar_panel import SidebarPanel


class _FakePanel:
    # _apply_title_theme calls self.title_stylesheet(...) -- borrow the
    # real staticmethod rather than duplicating its formatting here. Must
    # be re-wrapped in staticmethod() -- a plain attribute assignment would
    # bind it as an instance method instead, passing self as an extra arg.
    title_stylesheet = staticmethod(SidebarPanel.title_stylesheet)

    def __init__(self, title_label=None):
        self.title_label = title_label


class _FakeLabel:
    def __init__(self):
        self.stylesheet = None

    def setStyleSheet(self, value):  # noqa: N802 - matches Qt's method name
        self.stylesheet = value


def test_apply_title_theme_sets_the_stylesheet_when_title_label_exists():
    label = _FakeLabel()
    panel = _FakePanel(title_label=label)

    SidebarPanel._apply_title_theme(panel, "#333333", "#dee2e6")

    assert label.stylesheet == SidebarPanel.title_stylesheet("#333333", "#dee2e6")


def test_apply_title_theme_is_a_noop_when_title_label_is_none():
    """Regression (#188): _apply_theme can in principle run before
    _set_title() has created title_label (e.g. via the base
    ThemeEvents.THEME_CHANGED subscription, depending on subclass init
    order) -- must not raise AttributeError."""
    panel = _FakePanel(title_label=None)

    SidebarPanel._apply_title_theme(panel, "#333333", "#dee2e6")  # must not raise
