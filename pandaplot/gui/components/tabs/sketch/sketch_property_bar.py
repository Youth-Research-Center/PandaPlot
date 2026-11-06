"""Toolbar that shows and edits the style of the selection or of new elements."""
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from PySide6.QtCore import QRectF, QSize, Qt
from PySide6.QtGui import QAction, QActionGroup, QColor, QFont, QFontDatabase, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QLabel, QMenu, QToolBar, QToolButton, QWidget

from pandaplot.commands.project.sketch import UpdateSketchElementStyleCommand
from pandaplot.gui.components.common.drop_down_combo_box import DropDownComboBox
from pandaplot.gui.components.common.number_input import DecimalInput, IntegerInput
from pandaplot.gui.components.tabs.sketch.tools.tool_manager import TOOL_ELEMENT_TYPES
from pandaplot.models.project.items.sketch import SketchElement, StrokeStyle, TextAlignment
from pandaplot.models.project.items.sketch.sketch_element import STYLE_VALUE_CHECKS
from pandaplot.models.state.app_context import AppContext

if TYPE_CHECKING:
    from pandaplot.gui.components.tabs.sketch.sketch_canvas import SketchCanvas

MIXED = "Mixed"
ALL_STYLE_FIELDS = frozenset(STYLE_VALUE_CHECKS)
STROKE_STYLE_LABELS: dict[StrokeStyle, str] = {
    StrokeStyle.SOLID: "Solid",
    StrokeStyle.DASHED: "Dashed",
    StrokeStyle.DOTTED: "Dotted",
    StrokeStyle.DASH_DOT: "Dash-dot",
}
ALIGNMENT_LABELS: dict[TextAlignment, tuple[str, str]] = {
    TextAlignment.LEFT: ("Left", "Align text left"),
    TextAlignment.CENTER: ("Center", "Center text"),
    TextAlignment.RIGHT: ("Right", "Align text right"),
}
_SWATCH = 16
_NUMBER_WIDTH = 72


class _Mixed:
    """Marks a field whose value differs between the selected elements;
    `first` is the first selected element's value, which a number field
    steps from."""

    def __init__(self, first: Any = None):
        self.first = first


def swatch_icon(color: str | None | _Mixed) -> QIcon:
    """A colour swatch: the colour over white, a red slash for no colour, or
    a split swatch for differing colours."""
    pixmap = QPixmap(_SWATCH * 2, _SWATCH * 2)
    pixmap.setDevicePixelRatio(2)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    box = QRectF(1.5, 1.5, _SWATCH - 3, _SWATCH - 3)
    painter.fillRect(box, Qt.GlobalColor.white)
    if isinstance(color, _Mixed):
        painter.fillRect(QRectF(box.left(), box.top(), box.width() / 2, box.height()), QColor("#9CA3AF"))
        painter.fillRect(QRectF(box.center().x(), box.top(), box.width() / 2, box.height()), QColor("#374151"))
    elif color is None:
        painter.setPen(QPen(QColor("#DC2626"), 1.5))
        painter.drawLine(box.bottomLeft(), box.topRight())
    else:
        painter.fillRect(box, QColor(color))
    painter.setPen(QPen(QColor("#6B7280"), 1.0))
    painter.drawRect(box)
    painter.end()
    return QIcon(pixmap)


def describe_color(color: str | None | _Mixed) -> str:
    if isinstance(color, _Mixed):
        return MIXED
    return "none" if color is None else color


