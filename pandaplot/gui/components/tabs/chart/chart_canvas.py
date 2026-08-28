import logging

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

logger = logging.getLogger(__name__)


# Maps a NavigationToolbar2QT action name to its icon file, derived from
# matplotlib's own toolitems so it can't drift out of sync on a matplotlib upgrade.
NAV_ICON_FILES = {
    callback_name: image_file
    for _, _, image_file, callback_name in NavigationToolbar2QT.toolitems
    if callback_name
}


CM_PER_INCH = 2.54


def cm_to_inches(cm):
    """Convert centimeters to inches (matplotlib's Figure sizing is always in inches)."""
    return cm / CM_PER_INCH


def inches_to_cm(inches):
    """Convert inches to centimeters."""
    return inches * CM_PER_INCH


def set_figure_mathtext_parsing(fig, *, enabled: bool) -> None:
    """Enable or disable mathtext parsing on every text artist in `fig`.

    Matplotlib only parses a Text artist's mathtext (`$...$`) when it is
    actually measured or rendered -- i.e. during layout/draw, not when
    set_text()/set_xlabel()/etc. is called -- so invalid mathtext (e.g. an
    unbalanced `$...$` or `$\\theta_$` with no subscript body) surfaces as a
    ValueError/RuntimeError from tight_layout() or draw() rather than from
    whichever call actually set the text. Disabling parsing makes the text
    render literally instead, so a bad label degrades to raw text rather
    than breaking the whole figure."""
    for artist in fig.findobj(match=lambda o: hasattr(o, "set_parse_math")):
        artist.set_parse_math(enabled)


def run_with_mathtext_fallback(fig, action):
    """Run `action()` (a zero-arg callable that renders/lays out `fig`),
    falling back to literal (non-mathtext) text if it fails on invalid
    mathtext.

    Mathtext parsing is re-enabled for every text artist before the first
    attempt, so a label the user has since fixed is rendered as math again
    rather than staying disabled forever from an earlier failure. Only if
    that attempt still raises is parsing disabled and `action()` retried."""
    set_figure_mathtext_parsing(fig, enabled=True)
    try:
        action()
    except (ValueError, RuntimeError):
        logger.debug("invalid mathtext; retrying with mathtext parsing disabled", exc_info=True)
        set_figure_mathtext_parsing(fig, enabled=False)
        action()


def fit_size_cm(viewport_width_px, viewport_height_px, dpi,
                 min_width_cm=2, max_width_cm=50,
                 min_height_cm=2, max_height_cm=40):
    """Convert a pixel viewport size to a clamped chart size, rounded to 0.1 cm.

    Used to size a chart's initial preview to fill the visible preview
    panel when no size has been saved for it yet.
    """
    if dpi <= 0:
        raise ValueError(f"dpi must be positive, got {dpi}")
    width_cm = inches_to_cm(viewport_width_px / dpi)
    height_cm = inches_to_cm(viewport_height_px / dpi)
    width_cm = max(min_width_cm, min(max_width_cm, round(width_cm, 1)))
    height_cm = max(min_height_cm, min(max_height_cm, round(height_cm, 1)))
    return width_cm, height_cm


