"""Data tab: series/fit management -- add/remove, accordion expand/collapse,
selection, and the shared persistent dataset/X/Y/Y-axis/label configuration
form reparented into whichever card is currently selected.
"""
from typing import List, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from pandaplot.commands.project.chart import (
    AddSeriesCommand,
    ConvertSeriesToFitCommand,
    RemoveFitDataCommand,
    RemoveSeriesCommand,
    ReorderSeriesCommand,
)
from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.models.chart.chart_type_spec import CHART_TYPE_SPECS
from pandaplot.models.chart.error_bar_config import ErrorBarConfig
from pandaplot.models.chart.series_style_builder import build_series_style
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items import Dataset
from pandaplot.models.project.items.chart import DataSeries, YAxis, resolve_manual_fit_source_data
from pandaplot.services.theme.theme_manager import ThemeManager
from pandaplot.utils.item_display_options import dataset_display_options

# itemData for the Series Type combo's non-retype "Fit" entry -- selecting
# it doesn't retype the series in place like a real SeriesType; it converts
# the series into a FitData entry instead (see
# DataTab._convert_selected_series_to_fit and #298). Kept distinct from any
# SeriesType member so `currentData()` can tell the two apart.
_CONVERT_TO_FIT = "__convert_to_fit__"


class DataTab(QWidget):
    """Series/fit-data management: an expand/collapse card per series (plus
    any fit-data entries), backed by a single persistent configuration form
    that is reparented into whichever card is currently expanded (tracked by
    `self._expanded_series_index`).

    Selection (`self._expanded_series_index`) drives the Style tab's editing
    target (via `seriesSelected`) and the live configuration form shown here.
    It is independent of `self._expanded_card_indices`, which is purely the
    visual accordion open/closed state: a card can be expanded (showing its
    read-only detail row) without being selected.
    """

    configChanged = Signal()
    # Emitted for a dataset/X/Y/Y-axis edit on the selected series: this
    # marks the chart dirty but, matching pre-refactor behavior, must NOT
    # trigger a CHART_UPDATED publish the way `configChanged` does via the
    # panel's `_on_any_tab_config_changed` (see `_on_series_config_changed`).
    dirtyOnly = Signal()
    # Emitted whenever a series/fit becomes the selected entry -- consumed by
    # the panel to drive `StyleTab.set_selected(kind, obj)`.
    seriesSelected = Signal(str, object)
    # Emitted at the end of every card-list rebuild with the fresh
    # (data_series, fit_data) lists -- consumed by `StyleTab.set_series_list`
    # to keep its own chip row in lockstep with the Data tab's card list.
    seriesListChanged = Signal(list, list)
    # Emitted whenever a series edit could affect the Y2 axis chip (add/
    # remove/y_axis change) -- consumed by the panel to call
    # `AxesTab.refresh_axis_chips(chart)`, since this tab has no direct
    # reference to the Axes tab.
    axesRefreshRequested = Signal()

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.command_executor = app_context.command_executor
        self.current_project = None
        self.current_chart = None  # Current Chart object being edited
        self.datasets: List = []
        self._updating_controls: bool = False  # Guard to prevent feedback loops
        self._pending_label: str = ""  # Buffer while user types label
        # Reference to the expanded card's Y1/Y2 badge QLabel (and the design
        # tokens it was last styled with), so a live series Y-axis edit can
        # restyle it in place. See _on_series_config_changed.
        self._expanded_card_y_axis_badge: Optional[QLabel] = None
        self._expanded_card_y_axis_badge_tokens: dict = {}
        # Which entry (data series index, then fit-data index appended after
        # all series) is currently *selected* -- drives the Style tab's
        # editing target and the live configuration form shown below.
        # Independent of `_expanded_card_indices` below: a card can be
        # expanded (accordion open) without being selected.
        self._expanded_series_index: int = 0
        # Purely-visual accordion state: which cards show their expanded
        # detail view. The selected card is always implicitly expanded (it
        # hosts the live form) even if its index isn't in this set.
        self._expanded_card_indices: set = {0}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self._create_series_management_section(layout)
        layout.addStretch(1)

        self._connect_signals()

    @property
    def selected_index(self) -> int:
        return self._expanded_series_index

    # -- Construction ---------------------------------------------------

    def _create_series_management_section(self, layout):
        """Create the data series management section: an expand/collapse card
        per series (plus any fit-data entries), backed by a single persistent
        configuration form that is reparented into whichever card is
        currently expanded (tracked by `self._expanded_series_index`).
        """
        header_row = QHBoxLayout()
        self._series_section_header = SectionHeader("Series")
        header_row.addWidget(self._series_section_header)
        header_row.addStretch(1)
        self.add_series_button = PButton(
            "+ Add series", role="secondary", on_click=self._add_series
        )
        self.add_series_button.setCursor(Qt.CursorShape.PointingHandCursor)
        header_row.addWidget(self.add_series_button)
        layout.addLayout(header_row)

        self._series_cards_container = QWidget()
        self._series_cards_layout = QVBoxLayout(self._series_cards_container)
        self._series_cards_layout.setContentsMargins(0, 0, 0, 0)
        self._series_cards_layout.setSpacing(6)
        layout.addWidget(self._series_cards_container)

        # Persistent configuration form (dataset/X/Y/Y-axis/label). Created
        # once so signal connections in _connect_signals stay valid for the
        # tab's lifetime; it gets moved (reparented) into whichever card is
        # currently expanded by _build_expanded_series_card.
        self._series_form_widget = QWidget()
        series_config_layout = QGridLayout(self._series_form_widget)
        series_config_layout.setContentsMargins(0, 0, 0, 0)

        series_config_layout.addWidget(QLabel("Dataset:"), 0, 0)
        self.dataset_combo = QComboBox()
        series_config_layout.addWidget(self.dataset_combo, 0, 1)

        series_config_layout.addWidget(QLabel("X Column:"), 1, 0)
        self.x_column_combo = QComboBox()
        series_config_layout.addWidget(self.x_column_combo, 1, 1)

        series_config_layout.addWidget(QLabel("Y Column:"), 2, 0)
        self.y_column_combo = QComboBox()
        series_config_layout.addWidget(self.y_column_combo, 2, 1)

        self.z_column_label = QLabel("Z Column:")
        series_config_layout.addWidget(self.z_column_label, 3, 0)
        self.z_column_combo = QComboBox()
        self.z_column_combo.setToolTip(
            "Z column: mapped to color for a Colormap/Heatmap series, "
            "or the third axis for a 3D series")
        series_config_layout.addWidget(self.z_column_combo, 3, 1)

        self.u_column_label = QLabel("U Column:")
        series_config_layout.addWidget(self.u_column_label, 4, 0)
        self.u_column_combo = QComboBox()
        series_config_layout.addWidget(self.u_column_combo, 4, 1)

        self.v_column_label = QLabel("V Column:")
        series_config_layout.addWidget(self.v_column_label, 5, 0)
        self.v_column_combo = QComboBox()
        series_config_layout.addWidget(self.v_column_combo, 5, 1)

        series_config_layout.addWidget(QLabel("Y Axis:"), 6, 0)
        self.series_y_axis_control = SegmentedControl(
            [("Y₁ left", YAxis.PRIMARY), ("Y₂ right", YAxis.SECONDARY)]
        )
        series_config_layout.addWidget(self.series_y_axis_control, 6, 1)

        series_config_layout.addWidget(QLabel("Label:"), 7, 0)
        self.series_label_edit = QLineEdit()
        series_config_layout.addWidget(self.series_label_edit, 7, 1)

        # Checked -> pick independent +/- error columns below; unchecked
        # (default) -> a single column supplies a symmetric magnitude (the
        # rendered direction is then controlled by the Style tab's Error
        # Bars > Direction control).
        self.error_asymmetric_check = QCheckBox("Asymmetric Error Bars")
        self.error_asymmetric_check.setToolTip(
            "When checked, pick separate +/- error columns for independent "
            "upper/lower magnitudes instead of one symmetric column.")
        series_config_layout.addWidget(self.error_asymmetric_check, 8, 0, 1, 2)

        # Label text switches between "X Error Column" (symmetric magnitude)
        # and "X Error (+) Column" (asymmetric upper magnitude) depending on
        # the checkbox above; see _update_error_bar_mode_controls.
        self.x_error_column_label = QLabel("X Error Column:")
        series_config_layout.addWidget(self.x_error_column_label, 9, 0)
        self.x_error_column_combo = QComboBox()
        series_config_layout.addWidget(self.x_error_column_combo, 9, 1)

        self.x_error_minus_label = QLabel("X Error (-) Column:")
        series_config_layout.addWidget(self.x_error_minus_label, 10, 0)
        self.x_error_minus_column_combo = QComboBox()
        series_config_layout.addWidget(self.x_error_minus_column_combo, 10, 1)

        self.y_error_column_label = QLabel("Y Error Column:")
        series_config_layout.addWidget(self.y_error_column_label, 11, 0)
        self.y_error_column_combo = QComboBox()
        series_config_layout.addWidget(self.y_error_column_combo, 11, 1)

        # Only shown when "Asymmetric Error Bars" is checked, to supply the
        # lower-side (-) magnitude.
        self.y_error_minus_label = QLabel("Y Error (-) Column:")
        series_config_layout.addWidget(self.y_error_minus_label, 12, 0)
        self.y_error_minus_column_combo = QComboBox()
        series_config_layout.addWidget(self.y_error_minus_column_combo, 12, 1)

        self.magnitude_column_label = QLabel("Color-by Column (optional):")
        series_config_layout.addWidget(self.magnitude_column_label, 13, 0)
        self.magnitude_column_combo = QComboBox()
        series_config_layout.addWidget(self.magnitude_column_combo, 13, 1)

        series_config_layout.addWidget(QLabel("Series Type:"), 14, 0)
        self.series_type_combo = QComboBox()
        series_config_layout.addWidget(self.series_type_combo, 14, 1)

        # Only meaningful right before converting a series to a fit (see
        # _convert_selected_series_to_fit): read at that moment to snapshot
        # optional confidence-band columns into the new FitData. Not
        # persisted on DataSeries itself -- there is nothing to restore
        # from the model on reload, so these simply reset to "None" each
        # time _load_series_into_controls repopulates them.
        self.confidence_lower_column_label = QLabel("Confidence Lower Column (optional):")
        series_config_layout.addWidget(self.confidence_lower_column_label, 15, 0)
        self.confidence_lower_column_combo = QComboBox()
        series_config_layout.addWidget(self.confidence_lower_column_combo, 15, 1)

        self.confidence_upper_column_label = QLabel("Confidence Upper Column (optional):")
        series_config_layout.addWidget(self.confidence_upper_column_label, 16, 0)
        self.confidence_upper_column_combo = QComboBox()
        series_config_layout.addWidget(self.confidence_upper_column_combo, 16, 1)

        for widget in (
            self.z_column_label, self.z_column_combo,
            self.u_column_label, self.u_column_combo,
            self.v_column_label, self.v_column_combo,
            self.magnitude_column_label, self.magnitude_column_combo,
        ):
            widget.setVisible(False)

        self._rebuild_series_cards()

    def _connect_signals(self):
        """Connect widget signals."""
        self.dataset_combo.currentTextChanged.connect(self._on_dataset_changed)
        self.x_column_combo.currentTextChanged.connect(self._on_series_config_changed)
        self.y_column_combo.currentTextChanged.connect(self._on_series_config_changed)
        self.series_y_axis_control.currentValueChanged.connect(self._on_series_config_changed)
        self.x_error_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.y_error_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.x_error_minus_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.y_error_minus_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.z_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.u_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.v_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.magnitude_column_combo.currentIndexChanged.connect(self._on_series_config_changed)
        self.confidence_lower_column_combo.currentIndexChanged.connect(self._on_confidence_column_changed)
        self.confidence_upper_column_combo.currentIndexChanged.connect(self._on_confidence_column_changed)
        self.error_asymmetric_check.toggled.connect(self._on_error_symmetry_toggled)
        self.series_type_combo.currentIndexChanged.connect(self._on_series_type_changed)
        # Defer label persistence to editingFinished to avoid disruptive refresh while typing
        self.series_label_edit.textChanged.connect(self._on_label_typing)
        self.series_label_edit.editingFinished.connect(self._on_label_committed)

    # -- Selection / accordion -------------------------------------------

    def _expand_series(self, index: int):
        """Select `index` as the tab's live-edited entry: it drives the
        configuration form, the Style tab's target (via `seriesSelected`),
        and the selected-card border highlight. Independent of any other
        card's accordion open/closed state (`_expanded_card_indices`) -- see
        `_toggle_card_expanded` for that purely-visual toggle."""
        self._expanded_series_index = index
        self._expanded_card_indices.add(index)
        self._rebuild_series_cards()
        if not self.current_chart:
            return
        if index < len(self.current_chart.data_series):
            self.seriesSelected.emit("series", self.current_chart.data_series[index])
        else:
            self.seriesSelected.emit(
                "fit", self.current_chart.fit_data[index - len(self.current_chart.data_series)]
            )

    def _toggle_card_expanded(self, index: int):
        """Purely-visual accordion toggle: show/hide a card's read-only
        detail view, independent of which card is *selected*."""
        if index in self._expanded_card_indices:
            self._expanded_card_indices.discard(index)
        else:
            self._expanded_card_indices.add(index)
        self._rebuild_series_cards()

    def _rebuild_series_cards(self):
        """Rebuild the Data tab's card list from `self.current_chart`.

        Each entry renders as one of three variants: the *selected* entry
        always gets the full configuration card (hosting the one shared,
        live-wired form widget); other entries in `self._expanded_card_indices`
        get a read-only detail row (a purely visual accordion state,
        independent of selection); everything else gets the collapsed chip
        row.

        Safe to call at any point: fetches fresh theme tokens, so this also
        serves as the mechanism for picking up a live theme change (see
        `apply_theme`).
        """
        # Detach the persistent form widget from whatever card currently
        # hosts it *before* that card is torn down below, so it survives
        # the rebuild instead of being deleted as a child of a discarded card.
        if self._series_form_widget.parent() is not None:
            self._series_form_widget.setParent(None)

        while self._series_cards_layout.count():
            item = self._series_cards_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        theme_manager = self.app_context.get_manager(ThemeManager)
        tokens = theme_manager.get_design_tokens()

        if not self.current_chart:
            self.seriesListChanged.emit([], [])
            self.axesRefreshRequested.emit()
            return

        total_series = len(self.current_chart.data_series)

        for index, series in enumerate(self.current_chart.data_series):
            if index == self._expanded_series_index:
                card = self._build_expanded_series_card(index, tokens)
            elif index in self._expanded_card_indices:
                card = self._build_series_detail_row(series, index, tokens)
            else:
                card = self._build_collapsed_series_row(series, index, tokens)
            self._series_cards_layout.addWidget(card)

        for fit_offset, fit in enumerate(self.current_chart.fit_data):
            index = total_series + fit_offset
            if index == self._expanded_series_index:
                card = self._build_expanded_series_card(index, tokens)
            elif index in self._expanded_card_indices:
                card = self._build_fit_detail_row(fit, index, tokens)
            else:
                card = self._build_collapsed_fit_row(fit, index, tokens)
            self._series_cards_layout.addWidget(card)

        self.seriesListChanged.emit(self.current_chart.data_series, self.current_chart.fit_data)
        self.axesRefreshRequested.emit()

    # -- Card-building helpers --------------------------------------------

    def _make_swatch(self, color: str, tokens: dict) -> QFrame:
        swatch = QFrame()
        swatch.setFixedSize(14, 14)
        swatch.setStyleSheet(
            f"background-color: {color}; "
            f"border: 1px solid {tokens.get('border_control', '#999')}; "
            f"border-radius: {tokens.get('radius_swatch', 4)}px;"
        )
        return swatch

    def _build_trash_button(self, index: int) -> QPushButton:
        """Per-row delete icon (replaces the old single bottom Remove button
        so a specific series/fit can be removed regardless of which entry
        is selected/expanded)."""
        button = PButton(
            "\U0001f5d1", role="destructive", icon=True,  # wastebasket emoji
            on_click=lambda _checked=False, i=index: self._remove_series_at(i)
        )
        button.setFixedWidth(24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Remove")
        return button

    def _build_move_up_button(self, index: int) -> QPushButton:
        """Move this series one position earlier in the plotting order --
        i.e. it now draws *under* the series that used to be right before
        it (#189). Series-only (fit data has no reorder controls: fits
        always draw after every series regardless of list position -- see
        chart_editor.py's separate, always-later fit-plotting loop)."""
        button = PButton(
            "▲", role="secondary", icon=True,  # ▲
            on_click=lambda _checked=False, i=index: self._move_series(i, i - 1)
        )
        button.setAccessibleName("Move series up")
        button.setFixedWidth(24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Move up (draw earlier, further back)")
        button.setEnabled(index > 0)
        return button

    def _build_move_down_button(self, index: int, total_series: int) -> QPushButton:
        """Move this series one position later in the plotting order --
        drawn *over* the series that used to be right after it (#189)."""
        button = PButton(
            "▼", role="secondary", icon=True,  # ▼
            on_click=lambda _checked=False, i=index: self._move_series(i, i + 1)
        )
        button.setFixedWidth(24)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setToolTip("Move down (draw later, further to front)")
        button.setEnabled(index < total_series - 1)
        return button

    def _build_chevron_button(self, index: int, *, expanded: bool) -> QPushButton:
        """Accordion toggle: purely visual expand/collapse, independent of
        selection (see `_toggle_card_expanded`)."""
        chevron = PButton(
            "▾" if expanded else "▸", role="secondary", icon=True,
            on_click=lambda _checked=False, i=index: self._toggle_card_expanded(i)
        )
        chevron.setFixedWidth(24)
        chevron.setCursor(Qt.CursorShape.PointingHandCursor)
        return chevron

    def _install_select_on_click(self, card: QWidget, index: int):
        """Clicking anywhere on a collapsed/detail card's background selects
        it (moves the live-edited entry there), without affecting its own or
        any other card's accordion open/closed state."""
        def _handler(event, i=index):
            if event.button() == Qt.MouseButton.LeftButton:
                self._expand_series(i)
            event.accept()
        card.mousePressEvent = _handler
        card.setCursor(Qt.CursorShape.PointingHandCursor)

    def _build_collapsed_series_row(self, series, index: int, tokens: dict) -> QWidget:
        """A chip-like collapsed row: color square, name, Y-axis badge, trash, chevron."""
        card = Card()
        card.set_tokens(tokens)
        self._install_select_on_click(card, index)
        row = QHBoxLayout(card)

        row.addWidget(self._make_swatch(series.style.swatch_color, tokens))

        name_label = QLabel(series.label or f"{series.dataset_id}:{self._column_display_name(series.dataset_id, series.y_column_id, series.y_column)}")
        name_label.setStyleSheet(f"color: {tokens.get('text_primary', '#000')};")
        row.addWidget(name_label, 1)

        row.addWidget(self._build_y_axis_badge(series.y_axis, tokens))
        total_series = len(self.current_chart.data_series)
        row.addWidget(self._build_move_up_button(index))
        row.addWidget(self._build_move_down_button(index, total_series))
        row.addWidget(self._build_trash_button(index))
        row.addWidget(self._build_chevron_button(index, expanded=False))

        return card

    def _build_collapsed_fit_row(self, fit, index: int, tokens: dict) -> QWidget:
        """Collapsed row for a fit-data entry (no Y-axis picker for fits)."""
        card = Card()
        card.set_tokens(tokens)
        self._install_select_on_click(card, index)
        row = QHBoxLayout(card)

        row.addWidget(self._make_swatch(fit.style.color, tokens))

        name_label = QLabel(f"\U0001f527 {fit.label}")  # wrench emoji
        name_label.setStyleSheet(f"color: {tokens.get('text_primary', '#000')};")
        row.addWidget(name_label, 1)

        row.addWidget(self._build_trash_button(index))
        row.addWidget(self._build_chevron_button(index, expanded=False))

        return card

    def _dataset_display_name(self, dataset_id: str) -> str:
        """Resolve a dataset id to its display name, falling back to the raw
        id if the dataset can't be found (e.g. it was deleted)."""
        if self.current_project:
            dataset = self.current_project.find_item(dataset_id)
            if isinstance(dataset, Dataset):
                return dataset.name
        return dataset_id

    def _build_detail_field_grid(self, tokens: dict, fields: tuple) -> QGridLayout:
        """A read-only label/value grid matching the editable form's own
        label-left/value-right layout (see `_create_series_management_section`),
        used by the accordion-expanded-but-not-selected detail rows so they
        read like a stripped-down version of the same form rather than a
        single dense summary line."""
        grid = QGridLayout()
        grid.setContentsMargins(0, 6, 0, 0)
        for row, (label_text, value) in enumerate(fields):
            label = QLabel(label_text)
            label.setStyleSheet(f"color: {tokens.get('text_muted', '#666')};")
            grid.addWidget(label, row, 0)
            value_label = QLabel(value)
            value_label.setStyleSheet(f"color: {tokens.get('text_primary', '#000')};")
            grid.addWidget(value_label, row, 1)
        return grid

    def _build_series_detail_row(self, series, index: int, tokens: dict) -> QWidget:
        """Read-only detail view for a series card that's accordion-expanded
        but not the currently *selected* entry -- purely visual, since the
        one shared live-editable form can only live on the selected card.
        Mirrors the editable form's own fields (dataset/X/Y), but shows the
        dataset's display name rather than its id."""
        card = Card()
        card.set_tokens(tokens)
        self._install_select_on_click(card, index)
        outer = QVBoxLayout(card)

        header = QHBoxLayout()
        header.addWidget(self._make_swatch(series.style.swatch_color, tokens))
        name_label = QLabel(series.label or f"{series.dataset_id}:{self._column_display_name(series.dataset_id, series.y_column_id, series.y_column)}")
        name_label.setStyleSheet(f"color: {tokens.get('text_primary', '#000')};")
        header.addWidget(name_label, 1)
        header.addWidget(self._build_y_axis_badge(series.y_axis, tokens))
        total_series = len(self.current_chart.data_series)
        header.addWidget(self._build_move_up_button(index))
        header.addWidget(self._build_move_down_button(index, total_series))
        header.addWidget(self._build_trash_button(index))
        header.addWidget(self._build_chevron_button(index, expanded=True))
        outer.addLayout(header)

        outer.addLayout(self._build_detail_field_grid(tokens, (
            ("Dataset:", self._dataset_display_name(series.dataset_id)),
            ("X Column:", self._column_display_name(series.dataset_id, series.x_column_id, series.x_column)),
            ("Y Column:", self._column_display_name(series.dataset_id, series.y_column_id, series.y_column)),
        )))

        return card

    def _build_fit_detail_row(self, fit, index: int, tokens: dict) -> QWidget:
        """Read-only detail view for a fit card that's accordion-expanded but
        not the currently selected entry (see `_build_series_detail_row`)."""
        card = Card()
        card.set_tokens(tokens)
        self._install_select_on_click(card, index)
        outer = QVBoxLayout(card)

        header = QHBoxLayout()
        header.addWidget(self._make_swatch(fit.style.color, tokens))
        name_label = QLabel(f"\U0001f527 {fit.label}")
        name_label.setStyleSheet(f"color: {tokens.get('text_primary', '#000')};")
        header.addWidget(name_label, 1)
        header.addWidget(self._build_trash_button(index))
        header.addWidget(self._build_chevron_button(index, expanded=True))
        outer.addLayout(header)

        outer.addLayout(self._build_detail_field_grid(tokens, (
            ("Dataset:", self._dataset_display_name(fit.source_dataset_id)),
            ("Fit Type:", fit.fit_type),
            ("X Column:", self._column_display_name(fit.source_dataset_id, fit.source_x_column_id, fit.source_x_column)),
            ("Y Column:", self._column_display_name(fit.source_dataset_id, fit.source_y_column_id, fit.source_y_column)),
        )))

        return card

    def _build_y_axis_badge(self, y_axis, tokens: dict) -> QLabel:
        """Small 'Y₁'/'Y₂' badge, accented for the secondary axis."""
        badge = QLabel()
        self._apply_y_axis_badge_style(badge, y_axis, tokens)
        return badge

    def _apply_y_axis_badge_style(self, badge: QLabel, y_axis, tokens: dict):
        """Set a Y-axis badge's text/style in place (shared by initial build
        and live in-place refresh from `_on_series_config_changed`)."""
        is_secondary = y_axis == YAxis.SECONDARY
        badge.setText("Y₂" if is_secondary else "Y₁")
        bg = tokens.get("y2_accent_bg") if is_secondary else tokens.get("surface_inset", "#eee")
        fg = tokens.get("y2_accent") if is_secondary else tokens.get("text_muted", "#666")
        badge.setStyleSheet(
            f"background-color: {bg}; color: {fg}; "
            f"border-radius: {tokens.get('radius_chip', 12)}px; "
            "padding: 1px 8px; font-size: 10px; font-weight: 600;"
        )

    def _build_expanded_series_card(self, index: int, tokens: dict) -> QWidget:
        """The expanded card for the currently *selected* entry: title + the
        persistent config form, loaded with `index`'s values (a data-series
        index, or a fit-data index appended after all series, matching the
        combined indexing used throughout this tab). Rendered with an
        accent border (via the "selected" dynamic property) to distinguish
        it from unselected cards."""
        card = Card()
        card.set_tokens(tokens)
        card.setProperty("selected", True)  # noqa: FBT003 - Qt bound method, positional-only
        card.style().unpolish(card)
        card.style().polish(card)
        outer = QVBoxLayout(card)

        total_series = len(self.current_chart.data_series)
        is_fit = index >= total_series
        if is_fit:
            fit = self.current_chart.fit_data[index - total_series]
            title_text = f"\U0001f527 {fit.label}"
        else:
            series = self.current_chart.data_series[index]
            title_text = series.label or (
                f"{series.dataset_id}:"
                f"{self._column_display_name(series.dataset_id, series.y_column_id, series.y_column)}"
            )

        header = QHBoxLayout()
        title_label = QLabel(title_text)
        title_label.setStyleSheet(f"font-weight: 600; color: {tokens.get('text_primary', '#000')};")
        header.addWidget(title_label, 1)
        # Keep a reference so _on_series_config_changed can refresh this
        # badge in place on a live Y-axis edit, without a full card rebuild
        # (see that method's docstring for why a rebuild is unsafe there).
        self._expanded_card_y_axis_badge = None
        if not is_fit:
            badge = self._build_y_axis_badge(series.y_axis, tokens)
            self._expanded_card_y_axis_badge = badge
            self._expanded_card_y_axis_badge_tokens = tokens
            header.addWidget(badge)
            header.addWidget(self._build_move_up_button(index))
            header.addWidget(self._build_move_down_button(index, total_series))
        header.addWidget(self._build_trash_button(index))
        chevron = PButton(
            "▾", role="secondary", icon=True, enabled=False
        )  # ▾, indicates "currently expanded"
        chevron.setFixedWidth(24)
        header.addWidget(chevron)
        outer.addLayout(header)

        outer.addWidget(self._series_form_widget)

        if is_fit:
            self._load_fit_into_controls(fit)
            self.seriesSelected.emit("fit", fit)
        else:
            self._reset_controls_for_series()
            self._load_series_into_controls(series)
            self.seriesSelected.emit("series", series)

        return card

    # -- Add / remove -------------------------------------------------------

    def _add_series(self):
        """Add a new data series."""
        if not self.current_chart:
            return

        # Create a new series with default values. Combos carry the column id
        # as itemData; currentText() is only used to build the display label.
        dataset_id = self.dataset_combo.currentData() if self.dataset_combo.count() > 0 else ""
        dataset_name = self.dataset_combo.currentText() if self.dataset_combo.count() > 0 else ""
        x_column_id = self.x_column_combo.currentData() if self.x_column_combo.count() > 0 else ""
        y_column_id = self.y_column_combo.currentData() if self.y_column_combo.count() > 0 else ""
        y_column_name = self.y_column_combo.currentText() if self.y_column_combo.count() > 0 else ""
        u_column_id = self.u_column_combo.currentData() if self.u_column_combo.count() > 0 else ""
        v_column_id = self.v_column_combo.currentData() if self.v_column_combo.count() > 0 else ""
        magnitude_column_id = self.magnitude_column_combo.currentData() if self.magnitude_column_combo.count() > 0 else ""
        z_column_id = self.z_column_combo.currentData() if self.z_column_combo.count() > 0 else ""

        # A new series always gets the chart's own default type -- NOT
        # whatever the Series Type combo currently shows, since that combo
        # tracks whichever EXISTING series is selected (see
        # _load_series_into_controls) and merely looking at, say, a
        # Scatter series on a Line chart must not silently make the next
        # brand-new series Scatter too. To add a non-default type, add the
        # series (it gets the chart's default) then retype it via the
        # combo, same as retyping any other series.
        new_series_type = CHART_TYPE_SPECS[self.current_chart.chart_type].default_series_type
        # No "vector_ready" gate: u_column_id/v_column_id above reflect
        # whichever EXISTING series is currently selected, not the type
        # being created here -- if that series doesn't need them (e.g. a
        # Line series selected on a Vector chart), the U/V combos are
        # legitimately hidden and blank, and requiring them upfront would
        # make "+Add series" silently do nothing. Instead, create the
        # series with whatever U/V values happen to be available (often
        # empty) -- an incomplete Vector series already renders a graceful
        # "no U/V column configured" message, recoverable by selecting the
        # new series and filling in U/V via its own now-visible combos,
        # exactly matching apply_to's already-established bootstrap path.
        if dataset_id and x_column_id and y_column_id:
            style = build_series_style(
                new_series_type,
                color=self._get_next_series_color(),
                u_column_id=u_column_id,
                v_column_id=v_column_id,
                magnitude_column_id=magnitude_column_id,
                z_column_id=z_column_id or "",
            )

            new_series = DataSeries(
                dataset_id=dataset_id,
                x_column_id=x_column_id,
                y_column_id=y_column_id,
                label=f"{dataset_name}:{y_column_name}",
                series_type=new_series_type,
                style=style,
            )
            command = AddSeriesCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                series=new_series,
            )
            self.command_executor.execute_command(command)

            # Select the newly added series
            new_index = len(self.current_chart.data_series) - 1
            self._expanded_series_index = new_index
            self._expanded_card_indices.add(new_index)
            self._rebuild_series_cards()

    def _remove_series_at(self, index: int):
        """Remove the data series or fit-data entry at the combined `index`
        (data-series indices first, then fit-data indices appended after),
        adjusting selection and accordion state for the index shift."""
        if not self.current_chart:
            return

        total_series = len(self.current_chart.data_series)
        total_items = total_series + len(self.current_chart.fit_data)
        if index < 0 or index >= total_items:
            return

        if index < total_series:
            command = RemoveSeriesCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                series_index=index,
            )
        else:
            command = RemoveFitDataCommand(
                self.app_context,
                chart_id=self.current_chart.id,
                fit_index=index - total_series,
            )
        self.command_executor.execute_command(command)

        def _shift(i):
            if i > index:
                return i - 1
            if i == index:
                return None
            return i

        self._expanded_card_indices = {
            shifted for shifted in (_shift(i) for i in self._expanded_card_indices)
            if shifted is not None
        }

        remaining_items = len(self.current_chart.data_series) + len(self.current_chart.fit_data)
        shifted_selected = _shift(self._expanded_series_index)
        if shifted_selected is None:
            shifted_selected = index
        self._expanded_series_index = max(0, min(shifted_selected, max(remaining_items - 1, 0)))
        self._expanded_card_indices.add(self._expanded_series_index)
        self._rebuild_series_cards()

    def _move_series(self, from_index: int, to_index: int):
        """Move the data series at `from_index` to `to_index`, reordering
        its z-index (#189). The move-up/move-down buttons only ever request
        an adjacent step, and a single-step pop-then-insert is exactly a
        swap of those two positions, so the expanded/selected-card
        bookkeeping below just swaps the same two indices rather than
        needing `_remove_series_at`'s general shift-everything-between."""
        if not self.current_chart:
            return
        total_series = len(self.current_chart.data_series)
        if not (0 <= from_index < total_series) or not (0 <= to_index < total_series):
            return

        command = ReorderSeriesCommand(
            self.app_context,
            chart_id=self.current_chart.id,
            from_index=from_index,
            to_index=to_index,
        )
        if not self.command_executor.execute_command(command):
            return

        def _swap(i):
            if i == from_index:
                return to_index
            if i == to_index:
                return from_index
            return i

        self._expanded_card_indices = {_swap(i) for i in self._expanded_card_indices}
        self._expanded_series_index = _swap(self._expanded_series_index)
        self._rebuild_series_cards()

    # -- Live field edits -----------------------------------------------

    def _on_series_config_changed(self):
        """Handle dataset / column configuration changes for the selected series.

        Label changes are intentionally deferred to editingFinished handled by
        _on_label_committed to avoid disruptive list refresh while typing.
        """
        if self._updating_controls or not self.current_chart:
            return

        current_row = self._expanded_series_index
        if current_row < 0:
            return

        total_series = len(self.current_chart.data_series)
        if current_row < total_series:
            # Update data series (guard for safety)
            if current_row >= len(self.current_chart.data_series):
                return
            series = self.current_chart.data_series[current_row]
            if self.dataset_combo.currentData():
                series.dataset_id = self.dataset_combo.currentData()
            # Combos carry the stable column id as itemData; store ids directly.
            series.x_column_id = self.x_column_combo.currentData() or ""
            series.y_column_id = self.y_column_combo.currentData() or ""
            series.y_axis = self.series_y_axis_control.currentValue()
            error_bars = getattr(series.style, "error_bars", None)
            if error_bars is not None:
                error_bars.x_error_column_id = self.x_error_column_combo.currentData() or ""
                error_bars.y_error_column_id = self.y_error_column_combo.currentData() or ""
                error_bars.x_error_minus_column_id = self.x_error_minus_column_combo.currentData() or ""
                error_bars.y_error_minus_column_id = self.y_error_minus_column_combo.currentData() or ""
                error_bars.error_symmetric = not self.error_asymmetric_check.isChecked()
            if self._selected_series_is_vector():
                series.style.u_column_id = self.u_column_combo.currentData() or ""
                series.style.v_column_id = self.v_column_combo.currentData() or ""
                series.style.magnitude_column_id = self.magnitude_column_combo.currentData() or ""
            if self._selected_series_needs_z_column():
                series.style.z_column_id = self.z_column_combo.currentData() or ""

            # Refresh the Axes-tab Y2 chip immediately so switching a series
            # to the secondary axis is reflected without waiting for Apply
            # or a full chart reload. This only touches the axis_chips
            # SegmentedControl (not this tab's card list), so it's safe to
            # request from here.
            self.axesRefreshRequested.emit()

            # Re-emit `seriesSelected` for the still-selected series: the
            # panel wires this to `StyleTab.set_selected`, which re-checks
            # whether the Error Bars card should show now that an error
            # column may have just been added/cleared here. (The Style tab
            # lives on a different tab and has no other way to learn about
            # this edit.)
            self.seriesSelected.emit("series", series)

            # Update the expanded card's own Y1/Y2 badge in place too.
            # Deliberately NOT calling `_rebuild_series_cards()` from this
            # handler: that tears down and rebuilds the card list, including
            # detaching/reattaching `_series_form_widget` (which hosts the
            # very control that triggered this handler) - the same
            # reentrancy hazard already fixed once for live-edit handlers
            # touching the reparented series form widget. Updating the
            # existing badge label in place avoids that entirely.
            if getattr(self, "_expanded_card_y_axis_badge", None) is not None:
                self._apply_y_axis_badge_style(
                    self._expanded_card_y_axis_badge,
                    series.y_axis,
                    getattr(self, "_expanded_card_y_axis_badge_tokens", {}),
                )
        else:
            fit_index = current_row - total_series
            if fit_index < 0 or fit_index >= len(self.current_chart.fit_data):
                return
            fit = self.current_chart.fit_data[fit_index]
            if not fit.is_manual:
                # Auto-applied fits (from the Fit panel): source
                # dataset/columns are frozen at fit time, not editable.
                return
            self._apply_manual_fit_edits(fit)

        # Deliberately `dirtyOnly`, not `configChanged`: pre-refactor, this
        # exact edit path (dataset/X/Y/Y-axis on the selected series) set the
        # dirty flag and updated the status indicator but never published
        # ChartEvents.CHART_UPDATED. Routing it through `configChanged`
        # instead would make the panel's shared `_on_any_tab_config_changed`
        # publish CHART_UPDATED for every keystroke-driven combo change here,
        # which is a behavior change the refactor isn't meant to introduce.
        self.dirtyOnly.emit()

    def _apply_manual_fit_edits(self, fit):
        """Re-derive a manually-converted fit's data from its (possibly
        just-changed) source dataset/columns -- mirrors the live-edit
        semantics of a regular DataSeries' dataset/X/Y combos, except the
        result is still a snapshot (FitData.x_data/y_data are plain
        arrays, not a live reference): it's re-taken on every edit here
        rather than resolved at render time. Only reached for a
        manually-converted fit (fit.is_manual) -- see
        _on_series_config_changed.

        Applied atomically: X, Y, and any NON-empty confidence column
        pick must all resolve to real data before any of
        source_dataset_id/source_x_column_id/source_y_column_id/
        confidence_*_column_id are written, and before
        x_data/y_data/confidence_lower/confidence_upper are replaced.
        Committing a source id while leaving stale (or absent) data in
        place would let a combo show a new source while the chart still
        plots the old data (or silently drops a confidence band) with no
        indication anything is wrong -- an edit that can't be fully
        resolved is rejected as a whole, and the controls are reloaded to
        reflect the fit's actual, unchanged state instead. An EMPTY
        confidence column pick ("None") is always valid -- it just means
        no confidence band.
        """
        dataset_id = self.dataset_combo.currentData() or fit.source_dataset_id
        x_column_id = self.x_column_combo.currentData() or ""
        y_column_id = self.y_column_combo.currentData() or ""
        confidence_lower_column_id = self.confidence_lower_column_combo.currentData() or ""
        confidence_upper_column_id = self.confidence_upper_column_combo.currentData() or ""

        dataset = self.current_project.find_item(dataset_id) if self.current_project else None
        dataset = dataset if isinstance(dataset, Dataset) else None

        resolved = resolve_manual_fit_source_data(
            dataset,
            x_column_id,
            y_column_id,
            confidence_lower_column_id,
            confidence_upper_column_id,
        )
        if resolved is None:
            self._load_fit_into_controls(fit)
            return
        new_x, new_y, new_confidence_lower, new_confidence_upper = resolved

        fit.source_dataset_id = dataset_id
        fit.source_x_column_id = x_column_id
        fit.source_y_column_id = y_column_id
        fit.x_data = new_x
        fit.y_data = new_y
        fit.confidence_lower_column_id = confidence_lower_column_id
        fit.confidence_upper_column_id = confidence_upper_column_id
        fit.confidence_lower = new_confidence_lower
        fit.confidence_upper = new_confidence_upper

    def _on_confidence_column_changed(self):
        """Live-edit reaction for the two confidence-column combos,
        wired separately from `_on_series_config_changed`'s other
        combos: these two are only ever "live" for a manually-converted
        fit (see `_apply_manual_fit_edits`) -- for a regular DataSeries
        they're merely pre-staged values read once at conversion time
        (see `_convert_selected_series_to_fit`), so touching them there
        must be a true no-op. Sharing `_on_series_config_changed` would
        mark the panel dirty (via its unconditional trailing
        `dirtyOnly.emit()`) even though no model state actually changed
        for a series -- this dedicated handler only reacts, and only
        marks dirty, when a manual fit is actually selected.
        """
        if self._updating_controls or not self.current_chart:
            return
        current_row = self._expanded_series_index
        if current_row < 0:
            return
        total_series = len(self.current_chart.data_series)
        if current_row < total_series:
            return
        fit_index = current_row - total_series
        if fit_index < 0 or fit_index >= len(self.current_chart.fit_data):
            return
        fit = self.current_chart.fit_data[fit_index]
        if not fit.is_manual:
            return
        self._apply_manual_fit_edits(fit)
        self.dirtyOnly.emit()

    def _on_series_type_changed(self):
        """Retype the selected, already-existing series to the combo's
        newly chosen value (Chart.retype_series), then fully reload it
        into the controls -- this naturally refreshes vector-field
        visibility and the U/V/magnitude combos for the new type, the
        same as selecting a different series does.

        Selecting the "Fit" sentinel entry is not a retype: it converts
        the series into a FitData entry instead (see
        _convert_selected_series_to_fit) and returns early, since the
        series at `current_row` no longer exists in `data_series` once
        that conversion runs.
        """
        if self._updating_controls or not self.current_chart:
            return
        current_row = self._expanded_series_index
        if current_row < 0 or current_row >= len(self.current_chart.data_series):
            return
        new_type = self.series_type_combo.currentData()
        if new_type is None:
            return
        if new_type == _CONVERT_TO_FIT:
            self._convert_selected_series_to_fit(current_row)
            return
        self.current_chart.retype_series(current_row, new_type)
        series = self.current_chart.data_series[current_row]
        self._load_series_into_controls(series)
        self.seriesSelected.emit("series", series)
        self.dirtyOnly.emit()

    def _convert_selected_series_to_fit(self, index: int):
        """Convert the data series at `index` into a FitData entry via
        ConvertSeriesToFitCommand (#298), then select the newly created
        fit at its new combined index.

        The new fit is always appended to the end of `fit_data`, and
        converting one entry moves it from `data_series` to `fit_data`
        without changing the total item count -- so its new combined
        index (data-series indices first, then fit-data indices, per this
        tab's existing convention) is always the last one.
        """
        command = ConvertSeriesToFitCommand(
            self.app_context,
            chart_id=self.current_chart.id,
            series_index=index,
            confidence_lower_column_id=self.confidence_lower_column_combo.currentData() or "",
            confidence_upper_column_id=self.confidence_upper_column_combo.currentData() or "",
        )
        if not self.command_executor.execute_command(command):
            # Conversion failed (e.g. source dataset was deleted or a
            # column couldn't be resolved): the series at `index` is
            # still a real, unconverted DataSeries. Reload it into the
            # controls so the Series Type combo reflects its actual,
            # unchanged type instead of being left stuck on "Fit" --
            # setCurrentIndex on an already-current index wouldn't emit
            # currentIndexChanged, so without this the user couldn't even
            # retry by re-selecting "Fit". Guarded: ConvertSeriesToFitCommand
            # can also fail before ever touching data_series (chart not
            # found, or `index` itself out of range) -- there's no series
            # to reload in those cases, so leave the controls as-is rather
            # than risk indexing a chart/list that isn't in the expected
            # state.
            if self.current_chart is not None and 0 <= index < len(self.current_chart.data_series):
                series = self.current_chart.data_series[index]
                self._load_series_into_controls(series)
            return

        new_index = len(self.current_chart.data_series) + len(self.current_chart.fit_data) - 1
        self._expanded_series_index = new_index
        self._expanded_card_indices.add(new_index)
        self._rebuild_series_cards()

    def _on_error_symmetry_toggled(self):
        """Handle the Asymmetric error-bars checkbox: persist and refresh
        control enablement.

        Reported live: enabling asymmetric mode left the newly-revealed
        minus-side combos on "None", silently zeroing out the lower error
        bar even though the chart was, up to that toggle, showing a
        symmetric magnitude on both sides. Default each minus combo to
        whatever its plus-side sibling already has selected, so the
        rendered chart doesn't change the instant the checkbox is
        ticked -- only unchecking-then-rechecking or an already-set minus
        combo is left alone.
        """
        if self.error_asymmetric_check.isChecked():
            for minus_combo, plus_combo in (
                (self.x_error_minus_column_combo, self.x_error_column_combo),
                (self.y_error_minus_column_combo, self.y_error_column_combo),
            ):
                if not minus_combo.currentData():
                    index = minus_combo.findData(plus_combo.currentData())
                    if index >= 0:
                        minus_combo.setCurrentIndex(index)
        self._update_error_bar_mode_controls()
        self._on_series_config_changed()

    def _update_error_bar_mode_controls(self):
        """Sync the error-column controls to the current symmetric/
        asymmetric mode.

        Unchecked (symmetric): X/Y Error Column supply a single magnitude
        (the Style tab's Direction control decides which side it's drawn on);
        the -side pickers are hidden. Checked (asymmetric): X/Y Error Column
        become the + (upper) magnitude and the -side pickers appear for the
        lower magnitude.
        """
        asymmetric = self.error_asymmetric_check.isChecked()

        self.x_error_column_label.setText("X Error (+) Column:" if asymmetric else "X Error Column:")
        self.y_error_column_label.setText("Y Error (+) Column:" if asymmetric else "Y Error Column:")

        # x_error_column_combo tracks whether a data series (vs. fit data,
        # which has no error bars) is being edited; the -side pickers only
        # show up when both a series is selected and asymmetric is checked.
        show_minus = asymmetric and self.x_error_column_combo.isEnabled()
        for widget in (
            self.x_error_minus_label, self.x_error_minus_column_combo,
            self.y_error_minus_label, self.y_error_minus_column_combo,
        ):
            widget.setVisible(show_minus)
        self.x_error_minus_column_combo.setEnabled(show_minus)
        self.y_error_minus_column_combo.setEnabled(show_minus)

    def _load_series_into_controls(self, series):
        """Load a data series into the configuration controls."""
        # Enable all controls for series editing
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self._reset_controls_for_series()

            # Set dataset
            for i in range(self.dataset_combo.count()):
                if self.dataset_combo.itemData(i) == series.dataset_id:
                    self.dataset_combo.setCurrentIndex(i)
                    break

            # Repopulate column combos from the (possibly changed) dataset before
            # selecting the series' columns, so stale entries from a previous
            # dataset/column state (e.g. after undo/redo of a column rename)
            # don't linger.
            self._populate_column_combos(series.dataset_id)
            self._populate_error_column_combos(series.dataset_id)
            self._populate_confidence_column_combos(series.dataset_id)
            self._populate_vector_column_combos(series.dataset_id)
            self._populate_z_column_combo(series.dataset_id)
            self._update_vector_field_visibility()
            self._update_z_column_field_visibility()

            # Set columns by stable id (combos carry the id as itemData)
            x_index = self.x_column_combo.findData(series.x_column_id)
            if x_index >= 0:
                self.x_column_combo.setCurrentIndex(x_index)

            y_index = self.y_column_combo.findData(series.y_column_id)
            if y_index >= 0:
                self.y_column_combo.setCurrentIndex(y_index)

            # Set Y axis (primary/secondary). SegmentedControl.setCurrentValue
            # doesn't emit currentValueChanged, so no signal-blocking needed.
            self.series_y_axis_control.setCurrentValue(series.y_axis)

            # Set error columns by id (block signals while populating)
            error_bars = getattr(series.style, "error_bars", None) or ErrorBarConfig()
            for combo, column_id in (
                (self.x_error_column_combo, error_bars.x_error_column_id),
                (self.y_error_column_combo, error_bars.y_error_column_id),
                (self.x_error_minus_column_combo, error_bars.x_error_minus_column_id),
                (self.y_error_minus_column_combo, error_bars.y_error_minus_column_id),
            ):
                combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
                index = combo.findData(column_id)
                combo.setCurrentIndex(index if index >= 0 else 0)
                combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

            for combo, column_id in (
                (self.u_column_combo, getattr(series.style, "u_column_id", "")),
                (self.v_column_combo, getattr(series.style, "v_column_id", "")),
                (self.magnitude_column_combo, getattr(series.style, "magnitude_column_id", "")),
                (self.z_column_combo, getattr(series.style, "z_column_id", "")),
            ):
                combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
                index = combo.findData(column_id)
                combo.setCurrentIndex(index if index >= 0 else 0)
                combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

            type_index = self.series_type_combo.findData(series.series_type)
            self.series_type_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.series_type_combo.setCurrentIndex(type_index if type_index >= 0 else 0)
            self.series_type_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

            self.error_asymmetric_check.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.error_asymmetric_check.setChecked(not error_bars.error_symmetric)
            self.error_asymmetric_check.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self._update_error_bar_mode_controls()

            # Set label (block signals while populating)
            self.series_label_edit.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.series_label_edit.setText(series.label)
            self.series_label_edit.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self._pending_label = series.label
        finally:
            self._updating_controls = previous_guard

    def _load_fit_into_controls(self, fit):
        """Load fit data into the configuration controls.

        A manually-converted fit (fit.is_manual, see
        ConvertSeriesToFitCommand / #298 follow-up) keeps its
        dataset/X/Y/confidence-column combos editable, since it's a
        "custom fit" whose source data the user can still repoint --
        unlike an auto-applied fit (from the Fit panel), whose source
        columns are frozen at fit time.
        """
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            is_manual = fit.is_manual
            # Dataset/X/Y/confidence columns stay editable only for a
            # manually-converted fit; every other fit-only field (axis,
            # error bars, vector/Z, asymmetric error toggle) has no
            # meaning for a fit at all and is always disabled here.
            self.dataset_combo.setEnabled(is_manual)
            self.x_column_combo.setEnabled(is_manual)
            self.y_column_combo.setEnabled(is_manual)
            self.confidence_lower_column_combo.setEnabled(is_manual)
            self.confidence_upper_column_combo.setEnabled(is_manual)
            self.series_y_axis_control.setEnabled(False)
            self.x_error_column_combo.setEnabled(False)
            self.y_error_column_combo.setEnabled(False)
            self.u_column_combo.setEnabled(False)
            self.v_column_combo.setEnabled(False)
            self.magnitude_column_combo.setEnabled(False)
            self.z_column_combo.setEnabled(False)
            # The combo is shared with whichever series was last edited, so
            # without this it keeps showing that series' (or the chart's
            # default) SeriesType -- misleading here since a fit isn't
            # actually that type, just disabled/non-editable. Show the
            # "Fit" sentinel entry instead so the disabled combo reads
            # correctly (#298 follow-up).
            self.series_type_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            fit_entry_index = self.series_type_combo.findData(_CONVERT_TO_FIT)
            if fit_entry_index >= 0:
                self.series_type_combo.setCurrentIndex(fit_entry_index)
            self.series_type_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self.series_type_combo.setEnabled(False)
            self._update_vector_field_visibility()
            self._update_z_column_field_visibility()
            self.error_asymmetric_check.setEnabled(False)
            self._update_error_bar_mode_controls()

            if is_manual:
                self._populate_column_combos(fit.source_dataset_id)
                self._populate_confidence_column_combos(fit.source_dataset_id)

                for i in range(self.dataset_combo.count()):
                    if self.dataset_combo.itemData(i) == fit.source_dataset_id:
                        self.dataset_combo.setCurrentIndex(i)
                        break

                for combo, column_id in (
                    (self.x_column_combo, fit.source_x_column_id),
                    (self.y_column_combo, fit.source_y_column_id),
                    (self.confidence_lower_column_combo, fit.confidence_lower_column_id),
                    (self.confidence_upper_column_combo, fit.confidence_upper_column_id),
                ):
                    combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
                    index = combo.findData(column_id)
                    combo.setCurrentIndex(index if index >= 0 else 0)
                    combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

            # Show fit info in the label (block signals)
            self.series_label_edit.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.series_label_edit.setText(fit.label)
            self.series_label_edit.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            self._pending_label = fit.label
        finally:
            self._updating_controls = previous_guard

    def _on_label_typing(self, text: str):
        """Buffer label text while typing, without mutating the model.

        Marks the panel dirty immediately rather than deferring to
        editingFinished like the model write itself: Apply starts disabled,
        and a disabled QPushButton can't take focus, so it could never blur
        the field to fire editingFinished -- deadlocking Apply as disabled
        forever. Marking dirty per keystroke breaks that (safe: blockSignals
        during programmatic population means this only fires on real edits).
        """
        self._pending_label = text
        if not self._updating_controls and self.current_chart:
            self.dirtyOnly.emit()

    def _on_label_committed(self):
        """Persist buffered label to model after editing finishes.

        Unlike the old QListWidget-backed list, the label text isn't shown
        anywhere else while this entry is expanded (its card's title header
        is only (re)built on the next _rebuild_series_cards call), so no
        rebuild is needed here to avoid disruptive focus loss while typing.
        """
        if self._updating_controls or not self.current_chart:
            return
        current_row = self._expanded_series_index
        if current_row < 0:
            return
        total_series = len(self.current_chart.data_series)
        new_label = self._pending_label or self.series_label_edit.text()
        changed = False
        if current_row < total_series:
            if current_row < len(self.current_chart.data_series):
                entry = self.current_chart.data_series[current_row]
                changed = entry.label != new_label
                entry.label = new_label
        else:
            fit_index = current_row - total_series
            if 0 <= fit_index < len(self.current_chart.fit_data):
                entry = self.current_chart.fit_data[fit_index]
                changed = entry.label != new_label
                entry.label = new_label
        self._pending_label = new_label
        if changed:
            # Mirrors _on_series_config_changed: mark the panel dirty so the
            # footer's Apply button enables. Without this, a label-only edit
            # left Apply disabled (the model was already updated directly,
            # but silently -- no undo entry, no "unsaved changes" indicator,
            # and clicking the disabled Apply button did nothing), which is
            # why editing anything else afterwards was needed to make Apply
            # start doing something again.
            self.dirtyOnly.emit()

    def _reset_controls_for_series(self):
        """Reset controls for editing regular data series."""
        self.dataset_combo.setEnabled(True)
        self.x_column_combo.setEnabled(True)
        self.y_column_combo.setEnabled(True)
        self.series_y_axis_control.setEnabled(True)
        self.x_error_column_combo.setEnabled(True)
        self.y_error_column_combo.setEnabled(True)
        self.u_column_combo.setEnabled(True)
        self.v_column_combo.setEnabled(True)
        self.magnitude_column_combo.setEnabled(True)
        self.z_column_combo.setEnabled(True)
        self.confidence_lower_column_combo.setEnabled(True)
        self.confidence_upper_column_combo.setEnabled(True)
        self.series_type_combo.setEnabled(True)
        self.error_asymmetric_check.setEnabled(True)

    def _get_next_series_color(self) -> str:
        """Get the next color for a new series."""
        colors = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
                 "#8c564b", "#e377c2", "#7f7f7f", "#bcbd22", "#17becf"]

        if not self.current_chart or not self.current_chart.data_series:
            return colors[0]

        return colors[len(self.current_chart.data_series) % len(colors)]

    # -- Dataset / column combos ------------------------------------------

    def set_project(self, project):
        """Set the current project."""
        self.current_project = project
        self._update_datasets()

    def _update_datasets(self):
        """Update the available datasets.

        Signals are blocked while clearing/populating: `set_project` runs on
        every chart-tab switch, well after a chart/series may already be
        selected, so an unblocked `dataset_combo.currentTextChanged` would
        fire `_on_dataset_changed` -> `_on_series_config_changed` and
        silently overwrite the selected series' dataset/column ids with
        whatever landed at the freshly-rebuilt combo's index 0/1 --
        corrupting a series unrelated to the tab switch that triggered it.
        """
        previously_selected_id = (
            self.dataset_combo.currentData() if self.dataset_combo.count() > 0 else None
        )
        self.dataset_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            self.dataset_combo.clear()
            self.datasets = []

            if self.current_project:
                display_names = dict(dataset_display_options(self.current_project))
                # Iterate through all items in the project to find datasets
                for item in self.current_project.get_all_items():
                    if isinstance(item, Dataset):
                        self.dataset_combo.addItem(display_names[item.id], item.id)
                        self.datasets.append(item)

            # Rebuilding the combo (e.g. after a dataset rename refreshes its
            # display label) would otherwise silently reset the selection to
            # index 0, desyncing the combo from the series actually loaded
            # into the form -- restore it by id.
            if previously_selected_id is not None:
                restored_index = self.dataset_combo.findData(previously_selected_id)
                if restored_index >= 0:
                    self.dataset_combo.setCurrentIndex(restored_index)
        finally:
            self.dataset_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _column_display_name(self, dataset_id, column_id, fallback_name=""):
        """Resolve a column id to its current name for display, falling back to
        a stored legacy name (empty -> empty string)."""
        from pandaplot.models.project.items.chart import resolve_series_column
        dataset = self.current_project.find_item(dataset_id) if self.current_project else None
        return resolve_series_column(dataset, column_id, fallback_name) or ""

    def _populate_column_combos(self, dataset_id):
        """Fill the x/y column combos with the columns of the given dataset.

        Each item's display text is the column name and its itemData is the
        stable column id, so callers read the selected id via currentData().

        Signals are blocked while clearing/populating so this can safely be
        called from contexts that don't want side effects from
        currentTextChanged (e.g. while loading a series into controls).

        Returns the list of columns populated (empty list if none).
        """
        if not dataset_id or not self.current_project:
            return []
        dataset = self.current_project.find_item(dataset_id)
        if isinstance(dataset, Dataset) and dataset.data is not None:
            columns = list(dataset.data.columns)
            self.x_column_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            self.y_column_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
            try:
                self.x_column_combo.clear()
                self.y_column_combo.clear()
                for column in columns:
                    column_id = dataset.column_id(column) or ""
                    self.x_column_combo.addItem(column, column_id)
                    self.y_column_combo.addItem(column, column_id)
            finally:
                self.x_column_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
                self.y_column_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
            return columns
        return []

    def _populate_error_column_combos(self, dataset_id):
        """Fill the x/y (+/-) error column combos with a leading "None" entry
        followed by the columns of the given dataset.

        Signals are blocked while clearing/populating, same as
        _populate_column_combos. Item data is the column id (or "" for
        "None"), since "None" is itself a valid display label and can't be
        distinguished from a real column via currentText().
        """
        combos = (
            self.x_error_column_combo, self.y_error_column_combo,
            self.x_error_minus_column_combo, self.y_error_minus_column_combo,
        )
        for combo in combos:
            combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            for combo in combos:
                combo.clear()
                combo.addItem("None", "")

            if dataset_id and self.current_project:
                dataset = self.current_project.find_item(dataset_id)
                if isinstance(dataset, Dataset) and dataset.data is not None:
                    for column in dataset.data.columns:
                        column_id = dataset.column_id(column) or ""
                        for combo in combos:
                            combo.addItem(column, column_id)
        finally:
            for combo in combos:
                combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _populate_confidence_column_combos(self, dataset_id):
        """Fill the confidence lower/upper column combos with a leading
        "None" entry followed by the given dataset's columns -- mirrors
        _populate_error_column_combos' item-data convention (column id, or
        "" for "None"). Unlike the error columns, nothing here is written
        back to the model outside of the one-shot Fit conversion (see
        _convert_selected_series_to_fit), so no live-edit signal is wired
        to these combos.
        """
        combos = (self.confidence_lower_column_combo, self.confidence_upper_column_combo)
        for combo in combos:
            combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            for combo in combos:
                combo.clear()
                combo.addItem("None", "")

            if dataset_id and self.current_project:
                dataset = self.current_project.find_item(dataset_id)
                if isinstance(dataset, Dataset) and dataset.data is not None:
                    for column in dataset.data.columns:
                        column_id = dataset.column_id(column) or ""
                        for combo in combos:
                            combo.addItem(column, column_id)
        finally:
            for combo in combos:
                combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _populate_vector_column_combos(self, dataset_id):
        """Fill the U/V/magnitude column combos with the given dataset's
        columns, each preceded by a leading "None" entry (itemData "") --
        mirrors _populate_column_combos/_populate_error_column_combos'
        item-data convention (column id, or "" for "None"). All three
        combos get the same blank entry: even though U/V are conceptually
        "required" for a vector series, an untouched model field is
        genuinely "" (e.g. right after retyping an existing series to
        VECTOR via the Series Type combo), and the combo must be able to
        display that instead of being forced onto a real column that was
        never chosen."""
        combos = (self.u_column_combo, self.v_column_combo, self.magnitude_column_combo)
        for combo in combos:
            combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            for combo in combos:
                combo.clear()
                combo.addItem("None", "")

            if dataset_id and self.current_project:
                dataset = self.current_project.find_item(dataset_id)
                if isinstance(dataset, Dataset) and dataset.data is not None:
                    for column in dataset.data.columns:
                        column_id = dataset.column_id(column) or ""
                        for combo in combos:
                            combo.addItem(column, column_id)
        finally:
            for combo in combos:
                combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _populate_z_column_combo(self, dataset_id):
        """Fill the Z column combo with the given dataset's columns, preceded
        by a leading "None" entry (itemData "") -- mirrors
        _populate_vector_column_combos' item-data convention (column id, or
        "" for "None"), since an untouched z_column_id is genuinely "" (e.g.
        right after retyping an existing series to Colormap/Heatmap)."""
        combo = self.z_column_combo
        combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            combo.clear()
            combo.addItem("None", "")

            if dataset_id and self.current_project:
                dataset = self.current_project.find_item(dataset_id)
                if isinstance(dataset, Dataset) and dataset.data is not None:
                    for column in dataset.data.columns:
                        column_id = dataset.column_id(column) or ""
                        combo.addItem(column, column_id)
        finally:
            combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _selected_series_is_vector(self) -> bool:
        """Whether the currently expanded, already-existing series is
        itself a VECTOR series. This exists specifically for the
        currently-selected, already-existing series -- distinct from the
        type chosen for a not-yet-created new series, which is read from
        the Series Type combo instead. An existing series can hold a
        different type than its chart's (see Chart.set_chart_type), so
        per-series field visibility/write-back must read the series' own
        type."""
        if not self.current_chart:
            return False
        row = self._expanded_series_index
        if row < 0 or row >= len(self.current_chart.data_series):
            return False
        return self.current_chart.data_series[row].series_type == SeriesType.VECTOR

    def _populate_series_type_combo(self):
        """(Re)populate the Series Type combo with the types the current
        chart's own type allows (CHART_TYPE_SPECS[chart_type].
        allowed_series_types) -- called on load() and whenever the
        chart's own type changes live (see refresh_vector_fields), since
        the allowed set depends on it."""
        self.series_type_combo.blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        try:
            self.series_type_combo.clear()
            if not self.current_chart:
                return
            spec = CHART_TYPE_SPECS[self.current_chart.chart_type]
            for series_type in sorted(spec.allowed_series_types, key=lambda t: t.value):
                self.series_type_combo.addItem(series_type.value.title(), series_type)
            # "Fit" is a conversion action, not a real SeriesType -- offered
            # regardless of the chart's own allowed_series_types, since fit
            # entries have always been chart-type-agnostic (#298). Appended
            # last so it never affects the default-index lookup below.
            self.series_type_combo.addItem("Fit", _CONVERT_TO_FIT)
            default_index = self.series_type_combo.findData(spec.default_series_type)
            self.series_type_combo.setCurrentIndex(default_index if default_index >= 0 else 0)
        finally:
            self.series_type_combo.blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only

    def _update_vector_field_visibility(self):
        """Show the U/V/magnitude rows only when editing a series whose
        own type is Vector -- every other series type has no use for
        them, regardless of the chart's own type (see
        _selected_series_is_vector)."""
        is_vector = self._selected_series_is_vector()
        for widget in (
            self.u_column_label, self.u_column_combo,
            self.v_column_label, self.v_column_combo,
            self.magnitude_column_label, self.magnitude_column_combo,
        ):
            widget.setVisible(is_vector)

    def _selected_series_needs_z_column(self) -> bool:
        """Whether the currently expanded, already-existing series' own
        type needs a Z column (COLORMAP/HEATMAP), mirroring
        _selected_series_is_vector's reasoning: driven by the series' own
        type, not the chart's."""
        if not self.current_chart:
            return False
        row = self._expanded_series_index
        if row < 0 or row >= len(self.current_chart.data_series):
            return False
        return SERIES_TYPE_SPECS[self.current_chart.data_series[row].series_type].needs_z_column

    def _update_z_column_field_visibility(self):
        """Show the Z Column row only when editing a series whose own type
        needs it (Colormap/Heatmap) -- mirrors _update_vector_field_visibility."""
        show = self._selected_series_needs_z_column()
        self.z_column_label.setVisible(show)
        self.z_column_combo.setVisible(show)

    def refresh_vector_fields(self):
        """Re-evaluate the Series Type combo's options and the selected
        series' vector-field visibility/combos after the chart's own
        type changes live.

        Called by ChartPropertiesPanel when the Chart tab's type combo
        changes live, via `chartTypeChanged` -- which now fires only
        after `Chart.set_chart_type()` has already run (Task 1's
        ordering fix), so the model here is always already retyped.
        """
        self._populate_series_type_combo()
        if not self.current_chart:
            self._update_vector_field_visibility()
            self._update_z_column_field_visibility()
            return
        current_row = self._expanded_series_index
        if current_row < 0 or current_row >= len(self.current_chart.data_series):
            self._update_vector_field_visibility()
            self._update_z_column_field_visibility()
            return
        self._load_series_into_controls(self.current_chart.data_series[current_row])

    def _on_dataset_changed(self):
        """Handle dataset selection change."""
        dataset_id = self.dataset_combo.currentData()
        columns = self._populate_column_combos(dataset_id)
        self._populate_error_column_combos(dataset_id)
        self._populate_confidence_column_combos(dataset_id)
        self._populate_vector_column_combos(dataset_id)
        self._populate_z_column_combo(dataset_id)

        # Set defaults if possible
        if columns:
            self.x_column_combo.setCurrentIndex(0)
            self.y_column_combo.setCurrentIndex(1 if len(columns) >= 2 else 0)

        # setCurrentIndex() only emits currentTextChanged when the index
        # actually changes, which it won't for indices auto-selected by
        # _populate_column_combos while signals were blocked. Sync
        # explicitly so the selected series' x_column/y_column never go
        # stale relative to the combos.
        self._on_series_config_changed()

    # -- Panel-facing lifecycle: load / apply_to / clear / apply_theme ------

    def load(self, chart):
        """Load a Chart object's series/fit list into this tab.

        Reloading the *same* chart object (e.g. the full-panel refresh that
        follows every Apply, via `ChartPropertiesPanel._on_chart_updated`'s
        "chart" branch) preserves the current selection instead of jumping
        back to the first entry -- otherwise, editing/renaming any series
        other than the first one and clicking Apply silently moves the live
        form to series 0, so a second edit on the entry the user thinks is
        still selected actually edits the wrong one. A different chart
        object (switching to another chart tab, or the first-ever load)
        still starts at index 0.

        Args:
            chart: Chart object to load, or None to clear.
        """
        same_chart = chart is not None and chart is self.current_chart
        self.current_chart = chart
        if chart:
            self._populate_series_type_combo()
            previous_guard = self._updating_controls
            self._updating_controls = True
            try:
                total_items = len(chart.data_series) + len(chart.fit_data)
                if same_chart and total_items:
                    self._expanded_series_index = max(
                        0, min(self._expanded_series_index, total_items - 1)
                    )
                    self._expanded_card_indices.add(self._expanded_series_index)
                else:
                    self._expanded_series_index = 0
                    self._expanded_card_indices = {0}
                self._rebuild_series_cards()
            finally:
                self._updating_controls = previous_guard
        else:
            self.clear()

    def apply_to(self, chart):
        """Apply the currently selected series/fit's non-style fields
        (dataset/x/y/y_axis are already live-written to the model by
        `_on_series_config_changed`; this only re-asserts `y_axis`, matching
        the previous behavior) and create a default series if none exist yet.
        """
        current_row = self._expanded_series_index
        if current_row >= 0:
            total_series = len(chart.data_series)
            if current_row < total_series:
                series = chart.data_series[current_row]
                series.y_axis = self.series_y_axis_control.currentValue()

        # An empty data_series list alone doesn't mean "uninitialized
        # chart, bootstrap a default series from whatever the form
        # currently shows" -- a chart converted to be all-fit (e.g. its
        # only series was just turned into a manual fit via #298) is
        # legitimately empty here too, and the form's combos are showing
        # the SELECTED FIT's own source columns at this point, not blank
        # defaults. Without the fit_data check, clicking Apply while
        # editing that fit would silently recreate a duplicate series
        # alongside it.
        if not chart.data_series and not chart.fit_data:
            dataset_id = self.dataset_combo.currentData()
            dataset_name = self.dataset_combo.currentText()
            x_column_id = self.x_column_combo.currentData()
            y_column_id = self.y_column_combo.currentData()
            y_column_name = self.y_column_combo.currentText()
            # Same reasoning as _add_series: a brand-new series always gets
            # the chart's own default type, not whatever the combo happens
            # to show (which tracks the selected existing series).
            new_series_type = CHART_TYPE_SPECS[chart.chart_type].default_series_type
            if dataset_id and x_column_id and y_column_id:
                chart.add_data_series(
                    dataset_id,
                    x_column_id=x_column_id,
                    y_column_id=y_column_id,
                    label=f"{dataset_name}:{y_column_name}",
                    y_axis=self.series_y_axis_control.currentValue(),
                    series_type=new_series_type,
                    style=build_series_style(
                        new_series_type,
                        error_bars=ErrorBarConfig(
                            x_error_column_id=self.x_error_column_combo.currentData() or "",
                            y_error_column_id=self.y_error_column_combo.currentData() or "",
                            x_error_minus_column_id=self.x_error_minus_column_combo.currentData() or "",
                            y_error_minus_column_id=self.y_error_minus_column_combo.currentData() or "",
                            error_symmetric=not self.error_asymmetric_check.isChecked(),
                        ),
                        u_column_id=self.u_column_combo.currentData() or "",
                        v_column_id=self.v_column_combo.currentData() or "",
                        magnitude_column_id=self.magnitude_column_combo.currentData() or "",
                        z_column_id=self.z_column_combo.currentData() or "",
                    ),
                )

    def clear(self):
        """Reset controls to neutral defaults without touching any chart."""
        self.current_chart = None
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.series_label_edit.clear()
            self._expanded_series_index = 0
            self._expanded_card_indices = {0}
            self._rebuild_series_cards()
        finally:
            self._updating_controls = previous_guard

    def apply_theme(self, tokens: dict):
        """Apply theme styling to series management widgets, and rebuild the
        card list so cards/SegmentedControl pick up fresh tokens too."""
        self._series_section_header.set_tokens(tokens)
        self.series_y_axis_control.set_tokens(tokens)
        self._rebuild_series_cards()
