"""Shared "Insert function" menu builder for the dataset TransformPanel and
ChartTransformPanel -- both offer a categorized menu of ready-made
transformation expressions with the same shape (see #284)."""

from typing import Callable

from PySide6.QtWidgets import QMenu, QWidget


def build_function_menu(
    parent: QWidget,
    templates: dict[str, list[dict]],
    on_insert: Callable[[str], None],
) -> QMenu:
    """Build a categorized menu of ready-made transformation functions.

    `templates` maps a category name to a list of entries, each a dict with
    "name" (the menu label), "description", and "code" keys -- the shape
    returned by both TransformController.get_transformation_templates() and
    expression_engine.get_transformation_templates(). Selecting an entry
    calls `on_insert(entry["code"])`.
    """
    menu = QMenu(parent)
    for category, entries in templates.items():
        submenu = menu.addMenu(category)
        for entry in entries:
            action = submenu.addAction(entry["name"])
            action.setToolTip(f"{entry['description']}  →  {entry['code']}")
            action.triggered.connect(
                lambda _checked=False, code=entry["code"]: on_insert(code)
            )
    menu.setToolTipsVisible(True)
    return menu
