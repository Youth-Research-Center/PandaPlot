"""Bundled icons that mark each project item type in tabs, trees, search results and pickers."""

from PySide6.QtGui import QIcon

from pandaplot.gui.resources.themed_icons import DEFAULT_ICON_SIZE, themed_icon
from pandaplot.models.state.app_context import AppContext

ITEM_TYPE_ICON_NAMES: dict[str, str] = {
    "project": "folder",
    "folder": "folder-simple",
    "collection": "folder-simple",
    "note": "note-pencil",
    "dataset": "table",
    "chart": "chart-line",
    "imagegallery": "images",
    "image": "image",
    "sketch": "pencil-simple-line",
}

DEFAULT_ITEM_ICON_NAME = "file"

# Foreground of a selected row in the project tree and the search results, whose selected rows are painted with the accent colour.
SELECTED_ROW_FOREGROUND = "#FFFFFF"


def item_icon_name(item_type: str) -> str:
    """Return the bundled icon name for an item type, or the default file icon for an unknown type."""
    return ITEM_TYPE_ICON_NAMES.get(item_type, DEFAULT_ITEM_ICON_NAME)


def item_icon(app_context: AppContext, item_type: str, *, size: int = DEFAULT_ICON_SIZE, selected_color: str | None = None) -> QIcon:
    """Render the icon of an item type tinted for the current theme.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        item_type: Project item type such as ``"dataset"`` or ``"chart"``.
        size: Logical pixel size of the square icon.
        selected_color: Colour of the icon on a selected row, for views whose selection colour differs from the theme's text colour.

    Returns:
        The icon for `item_type`, or the default file icon when the type is unknown.
    """
    return themed_icon(app_context, item_icon_name(item_type), size=size, selected_color=selected_color)
