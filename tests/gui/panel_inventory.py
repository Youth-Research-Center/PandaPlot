"""Record what a panel contains, independent of widget classes, and compare it with a committed golden.

`panel_inventory(panel)` walks the panel in focus-chain (Tab) order and returns one line per control:

    role | "label or accessible name" | value=... items=[...] range=a..b decimals=n suffix="..." hidden disabled

Roles describe what a control does, not its class, so a migration that swaps a widget class for a restyled one keeps
the same lines. `assert_matches_golden()` compares label text case-insensitively, because sub-group titles change
case by design (spec §7.4). Set `PANDAPLOT_UPDATE_GOLDENS=1` to rewrite the goldens; see
`tests/e2e/panel_inventory/README.md`.
"""

import difflib
import json
import os
from collections.abc import Iterable
from pathlib import Path

from PySide6.QtCore import QAbstractItemModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QAbstractSlider,
    QAbstractSpinBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QScrollBar,
    QSpinBox,
    QTabBar,
    QTableView,
    QTabWidget,
    QTextEdit,
    QWidget,
)

from pandaplot.gui.components.common.color_swatch_row import ColorSwatchRow
from pandaplot.gui.components.common.font_family_options import list_available_font_families
from pandaplot.gui.components.common.number_input import DecimalInput, NumberInput
from pandaplot.gui.components.common.segmented_control import SegmentedControl
from pandaplot.gui.components.common.slider_with_spinbox import SliderWithSpinbox

UPDATE_ENV = "PANDAPLOT_UPDATE_GOLDENS"

# Controls whose child widgets (inner line edits, popups, buttons, viewports) are part of the control itself.
_COMPOUND_TYPES = (
    QComboBox,
    QAbstractSpinBox,
    NumberInput,
    SliderWithSpinbox,
    SegmentedControl,
    ColorSwatchRow,
    QAbstractItemView,
    QTextEdit,
    QPlainTextEdit,
    QTabBar,
)


def _quote(text: str) -> str:
    return json.dumps(text, ensure_ascii=False)


def _quote_list(texts: Iterable[str]) -> str:
    return "[" + ", ".join(_quote(text) for text in texts) + "]"


def _number(value: float) -> str:
    """Lossless text for a value: whole numbers without a decimal point, other floats as their shortest round trip."""
    if isinstance(value, float) and value.is_integer() and abs(value) < 2**53:
        return str(int(value))
    return repr(value)


def _font_family_labels() -> list[str]:
    return [label for label, _value in list_available_font_families()]


def _field_label(widget: QWidget) -> str:
    """Return the accessible name, else the text of a label that names this field (buddy or form row)."""
    if widget.accessibleName():
        return widget.accessibleName()
    parent = widget.parentWidget()
    if parent is None:
        return ""
    for label in parent.findChildren(QLabel):
        if label.buddy() is widget and label.text():
            return label.text()
    for form in parent.findChildren(QFormLayout):
        label = form.labelForField(widget)
        if isinstance(label, QLabel) and label.text():
            return label.text()
    return ""


def _model_rows(model: QAbstractItemModel, parent: QModelIndex, prefix: str = "") -> list[tuple[str, QModelIndex]]:
    """Return (path text, index) for every row in column 0, depth first; a child's text is prefixed with its parents'."""
    rows = []
    for row in range(model.rowCount(parent)):
        index = model.index(row, 0, parent)
        text = prefix + str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        rows.append((text, index))
        if model.rowCount(index) > 0:
            rows.extend(_model_rows(model, index, prefix=text + "/"))
    return rows


def _list_attributes(view: QAbstractItemView, model: QAbstractItemModel) -> list[str]:
    """Items, plus the selected and the checked ones when there are any (a changed default selection is content)."""
    rows = _model_rows(model, QModelIndex())
    attributes = [f"items={_quote_list(text for text, _index in rows)}"]
    selection = view.selectionModel()
    selected = [text for text, index in rows if selection is not None and selection.isSelected(index)]
    if selected:
        attributes.append(f"selected={_quote_list(selected)}")
    states = [(text, index.data(Qt.ItemDataRole.CheckStateRole)) for text, index in rows]
    if any(state is not None for _text, state in states):
        checked = [text for text, state in states if state is not None and Qt.CheckState(state) == Qt.CheckState.Checked]
        attributes.append(f"checked={_quote_list(checked)}")
        partial = [text for text, state in states if state is not None and Qt.CheckState(state) == Qt.CheckState.PartiallyChecked]
        if partial:
            attributes.append(f"partial={_quote_list(partial)}")
    return attributes


