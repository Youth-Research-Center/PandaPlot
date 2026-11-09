"""An icon plus wrapped plain text for success, error, warning and information messages."""

from enum import Enum

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QHBoxLayout, QLabel, QSizePolicy, QWidget

from pandaplot.gui.components.common.icon_label import IconLabel
from pandaplot.gui.resources.themed_icons import IconRole
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class StatusKind(Enum):
    """The kind of a status message: its icon, its tint and the word read out by assistive technology."""

    SUCCESS = ("check-circle", IconRole.SUCCESS, "Success")
    ERROR = ("x-circle", IconRole.ERROR, "Error")
    WARNING = ("warning", IconRole.WARNING, "Warning")
    INFO = ("info", IconRole.INFO, "Information")

    @property
    def icon_name(self) -> str:
        """Name of the bundled icon shown for this kind."""
        return self.value[0]

    @property
    def role(self) -> IconRole:
        """Icon role whose token tints the icon."""
        return self.value[1]

    @property
    def label(self) -> str:
        """Word that names the kind, e.g. ``"Error"``."""
        return self.value[2]


class StatusMessage(QWidget):
    """A status message: a kind-coloured icon beside word-wrapped plain text.

    The widget is hidden while it has no message. The icon is decorative; the whole widget exposes
    ``"<Kind>: <text>"`` as its accessible description. The owner calls `retint()` from its theme handler.

    Args:
        app_context: Provides the `ThemeManager` whose design tokens supply the colours.
        parent: Parent widget.
    """

    def __init__(self, app_context: AppContext, *, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._app_context = app_context
        self._kind: StatusKind | None = None
        self._message = ""
        self._icon: IconLabel | None = None

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(8)

        self._text = QLabel()
        self._text.setTextFormat(Qt.TextFormat.PlainText)
        self._text.setWordWrap(True)
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self._layout.addWidget(self._text, 1)

        self._apply_text_colour()
        self.setVisible(False)

    def set_message(self, kind: StatusKind, text: str) -> None:
        """Show `text` with the icon of `kind`; an empty `text` clears the message."""
        if not text:
            self.clear()
            return
        if kind is not self._kind or self._icon is None:
            self._replace_icon(kind)
        self._kind = kind
        self._message = text
        self._text.setText(text)
        self.setAccessibleDescription(f"{kind.label}: {text}")
        self.setVisible(True)

    def clear(self) -> None:
        """Remove the message and hide the widget."""
        self._kind = None
        self._message = ""
        self._text.clear()
        self.setAccessibleDescription("")
        self.setVisible(False)

    def message(self) -> str:
        """The text currently shown, or an empty string."""
        return self._message

    def kind(self) -> StatusKind | None:
        """The kind of the message currently shown, or ``None`` while empty."""
        return self._kind

    def retint(self) -> None:
        """Re-render the icon and text colour from the current theme tokens."""
        self._apply_text_colour()
        if self._icon is not None:
            self._icon.retint()

    def _replace_icon(self, kind: StatusKind) -> None:
        if self._icon is not None:
            self._layout.removeWidget(self._icon)
            self._icon.setParent(None)
            self._icon.deleteLater()
        self._icon = IconLabel(self._app_context, kind.icon_name, role=kind.role, parent=self)
        self._layout.insertWidget(0, self._icon, 0, Qt.AlignmentFlag.AlignTop)

    def _apply_text_colour(self) -> None:
        tokens = self._app_context.get_manager(ThemeManager).get_design_tokens()
        palette = self._text.palette()
        palette.setColor(QPalette.ColorRole.WindowText, QColor(tokens["text_primary"]))
        self._text.setPalette(palette)
