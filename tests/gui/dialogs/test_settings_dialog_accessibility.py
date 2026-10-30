"""Accessibility tests for SettingsDialog."""
import sys

from PySide6.QtWidgets import QApplication

from pandaplot.app import build_app_context
from pandaplot.gui.dialogs.settings_dialog import SettingsDialog


def test_accent_color_swatch_button_has_an_accessible_name():
    """The accent button shows only a background color, no text."""
    _app = QApplication.instance() or QApplication(sys.argv)
    dialog = SettingsDialog(build_app_context())
    try:
        assert dialog.accent_color_btn.accessibleName() == "Accent color"
        assert dialog.accent_color_btn.toolTip()
    finally:
        dialog.deleteLater()
