"""Axes tab: X/Y1/Y2 chip switcher over per-axis scale/limits/ticks/grid forms."""
import math

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from pandaplot.gui.components.common.card import Card
from pandaplot.gui.components.common.chip_row import ChipRow
from pandaplot.gui.components.common.p_button import PButton
from pandaplot.gui.components.common.section_header import SectionHeader
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.gui.components.common.toggle_switch import ToggleSwitch
from pandaplot.gui.components.common.value_combo_box import ValueComboBox
from pandaplot.models.chart.chart_configuration import ScaleType
from pandaplot.models.chart.series_type_spec import SERIES_TYPE_SPECS
from pandaplot.models.project.items.chart import YAxis

# Neutral palette for axis/tick colors (distinct from style_tab's saturated series palette).
AXES_SWATCH_PALETTE = ["#000000", "#404040", "#808080", "#bfbfbf", "#ffffff"]

# Colormaps offered for Colormap/Heatmap chart types' Z-driven point/cell
# coloring. Chart-level (not per-series): the colormap/colorbar/scale are
# shared across every Colormap/Heatmap series on a chart, since there's only
# ever one physical colorbar drawn.
COLORMAP_OPTIONS = [
    ("Viridis", "viridis"),
    ("Plasma", "plasma"),
    ("Cool", "cool"),
    ("Autumn", "autumn"),
    ("Jet", "jet"),
    ("Hot", "hot"),
    ("Coolwarm", "coolwarm"),
]


