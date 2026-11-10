"""Stylesheet shared by the forms that host `SeriesConfigCard`: the chart wizard and
the Add Series dialog."""


def series_form_stylesheet(palette: dict, *, scope: str) -> str:
    """Build the widget rules for labels, check boxes, line edits and lists in a series form.

    Every rule is prefixed with `scope` so it only reaches descendants of that selector and
    does not leak into other top-level windows parented to the form (such as the Help window).

    Args:
        palette: Surface palette from `ThemeManager.get_surface_palette()`.
        scope: Qt type selector the rules are scoped to (e.g. `"QWizardPage"`).

    Returns:
        The stylesheet text, one rule per widget kind, ending in a newline.
    """
    card_bg = palette.get("card_bg", "#f8f9fa")
    card_border = palette.get("card_border", "#dee2e6")
    base_fg = palette.get("base_fg", "#000000")
    secondary_fg = palette.get("secondary_fg", "#555555")
    accent = palette.get("accent", "#4A90E2")
    # Inputs sit one shade off the surface so fields read as distinct wells.
    input_bg = palette.get("card_hover", "#e9ecef")

    return f"""
            {scope} QLabel, {scope} QCheckBox {{
                color: {base_fg};
            }}
            {scope} QCheckBox::indicator {{
                width: 14px;
                height: 14px;
                border: 1px solid {card_border};
                border-radius: 3px;
                background-color: {input_bg};
            }}
            {scope} QCheckBox::indicator:checked {{
                background-color: {accent};
                border-color: {accent};
            }}
            {scope} QLineEdit {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                padding: 4px 8px;
                min-height: 22px;
                color: {base_fg};
            }}
            {scope} QLineEdit:focus {{
                border-color: {accent};
            }}
            {scope} QLineEdit:hover {{
                border-color: {accent};
            }}
            {scope} QLineEdit:disabled {{
                color: {secondary_fg};
                background-color: {card_bg};
                border-color: {card_border};
            }}
            {scope} QListWidget {{
                background-color: {input_bg};
                border: 1px solid {card_border};
                border-radius: 4px;
                color: {base_fg};
                outline: none;
            }}
            {scope} QListWidget::item {{
                padding: 4px 6px;
            }}
            {scope} QListWidget::item:selected {{
                background-color: {accent};
                color: white;
            }}
"""
