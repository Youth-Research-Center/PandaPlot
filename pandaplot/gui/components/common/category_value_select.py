"""A value picker split in two dropdowns: a category, then a value in it."""
from collections.abc import Sequence
from typing import cast

from PySide6.QtCore import QObject, QSignalBlocker, Signal
from PySide6.QtGui import QStandardItemModel

from pandaplot.gui.components.common.value_combo_box import ValueComboBox


class CategoryValueSelect(QObject):
    """Two linked dropdowns: pick a category, then one of its values.

    Only the current category's values are listed at a time, so a long
    catalogue (the chart types) never has to be shown whole. The selector
    does not lay its dropdowns out: the owner adds `category_combo` and
    `value_combo` to its own layout, which lets each sit on a labelled row.

    Exposes the `currentValue()` / `setCurrentValue()` / `currentValueChanged`
    API of `ValueComboBox`. As there, `setCurrentValue()` does not emit.
    Choosing a category selects its first enabled value and emits once.

    A value can be disabled (with a tooltip saying why) through
    `set_value_enabled()`. A category whose values are all disabled is
    disabled too, unless it holds the current value.
    """

    currentValueChanged = Signal(object)

    def __init__(
        self,
        groups: Sequence[tuple[str, Sequence[tuple[str, object]]]],
        parent: QObject | None = None,
    ) -> None:
        """Args:
            groups: `(category label, [(value label, value), ...])` pairs in
                display order. Every category must hold at least one value.

        Raises:
            ValueError: If there are no categories, or one has no values.
        """
        super().__init__(parent)
        if not groups:
            raise ValueError("CategoryValueSelect requires at least one category")
        for label, values in groups:
            if not values:
                raise ValueError(f"Category {label!r} has no values")
        self._groups: list[tuple[str, tuple[tuple[str, object], ...]]] = [(label, tuple(values)) for label, values in groups]
        self._disabled: dict[object, str] = {}

        self.category_combo = ValueComboBox([(label, label) for label, _values in self._groups])
        self.category_combo.setAccessibleName("Category")
        self.value_combo = ValueComboBox(list(self._groups[0][1]))
        self.value_combo.setAccessibleName("Type")

        self.category_combo.currentValueChanged.connect(self._on_category_changed)
        self.value_combo.currentValueChanged.connect(self.currentValueChanged)

    def currentValue(self) -> object:
        return self.value_combo.currentValue()

    def setCurrentValue(self, value: object) -> None:
        """Select `value`, switching category if needed. Does not emit; a
        value in no category is ignored."""
        category_index = self._category_index_of(value)
        if category_index is None:
            return
        with QSignalBlocker(self.category_combo), QSignalBlocker(self.value_combo):
            self.category_combo.setCurrentIndex(category_index)
            self._populate_values(category_index)
            self.value_combo.setCurrentIndex(self.value_combo.findData(value))
        self._refresh_category_states()

    def set_value_enabled(self, value: object, *, enabled: bool, tooltip: str = "") -> None:
        """Enable or disable `value`; `tooltip` explains a disabled one."""
        if enabled:
            self._disabled.pop(value, None)
        else:
            self._disabled[value] = tooltip
        self._apply_value_states()
        self._refresh_category_states()

    def is_value_enabled(self, value: object) -> bool:
        return value not in self._disabled

    def value_tooltip(self, value: object) -> str:
        return self._disabled.get(value, "")

    def set_tokens(self, tokens: dict) -> None:
        self.category_combo.set_tokens(tokens)
        self.value_combo.set_tokens(tokens)

    def _category_index_of(self, value: object) -> int | None:
        return next((index for index, (_label, values) in enumerate(self._groups) if any(v == value for _l, v in values)), None)

    def _populate_values(self, category_index: int) -> None:
        with QSignalBlocker(self.value_combo):
            self.value_combo.clear()
            for label, value in self._groups[category_index][1]:
                self.value_combo.addItem(label, value)
        self._apply_value_states()

    def _apply_value_states(self) -> None:
        model = cast(QStandardItemModel, self.value_combo.model())
        for index in range(self.value_combo.count()):
            value = self.value_combo.itemData(index)
            item = model.item(index)
            item.setEnabled(value not in self._disabled)
            item.setToolTip(self._disabled.get(value, ""))

    def _refresh_category_states(self) -> None:
        current = self.category_combo.currentIndex()
        for index, (_label, values) in enumerate(self._groups):
            all_disabled = index != current and all(value in self._disabled for _l, value in values)
            item = cast(QStandardItemModel, self.category_combo.model()).item(index)
            item.setEnabled(not all_disabled)
            item.setToolTip("None of this category's types can be used for this chart" if all_disabled else "")

    def _on_category_changed(self, _label: object) -> None:
        index = self.category_combo.currentIndex()
        self._populate_values(index)
        values = [value for _l, value in self._groups[index][1]]
        first = next((value for value in values if value not in self._disabled), values[0])
        with QSignalBlocker(self.value_combo):
            self.value_combo.setCurrentIndex(self.value_combo.findData(first))
        # The category just left no longer holds the current value, so it may
        # now be fully disabled.
        self._refresh_category_states()
        self.currentValueChanged.emit(first)
