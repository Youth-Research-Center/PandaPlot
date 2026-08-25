"""Style tab: chart-style card (title/subtitle font, padding, size, dpi) plus
the Line/Marker cards for whichever series/fit entry is currently selected.
"""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.color_swatch_row import ColorSwatchRow
from pandaplot.gui.components.common.font_family_options import list_available_font_families
from pandaplot.gui.components.common.line_style_icons import build_line_style_icon
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.components.common.slider_with_spinbox import SliderWithSpinbox
from pandaplot.gui.components.common.toggle_switch import ToggleSwitch
from pandaplot.gui.components.common.value_combo_box import ValueComboBox
from pandaplot.gui.components.sidebar.chart.tabs.axes_tab import AXES_SWATCH_PALETTE
from pandaplot.models.chart.chart_configuration import (
    LineStyleType,
    MarkerType,
)
from pandaplot.models.chart.error_direction import ErrorDirection
from pandaplot.models.chart.series_style import (
    ColormapSeriesStyle,
    HeatmapSeriesStyle,
    LineSeriesStyle,
    ScatterSeriesStyle,
    VectorSeriesStyle,
)
from pandaplot.models.chart.series_type import SeriesType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import DataSeries, FitData
from pandaplot.models.state.config import (
    MAX_CHART_HEIGHT_CM,
    MAX_CHART_WIDTH_CM,
    MIN_CHART_HEIGHT_CM,
    MIN_CHART_WIDTH_CM,
)
from pandaplot.services.config.config_manager import ConfigManager

# Preset swatch palette offered by the Style tab's line/marker color pickers.
STYLE_SWATCH_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]

# Common matplotlib colormaps offered for vector-plot magnitude coloring.
# "" (Solid color) means: ignore magnitude, use vector_color for every arrow.
VECTOR_COLORMAPS = [
    ("Solid color", ""),
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Cool", "cool"),
    ("Autumn", "autumn"),
    ("Jet", "jet"),
]

# Colormaps offered for Colormap/Heatmap chart types' Z-driven point/cell
# coloring (mirrors VECTOR_COLORMAPS, minus the "Solid color" option --
# these two types always color by Z, there is no fallback fixed color).
COLORMAP_OPTIONS = [
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Cool", "cool"),
    ("Autumn", "autumn"),
    ("Jet", "jet"),
    ("Hot", "hot"),
    ("Coolwarm", "coolwarm"),
]

# Heatmap-only: how scattered (x, y, z) points become a regular grid for
# pcolormesh (see chart_heatmap.build_heatmap_grid). Colormap (a color-mapped
# scatter) has no gridding concept -- these controls are hidden for it
# entirely (see SeriesTypeSpec.supports_gridding).
HEATMAP_GRIDDING_OPTIONS = [
    ("Exact grid", "grid"),
    ("Binned (mean)", "binned"),
    ("Interpolated", "interpolated"),
]


def _make_bold_italic_checks_standalone() -> tuple[QCheckBox, QCheckBox]:
    """Same as the local closure `_make_bold_italic_checks` defined inside
    StyleTab.__init__ for the chart-level title/subtitle cards -- extracted
    as a module-level function so `_build_axis_style_form` (a regular
    method, outside that closure's scope) can reuse it without
    duplicating the two-line QCheckBox styling."""
    bold_check = QCheckBox("Bold")
    bold_check.setStyleSheet("QCheckBox { font-weight: bold; }")
    italic_check = QCheckBox("Italic")
    italic_check.setStyleSheet("QCheckBox { font-style: italic; }")
    return bold_check, italic_check


