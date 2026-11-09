"""Wizard labels for the data-column roles of a chart series (shared by the wizard and the help text)."""

ROLE_LABELS: dict[str, str] = {
    "x": "X column", "y": "Y column", "values": "Values column",
    "u": "U column", "v": "V column", "w": "W column",
    "magnitude": "Color-by column (optional)",
    # Plain "Z column" rather than "Z (color) column": Z drives point color
    # on a Colormap/Heatmap chart but is the third spatial axis on every
    # 3-D one, and one label has to be true of both.
    "z": "Z column",
    "labels": "Labels column (optional)",
}
