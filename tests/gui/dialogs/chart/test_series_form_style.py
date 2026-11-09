"""Tests for the stylesheet shared by the chart wizard and the Add Series dialog."""
import pytest
from PySide6.QtWidgets import QApplication

from pandaplot.gui.dialogs.chart.chart_wizard import ChartWizard
from pandaplot.gui.dialogs.chart.series_form_style import series_form_stylesheet
from tests.gui.dialogs.chart.test_wizard_help import _fake_app_context

_PALETTE = {
    "card_bg": "#111111", "card_hover": "#222222", "card_border": "#444444",
    "base_fg": "#eeeeee", "secondary_fg": "#aaaaaa", "accent": "#ff00ff",
}

# The wizard's stylesheet exactly as it was written before the shared rules were extracted.
_PRE_EXTRACTION_WIZARD_STYLESHEET = """
            QWizard {
                background-color: #111111;
                color: #eeeeee;
            }
            QWizardPage {
                background-color: #111111;
                color: #eeeeee;
            }
            QWizardPage QLabel, QWizardPage QCheckBox {
                color: #eeeeee;
            }
            QWizardPage QCheckBox::indicator {
                width: 14px;
                height: 14px;
                border: 1px solid #444444;
                border-radius: 3px;
                background-color: #222222;
            }
            QWizardPage QCheckBox::indicator:checked {
                background-color: #ff00ff;
                border-color: #ff00ff;
            }
            QWizardPage QLineEdit {
                background-color: #222222;
                border: 1px solid #444444;
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
                color: #eeeeee;
            }
            QWizardPage QLineEdit:focus {
                border-color: #ff00ff;
            }
            QWizardPage QLineEdit:hover {
                border-color: #ff00ff;
            }
            QWizardPage QLineEdit:disabled {
                color: #aaaaaa;
                background-color: #111111;
                border-color: #444444;
            }
            QWizardPage QListWidget {
                background-color: #222222;
                border: 1px solid #444444;
                border-radius: 4px;
                color: #eeeeee;
                outline: none;
            }
            QWizardPage QListWidget::item {
                padding: 4px 6px;
            }
            QWizardPage QListWidget::item:selected {
                background-color: #ff00ff;
                color: white;
            }
        """


@pytest.fixture(scope="module", autouse=True)
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_wizard_stylesheet_is_unchanged_by_the_extraction(qtbot):
    wizard = ChartWizard(app_context=_fake_app_context(), datasets=[("ds-1", "Sales")])
    qtbot.addWidget(wizard)

    # The pre-extraction literal ended with indentation whitespace before its closing quotes; nothing else differs.
    assert wizard.styleSheet() == _PRE_EXTRACTION_WIZARD_STYLESHEET.rstrip(" ")


def test_every_rule_is_prefixed_with_the_scope():
    sheet = series_form_stylesheet(_PALETTE, scope="SeriesConfigCard")

    selectors = [line.strip() for line in sheet.splitlines() if line.strip().endswith("{")]
    assert selectors
    assert all(selector.startswith("SeriesConfigCard ") for selector in selectors)


def test_falls_back_to_defaults_for_an_empty_palette():
    assert "#f8f9fa" in series_form_stylesheet({}, scope="X")
