"""Shared refusal for edits that would overwrite a live formula column (#154).

A live formula column is derived data: its values are whatever its formula
yields, and they change when a source column changes. Writing into it by hand
would leave it disagreeing with its own formula until the next recompute undoes
the edit, so every command that writes cell values refuses up front instead.
"""

from collections.abc import Iterable

from pandaplot.gui.controllers.ui_controller import UIController
from pandaplot.models.project.items.dataset import Dataset


def refuse_live_formula_edit(
    dataset: Dataset,
    ui_controller: UIController,
    *,
    title: str,
    column_names: Iterable[str] = (),
    column_positions: Iterable[int] = (),
) -> bool:
    """Warn and return True if an edit would touch a live formula column.

    Args:
        dataset: The dataset being edited.
        ui_controller: Used to tell the user why the edit was refused.
        title: Title of the warning dialog (the command's usual title).
        column_names: Names of the columns the edit would write to.
        column_positions: Positions of further columns it would write to;
            positions outside the dataset are ignored.

    Returns:
        True if at least one of the columns is a live formula column and the
        user has been told; the caller should then abort without changing
        anything.
    """
    columns = [str(column) for column in dataset.data.columns]
    names = [str(name) for name in column_names]
    names += [columns[position] for position in column_positions if 0 <= position < len(columns)]

    live = [name for name in dict.fromkeys(names) if dataset.is_live_formula_column(name)]
    if not live:
        return False

    quoted = ", ".join(f"'{name}'" for name in live)
    if len(live) == 1:
        message = f"Column {quoted} is computed by a live formula and can't be edited directly. Edit its source column instead."
    else:
        message = f"Columns {quoted} are computed by live formulas and can't be edited directly. Edit their source columns instead."
    ui_controller.show_warning_message(title, message)
    return True