class AxesTab(QWidget):
    """X/Y1/Y2 chip switcher above a single form area that shows only the
    selected axis's controls.

    Each axis (x, y, y2) gets its own independent set of widgets (built by
    `_build_axis_form_widgets`) rather than one shared form, because (unlike
    the Data/Style tabs' "currently edited series") the three axes are
    genuinely independent, simultaneously-existing config state - nothing
    here is "the currently active axis's data", so there's no shared model
    to reparent a single form around.
    """

    configChanged = Signal()

    def __init__(self, app_context, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self._chart = None
        self._updating_controls = False
        # Whether the user has ever actually typed into the colorbar label
        # field for the currently loaded chart -- distinguishes "never
        # customized" (fall back to the Z column's name) from "customized to
        # empty" (show no label at all). Without this, _write_color_axis_config
        # writing the field's current (blank) text on every unrelated field
        # change would be indistinguishable from an explicit clear.
        self._colorbar_label_customized = False

        layout = QVBoxLayout(self)

        self.axis_chips = ChipRow()
        self.axis_chips.setItems([("X", "x"), ("Y₁", "y")])
        self.axis_chips.currentValueChanged.connect(self._on_axis_chip_selected)
        layout.addWidget(self.axis_chips)

        self._axis_form_container = QWidget()
        self._axis_form_container_layout = QVBoxLayout(self._axis_form_container)
        self._axis_form_container_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._axis_form_container)
        layout.addStretch()

        self.axes_forms = {}
        for prefix in ("x", "y", "y2"):
            self._build_axis_form_widgets(prefix)
        self._build_color_axis_form_widgets()
        self._show_axis_form("x")

    def _build_axis_form_widgets(self, prefix: str):
        """Build one axis's full control set and register it in `self.axes_forms[prefix]`."""
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        label_layout = QGridLayout()
        label_layout.addWidget(QLabel("Label:"), 0, 0)
        label_edit = QLineEdit()
        label_edit.setToolTip("Supports $LaTeX$ math notation, e.g. $x^2$")
        label_layout.addWidget(label_edit, 0, 1, 1, 2)
        form_layout.addLayout(label_layout)

        scale_control = SegmentedControl([("Linear", ScaleType.LINEAR), ("Log", ScaleType.LOG)])
        form_layout.addWidget(scale_control)

        log_base_row = QWidget()
        log_base_layout = QGridLayout(log_base_row)
        log_base_layout.setContentsMargins(0, 0, 0, 0)
        log_base_label = QLabel("Base:")
        log_base_layout.addWidget(log_base_label, 0, 0)
        log_base_combo = QComboBox()
        for text, value in [("10", 10.0), ("2", 2.0), ("e (natural log)", math.e), ("Custom...", "custom")]:
            log_base_combo.addItem(text, value)
        log_base_layout.addWidget(log_base_combo, 0, 1)
        log_base_custom_spin = QDoubleSpinBox()
        log_base_custom_spin.setRange(0.001, 1000.0)
        log_base_custom_spin.setSingleStep(0.1)
        log_base_custom_spin.setValue(10.0)
        log_base_layout.addWidget(log_base_custom_spin, 1, 0, 1, 2)
        log_base_custom_spin.setVisible(False)
        form_layout.addWidget(log_base_row)
        log_base_row.setVisible(False)

        side_control = None
        if prefix in ("y", "y2"):
            side_control = SegmentedControl([("Left", "left"), ("Right", "right")])
            form_layout.addWidget(side_control)

        range_card = Card()
        range_layout = QGridLayout(range_card)
        range_layout.addWidget(SectionHeader("Range"), 0, 0)
        range_layout.addWidget(QLabel("Auto"), 0, 1)
        auto_toggle = ToggleSwitch(checked=True)
        range_layout.addWidget(auto_toggle, 0, 2)
        min_spin = QDoubleSpinBox()
        min_spin.setRange(-1e9, 1e9)
        # Task 4 made these boxes display machine-computed data ranges (not
        # just user-typed values); Qt's default of 2 decimal places silently
        # rounds away small-magnitude data (e.g. 0.001-0.009 -> 0.00/0.01),
        # which can then write degenerate limits into config on an
        # Auto->Manual toggle.
        min_spin.setDecimals(6)
        min_spin.setEnabled(False)
        max_spin = QDoubleSpinBox()
        max_spin.setRange(-1e9, 1e9)
        max_spin.setDecimals(6)
        max_spin.setValue(1.0)
        max_spin.setEnabled(False)
        range_layout.addWidget(QLabel("Min:"), 1, 0)
        range_layout.addWidget(min_spin, 1, 1, 1, 2)
        range_layout.addWidget(QLabel("Max:"), 2, 0)
        range_layout.addWidget(max_spin, 2, 1, 1, 2)
        form_layout.addWidget(range_card)

        ticks_card = Card()
        ticks_layout = QGridLayout(ticks_card)
        ticks_layout.addWidget(SectionHeader("Ticks"), 0, 0, 1, 2)
        mode_control = SegmentedControl([("Auto", "auto"), ("Count", "count"), ("Step", "step")])
        ticks_layout.addWidget(mode_control, 1, 0, 1, 2)
        count_spin = QSpinBox()
        count_spin.setRange(2, 50)
        count_spin.setValue(5)
        step_spin = QDoubleSpinBox()
        step_spin.setRange(0.001, 1e9)
        step_spin.setValue(1.0)
        count_label = QLabel("Count:")
        ticks_layout.addWidget(count_label, 2, 0)
        ticks_layout.addWidget(count_spin, 2, 1)
        step_label = QLabel("Step:")
        ticks_layout.addWidget(step_label, 3, 0)
        ticks_layout.addWidget(step_spin, 3, 1)
        count_label.setVisible(False)
        count_spin.setVisible(False)
        step_label.setVisible(False)
        step_spin.setVisible(False)
        format_combo = QComboBox()
        for text, value in [("Auto", "auto"), ("Integer", "integer"), ("1 Decimal", "1decimal"),
                            ("2 Decimals", "2decimal"), ("Scientific", "scientific"), ("Custom...", "custom")]:
            format_combo.addItem(text, value)
        ticks_layout.addWidget(QLabel("Format:"), 4, 0)
        ticks_layout.addWidget(format_combo, 4, 1)
        format_custom_edit = QLineEdit()
        format_custom_edit.setPlaceholderText("e.g. {:.2f} units")
        format_custom_edit.setEnabled(False)
        ticks_layout.addWidget(format_custom_edit, 5, 0, 1, 2)
        grid_toggle = ToggleSwitch(checked=True)
        ticks_layout.addWidget(QLabel("Show grid"), 6, 0)
        ticks_layout.addWidget(grid_toggle, 6, 1)

        tick_direction_control = SegmentedControl(
            [("Out", "out"), ("In", "in"), ("In & Out", "inout")]
        )
        ticks_layout.addWidget(QLabel("Direction:"), 7, 0)
        ticks_layout.addWidget(tick_direction_control, 7, 1)

        minor_ticks_toggle = ToggleSwitch()
        ticks_layout.addWidget(QLabel("Minor ticks"), 8, 0)
        ticks_layout.addWidget(minor_ticks_toggle, 8, 1)

        # Minor ticks can point a different way than major ticks (e.g. major
        # ticks outside the axis, minor ticks inside) -- only meaningful (and
        # shown) once minor ticks are actually turned on.
        minor_tick_direction_label = QLabel("Minor direction:")
        minor_tick_direction_control = SegmentedControl(
            [("Out", "out"), ("In", "in"), ("In & Out", "inout")]
        )
        ticks_layout.addWidget(minor_tick_direction_label, 9, 0)
        ticks_layout.addWidget(minor_tick_direction_control, 9, 1)
        minor_tick_direction_label.setVisible(False)
        minor_tick_direction_control.setVisible(False)

        # Minor gridlines only draw where minor tick locations exist, so
        # this toggle -- like minor tick direction above -- is only shown
        # (and meaningful) once minor ticks are actually turned on.
        minor_grid_label = QLabel("Minor grid:")
        minor_grid_toggle = ToggleSwitch()
        ticks_layout.addWidget(minor_grid_label, 10, 0)
        ticks_layout.addWidget(minor_grid_toggle, 10, 1)
        minor_grid_label.setVisible(False)
        minor_grid_toggle.setVisible(False)

        form_layout.addWidget(ticks_card)

        copy_button = None
        if prefix in ("y", "y2"):
            copy_button = PButton(
                "Copy settings to Y axis", role="secondary",
                on_click=lambda _checked=False, p=prefix: self._on_copy_axis_settings(p)
            )
            form_layout.addWidget(copy_button)

        self.axes_forms[prefix] = {
            "widget": form_widget, "label_edit": label_edit,
            "scale_control": scale_control, "side_control": side_control,
            "log_base_row": log_base_row, "log_base_combo": log_base_combo,
            "log_base_custom_spin": log_base_custom_spin,
            "range_card": range_card, "ticks_card": ticks_card,
            "auto_toggle": auto_toggle, "min_spin": min_spin, "max_spin": max_spin,
            "mode_control": mode_control, "count_spin": count_spin, "step_spin": step_spin,
            "count_label": count_label, "step_label": step_label,
            "format_combo": format_combo, "format_custom_edit": format_custom_edit,
            "grid_toggle": grid_toggle, "copy_button": copy_button,
            "tick_direction_control": tick_direction_control, "minor_ticks_toggle": minor_ticks_toggle,
            "minor_tick_direction_label": minor_tick_direction_label,
            "minor_tick_direction_control": minor_tick_direction_control,
            "minor_grid_label": minor_grid_label,
            "minor_grid_toggle": minor_grid_toggle,
        }

        # Wire this form's widgets directly to shared handlers - the forms
        # are built dynamically (there are no static self.x_*/self.y_*
        # attributes to hook up elsewhere), so wiring happens here.
        label_edit.textChanged.connect(self._on_field_changed)
        scale_control.currentValueChanged.connect(lambda _v, p=prefix: self._on_scale_changed(p))
        log_base_combo.currentIndexChanged.connect(lambda _i, p=prefix: self._on_log_base_combo_changed(p))
        log_base_custom_spin.valueChanged.connect(self._on_field_changed)
        if side_control is not None:
            side_control.currentValueChanged.connect(self._on_field_changed)
        auto_toggle.toggled.connect(
            lambda checked, p=prefix: self._on_axis_auto_limits_toggled(p, checked=checked)
        )
        min_spin.valueChanged.connect(self._on_field_changed)
        max_spin.valueChanged.connect(self._on_field_changed)
        mode_control.currentValueChanged.connect(lambda _v, p=prefix: self._on_axis_tick_mode_changed(p))
        count_spin.valueChanged.connect(self._on_field_changed)
        step_spin.valueChanged.connect(self._on_field_changed)
        format_combo.currentIndexChanged.connect(lambda _i, p=prefix: self._on_axis_tick_format_changed(p))
        format_custom_edit.textChanged.connect(self._on_field_changed)
        grid_toggle.toggled.connect(self._on_field_changed)
        tick_direction_control.currentValueChanged.connect(self._on_field_changed)
        minor_ticks_toggle.toggled.connect(
            lambda checked, p=prefix: self._on_minor_ticks_toggled(p, checked=checked)
        )
        minor_tick_direction_control.currentValueChanged.connect(self._on_field_changed)
        minor_grid_toggle.toggled.connect(self._on_field_changed)

        form_widget.setVisible(False)
        self._axis_form_container_layout.addWidget(form_widget)

    def _build_color_axis_form_widgets(self):
        """Build the "Color" axis form (colormap/colorbar/scale, shared by
        every Colormap/Heatmap series on the chart) and register it in
        `self.axes_forms["color"]`, alongside x/y/y2. Unlike those three,
        it isn't a real matplotlib axis -- no range/ticks/scale-type -- so
        it gets its own, differently-shaped form rather than going through
        `_build_axis_form_widgets`. Shown only when the chart has at least
        one series needing a Z column (see `refresh_axis_chips`), since
        there's only ever one physical colorbar for the whole chart, not
        one per series (#193 -- moved here from the Style tab, which is
        where this used to live as the "Color Map" chip)."""
        form_widget = QWidget()
        form_layout = QVBoxLayout(form_widget)
        form_layout.setContentsMargins(0, 0, 0, 0)

        colormap_card = Card()
        colormap_layout = QGridLayout(colormap_card)
        colormap_layout.addWidget(SectionHeader("Color Map"), 0, 0, 1, 2)

        colormap_layout.addWidget(QLabel("Colormap:"), 1, 0)
        colormap_control = ValueComboBox(COLORMAP_OPTIONS)
        colormap_layout.addWidget(colormap_control, 1, 1)

        colormap_layout.addWidget(QLabel("Show colorbar:"), 2, 0)
        colorbar_show_toggle = ToggleSwitch(checked=True)
        colormap_layout.addWidget(colorbar_show_toggle, 2, 1)

        colormap_layout.addWidget(QLabel("Colorbar label:"), 3, 0)
        colorbar_label_edit = QLineEdit()
        colormap_layout.addWidget(colorbar_label_edit, 3, 1)

        colormap_layout.addWidget(QLabel("Auto scale:"), 4, 0)
        color_scale_auto_toggle = ToggleSwitch(checked=True)
        colormap_layout.addWidget(color_scale_auto_toggle, 4, 1)

        color_vmin_label = QLabel("Min:")
        colormap_layout.addWidget(color_vmin_label, 5, 0)
        color_vmin_spin = QDoubleSpinBox()
        color_vmin_spin.setRange(-1e9, 1e9)
        color_vmin_spin.setDecimals(3)
        colormap_layout.addWidget(color_vmin_spin, 5, 1)

        color_vmax_label = QLabel("Max:")
        colormap_layout.addWidget(color_vmax_label, 6, 0)
        color_vmax_spin = QDoubleSpinBox()
        color_vmax_spin.setRange(-1e9, 1e9)
        color_vmax_spin.setDecimals(3)
        color_vmax_spin.setValue(1.0)
        colormap_layout.addWidget(color_vmax_spin, 6, 1)

        form_layout.addWidget(colormap_card)
        form_layout.addStretch()

        self.axes_forms["color"] = {
            "widget": form_widget,
            "card": colormap_card,
            "colormap_control": colormap_control,
            "colorbar_show_toggle": colorbar_show_toggle,
            "colorbar_label_edit": colorbar_label_edit,
            "color_scale_auto_toggle": color_scale_auto_toggle,
            "color_vmin_label": color_vmin_label,
            "color_vmin_spin": color_vmin_spin,
            "color_vmax_label": color_vmax_label,
            "color_vmax_spin": color_vmax_spin,
        }

        colormap_control.currentValueChanged.connect(self._on_field_changed)
        colorbar_show_toggle.toggled.connect(self._on_field_changed)
        colorbar_label_edit.textChanged.connect(self._on_colorbar_label_changed)
        color_scale_auto_toggle.toggled.connect(self._on_color_scale_auto_toggled)
        color_vmin_spin.valueChanged.connect(self._on_field_changed)
        color_vmax_spin.valueChanged.connect(self._on_field_changed)

        form_widget.setVisible(False)
        self._axis_form_container_layout.addWidget(form_widget)

    def _on_colorbar_label_changed(self, _text: str) -> None:
        """Marks the colorbar label as user-customized before the normal
        live-write. `_read_color_axis_config`'s own `setText()` is wrapped in
        blockSignals, so `textChanged` here always means some other caller
        (a real edit, or a test driving the widget directly) set the text --
        never the tab's own load path."""
        self._colorbar_label_customized = True
        self._on_field_changed()

    def _on_color_scale_auto_toggled(self, _checked: bool):  # noqa: FBT001 - Qt signal-slot callback, called positionally
        """Handle the Color axis' "Auto scale" toggle."""
        self._update_color_scale_controls()
        self._on_field_changed()

    def _update_color_scale_controls(self):
        """Show the manual Min/Max fields only while "Auto scale" is off --
        while auto, the color scale is derived from the data's own min/max
        (see chart_heatmap.resolve_color_limits) and the fields have no
        effect (same hidden-not-disabled convention `_refresh_range_display`
        uses for a plain axis' manual Min/Max)."""
        form = self.axes_forms["color"]
        show_manual = not form["color_scale_auto_toggle"].isChecked()
        form["color_vmin_label"].setVisible(show_manual)
        form["color_vmin_spin"].setVisible(show_manual)
        form["color_vmax_label"].setVisible(show_manual)
        form["color_vmax_spin"].setVisible(show_manual)

    def _write_color_axis_config(self, config: dict):
        form = self.axes_forms["color"]
        config["colormap"] = form["colormap_control"].currentValue()
        config["colorbar_show"] = form["colorbar_show_toggle"].isChecked()
        # Only ever written once the user has actually typed into the field
        # (see _on_colorbar_label_edited) -- this method runs on every field
        # change on the whole tab, not just this one, so unconditionally
        # writing the widget's current (possibly still-blank) text here would
        # make "never customized" indistinguishable from "customized to
        # empty" the moment any other field changed.
        if self._colorbar_label_customized:
            config["colorbar_label"] = form["colorbar_label_edit"].text()
        config["color_scale_auto"] = form["color_scale_auto_toggle"].isChecked()
        config["color_vmin"] = form["color_vmin_spin"].value()
        config["color_vmax"] = form["color_vmax_spin"].value()

    def _read_color_axis_config(self, config: dict):
        form = self.axes_forms["color"]
        form["colormap_control"].setCurrentValue(config.get("colormap", "viridis"))
        form["colorbar_show_toggle"].blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        form["colorbar_show_toggle"].setChecked(checked=config.get("colorbar_show", True))
        form["colorbar_show_toggle"].blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
        stored_label = config.get("colorbar_label")
        self._colorbar_label_customized = stored_label is not None
        form["colorbar_label_edit"].blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        form["colorbar_label_edit"].setText(stored_label or "")
        form["colorbar_label_edit"].blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
        form["color_scale_auto_toggle"].blockSignals(True)  # noqa: FBT003 - Qt bound method, positional-only
        form["color_scale_auto_toggle"].setChecked(checked=config.get("color_scale_auto", True))
        form["color_scale_auto_toggle"].blockSignals(False)  # noqa: FBT003 - Qt bound method, positional-only
        form["color_vmin_spin"].setValue(config.get("color_vmin", 0.0))
        form["color_vmax_spin"].setValue(config.get("color_vmax", 1.0))
        self._update_color_scale_controls()

    def _show_axis_form(self, prefix: str):
        """Show only the selected axis's form, hiding the other two."""
        for key, form in self.axes_forms.items():
            form["widget"].setVisible(key == prefix)

    def _on_axis_chip_selected(self, prefix: str):
        self._show_axis_form(prefix)

    def _on_axis_auto_limits_toggled(self, prefix: str, *, checked: bool):
        self._refresh_range_display(prefix)
        self._on_field_changed()

    def _refresh_range_display(self, prefix: str):
        """Recompute the data-driven min/max for this axis and show it:
        Auto shows it disabled (for reference); Manual shows it enabled
        and freshly seeded (never restoring a previously-typed value --
        every Auto<->Manual transition recomputes from the current data)."""
        form = self.axes_forms[prefix]
        auto = form["auto_toggle"].isChecked()
        if self._chart is not None:
            from pandaplot.gui.components.tabs.chart.chart_editor import compute_axis_data_range
            project = self.app_context.app_state.current_project
            # A Log-scaled axis must ignore non-positive data points, same as
            # matplotlib's own autoscale would -- otherwise a computed min <= 0
            # gets shown here and later rejected/ignored by set_xlim/set_ylim.
            is_log = form["scale_control"].currentValue() == ScaleType.LOG
            computed = compute_axis_data_range(
                project, self._chart.data_series, prefix, positive_only=is_log
            )
        else:
            computed = None
        min_value, max_value = computed if computed is not None else (0.0, 1.0)
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            form["min_spin"].setValue(min_value)
            form["max_spin"].setValue(max_value)
        finally:
            self._updating_controls = previous_guard
        form["min_spin"].setEnabled(not auto)
        form["max_spin"].setEnabled(not auto)

    def _on_axis_tick_mode_changed(self, prefix: str):
        """Show only the field the current tick mode actually uses: Auto
        shows neither Count nor Step, Count shows only Count, Step shows
        only Step."""
        form = self.axes_forms[prefix]
        mode = form["mode_control"].currentValue()
        form["count_label"].setVisible(mode == "count")
        form["count_spin"].setVisible(mode == "count")
        form["step_label"].setVisible(mode == "step")
        form["step_spin"].setVisible(mode == "step")
        self._on_field_changed()

    def _on_minor_ticks_toggled(self, prefix: str, *, checked: bool):
        """Show the minor-tick direction control and minor grid toggle only
        once minor ticks are actually enabled -- they have nothing to apply
        to otherwise. (Minor-tick *color* visibility is now owned by
        StyleTab's Colors card, not this tab.)"""
        form = self.axes_forms[prefix]
        form["minor_tick_direction_label"].setVisible(checked)
        form["minor_tick_direction_control"].setVisible(checked)
        form["minor_grid_label"].setVisible(checked)
        form["minor_grid_toggle"].setVisible(checked)
        self._on_field_changed()

    def _on_axis_tick_format_changed(self, prefix: str):
        form = self.axes_forms[prefix]
        form["format_custom_edit"].setEnabled(form["format_combo"].currentData() == "custom")
        self._on_field_changed()

    def _on_scale_changed(self, prefix: str):
        """Show the Base row only for Log scale, and -- for an Auto axis --
        refresh the displayed range so the positive-only filtering
        `_refresh_range_display` applies for Log scale takes effect
        immediately (matches the guard `load()` uses around the same call:
        a Manual axis's displayed value must not be recomputed here)."""
        form = self.axes_forms[prefix]
        is_log = form["scale_control"].currentValue() == ScaleType.LOG
        form["log_base_row"].setVisible(is_log)
        if form["auto_toggle"].isChecked():
            self._refresh_range_display(prefix)
        self._on_field_changed()

    def _on_log_base_combo_changed(self, prefix: str):
        form = self.axes_forms[prefix]
        form["log_base_custom_spin"].setVisible(form["log_base_combo"].currentData() == "custom")
        self._on_field_changed()

    def _resolve_log_base(self, prefix: str) -> float:
        """Resolve the effective log base from the Base combo, reading the
        custom spin box when "Custom..." is selected. Rejects exactly 1.0
        (matplotlib's LogScale forbids it) by falling back to 10.0 --
        QDoubleSpinBox can't exclude a single interior value via setRange,
        so this is enforced here instead."""
        form = self.axes_forms[prefix]
        data = form["log_base_combo"].currentData()
        base = form["log_base_custom_spin"].value() if data == "custom" else data
        return base if base and base != 1.0 else 10.0

    def _on_copy_axis_settings(self, prefix: str):
        """Copy the shown Y axis's non-label settings to the other Y axis."""
        other = "y2" if prefix == "y" else "y"
        source = self.axes_forms[prefix]
        target = self.axes_forms[other]

        target["scale_control"].setCurrentValue(source["scale_control"].currentValue())
        target["log_base_combo"].setCurrentIndex(target["log_base_combo"].findData(source["log_base_combo"].currentData()))
        target["log_base_custom_spin"].setValue(source["log_base_custom_spin"].value())
        target["log_base_custom_spin"].setVisible(target["log_base_combo"].currentData() == "custom")
        target["log_base_row"].setVisible(target["scale_control"].currentValue() == ScaleType.LOG)
        if source["side_control"] is not None and target["side_control"] is not None:
            target["side_control"].setCurrentValue(source["side_control"].currentValue())
        target["auto_toggle"].setChecked(checked=source["auto_toggle"].isChecked())
        target["min_spin"].setValue(source["min_spin"].value())
        target["max_spin"].setValue(source["max_spin"].value())
        target["min_spin"].setEnabled(not target["auto_toggle"].isChecked())
        target["max_spin"].setEnabled(not target["auto_toggle"].isChecked())
        target["mode_control"].setCurrentValue(source["mode_control"].currentValue())
        target["count_spin"].setValue(source["count_spin"].value())
        target["step_spin"].setValue(source["step_spin"].value())
        target_mode = target["mode_control"].currentValue()
        target["count_label"].setVisible(target_mode == "count")
        target["count_spin"].setVisible(target_mode == "count")
        target["step_label"].setVisible(target_mode == "step")
        target["step_spin"].setVisible(target_mode == "step")
        format_index = target["format_combo"].findData(source["format_combo"].currentData())
        if format_index >= 0:
            target["format_combo"].setCurrentIndex(format_index)
        target["format_custom_edit"].setText(source["format_custom_edit"].text())
        target["format_custom_edit"].setEnabled(target["format_combo"].currentData() == "custom")
        target["grid_toggle"].setChecked(checked=source["grid_toggle"].isChecked())
        target["tick_direction_control"].setCurrentValue(source["tick_direction_control"].currentValue())
        target["minor_ticks_toggle"].setChecked(checked=source["minor_ticks_toggle"].isChecked())
        target["minor_tick_direction_control"].setCurrentValue(
            source["minor_tick_direction_control"].currentValue()
        )
        target["minor_grid_toggle"].setChecked(checked=source["minor_grid_toggle"].isChecked())
        target_minor_enabled = target["minor_ticks_toggle"].isChecked()
        target["minor_tick_direction_label"].setVisible(target_minor_enabled)
        target["minor_tick_direction_control"].setVisible(target_minor_enabled)
        target["minor_grid_label"].setVisible(target_minor_enabled)
        target["minor_grid_toggle"].setVisible(target_minor_enabled)

        self._on_field_changed()

    def refresh_axis_chips(self, chart):
        """Sync the Axes tab's chip row with whether any series currently
        uses the secondary Y axis or needs a Z column, adding/removing the
        Y2/Color chips accordingly. Safe to call whenever the chart or its
        series may have changed (chart load, series rebuild) - mirrors
        `_refresh_style_chips`.

        Public (and takes `chart` explicitly) because the not-yet-migrated
        Data tab (still on `ChartPropertiesPanel`) calls this whenever a
        series' `y_axis` or type changes.
        """
        self._chart = chart
        has_secondary = bool(chart) and any(
            series.y_axis == YAxis.SECONDARY for series in chart.data_series
        )
        needs_color_axis = bool(chart) and any(
            SERIES_TYPE_SPECS[series.series_type].needs_z_column for series in chart.data_series
        )
        items = [("X", "x"), ("Y₁", "y")]
        if has_secondary:
            items.append(("Y₂", "y2"))
        if needs_color_axis:
            items.append(("Color", "color"))
        self.axis_chips.setItems(items)

    def _write_axis_config(self, prefix: str, config: dict):
        """Write one axis form's widget values into `config` (the mutable chart.config dict)."""
        form = self.axes_forms[prefix]
        config[f"{prefix}_label"] = form["label_edit"].text()
        if form["scale_control"].currentValue():
            config[f"{prefix}_scale"] = form["scale_control"].currentValue().value
        config[f"{prefix}_log_base"] = self._resolve_log_base(prefix)
        if form["side_control"] is not None:
            config[f"{prefix}_side"] = form["side_control"].currentValue()
        config[f"{prefix}_auto_limits"] = form["auto_toggle"].isChecked()
        config[f"{prefix}_min"] = form["min_spin"].value()
        config[f"{prefix}_max"] = form["max_spin"].value()
        config[f"{prefix}_tick_mode"] = form["mode_control"].currentValue()
        config[f"{prefix}_tick_count"] = form["count_spin"].value()
        config[f"{prefix}_tick_step"] = form["step_spin"].value()
        config[f"{prefix}_tick_format"] = form["format_combo"].currentData()
        config[f"{prefix}_tick_format_custom"] = form["format_custom_edit"].text()
        config[f"show_grid_{prefix}"] = form["grid_toggle"].isChecked()
        config[f"{prefix}_tick_direction"] = form["tick_direction_control"].currentValue()
        config[f"{prefix}_minor_ticks"] = form["minor_ticks_toggle"].isChecked()
        config[f"{prefix}_minor_tick_direction"] = form["minor_tick_direction_control"].currentValue()
        config[f"{prefix}_show_minor_grid"] = form["minor_grid_toggle"].isChecked()

    def _read_axis_config(self, prefix: str, config: dict):
        """Populate one axis form's widgets from `config`. Assumes the caller
        already has `self._updating_controls` set so change signals don't
        write half-loaded values back out."""
        form = self.axes_forms[prefix]
        form["label_edit"].setText(config.get(f"{prefix}_label", ""))

        scale_value = config.get(f"{prefix}_scale", "linear")
        try:
            form["scale_control"].setCurrentValue(ScaleType(scale_value))
        except ValueError:
            form["scale_control"].setCurrentValue(ScaleType.LINEAR)

        log_base = config.get(f"{prefix}_log_base", 10.0)
        preset_index = form["log_base_combo"].findData(log_base)
        if preset_index >= 0:
            form["log_base_combo"].setCurrentIndex(preset_index)
            form["log_base_custom_spin"].setVisible(False)
        else:
            form["log_base_combo"].setCurrentIndex(form["log_base_combo"].findData("custom"))
            form["log_base_custom_spin"].setValue(log_base)
            form["log_base_custom_spin"].setVisible(True)
        is_log = form["scale_control"].currentValue() == ScaleType.LOG
        form["log_base_row"].setVisible(is_log)

        if form["side_control"] is not None:
            default_side = "left" if prefix == "y" else "right"
            form["side_control"].setCurrentValue(config.get(f"{prefix}_side", default_side))

        auto_limits = config.get(f"{prefix}_auto_limits", True)
        form["auto_toggle"].setChecked(checked=auto_limits)
        # Auto mode's displayed min/max is owned by `_refresh_range_display`
        # (recomputed from live data whenever it's called). Manual mode has
        # no such recompute on load -- per spec, a Manual axis's value only
        # ever changes via an explicit Auto->Manual toggle or the user
        # typing, never merely by loading/reopening a chart -- so it must be
        # restored here from the actual saved config.
        form["min_spin"].setValue(config.get(f"{prefix}_min", 0.0))
        form["max_spin"].setValue(config.get(f"{prefix}_max", 1.0))
        form["min_spin"].setEnabled(not auto_limits)
        form["max_spin"].setEnabled(not auto_limits)

        tick_mode = config.get(f"{prefix}_tick_mode", "auto")
        form["mode_control"].setCurrentValue(tick_mode)
        form["count_spin"].setValue(config.get(f"{prefix}_tick_count", 5))
        form["step_spin"].setValue(config.get(f"{prefix}_tick_step", 1.0))
        form["count_label"].setVisible(tick_mode == "count")
        form["count_spin"].setVisible(tick_mode == "count")
        form["step_label"].setVisible(tick_mode == "step")
        form["step_spin"].setVisible(tick_mode == "step")

        tick_format = config.get(f"{prefix}_tick_format", "auto")
        format_index = form["format_combo"].findData(tick_format)
        form["format_combo"].setCurrentIndex(format_index if format_index >= 0 else 0)
        form["format_custom_edit"].setText(config.get(f"{prefix}_tick_format_custom", ""))
        form["format_custom_edit"].setEnabled(tick_format == "custom")

        form["grid_toggle"].setChecked(checked=config.get(f"show_grid_{prefix}", True))

        form["tick_direction_control"].setCurrentValue(config.get(f"{prefix}_tick_direction", "out"))
        minor_ticks_enabled = config.get(f"{prefix}_minor_ticks", False)
        form["minor_ticks_toggle"].setChecked(checked=minor_ticks_enabled)
        form["minor_tick_direction_control"].setCurrentValue(
            config.get(f"{prefix}_minor_tick_direction", "out")
        )
        form["minor_tick_direction_label"].setVisible(minor_ticks_enabled)
        form["minor_tick_direction_control"].setVisible(minor_ticks_enabled)
        form["minor_grid_toggle"].setChecked(checked=config.get(f"{prefix}_show_minor_grid", False))
        form["minor_grid_label"].setVisible(minor_ticks_enabled)
        form["minor_grid_toggle"].setVisible(minor_ticks_enabled)

    def _on_field_changed(self):
        if self._chart is None or self._updating_controls:
            return
        config = self._chart.config
        for prefix in ("x", "y", "y2"):
            self._write_axis_config(prefix, config)
        self._write_color_axis_config(config)
        self.configChanged.emit()

    def load(self, chart):
        previous_guard = self._updating_controls
        self._updating_controls = True
        self._chart = chart
        try:
            for prefix in ("x", "y", "y2"):
                self._read_axis_config(prefix, chart.config)
                # Only Auto axes get their range recomputed from live data on
                # load -- `_read_axis_config` just restored a Manual axis's
                # actually-saved min/max above, and merely loading/reopening
                # a chart must not overwrite it (only an explicit
                # Auto->Manual toggle should recompute; see
                # _on_axis_auto_limits_toggled).
                if self.axes_forms[prefix]["auto_toggle"].isChecked():
                    self._refresh_range_display(prefix)
            self._read_color_axis_config(chart.config)
            self.refresh_axis_chips(chart)
            self._show_axis_form("x")
            self.axis_chips.setCurrentValue("x")
        finally:
            self._updating_controls = previous_guard

    def apply_to(self, chart):
        for prefix in ("x", "y", "y2"):
            self._write_axis_config(prefix, chart.config)
        self._write_color_axis_config(chart.config)

    def clear(self):
        self._chart = None
        previous_guard = self._updating_controls
        self._updating_controls = True
        try:
            for prefix in ("x", "y", "y2"):
                self._read_axis_config(prefix, {})
            self._read_color_axis_config({})
            self.refresh_axis_chips(None)
        finally:
            self._updating_controls = previous_guard

    def apply_theme(self, tokens: dict):
        self.axis_chips.set_tokens(tokens)
        for prefix in ("x", "y", "y2"):
            form = self.axes_forms[prefix]
            form["scale_control"].set_tokens(tokens)
            if form["side_control"] is not None:
                form["side_control"].set_tokens(tokens)
            form["range_card"].set_tokens(tokens)
            form["ticks_card"].set_tokens(tokens)
            form["mode_control"].set_tokens(tokens)
            form["auto_toggle"].set_tokens(tokens)
            form["grid_toggle"].set_tokens(tokens)
            form["tick_direction_control"].set_tokens(tokens)
            form["minor_ticks_toggle"].set_tokens(tokens)
            form["minor_tick_direction_control"].set_tokens(tokens)
            form["minor_grid_toggle"].set_tokens(tokens)
        color_form = self.axes_forms["color"]
        color_form["card"].set_tokens(tokens)
        color_form["colormap_control"].set_tokens(tokens)
        color_form["colorbar_show_toggle"].set_tokens(tokens)
        color_form["color_scale_auto_toggle"].set_tokens(tokens)
