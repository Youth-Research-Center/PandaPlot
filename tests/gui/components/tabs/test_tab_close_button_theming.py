"""Tab's close-button hover/pressed red was hardcoded (#FF6B6B/#FF5252/
#E53935) independent of ThemeManager's status_danger token (#DC3545 light /
#C24141 dark) -- two different reds for the same "danger" concept."""
import re
import sys
from unittest.mock import Mock

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from pandaplot.gui.components.tabs.tab import CustomTabWidget
from pandaplot.models.state.app_context import AppContext


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication(sys.argv)
    yield app


def _rule(stylesheet: str, selector: str) -> dict:
    match = re.search(re.escape(selector) + r"\s*\{([^}]*)\}", stylesheet)
    assert match, f"{selector} not found in stylesheet"
    return dict(
        (key.strip(), value.strip())
        for key, value in (decl.split(":", 1)
                           for decl in match.group(1).split(";") if ":" in decl)
    )


def test_close_button_hover_color_derives_from_status_danger_token():
    app_context = Mock(spec=AppContext)
    app_context.event_bus = Mock()
    theme_manager = Mock()
    theme_manager.get_surface_palette.return_value = {
        "card_bg": "#FFFFFF", "card_hover": "#E9ECEF", "card_pressed": "#DEE2E6",
        "card_border": "#DEE2E6", "base_fg": "#000000", "secondary_fg": "#555555",
        "accent": "#4A56C6",
    }
    theme_manager.get_design_tokens.return_value = {"status_danger": "#DC3545"}
    app_context.get_manager.return_value = theme_manager

    tab = CustomTabWidget(app_context, None)
    tab._apply_theme()

    hover_rule = _rule(tab.styleSheet(), r"QTabBar::close-button:hover")
    assert hover_rule["background-color"].upper() == "#DC3545"
    assert hover_rule["background-color"].upper() != "#FF6B6B"
