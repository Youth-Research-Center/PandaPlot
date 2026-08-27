"""Step 2 of the chart creation wizard: one or more series, each configured
by a collapsible SeriesConfigCard, plus a 'Create empty plot' escape hatch.
"""
from typing import Callable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QHBoxLayout, QScrollArea, QVBoxLayout, QWidget

from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.core.widget_extension import PWizardPage
from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.wizard_footer import WizardFooter
from pandaplot.gui.dialogs.chart.wizard_step_rail import WizardStepRail
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class ChartDataPage(PWizardPage):
    emptyRequested = Signal()

    def __init__(self, app_context: AppContext, parent: Optional[QWidget] = None):
        super().__init__(app_context=app_context, parent=parent)
        self.cards: list[SeriesConfigCard] = []
        self._chart_type: str = "line"
        self._datasets: list[tuple[str, str]] = []
        self._columns_provider: Optional[Callable[[str], list[tuple[str, str]]]] = None
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
        outer.addLayout(content, 1)

        header_row = QHBoxLayout()
        header_row.addWidget(SectionHeader("Series"))
        header_row.addStretch(1)
        self.add_series_button = PButton(
            "+ Add series", role="secondary", on_click=self._add_card
        )
        self.add_series_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header_row.addWidget(self.add_series_button)
        content.addLayout(header_row)

        cards_container = QWidget()
        self.cards_container = QVBoxLayout(cards_container)
        self.cards_container.setContentsMargins(0, 0, 0, 0)
        self.cards_container.setSpacing(6)

        self.cards_scroll_area = QScrollArea()
        self.cards_scroll_area.setWidgetResizable(True)
        self.cards_scroll_area.setFrameShape(QScrollArea.Shape.NoFrame)
        self.cards_scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.cards_scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.cards_scroll_area.setWidget(cards_container)
        content.addWidget(self.cards_scroll_area, 1)

        self.footer = WizardFooter(step_number=2, total_steps=3, show_empty_link=True)
        self.footer.backClicked.connect(lambda: self.wizard().back())
        self.footer.nextClicked.connect(lambda: self.wizard().next())
        self.footer.cancelClicked.connect(lambda: self.wizard().reject())
        self.footer.emptyRequested.connect(self.emptyRequested.emit)
        self.empty_button = self.footer.empty_link
        outer.addWidget(self.footer)

        self.completeChanged.connect(lambda: self.footer.set_next_enabled(enabled=self.isComplete()))
        self.footer.set_next_enabled(enabled=self.isComplete())

    def _apply_theme(self):
        theme_manager = self.app_context.get_manager(ThemeManager)
        tokens = theme_manager.get_design_tokens()
        self.step_rail.set_tokens(tokens)
        self.footer.set_tokens(tokens)
        for card in self.cards:
            card.set_tokens(tokens)

    def set_chart_type(self, chart_type: str) -> bool:
        """Point the page at `chart_type`, rebuilding the cards if it changed.

        Returns True when the cards were actually rebuilt (so the caller knows
        a fresh, untouched card set exists and any initial selection should be
        re-applied), False when the existing cards were left alone.
        """
        if chart_type == self._chart_type and self.cards:
            return False
        self._chart_type = chart_type
        for card in list(self.cards):
            self._remove_card(card)
        self._add_card()
        return True

    def set_datasets(self, datasets: list[tuple[str, str]]) -> None:
        self._datasets = datasets
        for card in self.cards:
            card.set_datasets(datasets)

    def set_dataset_columns_provider(self, provider: Callable[[str], list[tuple[str, str]]]) -> None:
        self._columns_provider = provider
        for card in self.cards:
            self._refresh_card_columns(card)

    def _add_card(self) -> SeriesConfigCard:
        card = SeriesConfigCard(role_spec=get_chart_type_spec(self._chart_type), index=len(self.cards))
        card.set_datasets(self._datasets)
        card.removeRequested.connect(lambda c=card: self._remove_card(c))
        card.datasetChanged.connect(lambda _dataset_id, c=card: self._refresh_card_columns(c))
        card.configChanged.connect(self.completeChanged.emit)
        self.cards_container.addWidget(card)
        self.cards.append(card)
        theme_manager = self.app_context.get_manager(ThemeManager)
        card.set_tokens(theme_manager.get_design_tokens())
        self._refresh_card_columns(card)
        self.completeChanged.emit()
        return card

    def _remove_card(self, card: SeriesConfigCard) -> None:
        if card not in self.cards:
            return
        self.cards.remove(card)
        self.cards_container.removeWidget(card)
        card.setParent(None)
        card.deleteLater()
        for index, remaining_card in enumerate(self.cards):
            remaining_card.set_index(index)
        self.completeChanged.emit()

    def _refresh_card_columns(self, card: SeriesConfigCard) -> None:
        dataset_id = card.dataset_combo.currentData()
        if dataset_id and self._columns_provider is not None:
            card.set_dataset_columns(dataset_id, self._columns_provider(dataset_id))

    def series_configs(self) -> list[dict]:
        return [card.get_series_config() for card in self.cards]

    def isComplete(self) -> bool:
        return bool(self.cards) and all(card.is_complete() for card in self.cards)
