"""Interstitial step of the chart creation wizard shown when the project has
no datasets yet: import one (and continue into the normal Data step) or
create an empty chart, since there is otherwise nothing for the wizard's
Data step to let the user configure.
"""
from typing import Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QHBoxLayout, QLabel, QVBoxLayout, QWidget

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.core.widget_extension import PWizardPage
from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartNoDatasetPage(PWizardPage):
    """Shown instead of `ChartDataPage` when the project has zero datasets."""

    importRequested = Signal()
    emptyRequested = Signal()

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self._initialize()

    def _init_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        self.step_rail = WizardStepRail(["Type", "Data", "Labels"])
        rail_row = QHBoxLayout()
        rail_row.setContentsMargins(14, 10, 14, 10)
        rail_row.addWidget(self.step_rail)
        outer.addLayout(rail_row)

        content = QVBoxLayout()
        content.setContentsMargins(14, 14, 14, 14)
        content.setSpacing(12)
        outer.addLayout(content, 1)

        self.heading_label = QLabel("This project has no datasets yet")
        content.addWidget(self.heading_label)

        options_row = QHBoxLayout()
        options_row.setSpacing(10)
        content.addLayout(options_row, 1)

        import_card = Card()
        import_layout = QVBoxLayout(import_card)
        import_layout.addWidget(SectionHeader("Import a dataset"))
        self.import_description = QLabel("Bring in data to build your chart from.")
        self.import_description.setWordWrap(True)
        import_layout.addWidget(self.import_description)
        import_layout.addStretch(1)
        self.import_button = PButton(
            "Import Dataset", role="primary", on_click=self.importRequested.emit
        )
        import_layout.addWidget(self.import_button)
        options_row.addWidget(import_card, 1)

        empty_card = Card()
        empty_layout = QVBoxLayout(empty_card)
        empty_layout.addWidget(SectionHeader("Create an empty chart"))
        self.empty_description = QLabel("Start with a blank chart and add data later.")
        self.empty_description.setWordWrap(True)
        empty_layout.addWidget(self.empty_description)
        empty_layout.addStretch(1)
        self.empty_button = PButton(
            "Create Empty Chart", role="secondary", on_click=self.emptyRequested.emit
        )
        empty_layout.addWidget(self.empty_button)
        options_row.addWidget(empty_card, 1)

        self.footer = WizardFooter(
            step_number=2, total_steps=3, show_empty_link=False, show_next=False,
        )
        self.footer.backClicked.connect(lambda: self.wizard().back())
        self.footer.cancelClicked.connect(lambda: self.wizard().reject())
        outer.addWidget(self.footer)

    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        tokens = theme_manager.get_design_tokens()
        self.step_rail.set_tokens(tokens)
        self.footer.set_tokens(tokens)
        text_primary = tokens.get("text_primary", "#1C1E26")
        text_muted = tokens.get("text_muted", "#6B7280")
        self.heading_label.setStyleSheet(
            f"font-size: 13px; font-weight: 600; color: {text_primary};"
        )
        for label in (self.import_description, self.empty_description):
            label.setStyleSheet(f"color: {text_muted};")

    def nextId(self) -> int:
        wizard = self.wizard()
        return getattr(wizard, "_data_page_id", -1)
