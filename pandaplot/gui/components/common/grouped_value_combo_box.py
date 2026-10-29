from collections.abc import Sequence
from typing import cast

from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import QWidget

from pandaplot.gui.components.common.grouped_list import GroupedListView, configure_group_header
from pandaplot.gui.components.common.value_combo_box import ValueComboBox


class GroupedValueComboBox(ValueComboBox):
    """ValueComboBox whose items are listed under group headers.

    Each header is a disabled item with no value (see grouped_list.py):
    QComboBox skips disabled items when navigating with the arrow keys or the
    wheel, the popup's GroupedListView keeps Home/End/PageUp/PageDown off
    them, and findData() never matches one, so a header can't become the
    current item. A group with no items gets no header. Anything iterating
    the items by index must skip rows where is_header() is True.
    """

    def __init__(
        self,
        groups: Sequence[tuple[str, Sequence[tuple[str, object]]]],
        parent: QWidget | None = None,
    ):
        super().__init__([item for _header, items in groups for item in items], parent=parent)
        # Replaces DropDownComboBox's plain QListView; still an explicit view,
        # so the popup keeps opening below the field.
        self.setView(GroupedListView())

        # QComboBox's default model; making an item a header needs its flags.
        model = cast(QStandardItemModel, self.model())
        # Inserted after the values so ValueComboBox's construction is
        # unchanged; signals are blocked because inserting above the current
        # item moves its index, which isn't a change of value.
        self.blockSignals(True)  # noqa: FBT003 -- Qt bound method, positional-only
        row = 0
        for header, items in groups:
            if not items:
                continue
            self.insertItem(row, header)
            configure_group_header(model.item(row), header)
            row += len(items) + 1
        self.blockSignals(False)  # noqa: FBT003 -- Qt bound method, positional-only

    def is_header(self, index: int) -> bool:
        """Whether the item at `index` is a group header rather than a value."""
        return self.itemData(index) is None