def _describe(widget: QWidget) -> tuple[str, str, list[str]] | None:
    """Return (role, label, attributes) for a recorded control, or None for layout-only widgets."""
    if isinstance(widget, QComboBox):
        items = [widget.itemText(i) for i in range(widget.count())]
        shown = "<installed font families>" if items and items == _font_family_labels() else _quote_list(items)
        attributes = [f"value={_quote(widget.currentText())}", f"items={shown}"]
        if widget.isEditable():
            attributes.append("editable")
        return "combo", _field_label(widget), attributes
    if isinstance(widget, SliderWithSpinbox):
        spin = widget.findChild(DecimalInput)
        attributes = [f"value={_number(widget.value())}"]
        if spin is not None:
            attributes += [f"range={_number(spin.minimum())}..{_number(spin.maximum())}", f"decimals={spin.decimals()}"]
        return "slider", _field_label(widget), attributes
    if isinstance(widget, (QSpinBox, QDoubleSpinBox, NumberInput)):
        attributes = [f"value={_number(widget.value())}", f"range={_number(widget.minimum())}..{_number(widget.maximum())}"]
        decimals = widget.decimals() if isinstance(widget, (QDoubleSpinBox, DecimalInput)) else 0
        attributes.append(f"decimals={decimals}")
        if widget.suffix():
            attributes.append(f"suffix={_quote(widget.suffix())}")
        if widget.specialValueText():
            attributes.append(f"special={_quote(widget.specialValueText())}")
        return "number", _field_label(widget), attributes
    if isinstance(widget, SegmentedControl):
        buttons = widget.findChildren(QAbstractButton)
        attributes = [f"value={_quote(next((b.text() for b in buttons if b.property('selected')), ''))}"]
        attributes.append(f"items={_quote_list(b.text() for b in buttons)}")
        return "choice", _field_label(widget), attributes
    if isinstance(widget, ColorSwatchRow):
        return "color", _field_label(widget), [f"value={_quote(widget.currentColor())}"]
    if isinstance(widget, QScrollBar):
        return None  # Its range follows the window size, not the panel's content.
    if isinstance(widget, QAbstractSlider):
        return "slider", _field_label(widget), [f"value={widget.value()}", f"range={widget.minimum()}..{widget.maximum()}"]
    if isinstance(widget, QAbstractButton):
        label = widget.text() or widget.accessibleName()
        if widget.isCheckable():
            return "checkable", label, [f"checked={'true' if widget.isChecked() else 'false'}"]
        return "button", label, []
    if isinstance(widget, QLineEdit):
        attributes = [f"value={_quote(widget.text())}"]
        if widget.placeholderText():
            attributes.append(f"placeholder={_quote(widget.placeholderText())}")
        if widget.isReadOnly():
            attributes.append("read-only")
        return "text", _field_label(widget), attributes
    if isinstance(widget, (QTextEdit, QPlainTextEdit)):
        attributes = [f"value={_quote(widget.toPlainText())}"]
        if widget.placeholderText():
            attributes.append(f"placeholder={_quote(widget.placeholderText())}")
        if widget.isReadOnly():
            attributes.append("read-only")
        return "text", _field_label(widget), attributes
    if isinstance(widget, QTableView) and widget.model() is not None:
        model = widget.model()
        headers = [str(model.headerData(c, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)) for c in range(model.columnCount())]
        return "list", _field_label(widget), [f"columns={_quote_list(headers)}", f"rows={model.rowCount()}"]
    if isinstance(widget, QAbstractItemView) and widget.model() is not None:
        return "list", _field_label(widget), _list_attributes(widget, widget.model())
    if isinstance(widget, QTabWidget):
        tabs = [widget.tabText(i) for i in range(widget.count())]
        return "tabs", widget.accessibleName(), [f"value={_quote(widget.tabText(widget.currentIndex()))}", f"items={_quote_list(tabs)}"]
    if isinstance(widget, QGroupBox):
        attributes = [f"checked={'true' if widget.isChecked() else 'false'}"] if widget.isCheckable() else []
        return "group", widget.title(), attributes
    if isinstance(widget, QLabel):
        if not widget.text() or widget.buddy() is not None or _labels_a_form_field(widget):
            return None
        return "label", widget.text(), []
    return None


