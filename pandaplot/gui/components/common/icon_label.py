"""A decorative themed icon for headers and messages (the adjacent text carries the meaning)."""

from PySide6.QtCore import QSize
from PySide6.QtWidgets import QLabel, QWidget

from pandaplot.gui.resources.themed_icons import DEFAULT_ICON_SIZE, IconRole, themed_icon
from pandaplot.models.state.app_context import AppContext


class IconLabel(QLabel):
    """A fixed-size label showing a bundled icon tinted from the design tokens.

    The owner calls `retint()` from its theme handler. The icon is decorative, so it has no accessible name.
    """

    def __init__(
        self,
        app_context: AppContext,
        icon_name: str,
        *,
        size: int = DEFAULT_ICON_SIZE,
        role: IconRole = IconRole.TEXT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._app_context = app_context
        self._icon_name = icon_name
        self._size = size
        self._role = role
        self.setFixedSize(size, size)
        self.retint()

    @property
    def icon_name(self) -> str:
        """Name of the bundled icon shown."""
        return self._icon_name

    def retint(self) -> None:
        """Re-render the icon from the current theme tokens.

        Raises:
            KeyError: If the icon is not bundled.
        """
        icon = themed_icon(self._app_context, self._icon_name, role=self._role, size=self._size)
        self.setPixmap(icon.pixmap(QSize(self._size, self._size)))
