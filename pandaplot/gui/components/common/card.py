from PySide6.QtWidgets import QFrame, QWidget


class Card(QFrame):
    """Bordered, rounded container (Range/Ticks/Frame groups)."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setProperty("card", True)  # noqa: FBT003 -- Qt bound method, positional-only
        self.setContentsMargins(9, 9, 9, 9)

    def set_tokens(self, tokens: dict):
        # Styling is entirely QSS-driven (see ThemeManager.build_stylesheet);
        # re-polish so a live theme change is picked up immediately.
        self.style().unpolish(self)
        self.style().polish(self)