class SketchPropertyBar(QToolBar):
    """Shows the style of the selected elements and changes it, or, with
    nothing selected, the style the active tool gives new elements.

    A control the selection (or the tool's element type) doesn't draw with
    is disabled, e.g. fill for a line. Where the selected elements differ,
    a control shows "Mixed"; changing it gives them all the new value.
    Every change to a selection is one `UpdateSketchElementStyleCommand`.
    """

    def __init__(self, canvas: "SketchCanvas", app_context: AppContext, parent: QWidget | None = None):
        super().__init__("Sketch style", parent)
        self.canvas = canvas
        self.app_context = app_context
        self.setAccessibleName("Sketch style")
        self.setIconSize(QSize(_SWATCH, _SWATCH))
        self.field_widgets: dict[str, list[QWidget | QAction]] = {}
        self._syncing = False
        self._shown: dict[str, Any] = {}
        self._build()
        canvas.selection_changed.connect(self.refresh)
        canvas.rebuilt.connect(self.refresh)
        canvas.tool_manager.tool_changed.connect(lambda _mode: self.refresh())
        self.refresh()

    # -- building ----------------------------------------------------------

    def _build(self) -> None:
        self.scope_label = QLabel(self)
        self.scope_label.setAccessibleName("Style applies to")
        self.addWidget(self.scope_label)
        self.addSeparator()

        self.stroke_button = self._color_button("Stroke", "stroke_color")
        self.stroke_button.clicked.connect(lambda: self._pick_color("stroke_color", "Stroke Colour"))

        # No -/+ buttons in this compact bar; arrow keys and the wheel step.
        self.width_input = DecimalInput(self, steppers=False)
        self.width_input.setFixedWidth(_NUMBER_WIDTH)
        self.width_input.setRange(0.0, 50.0)
        self.width_input.setDecimals(1)
        self.width_input.setSingleStep(0.5)
        self.width_input.setSuffix(" px")
        self.width_input.setAccessibleName("Line width")
        self.width_input.setToolTip("Line width (0 draws no outline)")
        self.width_input.valueChanged.connect(lambda value: self._set("stroke_width", value))
        self._add("stroke_width", self.width_input)

        self.style_combo = DropDownComboBox(self)
        for stroke_style, label in STROKE_STYLE_LABELS.items():
            self.style_combo.addItem(label, stroke_style)
        self.style_combo.setPlaceholderText(MIXED)
        self.style_combo.setAccessibleName("Line style")
        self.style_combo.setToolTip("Line style")
        self.style_combo.currentIndexChanged.connect(self._on_stroke_style_index)
        self._add("stroke_style", self.style_combo)

        self.fill_button = self._color_button("Fill", "fill_color")
        fill_menu = QMenu(self.fill_button)
        self.no_fill_action = QAction("No fill", fill_menu)
        self.no_fill_action.triggered.connect(lambda: self._set("fill_color", None))
        self.choose_fill_action = QAction("Choose colour…", fill_menu)
        self.choose_fill_action.triggered.connect(lambda: self._pick_color("fill_color", "Fill Colour"))
        fill_menu.addAction(self.no_fill_action)
        fill_menu.addAction(self.choose_fill_action)
        self.fill_button.setMenu(fill_menu)
        self.fill_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.addSeparator()

        self.font_combo = DropDownComboBox(self)
        self.font_combo.addItems(QFontDatabase.families())
        self.font_combo.setPlaceholderText(MIXED)
        self.font_combo.setAccessibleName("Font")
        self.font_combo.setToolTip("Font")
        self.font_combo.setMaximumWidth(180)
        self.font_combo.currentIndexChanged.connect(lambda index: self._on_font_index(index))
        self._add("font_family", self.font_combo)

        self.size_input = IntegerInput(self, steppers=False)
        self.size_input.setFixedWidth(_NUMBER_WIDTH)
        self.size_input.setRange(1, 999)
        self.size_input.setSuffix(" px")
        self.size_input.setAccessibleName("Font size")
        self.size_input.setToolTip("Font size")
        self.size_input.valueChanged.connect(lambda value: self._set("font_size", value))
        self._add("font_size", self.size_input)

        self.bold_action = self._toggle_action("B", "Bold", "is_bold", font_setter=QFont.setBold)
        self.italic_action = self._toggle_action("I", "Italic", "is_italic", font_setter=QFont.setItalic)

        self.alignment_group = QActionGroup(self)
        # Optional so that none is checked while the selection is mixed.
        self.alignment_group.setExclusionPolicy(QActionGroup.ExclusionPolicy.ExclusiveOptional)
        self.alignment_actions: dict[TextAlignment, QAction] = {}
        for alignment, (label, tooltip) in ALIGNMENT_LABELS.items():
            action = QAction(label, self)
            action.setCheckable(True)
            action.setToolTip(tooltip)
            action.triggered.connect(lambda checked, alignment=alignment: self._on_alignment(alignment, checked=checked))
            self.alignment_group.addAction(action)
            self.addAction(action)
            self.field_widgets.setdefault("alignment", []).append(action)
            self.alignment_actions[alignment] = action

    def _add(self, field_name: str, widget: QWidget) -> None:
        self.addWidget(widget)
        self.field_widgets.setdefault(field_name, []).append(widget)

    def _color_button(self, text: str, field_name: str) -> QToolButton:
        button = QToolButton(self)
        button.setText(text)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setAccessibleName(f"{text} colour")
        self._add(field_name, button)
        return button

    def _toggle_action(self, text: str, name: str, field_name: str, *, font_setter: Callable[[QFont, bool], None]) -> QAction:
        action = QAction(text, self)
        action.setCheckable(True)
        action.setToolTip(name)
        font = action.font()
        font_setter(font, True)  # noqa: FBT003 -- QFont setter takes the flag positionally
        action.setFont(font)
        action.triggered.connect(lambda checked: self._set(field_name, checked))
        self.addAction(action)
        button = self.widgetForAction(action)
        if button is not None:
            button.setAccessibleName(name)
        self.field_widgets.setdefault(field_name, []).append(action)
        return action

    # -- what the bar edits --------------------------------------------------

    def _selected_elements(self) -> list[SketchElement]:
        elements = []
        for element_id in self.canvas.selected_ids:
            found = self.canvas.sketch.find_element(element_id)
            if found is not None:
                elements.append(found[1])
        return elements

    def _targets(self) -> tuple[frozenset[str], dict[str, Any], str]:
        """The editable fields, their shown values, and what they apply to."""
        elements = self._selected_elements()
        if elements:
            fields: set[str] = set()
            values: dict[str, Any] = {}
            for name in ALL_STYLE_FIELDS:
                found = [getattr(element, name) for element in elements if name in type(element).STYLE_FIELDS]
                if found:
                    fields.add(name)
                    values[name] = found[0] if all(value == found[0] for value in found) else _Mixed(found[0])
            count = len(elements)
            return frozenset(fields), values, f"Selection ({count} element{'s' if count != 1 else ''})"
        manager = self.canvas.tool_manager
        element_type = TOOL_ELEMENT_TYPES.get(manager.mode)
        fields = element_type.STYLE_FIELDS if element_type is not None else ALL_STYLE_FIELDS
        values = {name: getattr(manager.style, name) for name in fields}
        return frozenset(fields), values, "New elements"

    # -- showing -------------------------------------------------------------

    def refresh(self) -> None:
        """Show the current selection's style, or the new-element style."""
        fields, values, scope = self._targets()
        self._shown = values
        self._syncing = True
        try:
            self.scope_label.setText(scope)
            for name, widgets in self.field_widgets.items():
                for widget in widgets:
                    widget.setEnabled(name in fields)
            self._show_color(self.stroke_button, "Stroke", values.get("stroke_color", "#000000"))
            self._show_color(self.fill_button, "Fill", values.get("fill_color"))
            self._show_number(self.width_input, values.get("stroke_width", 0.0))
            self._show_combo(self.style_combo, values.get("stroke_style", StrokeStyle.SOLID))
            self._show_font(values.get("font_family", ""))
            self._show_number(self.size_input, values.get("font_size", 14))
            self.bold_action.setChecked(values.get("is_bold") is True)
            self.italic_action.setChecked(values.get("is_italic") is True)
            alignment = values.get("alignment")
            for value, action in self.alignment_actions.items():
                action.setChecked(value == alignment)
        finally:
            self._syncing = False

    @staticmethod
    def _show_color(button: QToolButton, label: str, value: Any) -> None:
        button.setIcon(swatch_icon(value))
        description = describe_color(value)
        button.setToolTip(f"{label} colour: {description}")
        button.setAccessibleDescription(f"Current {label.lower()} colour: {description}")

    @staticmethod
    def _show_number(number_input: DecimalInput | IntegerInput, value: Any) -> None:
        if isinstance(value, _Mixed):
            number_input.setValue(value.first)
            number_input.setMixed(MIXED)
        else:
            number_input.setValue(value)

    @staticmethod
    def _show_combo(combo: DropDownComboBox, value: Any) -> None:
        combo.setCurrentIndex(-1 if isinstance(value, _Mixed) else combo.findData(value))

    def _show_font(self, value: Any) -> None:
        if isinstance(value, _Mixed):
            self.font_combo.setCurrentIndex(-1)
            return
        index = self.font_combo.findText(value)
        if index < 0 and value:
            # A family saved on another machine and not installed here.
            self.font_combo.addItem(value)
            index = self.font_combo.count() - 1
        self.font_combo.setCurrentIndex(index)

    # -- changing --------------------------------------------------------------

    def _set(self, field_name: str, value: Any) -> None:
        """Apply one style change to the selection, or to new elements."""
        if self._syncing:
            return
        elements = self._selected_elements()
        if elements:
            command = UpdateSketchElementStyleCommand(self.app_context, self.canvas.sketch, [element.id for element in elements], {field_name: value})
            if not self.app_context.get_command_executor().execute_command(command):
                # Nothing changed (or it was refused): show the model again.
                self.refresh()
            return
        setattr(self.canvas.tool_manager.style, field_name, value)
        self.refresh()

    def _pick_color(self, field_name: str, title: str) -> None:
        current = self._shown.get(field_name)
        initial = current if isinstance(current, str) else "#000000"
        color = self.app_context.get_ui_controller().get_color(title, initial, with_alpha=True)
        if color is not None:
            self._set(field_name, color)

    def _on_stroke_style_index(self, index: int) -> None:
        if index >= 0:
            # Qt hands item data back as a plain string.
            self._set("stroke_style", StrokeStyle(self.style_combo.itemData(index)))

    def _on_font_index(self, index: int) -> None:
        if index >= 0:
            self._set("font_family", self.font_combo.itemText(index))

    def _on_alignment(self, alignment: TextAlignment, *, checked: bool) -> None:
        if checked:
            self._set("alignment", alignment)
        else:
            # Clicking the checked alignment unchecks it; alignment can't be "none".
            self.refresh()

