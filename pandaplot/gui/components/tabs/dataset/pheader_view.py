"""Pandas custom header view that supports dtypes."""

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QFont, QPalette
from PySide6.QtWidgets import QHeaderView


def formula_marker(dataset, column_name: str) -> str:
    """Short header marker for a formula column (#154), or "" for a plain one.

    Borrowed from spreadsheets: "fx" says the displayed values came from an
    expression rather than being typed in; "fx live" says the expression is
    re-evaluated on its own when a source column changes.
    """
    if dataset is None:
        return ""
    spec = dataset.formula_column_by_name(column_name)
    if spec is None:
        return ""
    return "fx live" if spec.live else "fx"


def formula_tooltip(dataset, column_name: str) -> str | None:
    """Full explanation of a formula column for a header tooltip, or None."""
    if dataset is None:
        return None
    spec = dataset.formula_column_by_name(column_name)
    if spec is None:
        return None
    kind = (
        "Live formula column (recomputes automatically)"
        if spec.live
        else "Formula column (static until the transform is re-run)"
    )
    return f"{kind}\n{spec.expression}"


class PHeaderView(QHeaderView):
    """Custom header view that displays column number, name, and data type in two rows."""
    
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.dataset = None
        
    def set_dataset(self, dataset):
        """Set the dataset to get column information from."""
        self.dataset = dataset
        
    def paintSection(self, painter, rect, logical_index):
        """Paint a header section with custom two-row layout."""
        if not self.dataset or self.orientation() != Qt.Orientation.Horizontal:
            # Fall back to default painting for vertical headers or when no dataset
            super().paintSection(painter, rect, logical_index)
            return
            
        painter.save()
        
        # Clear the background
        painter.fillRect(rect, self.palette().button())
        
        # Draw border
        painter.setPen(self.palette().mid().color())
        painter.drawRect(rect)
        
        # Get column information
        column_name = str(self.dataset.data.columns[logical_index])
        column_dtype = str(self.dataset.data.dtypes.iloc[logical_index])
        column_number = logical_index + 1

        # Mark formula columns (#154) on the dtype line rather than the name
        # line, so the column's actual name stays readable in a narrow column.
        marker = formula_marker(self.dataset, column_name)
        if marker:
            column_dtype = f"{column_dtype}  {marker}"
        
        # Prepare fonts
        bold_font = QFont(painter.font())
        bold_font.setBold(True)
        
        italic_font = QFont(painter.font())
        italic_font.setItalic(True)
        italic_font.setPointSize(max(8, italic_font.pointSize() - 1))  # Smaller font for dtype
        
        # Calculate text areas
        top_rect = QRect(rect.x() + 4, rect.y() + 2, rect.width() - 8, rect.height() // 2)
        bottom_rect = QRect(rect.x() + 4, rect.y() + rect.height() // 2, rect.width() - 8, rect.height() // 2)
        
        # Draw first line: "1 - Speed"
        painter.setFont(bold_font)
        painter.setPen(self.palette().text().color())
        first_line = f"{column_number} - {column_name}"
        painter.drawText(top_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, first_line)
        
        # Draw second line: data type. QPalette.Mid is derived automatically
        # from the Button color assuming a light theme, so in dark theme
        # (dark Button color) it comes out darker still -- nearly invisible
        # against the dark background. PlaceholderText is explicitly set
        # per-theme (theme_manager._apply_to_qapp) to a color halfway between
        # the theme's text and background, so it stays legible-but-muted in
        # both themes.
        painter.setFont(italic_font)
        painter.setPen(self.palette().color(QPalette.ColorRole.PlaceholderText))
        painter.drawText(bottom_rect, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, column_dtype)
        
        painter.restore()
        
    def sizeHint(self):
        """Return size hint for the header - make it taller for two rows."""
        hint = super().sizeHint()
        if self.orientation() == Qt.Orientation.Horizontal:
            hint.setHeight(max(50, hint.height()))  # Ensure adequate height for two lines
        return hint