def _labels_a_form_field(label: QLabel) -> bool:
    parent = label.parentWidget()
    if parent is None:
        return False
    for form in parent.findChildren(QFormLayout):
        for row in range(form.rowCount()):
            label_item = form.itemAt(row, QFormLayout.ItemRole.LabelRole)
            if label_item is not None and label_item.widget() is label:
                field = form.itemAt(row, QFormLayout.ItemRole.FieldRole)
                return field is not None and field.widget() is not None
    return False


def _skipped(widget: QWidget, panel: QWidget, excluded: list[QWidget]) -> bool:
    """True when the widget is inside a compound control or an excluded subtree."""
    if any(root is widget or root.isAncestorOf(widget) for root in excluded):
        return True
    parent = widget.parentWidget()
    while parent is not None and parent is not panel:
        if isinstance(parent, _COMPOUND_TYPES):
            return True
        parent = parent.parentWidget()
    return False


def panel_inventory(panel: QWidget, *, exclude: Iterable[QWidget] = ()) -> list[str]:
    """Describe every control inside `panel` in focus-chain order.

    Args:
        panel: The panel to walk; it does not need to be shown.
        exclude: Subtrees to leave out (for example the Chart Properties tab pages, which have their own goldens).

    Returns:
        One line per control: role, quoted label or accessible name, then values and the `hidden`/`disabled` flags,
        both relative to `panel`.
    """
    excluded = list(exclude)
    lines = []
    widget = panel.nextInFocusChain()
    seen: set[int] = set()
    while widget is not None and widget is not panel and id(widget) not in seen:
        seen.add(id(widget))
        if panel.isAncestorOf(widget) and not _skipped(widget, panel, excluded):
            description = _describe(widget)
            if description is not None:
                role, label, attributes = description
                if not widget.isVisibleTo(panel):
                    attributes.append("hidden")
                if not widget.isEnabledTo(panel):
                    attributes.append("disabled")
                line = f"{role} | {_quote(label)} |"
                lines.append(f"{line} {' '.join(attributes)}" if attributes else line)
        widget = widget.nextInFocusChain()
    return lines


def _comparable(line: str) -> str:
    """Return the line with its quoted label case-folded."""
    role, separator, rest = line.partition(" | ")
    try:
        label, end = json.JSONDecoder().raw_decode(rest)
    except json.JSONDecodeError:
        return line
    return f"{role}{separator}{_quote(str(label).casefold())}{rest[end:]}"


def assert_matches_golden(lines: list[str], golden: Path) -> None:
    """Fail with a unified diff unless `lines` match the golden file (label text compared case-insensitively).

    Args:
        lines: The current inventory.
        golden: The committed golden file. With `PANDAPLOT_UPDATE_GOLDENS=1` it is (re)written instead.

    Raises:
        AssertionError: If the golden is missing or differs.
    """
    if os.environ.get(UPDATE_ENV) == "1":
        golden.parent.mkdir(parents=True, exist_ok=True)
        golden.write_text("".join(f"{line}\n" for line in lines), encoding="utf-8")
        return
    hint = f"Rerun with {UPDATE_ENV}=1 to write it, then review the diff (tests/e2e/panel_inventory/README.md)."
    if not golden.exists():
        raise AssertionError(f"Missing panel inventory golden {golden}. {hint}")
    expected = golden.read_text(encoding="utf-8").splitlines()
    if [_comparable(line) for line in expected] == [_comparable(line) for line in lines]:
        return
    diff = "\n".join(difflib.unified_diff(expected, lines, fromfile=f"golden {golden.name}", tofile="current", lineterm=""))
    raise AssertionError(f"Panel inventory differs from {golden}:\n{diff}\n{hint}")
