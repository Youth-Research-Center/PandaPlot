"""Semantic styling hooks for sidebar text, applied by ThemeManager.

A role (``QLabel[role="hint"]`` ...) or the ``error`` flag on a result text
area is a dynamic property rather than a per-widget stylesheet, so every panel
shows helper text, errors and warnings in the same theme colours and the
colours follow the theme without each panel re-applying them.
"""
from __future__ import annotations

from typing import Literal

from PySide6.QtWidgets import QLabel, QPlainTextEdit, QTextEdit

LabelRole = Literal["hint", "error", "warning", "code"]


def set_label_role(label: QLabel, role: LabelRole | None) -> None:
    """Give ``label`` a semantic role, or clear it with ``None``.

    Args:
        label: The label to style.
        role: ``"hint"`` for secondary helper text, ``"error"`` for a problem,
            ``"warning"`` for something to be careful about, ``"code"`` for a
            monospace boxed value such as a fitted equation, ``None`` for plain text.
    """
    new_role = role or ""
    if (label.property("role") or "") == new_role:
        return
    label.setProperty("role", new_role)
    label.style().unpolish(label)
    label.style().polish(label)


def set_error_state(text_area: QTextEdit | QPlainTextEdit, *, error: bool) -> None:
    """Show a result text area's content in the danger colour, or back to normal.

    Args:
        text_area: A result or preview text area inside a sidebar panel.
        error: Whether the text is an error message.
    """
    if bool(text_area.property("error")) == error:
        return
    text_area.setProperty("error", error)
    text_area.style().unpolish(text_area)
    text_area.style().polish(text_area)
