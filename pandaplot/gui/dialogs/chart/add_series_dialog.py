"""Dialog for adding one series to an existing chart: dataset and column pickers
for the chart's type, reusing the wizard's `SeriesConfigCard`."""
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QHBoxLayout, QLabel, QToolButton, QVBoxLayout, QWidget

from pandaplot.commands.project.chart.series_from_config import dataset_columns, dataset_options
from pandaplot.gui.components.common.help_button import build_help_button
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.core.widget_extension import PDialog
from pandaplot.gui.dialogs.chart.series_config_card import SeriesConfigCard
from pandaplot.gui.dialogs.chart.series_form_style import series_form_stylesheet
from pandaplot.models.chart.chart_role_labels import ROLE_LABELS
from pandaplot.models.chart.chart_type_spec import get_chart_type_spec
from pandaplot.models.events.event_types import UIEvents
from pandaplot.models.project import Project
from pandaplot.models.project.items import Chart, Dataset
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.help.help_types import CHART_TOPIC_SERIES
from pandaplot.services.theme.theme_manager import ThemeManager

_ADD_TOOLTIP = "Add this series to the chart"


class AddSeriesDialog(PDialog):
    """Modal form that collects the configuration of one new series for `chart`.

    Attributes:
        card: The series configuration card (standalone mode).
        add_button: Accepts the dialog; enabled only once the card is complete.
        cancel_button: Rejects the dialog.
        help_button: Opens the Help window on the series topic.
    """

    def __init__(self, app_context: AppContext, *, chart: Chart, project: Project, parent: QWidget | None = None):
        """Create the dialog.

        Args:
            app_context: Application context.
            chart: The chart the series will be added to; its type selects the role pickers.
            project: The project whose datasets can be chosen.
            parent: Optional parent widget.
        """
        super().__init__(app_context=app_context, parent=parent)
        self._chart = chart
        self._project = project
        self._initialize()

    def _init_ui(self) -> None:
        self.setWindowTitle("Add Series")
        self.setAccessibleName("Add Series")
        self.setAccessibleDescription(f"Choose the data for a new series on {self._chart.name}")
        self.setModal(True)

        layout = QVBoxLayout(self)
        self.heading_label = QLabel(f"Add a series to {self._chart.name}")
        layout.addWidget(self.heading_label)

        self.card = SeriesConfigCard(get_chart_type_spec(self._chart.chart_type), standalone=True)
        self.card.set_datasets(dataset_options(self._project))
        initial_dataset_id = self._initial_dataset_id()
        if initial_dataset_id is not None:
            self.card.dataset_combo.blockSignals(True)  # noqa: FBT003 - Qt method, no keyword args
            try:
                self.card.dataset_combo.setCurrentIndex(self.card.dataset_combo.findData(initial_dataset_id))
            finally:
                self.card.dataset_combo.blockSignals(False)  # noqa: FBT003 - Qt method, no keyword args
        self._refill_columns()
        self.card.datasetChanged.connect(lambda _dataset_id: self._refill_columns())
        self.card.configChanged.connect(self._update_add_state)
        layout.addWidget(self.card)

        buttons = QHBoxLayout()
        self.help_button: QToolButton = build_help_button(
            accessible_name="Help: Add Series",
            accessible_description="Opens the Help window on adding series",
            tooltip="Open help for series",
            parent=self,
        )
        self.help_button.clicked.connect(lambda _checked=False: self._request_help())
        buttons.addWidget(self.help_button)
        buttons.addStretch(1)
        self.cancel_button = PButton("Cancel", role="secondary", on_click=self.reject, parent=self)
        self.cancel_button.setAccessibleName("Cancel")
        self.cancel_button.setAutoDefault(False)
        buttons.addWidget(self.cancel_button)
        self.add_button = PButton("Add", role="primary", on_click=self.accept, parent=self)
        self.add_button.setAccessibleName("Add series")
        self.add_button.setDefault(True)
        buttons.addWidget(self.add_button)
        layout.addLayout(buttons)

        self.help_shortcut = QShortcut(QKeySequence(QKeySequence.StandardKey.HelpContents), self)
        self.help_shortcut.activated.connect(self._request_help)
        self._update_add_state()

    def _initial_dataset_id(self) -> str | None:
        """Dataset to preselect: the last non-fit series' dataset if it still exists, else the first option."""
        for series in reversed(self._chart.data_series):
            if not series.is_fit and isinstance(self._project.find_item(series.dataset_id), Dataset):
                return series.dataset_id
        return None

    def _refill_columns(self) -> None:
        dataset_id = self.card.dataset_combo.currentData()
        if dataset_id:
            self.card.set_dataset_columns(dataset_id, dataset_columns(self._project, dataset_id))

    def _update_add_state(self) -> None:
        complete = self.card.is_complete()
        self.add_button.setEnabled(complete)
        self.add_button.setToolTip(_ADD_TOOLTIP if complete else self._missing_hint())

    def _missing_hint(self) -> str:
        if not self.card.dataset_combo.currentData():
            return "Choose a dataset"
        spec = get_chart_type_spec(self._chart.chart_type)
        missing = [ROLE_LABELS[role] for role in spec.required_roles if not self.card._role_combos[role].currentData()]
        return f"Choose: {', '.join(missing)}"

    def _request_help(self) -> None:
        self.publish_event(UIEvents.HELP_REQUESTED, {"topic_id": CHART_TOPIC_SERIES})

    def series_config(self) -> dict:
        """Return the card's role-keyed column config (see `SeriesConfigCard.get_series_config`)."""
        return self.card.get_series_config()

    def _apply_theme(self) -> None:
        # Widget rules are scoped to `SeriesConfigCard`, not to this dialog: the Help window
        # is created as a child of the active modal dialog and would otherwise inherit them.
        theme_manager = self.app_context.get_manager(ThemeManager)
        palette = theme_manager.get_surface_palette()
        card_bg = palette.get("card_bg", "#f8f9fa")
        base_fg = palette.get("base_fg", "#000000")
        self.setStyleSheet(
            f"AddSeriesDialog {{ background-color: {card_bg}; color: {base_fg}; }}\n"
            + series_form_stylesheet(palette, scope="SeriesConfigCard")
        )
        self.heading_label.setStyleSheet(f"color: {base_fg}; font-weight: bold;")
        self.card.set_tokens(theme_manager.get_design_tokens())