class ChartCanvas(FigureCanvas):
    """Custom matplotlib canvas for displaying charts."""

    def __init__(self, width=10, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="none")
        super().__init__(self.fig)
        self.axes = self.fig.add_subplot(111)
        self.axes2 = None  # Secondary Y axis (created via twinx() when needed)
        self.setParent(None)

        # Enable zoom and pan functionality
        self.setup_navigation()

        # Store original limits for reset functionality
        self.original_xlim = None
        self.original_ylim = None
        self.original_ylim2 = None
        self.original_zlim = None

    def draw(self):
        """Render the canvas, falling back to literal (non-mathtext) labels
        if a label/title contains invalid mathtext (e.g. `$\\theta_$`).

        Matplotlib only parses mathtext when a Text artist is actually
        measured or drawn, so a bad label raises here rather than when it
        was set -- without this, the exception propagates out of draw() and
        the preview is left showing a stale or partially-updated chart."""
        run_with_mathtext_fallback(self.fig, super().draw)

    def setup_navigation(self):
        """Set up zoom and pan functionality."""
        # Enable matplotlib's built-in navigation toolbar functionality
        # This provides zoom, pan, and reset functionality
        self.toolbar = NavigationToolbar2QT(self, self.parent())

        # Home/Back/Forward rely on matplotlib's own navigation stack, which
        # goes stale every time update_chart() clears and rebuilds the axes.
        # This app's "Reset Zoom" action (store_original_limits/reset_zoom)
        # covers the same need reliably, so drop the fragile duplicates.
        self._remove_toolbar_actions(("home", "back", "forward"))

        # Store the navigation toolbar for external access
        self.navigation_toolbar = self.toolbar

    def _remove_toolbar_actions(self, action_names):
        """Remove named actions (by their matplotlib callback name) from the nav toolbar."""
        actions_map = getattr(self.toolbar, "_actions", None)
        if actions_map is None:
            logger.debug("Navigation toolbar has no '_actions' mapping; skipping action removal")
            return

        for name in action_names:
            action = actions_map.pop(name, None)
            if action is not None:
                self.toolbar.removeAction(action)

        remaining = self.toolbar.actions()
        if remaining and remaining[0].isSeparator():
            self.toolbar.removeAction(remaining[0])

    def apply_navigation_theme(self, base_fg="#495057", surface_bg="#f8f9fa", border_color="#e9ecef"):
        """Apply theme-aware styling to the navigation toolbar."""
        if hasattr(self, "navigation_toolbar"):
            hover_bg = border_color
            pressed_bg = "#dee2e6"

            # More aggressive styling for matplotlib NavigationToolbar2QT
            self.navigation_toolbar.setStyleSheet(f"""
                QToolBar {{
                    background-color: {surface_bg};
                    border: 1px solid {border_color};
                    border-radius: 3px;
                    margin: 2px;
                    color: {base_fg};
                    spacing: 2px;
                }}
                QToolBar QToolButton {{
                    background-color: {surface_bg};
                    color: {base_fg};
                    border: 1px solid {border_color};
                    padding: 4px 6px;
                    margin: 1px;
                    border-radius: 3px;
                    font-size: 12px;
                    min-width: 24px;
                    min-height: 24px;
                }}
                QToolBar QToolButton:hover {{
                    background-color: {hover_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:pressed {{
                    background-color: {pressed_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:checked {{
                    background-color: {pressed_bg};
                    color: {base_fg};
                    border-color: {base_fg};
                }}
                QToolBar QToolButton:disabled {{
                    color: #999999;
                    background-color: {surface_bg};
                    border-color: #cccccc;
                }}
                QToolBar QLabel {{
                    color: {base_fg};
                    background-color: transparent;
                    padding: 2px;
                }}
                QToolBar QLineEdit {{
                    background-color: {surface_bg};
                    border: 1px solid {border_color};
                    color: {base_fg};
                    padding: 2px;
                    border-radius: 2px;
                }}
            """)

            # Force icon color update by setting the toolbar's palette
            # This is crucial for matplotlib's _icon() method to work correctly
            from PySide6.QtGui import QColor, QPalette
            palette = self.navigation_toolbar.palette()

            # Convert hex color to QColor
            fg_color = QColor(base_fg)
            bg_color = QColor(surface_bg)

            # Set palette colors that matplotlib's _icon() method checks
            # Matplotlib checks: self.palette().color(self.backgroundRole()).value() < 128
            # and uses: self.palette().color(self.foregroundRole())
            palette.setColor(QPalette.ColorRole.WindowText, fg_color)
            palette.setColor(QPalette.ColorRole.ButtonText, fg_color)
            palette.setColor(QPalette.ColorRole.Text, fg_color)
            palette.setColor(QPalette.ColorRole.Window, bg_color)
            palette.setColor(QPalette.ColorRole.Button, bg_color)
            palette.setColor(QPalette.ColorRole.Base, bg_color)

            self.navigation_toolbar.setPalette(palette)

            # Force toolbar to regenerate icons with new colors
            # This triggers matplotlib's icon color logic
            if hasattr(self.navigation_toolbar, "_actions"):
                for action_name, action in self.navigation_toolbar._actions.items():
                    if hasattr(action, "setIcon"):
                        # Get the original icon file name and regenerate it
                        # This forces matplotlib to re-evaluate the colors
                        try:
                            # Get the icon file from the toolbar's _icon method
                            # to force matplotlib to re-evaluate the colors
                            if action_name in NAV_ICON_FILES:
                                new_icon = self.navigation_toolbar._icon(
                                    f"{NAV_ICON_FILES[action_name]}.png")
                                action.setIcon(new_icon)
                        except Exception as e:
                            # If regeneration fails, continue with other actions
                            logger.debug(
                                "Failed to regenerate icon for %s: %s", action_name, e)

    @property
    def is_3d(self) -> bool:
        """Whether the main axes is currently an mplot3d axes.

        Read off the live axes object (matplotlib names the 3-D projection
        "3d") rather than tracked in a separate attribute, so it can never
        disagree with what was actually built.
        """
        return getattr(self.axes, "name", "") == "3d"

    def set_projection(self, *, projection_3d: bool) -> None:
        """Switch the main axes between the 2-D and 3-D (mplot3d)
        projection, rebuilding it only when the projection actually
        changes.

        A matplotlib Axes' projection is fixed at construction -- there is
        no set_projection() -- so switching chart type between a 2-D and a
        3-D type means replacing the axes object outright. Any secondary Y
        axis goes with it: it's a twinx() child of the axes being removed,
        and mplot3d has no twinx equivalent to recreate it on.

        The stored zoom-reset limits are dropped too, since they describe
        an axes that no longer exists; the next render's
        store_original_limits() re-seeds them.
        """
        if self.is_3d == projection_3d:
            return
        if self.axes2 is not None:
            self.axes2.remove()
            self.axes2 = None
        self.fig.delaxes(self.axes)
        self.axes = self.fig.add_subplot(111, projection="3d" if projection_3d else None)
        self.original_xlim = None
        self.original_ylim = None
        self.original_ylim2 = None
        self.original_zlim = None

    def store_original_limits(self):
        """Store the current axis limits as the reset-zoom baseline.

        Called after every re-render, so 'reset zoom' returns to the most
        recently configured view rather than the chart's very first render.
        """
        self.original_xlim = self.axes.get_xlim()
        self.original_ylim = self.axes.get_ylim()
        self.original_zlim = self.axes.get_zlim() if self.is_3d else None
        if self.axes2 is not None:
            self.original_ylim2 = self.axes2.get_ylim()

    def reset_zoom(self):
        """Reset zoom to original view."""
        if self.original_xlim is not None and self.original_ylim is not None:
            self.axes.set_xlim(self.original_xlim)
            self.axes.set_ylim(self.original_ylim)
            if self.is_3d and self.original_zlim is not None:
                self.axes.set_zlim(self.original_zlim)
            if self.axes2 is not None and self.original_ylim2:
                self.axes2.set_ylim(self.original_ylim2)
            self.draw()

    def set_size(
        self, width, height, pad: float = 2.0, w_pad: float = 2.0, h_pad: float = 2.0,
        top_margin: float = 1.0,
    ):
        """Change the figure size."""
        self.fig.set_size_inches(width, height)
        try:
            run_with_mathtext_fallback(
                self.fig,
                lambda: self.fig.tight_layout(pad=pad, w_pad=w_pad, h_pad=h_pad, rect=(0, 0, 1, top_margin)),
            )
        except Exception:
            logger.debug("tight_layout failed while resizing chart canvas", exc_info=True)
        self.resize(*self.get_width_height())
        self.draw()

    def set_dpi(
        self, dpi, pad: float = 2.0, w_pad: float = 2.0, h_pad: float = 2.0, top_margin: float = 1.0,
    ):
        """Change the figure DPI, keeping the widget's pixel size in sync."""
        if self.fig.dpi == dpi:
            return
        self.fig.set_dpi(dpi)
        try:
            run_with_mathtext_fallback(
                self.fig,
                lambda: self.fig.tight_layout(pad=pad, w_pad=w_pad, h_pad=h_pad, rect=(0, 0, 1, top_margin)),
            )
        except Exception:
            logger.debug("tight_layout failed while changing chart canvas DPI", exc_info=True)
        self.resize(*self.get_width_height())
        self.draw()
