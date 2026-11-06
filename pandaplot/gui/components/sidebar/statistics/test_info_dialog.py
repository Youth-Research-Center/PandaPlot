"""
Educational info dialog for statistical tests.

Shows a learner-friendly explanation, a simple mathematical formula and a
worked example for a given test, so users can understand what they are running.
"""

import html

from PySide6.QtWidgets import QDialog, QDialogButtonBox, QTextBrowser, QVBoxLayout

from pandaplot.analysis import StatTestInfo
from pandaplot.models.state.app_context import AppContext
from pandaplot.services.theme.theme_manager import ThemeManager


class InfoDialogHelper(QDialog):
    """A small dialog that explains a statistical test to the user."""

    def __init__(self, app_context: AppContext, info: StatTestInfo, parent=None):
        super().__init__(parent)
        self.app_context = app_context
        self.info = info

        self.setWindowTitle(f"About: {info.label}")
        self.setModal(True)
        self.resize(460, 560)

        layout = QVBoxLayout(self)

        self.browser = QTextBrowser()
        self.browser.setOpenExternalLinks(False)
        self.browser.setHtml(self._build_html())
        layout.addWidget(self.browser)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # HTML rendering
    # ------------------------------------------------------------------

    @staticmethod
    def _prose(text: str) -> str:
        """Render plain text with paragraph/line breaks as safe HTML."""
        if not text:
            return ""
        paragraphs = [p for p in text.split("\n\n")]
        rendered = []
        for para in paragraphs:
            rendered.append("<p>" + html.escape(para).replace("\n", "<br>") + "</p>")
        return "".join(rendered)

    def _palette(self) -> dict:
        theme_manager = self.app_context.get_manager(ThemeManager)
        return theme_manager.get_surface_palette()

    def _build_html(self) -> str:
        palette = self._palette()
        base_fg = palette.get("base_fg", "#333333")
        secondary_fg = palette.get("secondary_fg", "#666666")
        accent = palette.get("accent", "#4A90E2")
        card_bg = palette.get("card_bg", "#ffffff")
        code_bg = palette.get("card_border", "#eef1f4")

        info = self.info
        explanation = info.explanation or info.description

        sections = []
        sections.append(f"<h2 style='color:{base_fg};margin:0 0 4px 0;'>{html.escape(info.label)}</h2>")

        if explanation:
            sections.append(f"<h3 style='color:{accent};'>What it does</h3>")
            sections.append(f"<div style='color:{base_fg};'>{self._prose(explanation)}</div>")

        if info.formula:
            formula_html = html.escape(info.formula).replace("\n", "<br>")
            sections.append(f"<h3 style='color:{accent};'>Formula</h3>")
            sections.append(
                f"<div style='background-color:{code_bg};color:{base_fg};padding:10px;"
                f"border-radius:4px;font-family:Menlo,Consolas,monospace;font-size:10pt;'>{formula_html}</div>"
            )

        if info.assumptions:
            sections.append(f"<h3 style='color:{accent};'>Assumptions</h3>")
            sections.append(f"<div style='color:{secondary_fg};'>{self._prose(info.assumptions)}</div>")

        if info.example:
            sections.append(f"<h3 style='color:{accent};'>Example</h3>")
            sections.append(f"<div style='color:{base_fg};'>{self._prose(info.example)}</div>")

        body = "".join(sections)
        return (
            f"<body style='background-color:{card_bg};line-height:1.4;'>"
            f"{body}</body>"
        )
