from PySide6.QtWidgets import QLabel, QWidget


class SectionHeader(QLabel):
    """Small-caps uppercase group-title label (e.g. 'SERIES', 'LINE')."""

    def __init__(self, text: str, parent: QWidget | None = None):
        super().__init__(text.upper(), parent)
        self.set_tokens({})

    def set_tokens(self, tokens: dict):
        color = tokens.get("text_muted", "#6B7280")
        disabled_color = tokens.get("text_disabled", "#AEB2BC")
        self.setStyleSheet(
            f"QLabel {{ font-size: 10.5px; font-weight: 700; letter-spacing: 1px; color: {color}; }}"
            f"QLabel:disabled {{ color: {disabled_color}; }}"
        )