class StyleTab(QWidget):
    """Chart-style settings plus per-entry Line/Marker style controls.

    There is deliberately no independent series selector here: the chip row
    mirrors the "currently selected entry" state the Data tab's
    expand/collapse cards drive -- the panel is the source of truth for that
    selection and calls `set_selected` directly; a non-"chart" chip click is
    relayed back to the panel (which still owns `_expand_series`) via
    `seriesChipSelected`.

    No rendered line/marker preview: this panel has no chart canvas of its
    own, and the live chart view already re-renders on every change.
    """

    configChanged = Signal()
    # Emitted when a non-"chart" chip (an int combined series/fit index) is
    # clicked. "chart" is handled internally since the Data tab has no
    # "chart" entry of its own.
    seriesChipSelected = Signal(object)

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self._chart = None
        self._updating_controls = False
        # (kind, obj) where kind is "chart", "series", or "fit".
        self._current_target = ("chart", None)
        # Whether `set_series_list` has ever run a real population (i.e. the
        # Data tab has emitted `seriesListChanged` at least once for an
        # actual chart). `style_series_chips` starts life pre-seeded with
        # only a "Chart" placeholder item (see below) purely so the
        # ValueComboBox constructor has a non-empty initial item list --
        # that is NOT a genuine user selection of "Chart" and must not be
        # mistaken for one on the very first real population, or the
        # newly-loaded chart's first series would wrongly appear to have
        # "Chart" as the sticky previously-selected target.
        self._series_list_initialized: bool = False
        self._chart_type = None
        # Latest data_series list (kept in sync by set_series_list) so the
        # Fill card's "Fill to" selector can offer the other series to fill
        # between. Indices into this list are what fill_to_index stores.
        self._data_series: list = []
        # Whether the Custom size/DPI fields have already been pre-filled
        # for the currently loaded chart (reset on every load_chart_style/
        # clear_chart_style call). Prevents re-filling with defaults if the
        # user toggles back and forth between Custom and a preset.
        self._custom_size_prefilled: bool = False
        self._custom_dpi_prefilled: bool = False

        layout = QVBoxLayout(self)

        self.style_series_chips = ValueComboBox([("Chart", "chart"), ("Axes", "axes")])
        self.style_series_chips.currentValueChanged.connect(self._on_chip_selected)
        layout.addWidget(self.style_series_chips)

        # CHART-level rendering settings -- shown instead of the Line/Marker/
        # Error Bars cards when the "Chart" chip is selected. Split into
        # bordered sections (Font Size/Padding/Size/DPI), matching the
        # Line/Marker/Error Bars pattern below, rather than one big indented
        # card -- each section's own border does the visual grouping that
        # indentation used to, freeing up width for the input fields.
        self.chart_style_cards: list[Card] = []

        def _field_row(grid: QGridLayout, row: int, label_text: str, field: QWidget, tooltip: str | None = None):
            label = QLabel(label_text)
            if tooltip:
                label.setToolTip(tooltip)
            grid.addWidget(label, row, 0)
            grid.addWidget(field, row, 1)

        def _make_bold_italic_checks() -> tuple[QCheckBox, QCheckBox]:
            bold_check = QCheckBox("Bold")
            bold_check.setStyleSheet("QCheckBox { font-weight: bold; }")
            italic_check = QCheckBox("Italic")
            italic_check.setStyleSheet("QCheckBox { font-style: italic; }")
            return bold_check, italic_check

        def _bold_italic_widget(bold_check: QCheckBox, italic_check: QCheckBox) -> QWidget:
            row = QHBoxLayout()
            row.setContentsMargins(0, 0, 0, 0)
            row.addWidget(bold_check)
            row.addWidget(italic_check)
            row.addStretch(1)
            widget = QWidget()
            widget.setLayout(row)
            return widget

        # -- Font Size card --
        self.font_size_card = Card()
        self.chart_style_cards.append(self.font_size_card)
        font_size_layout = QGridLayout(self.font_size_card)
        font_size_layout.addWidget(SectionHeader("Font Size"), 0, 0, 1, 2)

        self.title_font_size_spin = QSpinBox()
        self.title_font_size_spin.setRange(8, 32)
        self.title_font_size_spin.setValue(14)
        _field_row(font_size_layout, 1, "Title", self.title_font_size_spin)
        self.title_bold_check, self.title_italic_check = _make_bold_italic_checks()
        self.title_bold_check.setChecked(True)
        font_size_layout.addWidget(
            _bold_italic_widget(self.title_bold_check, self.title_italic_check), 2, 1,
        )

        self.title_font_family_combo = ValueComboBox(list_available_font_families())
        _field_row(font_size_layout, 3, "Title font", self.title_font_family_combo)

        self.subtitle_font_size_spin = QSpinBox()
        self.subtitle_font_size_spin.setRange(8, 32)
        self.subtitle_font_size_spin.setValue(12)
        _field_row(font_size_layout, 4, "Subtitle", self.subtitle_font_size_spin)
        self.subtitle_bold_check, self.subtitle_italic_check = _make_bold_italic_checks()
        font_size_layout.addWidget(
            _bold_italic_widget(self.subtitle_bold_check, self.subtitle_italic_check), 5, 1,
        )

        self.subtitle_font_family_combo = ValueComboBox(list_available_font_families())
        _field_row(font_size_layout, 6, "Subtitle font", self.subtitle_font_family_combo)

        # -- Title/subtitle color (rows 7-9, appended after the existing
        # title/subtitle font-size/bold/italic/font-family rows above to
        # avoid renumbering them) --
        self.title_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        font_size_layout.addWidget(QLabel("Title color:"), 7, 0)
        font_size_layout.addWidget(self.title_color_row, 7, 1)

        self.subtitle_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        self.subtitle_match_title_toggle = ToggleSwitch(checked=True)
        font_size_layout.addWidget(QLabel("Subtitle color:"), 8, 0)
        font_size_layout.addWidget(self.subtitle_color_row, 8, 1)
        font_size_layout.addWidget(QLabel("Match title:"), 9, 0)
        font_size_layout.addWidget(self.subtitle_match_title_toggle, 9, 1)
        # Hidden by default: subtitle_match_title_toggle starts checked, so
        # the subtitle color swatch (which would otherwise be redundant with
        # the title's) stays hidden until the user opts out of matching.
        self.subtitle_color_row.setVisible(False)

        layout.addWidget(self.font_size_card)

        # -- Padding card --
        self.padding_card = Card()
        self.chart_style_cards.append(self.padding_card)
        padding_layout = QGridLayout(self.padding_card)
        padding_layout.addWidget(SectionHeader("Padding"), 0, 0, 1, 2)

        self.chart_padding_spin = QDoubleSpinBox()
        self.chart_padding_spin.setRange(0.0, 10.0)
        self.chart_padding_spin.setSingleStep(0.5)
        self.chart_padding_spin.setValue(2.0)
        _field_row(padding_layout, 1, "Figure", self.chart_padding_spin)

        self.chart_padding_w_spin = QDoubleSpinBox()
        self.chart_padding_w_spin.setRange(0.0, 10.0)
        self.chart_padding_w_spin.setSingleStep(0.5)
        self.chart_padding_w_spin.setValue(2.0)
        _field_row(padding_layout, 2, "Width", self.chart_padding_w_spin)

        self.chart_padding_h_spin = QDoubleSpinBox()
        self.chart_padding_h_spin.setRange(0.0, 10.0)
        self.chart_padding_h_spin.setSingleStep(0.5)
        self.chart_padding_h_spin.setValue(2.0)
        _field_row(padding_layout, 3, "Height", self.chart_padding_h_spin)

        self.main_title_padding_spin = QDoubleSpinBox()
        self.main_title_padding_spin.setRange(0.0, 100.0)
        self.main_title_padding_spin.setSingleStep(1.0)
        self.main_title_padding_spin.setValue(10.0)
        _field_row(
            padding_layout, 4, "Title", self.main_title_padding_spin,
            tooltip="Gap between the top edge of the figure and the main title",
        )

        self.title_padding_spin = QDoubleSpinBox()
        self.title_padding_spin.setRange(0.0, 50.0)
        self.title_padding_spin.setSingleStep(1.0)
        self.title_padding_spin.setValue(6.0)
        _field_row(
            padding_layout, 5, "Subtitle", self.title_padding_spin,
            tooltip="Gap between the plot area and the subtitle text",
        )

        self.top_margin_spin = QDoubleSpinBox()
        self.top_margin_spin.setRange(0.5, 1.0)
        self.top_margin_spin.setSingleStep(0.01)
        self.top_margin_spin.setDecimals(2)
        self.top_margin_spin.setValue(1.0)
        _field_row(
            padding_layout, 6, "Top margin", self.top_margin_spin,
            tooltip=(
                "Fraction of the figure height reserved above the plot "
                "(1.0 = no reservation, let it auto-size). Unlike the "
                "Title/Subtitle padding above, this is a fixed reservation "
                "independent of whether a title/subtitle is present -- "
                "lower it manually to reclaim space when you remove one."
            ),
        )

        layout.addWidget(self.padding_card)

        # -- Size card --
        self.size_card = Card()
        self.chart_style_cards.append(self.size_card)
        size_layout = QGridLayout(self.size_card)
        size_layout.addWidget(SectionHeader("Size"), 0, 0, 1, 2)

        self.chart_size_combo = QComboBox()
        self.chart_size_combo.addItem("15 × 8 cm", (15.0, 8.0))
        self.chart_size_combo.addItem("20 × 15 cm", (20.0, 15.0))
        self.chart_size_combo.addItem("Custom", "custom")
        self.chart_size_combo.addItem("Use app default", None)
        _field_row(size_layout, 1, "Size", self.chart_size_combo)

        self.custom_size_row = QWidget()
        custom_size_layout = QGridLayout(self.custom_size_row)
        custom_size_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_width_spin = QDoubleSpinBox()
        self.chart_width_spin.setRange(MIN_CHART_WIDTH_CM, MAX_CHART_WIDTH_CM)
        self.chart_width_spin.setSuffix(" cm")
        _field_row(custom_size_layout, 0, "Width", self.chart_width_spin)
        self.chart_height_spin = QDoubleSpinBox()
        self.chart_height_spin.setRange(MIN_CHART_HEIGHT_CM, MAX_CHART_HEIGHT_CM)
        self.chart_height_spin.setSuffix(" cm")
        _field_row(custom_size_layout, 1, "Height", self.chart_height_spin)
        size_layout.addWidget(self.custom_size_row, 2, 0, 1, 2)
        self.custom_size_row.setVisible(False)

        hint = QLabel("Size affects export & default fonts")
        hint.setStyleSheet("font-size: 10.5px;")
        size_layout.addWidget(hint, 3, 0, 1, 2)

        layout.addWidget(self.size_card)

        # -- DPI card --
        self.dpi_card = Card()
        self.chart_style_cards.append(self.dpi_card)
        dpi_layout = QGridLayout(self.dpi_card)
        dpi_layout.addWidget(SectionHeader("DPI"), 0, 0, 1, 2)

        self.chart_dpi_combo = QComboBox()
        self.chart_dpi_combo.addItem("100 dpi", 100)
        self.chart_dpi_combo.addItem("150 dpi", 150)
        self.chart_dpi_combo.addItem("300 dpi", 300)
        self.chart_dpi_combo.addItem("Custom", "custom")
        self.chart_dpi_combo.addItem("Use app default", None)
        _field_row(dpi_layout, 1, "DPI", self.chart_dpi_combo)

        self.custom_dpi_row = QWidget()
        custom_dpi_layout = QGridLayout(self.custom_dpi_row)
        custom_dpi_layout.setContentsMargins(0, 0, 0, 0)
        self.chart_dpi_spin = QSpinBox()
        self.chart_dpi_spin.setRange(50, 600)
        _field_row(custom_dpi_layout, 0, "DPI", self.chart_dpi_spin)
        dpi_layout.addWidget(self.custom_dpi_row, 2, 0, 1, 2)
        self.custom_dpi_row.setVisible(False)

        layout.addWidget(self.dpi_card)

        # -- Background card --
        self.background_card = Card()
        self.chart_style_cards.append(self.background_card)
        bg_layout = QGridLayout(self.background_card)
        bg_layout.addWidget(SectionHeader("Background"), 0, 0, 1, 4)

        bg_layout.addWidget(QLabel("Figure:"), 1, 0)
        self.figure_bg_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        bg_layout.addWidget(self.figure_bg_color_row, 1, 1)
        bg_layout.addWidget(QLabel("Transparent:"), 2, 1)
        self.figure_bg_transparent_toggle = ToggleSwitch()
        bg_layout.addWidget(self.figure_bg_transparent_toggle, 2, 2)

        bg_layout.addWidget(QLabel("Plot area:"), 3, 0)
        self.axes_bg_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        bg_layout.addWidget(self.axes_bg_color_row, 3, 1)
        bg_layout.addWidget(QLabel("Transparent:"), 4, 1)
        self.axes_bg_transparent_toggle = ToggleSwitch()
        bg_layout.addWidget(self.axes_bg_transparent_toggle, 4, 2)

        layout.addWidget(self.background_card)

        # LINE group
        self.line_card = Card()
        line_card = self.line_card
        line_layout = QGridLayout(line_card)
        line_layout.addWidget(SectionHeader("Line"), 0, 0, 1, 2)

        line_layout.addWidget(QLabel("Color:"), 1, 0)
        self.line_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        line_layout.addWidget(self.line_color_row, 1, 1)

        line_layout.addWidget(QLabel("Style:"), 2, 0)
        _line_style_items = [
            ("Solid", LineStyleType.SOLID),
            ("Dashed", LineStyleType.DASHED),
            ("Dotted", LineStyleType.DOTTED),
            ("Dash-Dot", LineStyleType.DASHDOT),
            ("None", LineStyleType.NONE),
        ]
        _default_tokens = {"text_primary": "#1C1E26"}
        self.line_style_control = ValueComboBox(
            _line_style_items,
            icons=[build_line_style_icon(style, _default_tokens) for _, style in _line_style_items],
        )
        line_layout.addWidget(self.line_style_control, 2, 1)

        line_layout.addWidget(QLabel("Width:"), 3, 0)
        self.line_width_slider = SliderWithSpinbox(minimum=0.1, maximum=10.0, decimals=1)
        line_layout.addWidget(self.line_width_slider, 3, 1)

        line_layout.addWidget(QLabel("Opacity:"), 4, 0)
        self.line_opacity_slider = SliderWithSpinbox(minimum=0.0, maximum=1.0, decimals=2)
        line_layout.addWidget(self.line_opacity_slider, 4, 1)

        layout.addWidget(line_card)

        # CONFIDENCE BAND group -- shades the region between
        # FitData.confidence_lower/confidence_upper around a fit line.
        # Fit-only (a data series has no confidence interval concept).
        self.band_card = Card()
        band_card = self.band_card
        band_layout = QGridLayout(band_card)

        band_header_row = QHBoxLayout()
        self.band_header = SectionHeader("Confidence Band")
        band_header_row.addWidget(self.band_header)
        band_header_row.addStretch(1)
        self.band_enabled_toggle = ToggleSwitch()
        band_header_row.addWidget(self.band_enabled_toggle)
        band_layout.addLayout(band_header_row, 0, 0, 1, 2)

        self.band_color_label = QLabel("Color:")
        band_layout.addWidget(self.band_color_label, 1, 0)
        self.band_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        band_layout.addWidget(self.band_color_row, 1, 1)

        # "Match line" reuses the "" == inherit-style.color convention
        # (same pattern as fill_match_line_toggle below): a fresh FitStyle
        # has band_color="", meaning the band should track the fit line's
        # own color rather than freezing a stale/prefilled swatch value.
        self.band_match_line_label = QLabel("Match line:")
        band_layout.addWidget(self.band_match_line_label, 2, 0)
        self.band_match_line_toggle = ToggleSwitch(checked=True)
        band_layout.addWidget(self.band_match_line_toggle, 2, 1)

        self.band_opacity_label = QLabel("Opacity:")
        band_layout.addWidget(self.band_opacity_label, 3, 0)
        self.band_opacity_slider = SliderWithSpinbox(minimum=0.0, maximum=1.0, decimals=2)
        band_layout.addWidget(self.band_opacity_slider, 3, 1)

        layout.addWidget(band_card)

        # FILL group -- shade the area under the curve (down to a baseline) or
        # between this series and another series in the same chart.
        self.fill_card = Card()
        fill_card = self.fill_card
        fill_layout = QGridLayout(fill_card)

        fill_header_row = QHBoxLayout()
        self.fill_header = SectionHeader("Fill")
        fill_header_row.addWidget(self.fill_header)
        fill_header_row.addStretch(1)
        self.fill_enabled_toggle = ToggleSwitch()
        fill_header_row.addWidget(self.fill_enabled_toggle)
        fill_layout.addLayout(fill_header_row, 0, 0, 1, 2)

        # Orientation switch: off => vertical fill to a Y baseline
        # (fill_between); on => horizontal fill to an X baseline
        # (fill_betweenx). It also flips how the baseline field and "Fill to"
        # interpolation are interpreted (see _update_fill_controls_visibility).
        self.fill_horizontal_label = QLabel("Horizontal:")
        fill_layout.addWidget(self.fill_horizontal_label, 1, 0)
        self.fill_horizontal_toggle = ToggleSwitch()
        fill_layout.addWidget(self.fill_horizontal_toggle, 1, 1)

        # "Fill to" is repopulated per selected series (see load_series_style):
        # a "Baseline" entry (value -1) plus every *other* series in the chart
        # (value = its index in data_series). Seeded with just Baseline so the
        # ValueComboBox has a non-empty initial item list.
        self.fill_to_label = QLabel("Fill to:")
        fill_layout.addWidget(self.fill_to_label, 2, 0)
        self.fill_to_control = ValueComboBox([("Baseline", -1)])
        fill_layout.addWidget(self.fill_to_control, 2, 1)

        self.fill_base_label = QLabel("Baseline:")
        fill_layout.addWidget(self.fill_base_label, 3, 0)
        self.fill_base_spin = QDoubleSpinBox()
        self.fill_base_spin.setRange(-1e9, 1e9)
        self.fill_base_spin.setDecimals(3)
        fill_layout.addWidget(self.fill_base_spin, 3, 1)

        self.fill_color_label = QLabel("Color:")
        fill_layout.addWidget(self.fill_color_label, 4, 0)
        self.fill_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        fill_layout.addWidget(self.fill_color_row, 4, 1)

        self.fill_match_line_label = QLabel("Match line:")
        fill_layout.addWidget(self.fill_match_line_label, 5, 0)
        self.fill_match_line_toggle = ToggleSwitch(checked=True)
        fill_layout.addWidget(self.fill_match_line_toggle, 5, 1)

        self.fill_opacity_label = QLabel("Opacity:")
        fill_layout.addWidget(self.fill_opacity_label, 6, 0)
        self.fill_opacity_slider = SliderWithSpinbox(minimum=0.0, maximum=1.0, decimals=2)
        fill_layout.addWidget(self.fill_opacity_slider, 6, 1)

        layout.addWidget(fill_card)

        # MARKERS group
        self.marker_card = Card()
        marker_card = self.marker_card
        marker_layout = QGridLayout(marker_card)

        marker_header_row = QHBoxLayout()
        self.marker_header = SectionHeader("Markers")
        marker_header_row.addWidget(self.marker_header)
        marker_header_row.addStretch(1)
        self.markers_enabled_toggle = ToggleSwitch()
        marker_header_row.addWidget(self.markers_enabled_toggle)
        marker_layout.addLayout(marker_header_row, 0, 0, 1, 2)

        self.marker_shape_label = QLabel("Shape:")
        marker_layout.addWidget(self.marker_shape_label, 1, 0)
        self.marker_shape_control = ValueComboBox(
            [
                ("● Circle", MarkerType.CIRCLE),
                ("■ Square", MarkerType.SQUARE),
                ("▲ Triangle", MarkerType.TRIANGLE),
                ("◆ Diamond", MarkerType.DIAMOND),
                ("★ Star", MarkerType.STAR),
                ("+ Plus", MarkerType.PLUS),
                ("✕ Cross", MarkerType.CROSS),
            ]
        )
        marker_layout.addWidget(self.marker_shape_control, 1, 1)

        self.marker_size_label = QLabel("Size:")
        marker_layout.addWidget(self.marker_size_label, 2, 0)
        self.marker_size_slider = SliderWithSpinbox(minimum=1.0, maximum=20.0, decimals=1)
        marker_layout.addWidget(self.marker_size_slider, 2, 1)

        # Edge width is independent of "Match line" (below) -- that only
        # controls fill/edge *color*, not the edge line's thickness -- so it
        # lives with the other always-visible marker fields, not the
        # color-picker group that Match line hides.
        self.marker_edge_width_label = QLabel("Edge width:")
        marker_layout.addWidget(self.marker_edge_width_label, 3, 0)
        self.marker_edge_width_slider = SliderWithSpinbox(minimum=0.0, maximum=5.0, decimals=1)
        marker_layout.addWidget(self.marker_edge_width_slider, 3, 1)

        self.marker_color_label = QLabel("Color:")
        marker_layout.addWidget(self.marker_color_label, 4, 0)
        self.marker_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        marker_layout.addWidget(self.marker_color_row, 4, 1)

        self.marker_match_line_label = QLabel("Match line:")
        marker_layout.addWidget(self.marker_match_line_label, 5, 0)
        self.marker_match_line_toggle = ToggleSwitch(checked=True)
        marker_layout.addWidget(self.marker_match_line_toggle, 5, 1)

        self.marker_edge_color_label = QLabel("Edge color:")
        marker_layout.addWidget(self.marker_edge_color_label, 6, 0)
        self.marker_edge_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        marker_layout.addWidget(self.marker_edge_color_row, 6, 1)

        layout.addWidget(marker_card)

        # ERROR BARS group -- which columns feed the error bars is configured
        # on the Data tab (including the Asymmetric Error Bars checkbox);
        # this group only controls how they render.
        self.error_bars_card = Card()
        error_bars_card = self.error_bars_card
        error_layout = QGridLayout(error_bars_card)
        error_layout.addWidget(SectionHeader("Error Bars"), 0, 0, 1, 2)

        error_layout.addWidget(QLabel("Direction:"), 1, 0)
        self.error_direction_control = ValueComboBox(
            [
                ("Both", ErrorDirection.BOTH),
                ("Above (+)", ErrorDirection.PLUS),
                ("Below (-)", ErrorDirection.MINUS),
            ]
        )
        error_layout.addWidget(self.error_direction_control, 1, 1)

        self.error_color_label = QLabel("Color:")
        error_layout.addWidget(self.error_color_label, 2, 0)
        self.error_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        error_layout.addWidget(self.error_color_row, 2, 1)

        error_layout.addWidget(QLabel("Match line:"), 3, 0)
        self.error_match_line_toggle = ToggleSwitch(checked=True)
        error_layout.addWidget(self.error_match_line_toggle, 3, 1)

        error_layout.addWidget(QLabel("Cap Size:"), 4, 0)
        self.error_cap_size_slider = SliderWithSpinbox(minimum=0.0, maximum=20.0, decimals=1)
        error_layout.addWidget(self.error_cap_size_slider, 4, 1)

        layout.addWidget(error_bars_card)

        # VECTOR group -- shown instead of Line/Fill/Marker/Error Bars for a
        # series on a Vector (quiver) chart, which has no line/marker/fill/
        # error-bar concept of its own.
        self.vector_card = Card()
        vector_card = self.vector_card
        vector_layout = QGridLayout(vector_card)
        vector_layout.addWidget(SectionHeader("Vector"), 0, 0, 1, 2)

        vector_layout.addWidget(QLabel("Color:"), 1, 0)
        self.vector_color_row = ColorSwatchRow(STYLE_SWATCH_PALETTE)
        vector_layout.addWidget(self.vector_color_row, 1, 1)

        vector_layout.addWidget(QLabel("Color by magnitude:"), 2, 0)
        self.vector_colormap_control = ValueComboBox(VECTOR_COLORMAPS)
        vector_layout.addWidget(self.vector_colormap_control, 2, 1)

        vector_layout.addWidget(QLabel("Scale:"), 3, 0)
        self.vector_scale_slider = SliderWithSpinbox(minimum=0.0, maximum=50.0, decimals=2)
        vector_layout.addWidget(self.vector_scale_slider, 3, 1)

        vector_layout.addWidget(QLabel("Width:"), 4, 0)
        self.vector_width_slider = SliderWithSpinbox(minimum=0.0005, maximum=0.05, decimals=4)
        vector_layout.addWidget(self.vector_width_slider, 4, 1)

        vector_layout.addWidget(QLabel("Head width:"), 5, 0)
        self.vector_head_width_slider = SliderWithSpinbox(minimum=0.0, maximum=20.0, decimals=1)
        vector_layout.addWidget(self.vector_head_width_slider, 5, 1)

        vector_layout.addWidget(QLabel("Head length:"), 6, 0)
        self.vector_head_length_slider = SliderWithSpinbox(minimum=0.0, maximum=20.0, decimals=1)
        vector_layout.addWidget(self.vector_head_length_slider, 6, 1)

        vector_layout.addWidget(QLabel("Head axis length:"), 7, 0)
        self.vector_head_axis_length_slider = SliderWithSpinbox(minimum=0.0, maximum=20.0, decimals=1)
        vector_layout.addWidget(self.vector_head_axis_length_slider, 7, 1)

        layout.addWidget(vector_card)

        # HEATMAP GRIDDING group -- per-series (SeriesTypeSpec.supports_
        # gridding -- Heatmap only; Colormap, a plain color-mapped scatter,
        # needs no gridding at all). The colormap/colorbar/scale that used
        # to live in this same card moved to a chart-level "Color Map" chip
        # (see colormap_config_card below) -- there's only ever one
        # physical colorbar for the whole chart, not one per series.
        self.heatmap_gridding_card = Card()
        heatmap_gridding_card = self.heatmap_gridding_card
        heatmap_gridding_layout = QGridLayout(heatmap_gridding_card)
        heatmap_gridding_layout.addWidget(SectionHeader("Gridding"), 0, 0, 1, 2)

        # "Exact grid" mode has no resolution to configure (it uses the
        # data's own lattice, see chart_heatmap.build_heatmap_grid), so the
        # resolution row is additionally hidden while that mode is selected
        # (see _on_heatmap_gridding_changed).
        self.heatmap_gridding_label = QLabel("Gridding:")
        heatmap_gridding_layout.addWidget(self.heatmap_gridding_label, 1, 0)
        self.heatmap_gridding_control = ValueComboBox(HEATMAP_GRIDDING_OPTIONS)
        heatmap_gridding_layout.addWidget(self.heatmap_gridding_control, 1, 1)

        self.heatmap_resolution_label = QLabel("Resolution:")
        heatmap_gridding_layout.addWidget(self.heatmap_resolution_label, 2, 0)
        self.heatmap_resolution_spin = QSpinBox()
        self.heatmap_resolution_spin.setRange(2, 500)
        self.heatmap_resolution_spin.setValue(50)
        heatmap_gridding_layout.addWidget(self.heatmap_resolution_spin, 2, 1)

        layout.addWidget(heatmap_gridding_card)

        # COLOR MAP group -- chart-level (not per-series): colormap,
        # colorbar, and color-scale limits are shared across every
        # Colormap/Heatmap series on the chart, since there's only ever one
        # physical colorbar drawn. Shown only when the "Color Map" chip in
        # style_series_chips is selected (see _update_target_cards_
        # visibility), which itself only appears when the chart has >=1
        # series with SeriesTypeSpec.needs_z_column (see set_series_list).
        self.colormap_config_card = Card()
        colormap_config_card = self.colormap_config_card
        colormap_config_layout = QGridLayout(colormap_config_card)
        colormap_config_layout.addWidget(SectionHeader("Color Map"), 0, 0, 1, 2)

        colormap_config_layout.addWidget(QLabel("Colormap:"), 1, 0)
        self.colormap_control = ValueComboBox(COLORMAP_OPTIONS)
        colormap_config_layout.addWidget(self.colormap_control, 1, 1)

        colormap_config_layout.addWidget(QLabel("Show colorbar:"), 2, 0)
        self.colorbar_show_toggle = ToggleSwitch(checked=True)
        colormap_config_layout.addWidget(self.colorbar_show_toggle, 2, 1)

        colormap_config_layout.addWidget(QLabel("Colorbar label:"), 3, 0)
        self.colorbar_label_edit = QLineEdit()
        colormap_config_layout.addWidget(self.colorbar_label_edit, 3, 1)

        colormap_config_layout.addWidget(QLabel("Auto scale:"), 4, 0)
        self.color_scale_auto_toggle = ToggleSwitch(checked=True)
        colormap_config_layout.addWidget(self.color_scale_auto_toggle, 4, 1)

        self.color_vmin_label = QLabel("Min:")
        colormap_config_layout.addWidget(self.color_vmin_label, 5, 0)
        self.color_vmin_spin = QDoubleSpinBox()
        self.color_vmin_spin.setRange(-1e9, 1e9)
        self.color_vmin_spin.setDecimals(3)
        colormap_config_layout.addWidget(self.color_vmin_spin, 5, 1)

        self.color_vmax_label = QLabel("Max:")
        colormap_config_layout.addWidget(self.color_vmax_label, 6, 0)
        self.color_vmax_spin = QDoubleSpinBox()
        self.color_vmax_spin.setRange(-1e9, 1e9)
        self.color_vmax_spin.setDecimals(3)
        self.color_vmax_spin.setValue(1.0)
        colormap_config_layout.addWidget(self.color_vmax_spin, 6, 1)

        layout.addWidget(colormap_config_card)

        # -- Axes (appearance) section: its own top-level selection in
        # style_series_chips (sibling to "Chart"/series/fit), not nested
        # under "Chart" -- axis appearance is a chart-wide concern like the
        # Font Size/Padding/Size/DPI cards above, but gets its own entry in
        # the selector rather than being folded into "Chart"'s cards.
        self.axes_style_selector = ValueComboBox([("X", "x"), ("Y₁", "y")])
        self.axes_style_widgets: list[QWidget] = [self.axes_style_selector]
        layout.addWidget(self.axes_style_selector)

        self._axes_style_form_container = QWidget()
        self._axes_style_form_container_layout = QVBoxLayout(self._axes_style_form_container)
        self._axes_style_form_container_layout.setContentsMargins(0, 0, 0, 0)
        self.axes_style_widgets.append(self._axes_style_form_container)
        layout.addWidget(self._axes_style_form_container)

        self.axes_style_forms = {}
        for prefix in ("x", "y", "y2"):
            self._build_axis_style_form(prefix)
        self._show_axis_style_form("x")
        self.axes_style_selector.currentValueChanged.connect(self._show_axis_style_form)

        layout.addStretch()
        for card in self.chart_style_cards:
            card.setVisible(False)
        for widget in self.axes_style_widgets:
            widget.setVisible(False)

        # Series/fit style field connections.
        self.line_color_row.colorChanged.connect(self._on_field_changed)
        self.line_style_control.currentValueChanged.connect(self._on_field_changed)
        self.line_width_slider.valueChanged.connect(self._on_field_changed)
        self.line_opacity_slider.valueChanged.connect(self._on_field_changed)
        self.band_enabled_toggle.toggled.connect(self._on_band_enabled_toggled)
        self.band_enabled_toggle.toggled.connect(self._on_field_changed)
        self.band_color_row.colorChanged.connect(self._on_field_changed)
        self.band_match_line_toggle.toggled.connect(self._on_band_match_line_toggled)
        self.band_opacity_slider.valueChanged.connect(self._on_field_changed)
        self.fill_enabled_toggle.toggled.connect(self._on_fill_enabled_toggled)
        self.fill_horizontal_toggle.toggled.connect(self._on_fill_orientation_toggled)
        self.fill_to_control.currentValueChanged.connect(self._on_fill_to_changed)
        self.fill_base_spin.valueChanged.connect(self._on_field_changed)
        self.fill_color_row.colorChanged.connect(self._on_field_changed)
        self.fill_match_line_toggle.toggled.connect(self._on_fill_match_line_toggled)
        self.fill_opacity_slider.valueChanged.connect(self._on_field_changed)
        self.markers_enabled_toggle.toggled.connect(self._on_markers_enabled_toggled)
        self.marker_shape_control.currentValueChanged.connect(self._on_field_changed)
        self.marker_size_slider.valueChanged.connect(self._on_field_changed)
        self.marker_color_row.colorChanged.connect(self._on_field_changed)
        self.marker_match_line_toggle.toggled.connect(self._on_marker_match_line_toggled)
        self.marker_edge_color_row.colorChanged.connect(self._on_field_changed)
        self.marker_edge_width_slider.valueChanged.connect(self._on_field_changed)
        self.error_direction_control.currentValueChanged.connect(self._on_field_changed)
        self.error_color_row.colorChanged.connect(self._on_field_changed)
        self.error_match_line_toggle.toggled.connect(self._on_error_match_line_toggled)
        self.error_cap_size_slider.valueChanged.connect(self._on_field_changed)
        self.vector_color_row.colorChanged.connect(self._on_field_changed)
        self.vector_colormap_control.currentValueChanged.connect(self._on_field_changed)
        self.vector_scale_slider.valueChanged.connect(self._on_field_changed)
        self.vector_width_slider.valueChanged.connect(self._on_field_changed)
        self.vector_head_width_slider.valueChanged.connect(self._on_field_changed)
        self.vector_head_length_slider.valueChanged.connect(self._on_field_changed)
        self.vector_head_axis_length_slider.valueChanged.connect(self._on_field_changed)
        self.colormap_control.currentValueChanged.connect(self._on_field_changed)
        self.colorbar_show_toggle.toggled.connect(self._on_field_changed)
        self.colorbar_label_edit.textChanged.connect(self._on_field_changed)
        self.color_scale_auto_toggle.toggled.connect(self._on_color_scale_auto_toggled)
        self.color_vmin_spin.valueChanged.connect(self._on_field_changed)
        self.color_vmax_spin.valueChanged.connect(self._on_field_changed)
        self.heatmap_gridding_control.currentValueChanged.connect(self._on_heatmap_gridding_changed)
        self.heatmap_resolution_spin.valueChanged.connect(self._on_field_changed)

        # chart_style_card field connections.
        self.title_font_size_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.subtitle_font_size_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.chart_padding_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.chart_padding_w_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.chart_padding_h_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.title_padding_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.main_title_padding_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.top_margin_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.title_bold_check.toggled.connect(self._on_chart_style_field_changed)
        self.title_italic_check.toggled.connect(self._on_chart_style_field_changed)
        self.subtitle_bold_check.toggled.connect(self._on_chart_style_field_changed)
        self.subtitle_italic_check.toggled.connect(self._on_chart_style_field_changed)
        self.title_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        self.subtitle_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        self.title_font_family_combo.currentValueChanged.connect(self._on_chart_style_field_changed)
        self.subtitle_font_family_combo.currentValueChanged.connect(self._on_chart_style_field_changed)
        self.subtitle_match_title_toggle.toggled.connect(self._on_subtitle_match_title_toggled)
        self.chart_size_combo.currentIndexChanged.connect(self._on_chart_size_combo_changed)
        self.chart_dpi_combo.currentIndexChanged.connect(self._on_chart_dpi_combo_changed)
        self.chart_width_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.chart_height_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.chart_dpi_spin.valueChanged.connect(self._on_chart_style_field_changed)
        self.figure_bg_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        self.figure_bg_transparent_toggle.toggled.connect(self._on_bg_transparent_toggled)
        self.axes_bg_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        self.axes_bg_transparent_toggle.toggled.connect(self._on_bg_transparent_toggled)

    # -- Chip selection / target routing -----------------------------------

    def _on_chip_selected(self, value):
        if value == "chart":
            self._current_target = ("chart", None)
            self._update_target_cards_visibility()
        elif value == "axes":
            self._current_target = ("axes", None)
            self._update_target_cards_visibility()
        elif value == "colormap_config":
            self._current_target = ("colormap_config", None)
            self._update_target_cards_visibility()
        elif value is not None:
            # The panel is the source of truth for series/fit selection --
            # this tab does not self-select a series; it only reacts to
            # set_selected(). `None` is the transient value QComboBox
            # reports mid-`clear()` (no current item yet) and isn't a real
            # selection to relay.
            self.seriesChipSelected.emit(value)

    def _update_target_cards_visibility(self):
        """Show the Chart card XOR the Line/Marker cards, matching whichever
        Style-tab chip is currently selected. Line/Fill/Marker/ErrorBars
        visibility for a selected series is driven by SERIES_TYPE_SPECS for
        the selected series' own type (falling back to the chart's type for
        the Chart/Axes chips, which have no specific series) -- the single
        source of truth for this, replacing per-type booleans this method
        used to compute locally.

        A selected *fit* is unaffected by the series' spec -- a fit is
        always rendered as a line regardless of chart type -- so the Line
        card stays visible for fit even on Scatter charts. The Marker card
        only applies to a series: fit data has no marker concept.
        """
        kind, obj = self._current_target
        is_chart = kind == "chart"
        for card in self.chart_style_cards:
            card.setVisible(is_chart)
        is_axes = kind == "axes"
        for widget in self.axes_style_widgets:
            widget.setVisible(is_axes)
        is_colormap_config = kind == "colormap_config"
        self.colormap_config_card.setVisible(is_colormap_config)
        if kind == "series" and isinstance(obj, DataSeries):
            spec = SERIES_TYPE_SPECS[obj.series_type]
        elif self._chart_type:
            spec = SERIES_TYPE_SPECS[SeriesType(self._chart_type)]
        else:
            spec = None
        marker_supported = spec is not None and spec.marker_mode != "unsupported"
        color_supported = spec is not None and spec.supports_color
        fill_supported = spec is not None and spec.supports_fill
        error_bars_supported = spec is not None and spec.supports_error_bars
        # The Line card holds both color/opacity controls (style.color/
        # style.alpha, rendered for line/bar/hist) and line_style/line_width
        # controls (rendered only for "line" -- see SeriesTypeSpec.supports_
        # line_style's docstring). Gating the whole card on supports_color
        # keeps color/opacity available for bar/hist even though their
        # line_style/line_width controls have no effect for those types,
        # matching pre-Phase-2 behavior exactly.
        self.line_card.setVisible(kind == "fit" or (kind == "series" and color_supported))
        self.band_card.setVisible(
            kind == "fit" and isinstance(obj, FitData) and obj.confidence_lower is not None
        )
        self.fill_card.setVisible(kind == "series" and fill_supported)
        self.marker_card.setVisible(kind == "series" and marker_supported)
        # Fit data has no error-bar fields at all (DataSeries-only), and even
        # for a series there's nothing to style unless an error column is
        # actually configured (on the Data tab) -- otherwise the card's
        # controls (direction/color/cap size) have no error bars to apply to.
        self.error_bars_card.setVisible(
            kind == "series" and isinstance(obj, DataSeries) and obj.has_error_data and error_bars_supported
        )
        self.vector_card.setVisible(kind == "series" and spec is not None and spec.needs_secondary_columns)
        self.heatmap_gridding_card.setVisible(kind == "series" and spec is not None and spec.supports_gridding)
        # Re-evaluate "Match line" visibility: it depends on both kind and
        # chart type (see _is_scatter_series_target), either of which may
        # have just changed.
        self._update_marker_controls_enabled()
        self._update_colormap_gridding_visibility()

    def _build_axis_style_form(self, prefix: str):
        """Build one axis's appearance form (title font/color, tick-value
        font/color [Task 6], spine/tick colors [Task 6]) and register it in
        `self.axes_style_forms[prefix]`."""
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        title_card = Card()
        title_layout = QGridLayout(title_card)
        title_layout.addWidget(SectionHeader("Axis title"), 0, 0, 1, 2)

        title_layout.addWidget(QLabel("Font size:"), 1, 0)
        font_size_spin = QSpinBox()
        font_size_spin.setRange(6, 32)
        font_size_spin.setValue(12)
        title_layout.addWidget(font_size_spin, 1, 1)

        title_layout.addWidget(QLabel("Font family:"), 2, 0)
        font_family_combo = ValueComboBox(list_available_font_families())
        title_layout.addWidget(font_family_combo, 2, 1)

        bold_check, italic_check = _make_bold_italic_checks_standalone()
        bold_italic_row = QHBoxLayout()
        bold_italic_row.setContentsMargins(0, 0, 0, 0)
        bold_italic_row.addWidget(bold_check)
        bold_italic_row.addWidget(italic_check)
        bold_italic_row.addStretch(1)
        bold_italic_widget = QWidget()
        bold_italic_widget.setLayout(bold_italic_row)
        title_layout.addWidget(bold_italic_widget, 3, 1)

        color_label = QLabel("Color:")
        title_layout.addWidget(color_label, 4, 0)
        color_row = ColorSwatchRow(AXES_SWATCH_PALETTE)
        title_layout.addWidget(color_row, 4, 1)
        match_x_toggle = None
        if prefix in ("y", "y2"):
            match_x_toggle = ToggleSwitch(checked=True)
            title_layout.addWidget(QLabel("Match X:"), 4, 2)
            title_layout.addWidget(match_x_toggle, 4, 3)
            color_label.setVisible(False)
            color_row.setVisible(False)

        title_layout.addWidget(QLabel("Rotation:"), 5, 0)
        rotation_spin = QSpinBox()
        rotation_spin.setRange(-90, 90)
        rotation_spin.setSuffix("°")
        rotation_spin.setValue(90 if prefix in ("y", "y2") else 0)
        title_layout.addWidget(rotation_spin, 5, 1)

        form_layout.addWidget(title_card)

        ticks_card = Card()
        ticks_layout = QGridLayout(ticks_card)
        ticks_layout.addWidget(SectionHeader("Tick values"), 0, 0, 1, 2)

        ticks_layout.addWidget(QLabel("Font size:"), 1, 0)
        tick_font_size_spin = QSpinBox()
        tick_font_size_spin.setRange(6, 32)
        tick_font_size_spin.setValue(10)
        ticks_layout.addWidget(tick_font_size_spin, 1, 1)

        ticks_layout.addWidget(QLabel("Font family:"), 2, 0)
        tick_font_family_combo = ValueComboBox(list_available_font_families())
        ticks_layout.addWidget(tick_font_family_combo, 2, 1)

        tick_bold_check, tick_italic_check = _make_bold_italic_checks_standalone()
        tick_bold_italic_row = QHBoxLayout()
        tick_bold_italic_row.setContentsMargins(0, 0, 0, 0)
        tick_bold_italic_row.addWidget(tick_bold_check)
        tick_bold_italic_row.addWidget(tick_italic_check)
        tick_bold_italic_row.addStretch(1)
        tick_bold_italic_widget = QWidget()
        tick_bold_italic_widget.setLayout(tick_bold_italic_row)
        ticks_layout.addWidget(tick_bold_italic_widget, 3, 1)

        ticks_layout.addWidget(QLabel("Color:"), 4, 0)
        tick_color_row = ColorSwatchRow(AXES_SWATCH_PALETTE)
        ticks_layout.addWidget(tick_color_row, 4, 1)

        ticks_layout.addWidget(QLabel("Rotation:"), 5, 0)
        tick_rotation_spin = QSpinBox()
        tick_rotation_spin.setRange(-90, 90)
        tick_rotation_spin.setSuffix("°")
        ticks_layout.addWidget(tick_rotation_spin, 5, 1)

        form_layout.addWidget(ticks_card)

        colors_card = Card()
        colors_layout = QGridLayout(colors_card)
        colors_layout.addWidget(SectionHeader("Colors"), 0, 0, 1, 2)

        colors_layout.addWidget(QLabel("Spine:"), 1, 0)
        spine_color_row = ColorSwatchRow(AXES_SWATCH_PALETTE)
        colors_layout.addWidget(spine_color_row, 1, 1)

        colors_layout.addWidget(QLabel("Major ticks:"), 2, 0)
        major_tick_color_row = ColorSwatchRow(AXES_SWATCH_PALETTE)
        colors_layout.addWidget(major_tick_color_row, 2, 1)

        minor_tick_color_label = QLabel("Minor ticks:")
        colors_layout.addWidget(minor_tick_color_label, 3, 0)
        minor_tick_color_row = ColorSwatchRow(AXES_SWATCH_PALETTE)
        colors_layout.addWidget(minor_tick_color_row, 3, 1)

        match_x_colors_toggle = None
        if prefix in ("y", "y2"):
            match_x_colors_toggle = ToggleSwitch(checked=True)
            colors_layout.addWidget(QLabel("Match X:"), 4, 0)
            colors_layout.addWidget(match_x_colors_toggle, 4, 1)

        form_layout.addWidget(colors_card)

        copy_button = None
        if prefix in ("y", "y2"):
            copy_button = PButton(
                "Copy style to Y axis", role="secondary",
                on_click=lambda _checked=False, p=prefix: self._on_copy_axis_style(p)
            )
            form_layout.addWidget(copy_button)

        self.axes_style_forms[prefix] = {
            "widget": form_widget, "title_card": title_card,
            "font_size_spin": font_size_spin, "font_family_combo": font_family_combo,
            "bold_check": bold_check, "italic_check": italic_check,
            "color_row": color_row, "color_label": color_label,
            "match_x_toggle": match_x_toggle,
            "rotation_spin": rotation_spin,
            "ticks_card": ticks_card,
            "tick_font_size_spin": tick_font_size_spin,
            "tick_font_family_combo": tick_font_family_combo,
            "tick_bold_check": tick_bold_check, "tick_italic_check": tick_italic_check,
            "tick_color_row": tick_color_row,
            "tick_rotation_spin": tick_rotation_spin,
            "colors_card": colors_card,
            "spine_color_row": spine_color_row,
            "major_tick_color_row": major_tick_color_row,
            "minor_tick_color_row": minor_tick_color_row,
            "minor_tick_color_label": minor_tick_color_label,
            "match_x_colors_toggle": match_x_colors_toggle,
            "copy_button": copy_button,
        }

        font_size_spin.valueChanged.connect(self._on_chart_style_field_changed)
        font_family_combo.currentValueChanged.connect(self._on_chart_style_field_changed)
        bold_check.toggled.connect(self._on_chart_style_field_changed)
        italic_check.toggled.connect(self._on_chart_style_field_changed)
        color_row.colorChanged.connect(self._on_chart_style_field_changed)
        rotation_spin.valueChanged.connect(self._on_chart_style_field_changed)
        if match_x_toggle is not None:
            match_x_toggle.toggled.connect(lambda checked, p=prefix: self._on_axis_style_match_x_toggled(p, checked))

        tick_font_size_spin.valueChanged.connect(self._on_chart_style_field_changed)
        tick_font_family_combo.currentValueChanged.connect(self._on_chart_style_field_changed)
        tick_bold_check.toggled.connect(self._on_chart_style_field_changed)
        tick_italic_check.toggled.connect(self._on_chart_style_field_changed)
        tick_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        tick_rotation_spin.valueChanged.connect(self._on_chart_style_field_changed)
        spine_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        major_tick_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        minor_tick_color_row.colorChanged.connect(self._on_chart_style_field_changed)
        if match_x_colors_toggle is not None:
            match_x_colors_toggle.toggled.connect(
                lambda checked, p=prefix: self._on_axis_style_match_x_colors_toggled(p, checked))

        form_widget.setVisible(False)
        self._axes_style_form_container_layout.addWidget(form_widget)

    def _show_axis_style_form(self, prefix: str):
        for key, form in self.axes_style_forms.items():
            form["widget"].setVisible(key == prefix)

    def _on_axis_style_match_x_toggled(self, prefix: str, checked: bool):
        """Hide the axis-title color swatch while matching X; pre-fill from
        X's current color the first time it's revealed (mirrors
        AxesTab._on_match_x_label_toggled)."""
        form = self.axes_style_forms[prefix]
        if not checked and not self._updating_controls:
            form["color_row"].setCurrentColor(self.axes_style_forms["x"]["color_row"].currentColor())
        form["color_label"].setVisible(not checked)
        form["color_row"].setVisible(not checked)
        self._on_chart_style_field_changed()

    def _on_axis_style_match_x_colors_toggled(self, prefix: str, checked: bool):
        """Mirrors AxesTab._on_match_x_colors_toggled, for the Style tab's
        Colors card (spine/major/minor tick colors).

        Unlike AxesTab's equivalent, minor-tick-color visibility here is
        gated only by the Match-X toggle, not additionally by "are minor
        ticks enabled" -- that state lives in the Axes tab, not this form;
        showing the minor-tick-color picker here even when minor ticks
        happen to be off is harmless, since it just sets a color that has
        no effect until minor ticks are turned on elsewhere.
        """
        form = self.axes_style_forms[prefix]
        x_form = self.axes_style_forms["x"]
        if not checked and not self._updating_controls:
            form["spine_color_row"].setCurrentColor(x_form["spine_color_row"].currentColor())
            form["major_tick_color_row"].setCurrentColor(x_form["major_tick_color_row"].currentColor())
            form["minor_tick_color_row"].setCurrentColor(x_form["minor_tick_color_row"].currentColor())
            form["tick_color_row"].setCurrentColor(x_form["tick_color_row"].currentColor())
        for widget_key in ("spine_color_row", "major_tick_color_row", "tick_color_row"):
            form[widget_key].setVisible(not checked)
        form["minor_tick_color_row"].setVisible(not checked)
        form["minor_tick_color_label"].setVisible(not checked)
        self._on_chart_style_field_changed()

    def _on_copy_axis_style(self, prefix: str):
        """Copy the shown Y axis's appearance fields (font/color, tick
        font/color, spine/tick colors) to the other Y axis. Mirrors
        AxesTab._on_copy_axis_settings, scoped to this tab's own fields."""
        other = "y2" if prefix == "y" else "y"
        source = self.axes_style_forms[prefix]
        target = self.axes_style_forms[other]

        target["font_size_spin"].setValue(source["font_size_spin"].value())
        target["font_family_combo"].setCurrentValue(source["font_family_combo"].currentValue())
        target["bold_check"].setChecked(source["bold_check"].isChecked())
        target["italic_check"].setChecked(source["italic_check"].isChecked())
        target["rotation_spin"].setValue(source["rotation_spin"].value())
        target["tick_font_size_spin"].setValue(source["tick_font_size_spin"].value())
        target["tick_font_family_combo"].setCurrentValue(source["tick_font_family_combo"].currentValue())
        target["tick_bold_check"].setChecked(source["tick_bold_check"].isChecked())
        target["tick_italic_check"].setChecked(source["tick_italic_check"].isChecked())
        target["tick_rotation_spin"].setValue(source["tick_rotation_spin"].value())

        # Match-X toggles MUST be set before the color swatches they gate
        # (see AxesTab._on_copy_axis_settings for why: setChecked fires
        # toggled unconditionally, and the handler pre-fills from X's
        # *current* color whenever set to "not matching").
        if source["match_x_toggle"] is not None and target["match_x_toggle"] is not None:
            target["match_x_toggle"].setChecked(source["match_x_toggle"].isChecked())
        if source["match_x_colors_toggle"] is not None and target["match_x_colors_toggle"] is not None:
            target["match_x_colors_toggle"].setChecked(source["match_x_colors_toggle"].isChecked())

        target["color_row"].setCurrentColor(source["color_row"].currentColor())
        target["tick_color_row"].setCurrentColor(source["tick_color_row"].currentColor())
        target["spine_color_row"].setCurrentColor(source["spine_color_row"].currentColor())
        target["major_tick_color_row"].setCurrentColor(source["major_tick_color_row"].currentColor())
        target["minor_tick_color_row"].setCurrentColor(source["minor_tick_color_row"].currentColor())

        target["color_label"].setVisible(not target["match_x_toggle"].isChecked())
        target["color_row"].setVisible(not target["match_x_toggle"].isChecked())
        matching_colors = target["match_x_colors_toggle"].isChecked()
        for widget_key in ("spine_color_row", "major_tick_color_row", "tick_color_row", "minor_tick_color_row"):
            target[widget_key].setVisible(not matching_colors)
        target["minor_tick_color_label"].setVisible(not matching_colors)

        self._on_chart_style_field_changed()

    def refresh_axis_style_selector(self, chart):
        """Sync `axes_style_selector`'s Y₂ item with whether any series
        currently uses the secondary Y axis (mirrors
        AxesTab.refresh_axis_chips). Safe to call whenever the chart or its
        series may have changed."""
        from pandaplot.models.project.items.chart import YAxis
        has_secondary = bool(chart) and any(
            series.y_axis == YAxis.SECONDARY for series in chart.data_series
        )
        current = self.axes_style_selector.currentValue()
        self.axes_style_selector.blockSignals(True)
        self.axes_style_selector.clear()
        self.axes_style_selector.addItem("X", "x")
        self.axes_style_selector.addItem("Y₁", "y")
        if has_secondary:
            self.axes_style_selector.addItem("Y₂", "y2")
        restore_index = self.axes_style_selector.findData(current) if current else -1
        self.axes_style_selector.setCurrentIndex(restore_index if restore_index >= 0 else 0)
        self.axes_style_selector.blockSignals(False)
        # setCurrentIndex() above ran with signals blocked (so rebuilding the
        # combo's items doesn't spuriously emit currentValueChanged), which
        # means _show_axis_style_form never fires if the selection was just
        # forced back to "X" (e.g. the last Y2 series was removed while Y2
        # was selected) -- the Y2 form would stay visible while the combo now
        # reads "X". Drive it explicitly so the visible form always matches.
        self._show_axis_style_form(self.axes_style_selector.currentValue() or "x")

    def _is_scatter_series_target(self) -> bool:
        """Whether the current target is a data series with no drawn line at
        all (Line card hidden; see _update_target_cards_visibility), so
        "match line" has nothing to refer to and marker colors must always
        be set explicitly. Spec-driven off SERIES_TYPE_SPECS.supports_color
        (the same flag gating the Line card) rather than hardcoding
        SeriesType.SCATTER, so it also covers Colormap (supports_color=False,
        required marker).

        BAR/HIST/VECTOR/HEATMAP have marker_mode="unsupported", so their
        Marker card is never shown regardless of this value."""
        kind, obj = self._current_target
        if kind != "series" or not isinstance(obj, DataSeries):
            return False
        return not SERIES_TYPE_SPECS[obj.series_type].supports_color

    def _is_z_driven_series_target(self) -> bool:
        """Whether the current target is a data series whose fill color is
        driven by its Z column through a colormap (Colormap/Heatmap --
        SeriesTypeSpec.needs_z_column), rather than by a fixed marker color.
        For such a series, style.marker.marker_color is read by no renderer
        (see render_colormap_series/render_heatmap_series), so the Marker
        card's "Color:" swatch is hidden outright -- showing it would be a
        silently-ignored control, the exact bug class this feature is meant
        to eliminate. Edge color/width, marker shape and size still apply
        and stay visible."""
        kind, obj = self._current_target
        if kind != "series" or not isinstance(obj, DataSeries):
            return False
        return SERIES_TYPE_SPECS[obj.series_type].needs_z_column

    def _is_required_marker_target(self) -> bool:
        """Whether the current target's marker can never be turned off --
        SeriesTypeSpec.marker_mode == "required" (Scatter, Colormap): a
        marker is the ONLY thing either type draws, so the Markers
        section's on/off toggle (meaningful for Line, marker_mode ==
        "optional", which already has a line to fall back on) is hidden
        rather than offered and then ignored."""
        kind, obj = self._current_target
        if kind != "series" or not isinstance(obj, DataSeries):
            return False
        return SERIES_TYPE_SPECS[obj.series_type].marker_mode == "required"

    def set_chart_type(self, chart_type):
        self._chart_type = chart_type
        self._update_target_cards_visibility()

    def _series_y_name(self, series) -> str:
        """Resolve a series' Y column id to its current name for a fallback
        chip label (used only when the series has no explicit label)."""
        from pandaplot.models.project.items.chart import resolve_series_column
        app_state = self.app_context.get_app_state()
        project = app_state.current_project if app_state.has_project else None
        dataset = project.find_item(series.dataset_id) if project else None
        return resolve_series_column(dataset, series.y_column_id, series.y_column) or ""

    def set_series_list(self, data_series, fit_data, selected_index: int = 0):
        """Sync `style_series_chips` with the same series+fit list the Data
        tab's cards are built from, keeping its selection in lockstep with
        `selected_index` (`DataTab.selected_index`) -- unless "Chart" is the
        currently selected target, which is independent of the series/fit
        list and must survive a refresh.

        Values are the combined index (int) for series/fit, or the "chart"
        sentinel, so selecting an entry can drive `set_selected` directly.
        `DataTab.seriesListChanged` is a plain `(data_series, fit_data)`
        two-arg signal, so the panel's connection wraps it to also pass
        `self.data_tab.selected_index` as `selected_index` here.

        The "was Chart explicitly selected" check is based on
        `style_series_chips.currentValue()`, not `self._current_target`:
        `_current_target` gets reflexively reassigned to the
        currently-expanded series/fit on every Data-tab card rebuild
        (emitted regardless of whether the user changed anything, e.g. an
        accordion toggle or theme refresh), so it can't reliably answer "did
        the user deliberately choose Chart". The chip widget's own value only
        changes via a direct chip click or this method's own prior
        conclusion, so it survives those reflexive reassignments.
        """
        self._data_series = list(data_series)
        previous_value = self.style_series_chips.currentValue()
        chip_items = [("Chart", "chart"), ("Axes", "axes")]
        if any(SERIES_TYPE_SPECS[series.series_type].needs_z_column for series in data_series):
            chip_items.append(("Color Map", "colormap_config"))
        for index, series in enumerate(data_series):
            label = series.label or f"{series.dataset_id}:{self._series_y_name(series)}"
            chip_items.append((label, index))
        total_series = len(data_series)
        for fit_offset, fit in enumerate(fit_data):
            index = total_series + fit_offset
            chip_items.append((f"\U0001f527 {fit.label}", index))

        self.style_series_chips.blockSignals(True)
        self.style_series_chips.clear()
        for label, value in chip_items:
            self.style_series_chips.addItem(label, value)
        self.style_series_chips.blockSignals(False)

        # Before any real population has happened, `previous_value` is just
        # the ValueComboBox constructor's placeholder ("chart") -- not a
        # genuine prior user selection -- so it must not be treated as one.
        # `_series_list_initialized` only latches True once this has run for
        # an actual chart with at least one series/fit entry (a call with
        # both empty -- e.g. a theme refresh before any chart is loaded, or a
        # chart with zero series -- has nothing real to remember a selection
        # from, so it must not count as "initialized" either, or it would
        # make the *next* call's placeholder "chart" look like a genuine
        # prior selection).
        chip_values = {value for _, value in chip_items}
        if (self._series_list_initialized
                and previous_value in ("chart", "axes", "colormap_config")
                and previous_value in chip_values):
            self.style_series_chips.setCurrentValue(previous_value)
        else:
            self.style_series_chips.setCurrentValue(selected_index)
        if data_series or fit_data:
            self._series_list_initialized = True

        final_value = self.style_series_chips.currentValue()
        if final_value == "chart":
            self._current_target = ("chart", None)
            self._update_target_cards_visibility()
        elif final_value == "axes":
            self._current_target = ("axes", None)
            self._update_target_cards_visibility()
        elif final_value == "colormap_config":
            self._current_target = ("colormap_config", None)
            self._update_target_cards_visibility()
        elif final_value < len(data_series):
            self.set_selected("series", data_series[final_value])
        else:
            self.set_selected("fit", fit_data[final_value - len(data_series)])

    def set_selected(self, kind: str, obj):
        self._current_target = (kind, obj)
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            if kind == "series":
                self.load_series_style(obj)
            elif kind == "fit":
                self.load_fit_style(obj)
        finally:
            self._updating_controls = previous_guard
        self._update_target_cards_visibility()

    def _on_subtitle_match_title_toggled(self, checked: bool):
        """Handle the 'Match title' toggle for subtitle color: hides the
        subtitle color swatch while matching (mirrors
        _update_marker_controls_enabled's hide-not-disable convention), and
        seeds it with the title's current color on every uncheck."""
        if not checked:
            self.subtitle_color_row.setCurrentColor(self.title_color_row.currentColor())
        self.subtitle_color_row.setVisible(not checked)
        if self._chart is not None:
            self._on_chart_style_field_changed()

    # -- Marker enable/match-line toggles ------------------------------------

    def _on_markers_enabled_toggled(self, _checked: bool):
        """Handle the Markers section's on/off toggle."""
        self._update_marker_controls_enabled()
        self._on_field_changed()

    def _on_marker_match_line_toggled(self, _checked: bool):
        """Handle the 'Match line' toggle for marker color."""
        self._update_marker_controls_enabled()
        self._on_field_changed()

    def _update_marker_controls_enabled(self):
        """Show the marker sub-controls only while markers are enabled;
        hide them (not just grey them out) when disabled, leaving only the
        greyed section title. Same "match line hides colors" sub-behavior
        once markers are on.

        For a scatter-chart series there is no drawn line at all (Line card
        hidden), so "Match line" is meaningless and that row is hidden
        outright whenever markers are on -- UNLESS the target is Z-driven
        (Colormap), whose fill varies per point through the colormap and so
        has its own thing to match (each point's own color via
        edgecolors="face") -- see the relabeling below.

        A required-marker series (Scatter, Colormap) can never turn its
        markers off -- they're the only thing it draws -- so the on/off
        toggle itself is hidden rather than offered and ignored.
        """
        is_scatter_series = self._is_scatter_series_target()
        is_z_driven = self._is_z_driven_series_target()
        required_marker = self._is_required_marker_target()
        markers_enabled = self.markers_enabled_toggle.isChecked() or required_marker
        self.marker_header.setEnabled(markers_enabled)
        self.markers_enabled_toggle.setVisible(not required_marker)

        for widget in (
            self.marker_shape_label, self.marker_shape_control,
            self.marker_size_label, self.marker_size_slider,
            self.marker_edge_width_label, self.marker_edge_width_slider,
        ):
            widget.setVisible(markers_enabled)

        # "Match line" (matching a drawn line's style.color) and "Match
        # point color" (Colormap: matching each point's own data-driven
        # fill) share this one toggle row, relabeled per target. A plain
        # Scatter has neither a line nor a per-point-varying fill to
        # match, so the row stays hidden for it -- its edge color is a
        # simple, always-visible, independently-set swatch.
        show_match_row = markers_enabled and (not is_scatter_series or is_z_driven)
        self.marker_match_line_label.setText("Match point color:" if is_z_driven else "Match line:")
        self.marker_match_line_label.setVisible(show_match_row)
        self.marker_match_line_toggle.setVisible(show_match_row)

        matching = show_match_row and self.marker_match_line_toggle.isChecked()
        show_edge_color = markers_enabled and not matching
        for widget in (self.marker_edge_color_label, self.marker_edge_color_row):
            widget.setVisible(show_edge_color)

        # A Colormap/Heatmap series' marker fill color is always driven by
        # its Z data through the colormap (see render_colormap_series) --
        # style.marker.marker_color is never read for such a series, so its
        # "Color:" row is hidden outright (regardless of the match toggle,
        # which for this target controls edge color instead) rather than
        # shown as a control that silently does nothing.
        show_fill_color = markers_enabled and not is_z_driven
        for widget in (self.marker_color_label, self.marker_color_row):
            widget.setVisible(show_fill_color)

    # -- Color Map controls (Colormap/Heatmap) ------------------------------

    def _on_color_scale_auto_toggled(self, _checked: bool):
        """Handle the Color Map 'Auto scale' toggle."""
        self._update_color_scale_controls()
        self._on_field_changed()

    def _update_color_scale_controls(self):
        """Show the manual Min/Max fields only while 'Auto scale' is off --
        while auto, the color scale is derived from the data's own min/max
        (see chart_heatmap.resolve_color_limits) and the fields have no
        effect (same hidden-not-disabled convention as
        _update_marker_controls_enabled)."""
        show_manual = not self.color_scale_auto_toggle.isChecked()
        self.color_vmin_label.setVisible(show_manual)
        self.color_vmin_spin.setVisible(show_manual)
        self.color_vmax_label.setVisible(show_manual)
        self.color_vmax_spin.setVisible(show_manual)

    def _on_heatmap_gridding_changed(self, _value):
        """Handle the Heatmap 'Gridding' mode change."""
        self._update_colormap_gridding_visibility()
        self._on_field_changed()

    def _update_colormap_gridding_visibility(self):
        """Show the Gridding/Resolution sub-controls only for a series whose
        type supports gridding (SeriesTypeSpec.supports_gridding -- Heatmap
        only; Colormap, a plain color-mapped scatter, needs no gridding at
        all). Resolution is further hidden while gridding mode is "grid"
        (build_heatmap_grid ignores resolution for that mode -- it pivots
        the data's own exact lattice instead of binning/interpolating)."""
        kind, obj = self._current_target
        if kind == "series" and isinstance(obj, DataSeries):
            spec = SERIES_TYPE_SPECS[obj.series_type]
        else:
            spec = None
        supports_gridding = spec is not None and spec.supports_gridding
        self.heatmap_gridding_label.setVisible(supports_gridding)
        self.heatmap_gridding_control.setVisible(supports_gridding)
        show_resolution = supports_gridding and self.heatmap_gridding_control.currentValue() != "grid"
        self.heatmap_resolution_label.setVisible(show_resolution)
        self.heatmap_resolution_spin.setVisible(show_resolution)

    # -- Error-bar match-line toggle ------------------------------------

    def _on_error_match_line_toggled(self, _checked: bool):
        """Handle the Error Bars 'Match line' toggle."""
        self._update_error_controls_visibility()
        self._on_field_changed()

    def _update_error_controls_visibility(self):
        """Hide the error-bar color picker while it matches the line color
        (see _update_marker_controls_enabled for the same convention)."""
        show_color = not self.error_match_line_toggle.isChecked()
        self.error_color_label.setVisible(show_color)
        self.error_color_row.setVisible(show_color)

    # -- Area fill controls ------------------------------------------------

    def _populate_fill_to_options(self, series):
        """Rebuild the 'Fill to' selector: a 'Baseline' entry (value -1) plus
        every other series in the chart (value = its index in data_series), so
        the user can fill the area between this curve and another one. Called
        while `_updating_controls` is set, so the resulting value change won't
        write back through `_on_field_changed`."""
        current_index = None
        for idx, other in enumerate(self._data_series):
            if other is series:
                current_index = idx
                break
        items = [("Baseline", -1)]
        for idx, other in enumerate(self._data_series):
            if idx == current_index:
                continue
            label = other.label or f"Series {idx + 1}"
            items.append((f"↕ {label}", idx))
        self.fill_to_control.blockSignals(True)
        self.fill_to_control.clear()
        for label, value in items:
            self.fill_to_control.addItem(label, value)
        self.fill_to_control.blockSignals(False)

    def _on_fill_enabled_toggled(self, _checked: bool):
        """Handle the Fill section's on/off toggle."""
        self._update_fill_controls_visibility()
        self._on_field_changed()

    def _on_fill_orientation_toggled(self, _checked: bool):
        """Handle the vertical/horizontal fill switch: only the baseline
        label's axis (X vs Y) changes in the UI."""
        self._update_fill_controls_visibility()
        self._on_field_changed()

    def _on_fill_to_changed(self, _value):
        """Handle a change of the 'Fill to' target (baseline vs. other series):
        the baseline value field only applies when filling to the baseline."""
        self._update_fill_controls_visibility()
        self._on_field_changed()

    def _update_band_controls_visibility(self):
        """Show the Confidence Band sub-controls only while the band is
        enabled; hidden, not just greyed, when off (same convention as
        _update_marker_controls_enabled / _update_fill_controls_visibility).
        The color swatch is additionally hidden whenever 'Match line' is
        checked, matching Marker's and Fill's show_color convention."""
        enabled = self.band_enabled_toggle.isChecked()
        self.band_header.setEnabled(enabled)
        show_color = enabled and not self.band_match_line_toggle.isChecked()
        self.band_color_label.setVisible(show_color)
        self.band_color_row.setVisible(show_color)
        self.band_opacity_label.setVisible(enabled)
        self.band_opacity_slider.setVisible(enabled)
        self.band_match_line_label.setVisible(enabled)
        self.band_match_line_toggle.setVisible(enabled)

    def _on_band_match_line_toggled(self, _checked: bool):
        """Handle the Confidence Band 'Match line' toggle: hide the color
        swatch while it's checked (same convention as Marker/Fill)."""
        self._update_band_controls_visibility()
        self._on_field_changed()

    def _on_band_enabled_toggled(self, _checked: bool):
        """Handle the Confidence Band section's on/off toggle."""
        self._update_band_controls_visibility()

    def _on_fill_match_line_toggled(self, _checked: bool):
        """Handle the Fill 'Match line' toggle for fill color."""
        self._update_fill_controls_visibility()
        self._on_field_changed()

    def _update_fill_controls_visibility(self):
        """Show the fill sub-controls only while fill is on -- hidden, not
        just greyed, when off (same convention as
        _update_marker_controls_enabled). While on: hide the color picker
        if it matches the line color, and hide the constant-baseline field
        when filling between two curves instead of to a baseline."""
        enabled = self.fill_enabled_toggle.isChecked()
        self.fill_header.setEnabled(enabled)

        for widget in (
            self.fill_horizontal_label, self.fill_horizontal_toggle,
            self.fill_to_label, self.fill_to_control,
            self.fill_match_line_label, self.fill_match_line_toggle,
        ):
            widget.setVisible(enabled)
        self.fill_opacity_label.setVisible(enabled)
        self.fill_opacity_slider.setVisible(enabled)

        # The baseline is a Y value for a vertical fill, an X value for a
        # horizontal one -- label it so the field's meaning is unambiguous.
        to_baseline = self.fill_to_control.currentValue() == -1
        horizontal = self.fill_horizontal_toggle.isChecked()
        self.fill_base_label.setText("X baseline:" if horizontal else "Y baseline:")
        show_baseline = enabled and to_baseline
        self.fill_base_label.setVisible(show_baseline)
        self.fill_base_spin.setVisible(show_baseline)

        show_color = enabled and not self.fill_match_line_toggle.isChecked()
        self.fill_color_label.setVisible(show_color)
        self.fill_color_row.setVisible(show_color)

    # -- Background transparent toggles ----------------------------------

    def _on_bg_transparent_toggled(self, _checked: bool):
        """Grey out the paired color swatch while its 'Transparent' toggle
        is on; the swatch keeps its last color underneath so re-enabling
        restores it (mirrors _update_marker_controls_enabled's convention)."""
        self.figure_bg_color_row.setEnabled(not self.figure_bg_transparent_toggle.isChecked())
        self.axes_bg_color_row.setEnabled(not self.axes_bg_transparent_toggle.isChecked())
        self._on_chart_style_field_changed()

    # -- Series/fit style: load / apply --------------------------------------

    def _on_field_changed(self):
        if self._updating_controls:
            return
        kind, obj = self._current_target
        if kind == "series":
            self.apply_series_style_to(obj)
        elif kind == "fit":
            self.apply_fit_style_to(obj)
        elif kind == "colormap_config":
            if self._chart is None:
                return
            self.apply_colormap_config_to(self._chart)
        else:
            return
        self.configChanged.emit()

    def apply_series_style_to(self, series):
        style = series.style
        if isinstance(style, VectorSeriesStyle):
            style.vector_color = self.vector_color_row.currentColor()
            style.vector_colormap = self.vector_colormap_control.currentValue()
            style.vector_scale = self.vector_scale_slider.value()
            style.vector_width = self.vector_width_slider.value()
            style.vector_head_width = self.vector_head_width_slider.value()
            style.vector_head_length = self.vector_head_length_slider.value()
            style.vector_head_axis_length = self.vector_head_axis_length_slider.value()
            return

        if isinstance(style, (ColormapSeriesStyle, HeatmapSeriesStyle)):
            if isinstance(style, HeatmapSeriesStyle):
                style.heatmap_gridding = self.heatmap_gridding_control.currentValue()
                style.heatmap_resolution = self.heatmap_resolution_spin.value()
                return
            # ColormapSeriesStyle only: it has no color/line/fill fields of
            # its own (fill color comes from z_data via colormap, not a
            # fixed style.color), but its marker shape/size/edge fields
            # still apply (marker_mode == "required") -- fall through
            # (skipping the style.color/line_style/fill writes above, which
            # this class doesn't declare) to the shared marker-writing block
            # below instead of returning.
            series.alpha = self.line_opacity_slider.value()
        else:
            style.color = self.line_color_row.currentColor()
            if isinstance(style, LineSeriesStyle):
                style.line_style = self.line_style_control.currentValue().value
                style.line_width = self.line_width_slider.value()
            series.alpha = self.line_opacity_slider.value()

        # "Markers enabled" isn't a separate persisted flag: it maps onto
        # MarkerType.NONE -- except for a required-marker target (Scatter,
        # Colormap), which can never write NONE regardless of the (hidden)
        # toggle's stored state. "Match line"/"Match point color" reuses the
        # "" == inherit convention for marker_color/marker_edge_color
        # (rendering falls back to style.color when empty -- see
        # series_renderers/line.py and scatter.py; render_colormap_series
        # falls back to matplotlib's "face" sentinel for marker_edge_color
        # instead, and never reads marker_color, since fill color always
        # comes from z_data there).
        if isinstance(style, (LineSeriesStyle, ScatterSeriesStyle, ColormapSeriesStyle)):
            if self.markers_enabled_toggle.isChecked() or self._is_required_marker_target():
                style.marker.marker_style = self.marker_shape_control.currentValue().value
                style.marker.marker_size = self.marker_size_slider.value()
                style.marker.marker_edge_width = self.marker_edge_width_slider.value()
                if self._is_z_driven_series_target():
                    # Colormap: the toggle controls edge color only -- fill
                    # is never read from marker_color for this target, so
                    # leave it untouched rather than overwrite it with the
                    # (hidden) fill-color row's stale current value.
                    matching = self.marker_match_line_toggle.isChecked()
                    style.marker.marker_edge_color = "" if matching else self.marker_edge_color_row.currentColor()
                else:
                    match_line = self.marker_match_line_toggle.isChecked() and not self._is_scatter_series_target()
                    style.marker.marker_color = "" if match_line else self.marker_color_row.currentColor()
                    style.marker.marker_edge_color = "" if match_line else self.marker_edge_color_row.currentColor()
            else:
                style.marker.marker_style = MarkerType.NONE.value

        # Error-bar fields now live on style.error_bars, which only
        # LineSeriesStyle/ScatterSeriesStyle/BarSeriesStyle declare --
        # HistSeriesStyle/VectorSeriesStyle have no such field, so this must
        # be gated (the Error Bars card itself is only shown for a series
        # whose spec supports error bars, but that visibility rule doesn't
        # protect this direct write).
        error_bars = getattr(style, "error_bars", None)
        if error_bars is not None:
            error_bars.error_direction = self.error_direction_control.currentValue()
            error_bars.error_color = (
                "" if self.error_match_line_toggle.isChecked()
                else self.error_color_row.currentColor()
            )
            error_bars.error_cap_size = self.error_cap_size_slider.value()

        # Area fill. "Match line" reuses the "" == inherit-style.color
        # convention. fill_to_index is -1 (fill down to the constant baseline)
        # or the index of another series to fill between. Only
        # LineSeriesStyle declares fill fields.
        if isinstance(style, LineSeriesStyle):
            style.fill_enabled = self.fill_enabled_toggle.isChecked()
            style.fill_orientation = (
                "horizontal" if self.fill_horizontal_toggle.isChecked() else "vertical"
            )
            style.fill_to_index = self.fill_to_control.currentValue()
            style.fill_base = self.fill_base_spin.value()
            style.fill_color = (
                "" if self.fill_match_line_toggle.isChecked()
                else self.fill_color_row.currentColor()
            )
            style.fill_alpha = self.fill_opacity_slider.value()

    def apply_fit_style_to(self, fit):
        style = fit.style
        style.color = self.line_color_row.currentColor()
        style.line_style = self.line_style_control.currentValue().value
        style.line_width = self.line_width_slider.value()
        style.alpha = self.line_opacity_slider.value()
        style.band_fill_enabled = self.band_enabled_toggle.isChecked()
        style.band_color = (
            "" if self.band_match_line_toggle.isChecked()
            else self.band_color_row.currentColor()
        )
        style.band_fill_alpha = self.band_opacity_slider.value()
        # Note: fit data doesn't use marker_size or marker colors.

    def load_series_style(self, series):
        """Populate the Line/Marker/Fill/Vector cards from a data series'
        typed style object. Reads use getattr(..., default) throughout --
        safe regardless of which of the 5 typed style classes `series.style`
        actually is, since a hidden card's controls still get *some* value
        (never shown, never applied back unless that card becomes visible
        for a different series/chart-type selection)."""
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            style = series.style

            self.vector_color_row.setCurrentColor(getattr(style, "vector_color", "#1f77b4"))
            self.vector_colormap_control.setCurrentValue(getattr(style, "vector_colormap", ""))
            self.vector_scale_slider.setValue(getattr(style, "vector_scale", 0.0))
            self.vector_width_slider.setValue(getattr(style, "vector_width", 0.005))
            self.vector_head_width_slider.setValue(getattr(style, "vector_head_width", 3.0))
            self.vector_head_length_slider.setValue(getattr(style, "vector_head_length", 5.0))
            self.vector_head_axis_length_slider.setValue(getattr(style, "vector_head_axis_length", 4.5))

            # Heatmap-only gridding fields (colormap/colorbar/scale moved to
            # the chart-level Color Map card -- see load_colormap_config).
            self.heatmap_gridding_control.setCurrentValue(getattr(style, "heatmap_gridding", "grid"))
            self.heatmap_resolution_spin.setValue(getattr(style, "heatmap_resolution", 50))
            self._update_colormap_gridding_visibility()

            color = getattr(style, "color", "#1f77b4")
            self.line_color_row.setCurrentColor(color)
            self.line_width_slider.setValue(getattr(style, "line_width", 2.0))
            self.line_opacity_slider.setValue(series.alpha)
            try:
                self.line_style_control.setCurrentValue(LineStyleType(getattr(style, "line_style", "solid")))
            except ValueError:
                self.line_style_control.setCurrentValue(LineStyleType.SOLID)

            # "Markers enabled" isn't a separate persisted flag: it's implied
            # by marker_style != MarkerType.NONE. If markers are off, the
            # shape control keeps showing the last remembered shape
            # (defaulting to circle) rather than "none", since "none" isn't
            # offered as a selectable shape here.
            marker = getattr(style, "marker", None)
            marker_style_value = getattr(marker, "marker_style", MarkerType.NONE.value)
            markers_enabled = marker_style_value != MarkerType.NONE.value
            self.markers_enabled_toggle.blockSignals(True)
            self.markers_enabled_toggle.setChecked(markers_enabled)
            self.markers_enabled_toggle.blockSignals(False)

            shape_value = marker_style_value if markers_enabled else MarkerType.CIRCLE.value
            try:
                self.marker_shape_control.setCurrentValue(MarkerType(shape_value))
            except ValueError:
                self.marker_shape_control.setCurrentValue(MarkerType.CIRCLE)

            self.marker_size_slider.setValue(getattr(marker, "marker_size", 2.0))

            # marker_color == "" is the existing "match line color"
            # convention, now shared by marker_edge_color too. For a
            # Z-driven (Colormap) target the toggle instead reflects
            # marker_edge_color -- that's the only field it controls there
            # (marker_color is unused, hidden outright; see
            # _update_marker_controls_enabled) -- computed from
            # series.series_type directly (not self._is_z_driven_series_
            # target(), which reads self._current_target and so would be
            # stale if this method is ever called without going through
            # set_selected first, e.g. a direct load in a test).
            is_z_driven = SERIES_TYPE_SPECS[series.series_type].needs_z_column
            marker_color = getattr(marker, "marker_color", "")
            marker_edge_color = getattr(marker, "marker_edge_color", "")
            self.marker_color_row.setCurrentColor(marker_color or color)
            self.marker_edge_color_row.setCurrentColor(marker_edge_color or color)
            self.marker_match_line_toggle.blockSignals(True)
            self.marker_match_line_toggle.setChecked(
                marker_edge_color == "" if is_z_driven else marker_color == ""
            )
            self.marker_match_line_toggle.blockSignals(False)
            self.marker_edge_width_slider.setValue(getattr(marker, "marker_edge_width", 1.0))

            self._update_marker_controls_enabled()

            # Error-bar fields now live on style.error_bars; not every style
            # class declares one (Hist/Vector don't), so read defensively.
            error_bars = getattr(style, "error_bars", None)
            try:
                self.error_direction_control.setCurrentValue(
                    ErrorDirection(getattr(error_bars, "error_direction", ErrorDirection.BOTH))
                )
            except ValueError:
                self.error_direction_control.setCurrentValue(ErrorDirection.BOTH)
            error_color = getattr(error_bars, "error_color", "")
            self.error_color_row.setCurrentColor(error_color or color)
            self.error_match_line_toggle.blockSignals(True)
            self.error_match_line_toggle.setChecked(error_color == "")
            self.error_match_line_toggle.blockSignals(False)
            self._update_error_controls_visibility()
            self.error_cap_size_slider.setValue(getattr(error_bars, "error_cap_size", 3.0))

            self._populate_fill_to_options(series)
            self.fill_enabled_toggle.blockSignals(True)
            self.fill_enabled_toggle.setChecked(getattr(style, "fill_enabled", False))
            self.fill_enabled_toggle.blockSignals(False)
            self.fill_horizontal_toggle.blockSignals(True)
            self.fill_horizontal_toggle.setChecked(getattr(style, "fill_orientation", "vertical") == "horizontal")
            self.fill_horizontal_toggle.blockSignals(False)
            self.fill_to_control.setCurrentValue(getattr(style, "fill_to_index", -1))
            self.fill_base_spin.setValue(getattr(style, "fill_base", 0.0))
            fill_color = getattr(style, "fill_color", "")
            self.fill_color_row.setCurrentColor(fill_color or color)
            self.fill_match_line_toggle.blockSignals(True)
            self.fill_match_line_toggle.setChecked(fill_color == "")
            self.fill_match_line_toggle.blockSignals(False)
            self.fill_opacity_slider.setValue(getattr(style, "fill_alpha", 0.3))
            self._update_fill_controls_visibility()
        finally:
            self._updating_controls = previous_guard

    def load_fit_style(self, fit):
        """Populate the Line/Band/Marker cards from a fit-data entry's
        typed style object. Fit data has no marker concept, so markers are
        forced off and locked; opacity applies to the fit line itself,
        band_fill_alpha to the confidence band separately."""
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            style = fit.style
            self.line_color_row.setCurrentColor(style.color)
            self.line_width_slider.setValue(style.line_width)
            self.line_opacity_slider.setValue(style.alpha)
            try:
                self.line_style_control.setCurrentValue(LineStyleType(style.line_style))
            except ValueError:
                self.line_style_control.setCurrentValue(LineStyleType.SOLID)

            self.band_enabled_toggle.setChecked(style.band_fill_enabled)
            self.band_color_row.setCurrentColor(style.band_color or style.color)
            self.band_match_line_toggle.blockSignals(True)
            self.band_match_line_toggle.setChecked(style.band_color == "")
            self.band_match_line_toggle.blockSignals(False)
            self.band_opacity_slider.setValue(style.band_fill_alpha)
            self._update_band_controls_visibility()

            self.markers_enabled_toggle.blockSignals(True)
            self.markers_enabled_toggle.setChecked(False)
            self.markers_enabled_toggle.blockSignals(False)
            self.marker_size_slider.setValue(0.0)  # Fit lines typically don't have markers
            self._update_marker_controls_enabled()
        finally:
            self._updating_controls = previous_guard

    # -- Chart-style card: load / apply / clear ------------------------------

    def load_chart_style(self, chart):
        self._chart = chart
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.load_colormap_config(chart)
            self.title_font_size_spin.setValue(chart.config.get("title_font_size", 14))
            self.subtitle_font_size_spin.setValue(chart.config.get("subtitle_font_size", 12))
            self.title_font_family_combo.setCurrentValue(chart.config.get("title_font_family", "DejaVu Sans"))
            self.subtitle_font_family_combo.setCurrentValue(
                chart.config.get("subtitle_font_family", "DejaVu Sans")
            )
            self.chart_padding_spin.setValue(chart.config.get("chart_padding", 2.0))
            self.chart_padding_w_spin.setValue(chart.config.get("chart_padding_w", 2.0))
            self.chart_padding_h_spin.setValue(chart.config.get("chart_padding_h", 2.0))
            self.title_padding_spin.setValue(chart.config.get("title_padding", 6.0))
            self.main_title_padding_spin.setValue(chart.config.get("main_title_padding", 10.0))
            self.top_margin_spin.setValue(chart.config.get("top_margin", 1.0))
            self.title_bold_check.setChecked(chart.config.get("title_bold", True))
            self.title_italic_check.setChecked(chart.config.get("title_italic", False))
            self.subtitle_bold_check.setChecked(chart.config.get("subtitle_bold", False))
            self.subtitle_italic_check.setChecked(chart.config.get("subtitle_italic", False))
            self.title_color_row.setCurrentColor(chart.config.get("title_color", "#000000"))
            match_title = chart.config.get("subtitle_match_title_color", True)
            self.subtitle_match_title_toggle.setChecked(match_title)
            self.subtitle_color_row.setCurrentColor(
                chart.config.get("title_color", "#000000") if match_title
                else chart.config.get("subtitle_color", "#000000")
            )
            self.subtitle_color_row.setVisible(not match_title)

            fig_bg = chart.style.get("figure_background_color", "#ffffff")
            self.figure_bg_transparent_toggle.setChecked(fig_bg is None)
            self.figure_bg_color_row.setCurrentColor(fig_bg or "#ffffff")
            self.figure_bg_color_row.setEnabled(fig_bg is not None)

            axes_bg = chart.style.get("axes_background_color", "#ffffff")
            self.axes_bg_transparent_toggle.setChecked(axes_bg is None)
            self.axes_bg_color_row.setCurrentColor(axes_bg or "#ffffff")
            self.axes_bg_color_row.setEnabled(axes_bg is not None)

            # QComboBox.findData() is unreliable for tuple-valued itemData
            # (Qt's QVariant comparison doesn't match Python tuple equality
            # here), so look up the matching index manually.
            target_size = (chart.config.get("width_cm"), chart.config.get("height_cm"))
            size_index = -1
            for i in range(self.chart_size_combo.count()):
                if self.chart_size_combo.itemData(i) == target_size:
                    size_index = i
                    break

            self._custom_size_prefilled = False
            if size_index >= 0:
                self.chart_size_combo.setCurrentIndex(size_index)
            elif target_size[0] is not None and target_size[1] is not None:
                self.chart_size_combo.setCurrentIndex(self.chart_size_combo.findData("custom"))
                self.chart_width_spin.setValue(target_size[0])
                self.chart_height_spin.setValue(target_size[1])
                self._custom_size_prefilled = True
            else:
                self.chart_size_combo.setCurrentIndex(self.chart_size_combo.count() - 1)

            self._custom_dpi_prefilled = False
            dpi_value = chart.config.get("dpi")
            dpi_index = self.chart_dpi_combo.findData(dpi_value)
            if dpi_index >= 0:
                self.chart_dpi_combo.setCurrentIndex(dpi_index)
            elif dpi_value is not None:
                self.chart_dpi_combo.setCurrentIndex(self.chart_dpi_combo.findData("custom"))
                self.chart_dpi_spin.setValue(dpi_value)
                self._custom_dpi_prefilled = True
            else:
                self.chart_dpi_combo.setCurrentIndex(self.chart_dpi_combo.count() - 1)

            for prefix in ("x", "y", "y2"):
                axis_form = self.axes_style_forms[prefix]
                axis_form["font_size_spin"].setValue(chart.config.get(f"{prefix}_font_size", 12))
                axis_form["font_family_combo"].setCurrentValue(chart.config.get(f"{prefix}_font_family", "DejaVu Sans"))
                axis_form["bold_check"].setChecked(chart.config.get(f"{prefix}_title_bold", False))
                axis_form["italic_check"].setChecked(chart.config.get(f"{prefix}_title_italic", False))
                match = True
                if axis_form["match_x_toggle"] is not None:
                    match = chart.config.get(f"{prefix}_match_x_label_color", True)
                    axis_form["match_x_toggle"].setChecked(match)
                axis_form["color_row"].setCurrentColor(chart.config.get(f"{prefix}_label_color", "#000000"))
                if axis_form["match_x_toggle"] is not None:
                    axis_form["color_label"].setVisible(not match)
                    axis_form["color_row"].setVisible(not match)
                default_rotation = 90 if prefix in ("y", "y2") else 0
                axis_form["rotation_spin"].setValue(chart.config.get(f"{prefix}_label_rotation", default_rotation))

                axis_form["tick_font_size_spin"].setValue(chart.config.get(f"{prefix}_tick_label_font_size", 10))
                axis_form["tick_font_family_combo"].setCurrentValue(
                    chart.config.get(f"{prefix}_tick_label_font_family", "DejaVu Sans"))
                axis_form["tick_bold_check"].setChecked(chart.config.get(f"{prefix}_tick_label_bold", False))
                axis_form["tick_italic_check"].setChecked(chart.config.get(f"{prefix}_tick_label_italic", False))
                axis_form["tick_color_row"].setCurrentColor(chart.config.get(f"{prefix}_tick_label_color", "#000000"))
                axis_form["tick_rotation_spin"].setValue(chart.config.get(f"{prefix}_tick_label_rotation", 0))
                match_colors = True
                if axis_form["match_x_colors_toggle"] is not None:
                    match_colors = chart.config.get(f"{prefix}_match_x_colors", True)
                    axis_form["match_x_colors_toggle"].setChecked(match_colors)
                axis_form["spine_color_row"].setCurrentColor(chart.config.get(f"{prefix}_spine_color", "#000000"))
                axis_form["major_tick_color_row"].setCurrentColor(
                    chart.config.get(f"{prefix}_major_tick_color", "#000000"))
                axis_form["minor_tick_color_row"].setCurrentColor(
                    chart.config.get(f"{prefix}_minor_tick_color", "#000000"))
                if axis_form["match_x_colors_toggle"] is not None:
                    for widget_key in ("spine_color_row", "major_tick_color_row", "tick_color_row",
                                       "minor_tick_color_row"):
                        axis_form[widget_key].setVisible(not match_colors)
                    axis_form["minor_tick_color_label"].setVisible(not match_colors)
            self.refresh_axis_style_selector(chart)
            self._show_axis_style_form(self.axes_style_selector.currentValue() or "x")
        finally:
            self._updating_controls = previous_guard

    def apply_chart_style_to(self, chart):
        chart.config["title_font_size"] = self.title_font_size_spin.value()
        chart.config["subtitle_font_size"] = self.subtitle_font_size_spin.value()
        chart.config["title_font_family"] = self.title_font_family_combo.currentValue()
        chart.config["subtitle_font_family"] = self.subtitle_font_family_combo.currentValue()
        chart.config["chart_padding"] = self.chart_padding_spin.value()
        chart.config["chart_padding_w"] = self.chart_padding_w_spin.value()
        chart.config["chart_padding_h"] = self.chart_padding_h_spin.value()
        chart.config["title_padding"] = self.title_padding_spin.value()
        chart.config["main_title_padding"] = self.main_title_padding_spin.value()
        chart.config["top_margin"] = self.top_margin_spin.value()
        chart.config["title_bold"] = self.title_bold_check.isChecked()
        chart.config["title_italic"] = self.title_italic_check.isChecked()
        chart.config["subtitle_bold"] = self.subtitle_bold_check.isChecked()
        chart.config["subtitle_italic"] = self.subtitle_italic_check.isChecked()
        chart.config["title_color"] = self.title_color_row.currentColor()
        chart.config["subtitle_match_title_color"] = self.subtitle_match_title_toggle.isChecked()
        chart.config["subtitle_color"] = self.subtitle_color_row.currentColor()
        chart.style["figure_background_color"] = (
            None if self.figure_bg_transparent_toggle.isChecked()
            else self.figure_bg_color_row.currentColor()
        )
        chart.style["axes_background_color"] = (
            None if self.axes_bg_transparent_toggle.isChecked()
            else self.axes_bg_color_row.currentColor()
        )
        chart.config["width_cm"], chart.config["height_cm"] = self._size_from_controls()
        chart.config["dpi"] = self._dpi_from_controls()

        for prefix in ("x", "y", "y2"):
            axis_form = self.axes_style_forms[prefix]
            chart.config[f"{prefix}_font_size"] = axis_form["font_size_spin"].value()
            chart.config[f"{prefix}_font_family"] = axis_form["font_family_combo"].currentValue()
            chart.config[f"{prefix}_title_bold"] = axis_form["bold_check"].isChecked()
            chart.config[f"{prefix}_title_italic"] = axis_form["italic_check"].isChecked()
            chart.config[f"{prefix}_label_color"] = axis_form["color_row"].currentColor()
            if axis_form["match_x_toggle"] is not None:
                chart.config[f"{prefix}_match_x_label_color"] = axis_form["match_x_toggle"].isChecked()
            chart.config[f"{prefix}_label_rotation"] = axis_form["rotation_spin"].value()
            chart.config[f"{prefix}_tick_label_font_size"] = axis_form["tick_font_size_spin"].value()
            chart.config[f"{prefix}_tick_label_font_family"] = axis_form["tick_font_family_combo"].currentValue()
            chart.config[f"{prefix}_tick_label_bold"] = axis_form["tick_bold_check"].isChecked()
            chart.config[f"{prefix}_tick_label_italic"] = axis_form["tick_italic_check"].isChecked()
            chart.config[f"{prefix}_tick_label_color"] = axis_form["tick_color_row"].currentColor()
            chart.config[f"{prefix}_tick_label_rotation"] = axis_form["tick_rotation_spin"].value()
            chart.config[f"{prefix}_spine_color"] = axis_form["spine_color_row"].currentColor()
            chart.config[f"{prefix}_major_tick_color"] = axis_form["major_tick_color_row"].currentColor()
            chart.config[f"{prefix}_minor_tick_color"] = axis_form["minor_tick_color_row"].currentColor()
            if axis_form["match_x_colors_toggle"] is not None:
                chart.config[f"{prefix}_match_x_colors"] = axis_form["match_x_colors_toggle"].isChecked()

    def clear_chart_style(self):
        self._chart = None
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.clear_colormap_config()
            self.title_font_size_spin.setValue(14)
            self.subtitle_font_size_spin.setValue(12)
            self.title_font_family_combo.setCurrentValue("DejaVu Sans")
            self.subtitle_font_family_combo.setCurrentValue("DejaVu Sans")
            self.chart_padding_spin.setValue(2.0)
            self.chart_padding_w_spin.setValue(2.0)
            self.chart_padding_h_spin.setValue(2.0)
            self.title_padding_spin.setValue(6.0)
            self.main_title_padding_spin.setValue(10.0)
            self.top_margin_spin.setValue(1.0)
            self.title_bold_check.setChecked(True)
            self.title_italic_check.setChecked(False)
            self.subtitle_bold_check.setChecked(False)
            self.subtitle_italic_check.setChecked(False)
            self.title_color_row.setCurrentColor("#000000")
            self.subtitle_match_title_toggle.setChecked(True)
            self.subtitle_color_row.setCurrentColor("#000000")
            self.subtitle_color_row.setVisible(False)
            self.figure_bg_transparent_toggle.setChecked(False)
            self.figure_bg_color_row.setCurrentColor("#ffffff")
            self.figure_bg_color_row.setEnabled(True)
            self.axes_bg_transparent_toggle.setChecked(False)
            self.axes_bg_color_row.setCurrentColor("#ffffff")
            self.axes_bg_color_row.setEnabled(True)
            self.chart_size_combo.setCurrentIndex(self.chart_size_combo.count() - 1)
            self.chart_width_spin.setValue(20.0)
            self.chart_height_spin.setValue(15.0)
            self._custom_size_prefilled = False
            self.chart_dpi_combo.setCurrentIndex(self.chart_dpi_combo.count() - 1)
            self.chart_dpi_spin.setValue(100)
            self._custom_dpi_prefilled = False

            for prefix in ("x", "y", "y2"):
                axis_form = self.axes_style_forms[prefix]
                axis_form["font_size_spin"].setValue(12)
                axis_form["font_family_combo"].setCurrentValue("DejaVu Sans")
                axis_form["bold_check"].setChecked(False)
                axis_form["italic_check"].setChecked(False)
                axis_form["color_row"].setCurrentColor("#000000")
                if axis_form["match_x_toggle"] is not None:
                    axis_form["match_x_toggle"].setChecked(True)
                axis_form["rotation_spin"].setValue(90 if prefix in ("y", "y2") else 0)
                axis_form["tick_font_size_spin"].setValue(10)
                axis_form["tick_font_family_combo"].setCurrentValue("DejaVu Sans")
                axis_form["tick_bold_check"].setChecked(False)
                axis_form["tick_italic_check"].setChecked(False)
                axis_form["tick_color_row"].setCurrentColor("#000000")
                axis_form["tick_rotation_spin"].setValue(0)
                axis_form["spine_color_row"].setCurrentColor("#000000")
                axis_form["major_tick_color_row"].setCurrentColor("#000000")
                axis_form["minor_tick_color_row"].setCurrentColor("#000000")
                if axis_form["match_x_colors_toggle"] is not None:
                    axis_form["match_x_colors_toggle"].setChecked(True)
            self.refresh_axis_style_selector(None)
        finally:
            self._updating_controls = previous_guard

    # -- Color Map config (chart-level) --------------------------------------

    def load_colormap_config(self, chart):
        """Populate the chart-level Color Map card from `chart.config`.
        Called from load_chart_style's call site (chart_properties_panel.py)
        so it's always populated regardless of which chip is currently
        selected, matching how Chart-card fields are loaded unconditionally
        too."""
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.colormap_control.setCurrentValue(chart.config.get("colormap", "viridis"))
            self.colorbar_show_toggle.blockSignals(True)
            self.colorbar_show_toggle.setChecked(chart.config.get("colorbar_show", True))
            self.colorbar_show_toggle.blockSignals(False)
            self.colorbar_label_edit.blockSignals(True)
            self.colorbar_label_edit.setText(chart.config.get("colorbar_label", ""))
            self.colorbar_label_edit.blockSignals(False)
            self.color_scale_auto_toggle.blockSignals(True)
            self.color_scale_auto_toggle.setChecked(chart.config.get("color_scale_auto", True))
            self.color_scale_auto_toggle.blockSignals(False)
            self.color_vmin_spin.setValue(chart.config.get("color_vmin", 0.0))
            self.color_vmax_spin.setValue(chart.config.get("color_vmax", 1.0))
            self._update_color_scale_controls()
        finally:
            self._updating_controls = previous_guard

    def apply_colormap_config_to(self, chart):
        chart.config["colormap"] = self.colormap_control.currentValue()
        chart.config["colorbar_show"] = self.colorbar_show_toggle.isChecked()
        chart.config["colorbar_label"] = self.colorbar_label_edit.text()
        chart.config["color_scale_auto"] = self.color_scale_auto_toggle.isChecked()
        chart.config["color_vmin"] = self.color_vmin_spin.value()
        chart.config["color_vmax"] = self.color_vmax_spin.value()

    def clear_colormap_config(self):
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            self.colormap_control.setCurrentValue("viridis")
            self.colorbar_show_toggle.setChecked(True)
            self.colorbar_label_edit.setText("")
            self.color_scale_auto_toggle.setChecked(True)
            self.color_vmin_spin.setValue(0.0)
            self.color_vmax_spin.setValue(1.0)
            self._update_color_scale_controls()
        finally:
            self._updating_controls = previous_guard

    # -- Chart size/dpi combo helpers -----------------------------------------

    def _app_chart_display_defaults(self):
        """Read the app-wide default chart width/height/dpi from Settings."""
        cfg_manager = self.app_context.get_manager(ConfigManager)
        display_cfg = getattr(getattr(cfg_manager, "config", None), "chart_display", None)
        default_width = getattr(display_cfg, "default_width_cm", 20.0) if display_cfg else 20.0
        default_height = getattr(display_cfg, "default_height_cm", 15.0) if display_cfg else 15.0
        default_dpi = getattr(display_cfg, "dpi", 100) if display_cfg else 100
        return default_width, default_height, default_dpi

    def _effective_chart_size_dpi(self):
        """Resolve the chart's current effective (width_cm, height_cm, dpi),
        preferring the chart's own saved values and falling back to the
        app-wide Settings defaults. Used to pre-fill the Custom fields the
        first time the user selects Custom for Size or DPI."""
        default_width, default_height, default_dpi = self._app_chart_display_defaults()
        if not self._chart:
            return default_width, default_height, default_dpi
        # Deferred import: chart_editor.py pulls in matplotlib, which must
        # stay lazy at app startup (see tests/test_startup_imports.py).
        from pandaplot.gui.components.tabs.chart.chart_editor import resolve_chart_size

        return resolve_chart_size(
            self._chart.config.get("width_cm"),
            self._chart.config.get("height_cm"),
            self._chart.config.get("dpi"),
            default_width, default_height, default_dpi,
        )

    def _size_from_controls(self):
        """Resolve (width_cm, height_cm) from chart_size_combo, reading the
        dedicated Custom spin boxes when that sentinel is selected."""
        data = self.chart_size_combo.currentData()
        if data == "custom":
            return self.chart_width_spin.value(), self.chart_height_spin.value()
        if data is None:
            return None, None
        return data

    def _dpi_from_controls(self):
        """Resolve dpi from chart_dpi_combo, reading the dedicated Custom
        spin box when that sentinel is selected."""
        data = self.chart_dpi_combo.currentData()
        if data == "custom":
            return self.chart_dpi_spin.value()
        return data

    def _on_chart_size_combo_changed(self):
        """Show/hide the Custom width/height row and pre-fill it the first
        time the user manually selects Custom for this loaded chart."""
        is_custom = self.chart_size_combo.currentData() == "custom"
        self.custom_size_row.setVisible(is_custom)
        if is_custom and not self._updating_controls and not self._custom_size_prefilled:
            width, height, _ = self._effective_chart_size_dpi()
            self.chart_width_spin.setValue(width)
            self.chart_height_spin.setValue(height)
            self._custom_size_prefilled = True
        self._on_chart_style_field_changed()

    def _on_chart_dpi_combo_changed(self):
        """Show/hide the Custom DPI row and pre-fill it the first time the
        user manually selects Custom for this loaded chart."""
        is_custom = self.chart_dpi_combo.currentData() == "custom"
        self.custom_dpi_row.setVisible(is_custom)
        if is_custom and not self._updating_controls and not self._custom_dpi_prefilled:
            _, _, dpi = self._effective_chart_size_dpi()
            self.chart_dpi_spin.setValue(dpi)
            self._custom_dpi_prefilled = True
        self._on_chart_style_field_changed()

    def _on_chart_style_field_changed(self):
        if self._chart is None or self._updating_controls:
            return
        config = self._chart.config
        config["title_font_size"] = self.title_font_size_spin.value()
        config["subtitle_font_size"] = self.subtitle_font_size_spin.value()
        config["title_font_family"] = self.title_font_family_combo.currentValue()
        config["subtitle_font_family"] = self.subtitle_font_family_combo.currentValue()
        config["chart_padding"] = self.chart_padding_spin.value()
        config["chart_padding_w"] = self.chart_padding_w_spin.value()
        config["chart_padding_h"] = self.chart_padding_h_spin.value()
        config["title_padding"] = self.title_padding_spin.value()
        config["main_title_padding"] = self.main_title_padding_spin.value()
        config["top_margin"] = self.top_margin_spin.value()
        config["title_bold"] = self.title_bold_check.isChecked()
        config["title_italic"] = self.title_italic_check.isChecked()
        config["subtitle_bold"] = self.subtitle_bold_check.isChecked()
        config["subtitle_italic"] = self.subtitle_italic_check.isChecked()
        config["title_color"] = self.title_color_row.currentColor()
        config["subtitle_match_title_color"] = self.subtitle_match_title_toggle.isChecked()
        config["subtitle_color"] = self.subtitle_color_row.currentColor()
        self._chart.style["figure_background_color"] = (
            None if self.figure_bg_transparent_toggle.isChecked()
            else self.figure_bg_color_row.currentColor()
        )
        self._chart.style["axes_background_color"] = (
            None if self.axes_bg_transparent_toggle.isChecked()
            else self.axes_bg_color_row.currentColor()
        )
        config["width_cm"], config["height_cm"] = self._size_from_controls()
        config["dpi"] = self._dpi_from_controls()

        for prefix in ("x", "y", "y2"):
            axis_form = self.axes_style_forms[prefix]
            config[f"{prefix}_font_size"] = axis_form["font_size_spin"].value()
            config[f"{prefix}_font_family"] = axis_form["font_family_combo"].currentValue()
            config[f"{prefix}_title_bold"] = axis_form["bold_check"].isChecked()
            config[f"{prefix}_title_italic"] = axis_form["italic_check"].isChecked()
            config[f"{prefix}_label_color"] = axis_form["color_row"].currentColor()
            if axis_form["match_x_toggle"] is not None:
                config[f"{prefix}_match_x_label_color"] = axis_form["match_x_toggle"].isChecked()
            config[f"{prefix}_label_rotation"] = axis_form["rotation_spin"].value()
            config[f"{prefix}_tick_label_font_size"] = axis_form["tick_font_size_spin"].value()
            config[f"{prefix}_tick_label_font_family"] = axis_form["tick_font_family_combo"].currentValue()
            config[f"{prefix}_tick_label_bold"] = axis_form["tick_bold_check"].isChecked()
            config[f"{prefix}_tick_label_italic"] = axis_form["tick_italic_check"].isChecked()
            config[f"{prefix}_tick_label_color"] = axis_form["tick_color_row"].currentColor()
            config[f"{prefix}_tick_label_rotation"] = axis_form["tick_rotation_spin"].value()
            config[f"{prefix}_spine_color"] = axis_form["spine_color_row"].currentColor()
            config[f"{prefix}_major_tick_color"] = axis_form["major_tick_color_row"].currentColor()
            config[f"{prefix}_minor_tick_color"] = axis_form["minor_tick_color_row"].currentColor()
            if axis_form["match_x_colors_toggle"] is not None:
                config[f"{prefix}_match_x_colors"] = axis_form["match_x_colors_toggle"].isChecked()
        self.configChanged.emit()

    # -- Theme ----------------------------------------------------------------

    def apply_theme(self, tokens: dict):
        self.title_color_row.set_tokens(tokens)
        self.subtitle_color_row.set_tokens(tokens)
        self.subtitle_match_title_toggle.set_tokens(tokens)
        self.style_series_chips.set_tokens(tokens)
        self.line_color_row.set_tokens(tokens)
        self.line_style_control.set_tokens(tokens)
        for _index in range(self.line_style_control.count()):
            _style = self.line_style_control.itemData(_index)
            self.line_style_control.setItemIcon(_index, build_line_style_icon(_style, tokens))
        self.line_width_slider.set_tokens(tokens)
        self.line_opacity_slider.set_tokens(tokens)
        self.markers_enabled_toggle.set_tokens(tokens)
        self.marker_shape_control.set_tokens(tokens)
        self.marker_size_slider.set_tokens(tokens)
        self.marker_color_row.set_tokens(tokens)
        self.marker_match_line_toggle.set_tokens(tokens)
        self.marker_edge_color_row.set_tokens(tokens)
        self.marker_edge_width_slider.set_tokens(tokens)
        self.error_direction_control.set_tokens(tokens)
        self.error_color_row.set_tokens(tokens)
        self.error_match_line_toggle.set_tokens(tokens)
        self.error_cap_size_slider.set_tokens(tokens)
        self.vector_card.set_tokens(tokens)
        self.vector_color_row.set_tokens(tokens)
        self.vector_colormap_control.set_tokens(tokens)
        self.vector_scale_slider.set_tokens(tokens)
        self.vector_width_slider.set_tokens(tokens)
        self.vector_head_width_slider.set_tokens(tokens)
        self.vector_head_length_slider.set_tokens(tokens)
        self.vector_head_axis_length_slider.set_tokens(tokens)
        self.heatmap_gridding_card.set_tokens(tokens)
        self.colormap_config_card.set_tokens(tokens)
        self.colormap_control.set_tokens(tokens)
        self.colorbar_show_toggle.set_tokens(tokens)
        self.color_scale_auto_toggle.set_tokens(tokens)
        self.heatmap_gridding_control.set_tokens(tokens)
        self.figure_bg_color_row.set_tokens(tokens)
        self.figure_bg_transparent_toggle.set_tokens(tokens)
        self.axes_bg_color_row.set_tokens(tokens)
        self.axes_bg_transparent_toggle.set_tokens(tokens)
        self.axes_style_selector.set_tokens(tokens)
        for form in self.axes_style_forms.values():
            form["title_card"].set_tokens(tokens)
            form["color_row"].set_tokens(tokens)
            if form["match_x_toggle"] is not None:
                form["match_x_toggle"].set_tokens(tokens)
            form["ticks_card"].set_tokens(tokens)
            form["tick_color_row"].set_tokens(tokens)
            form["colors_card"].set_tokens(tokens)
            form["spine_color_row"].set_tokens(tokens)
            form["major_tick_color_row"].set_tokens(tokens)
            form["minor_tick_color_row"].set_tokens(tokens)
            if form["match_x_colors_toggle"] is not None:
                form["match_x_colors_toggle"].set_tokens(tokens)
