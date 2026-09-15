"""A headless (no Qt widget) stand-in for ChartCanvas, implementing the
same narrow interface render_chart() uses -- .fig, .axes, .axes2,
.original_ylim2, .is_3d, .set_projection(), .store_original_limits(),
.draw(), .set_size(), .set_dpi() -- backed by matplotlib's plain
FigureCanvasAgg instead of FigureCanvasQTAgg.

Exists so a chart can be rendered on any thread (TaskScheduler worker
threads included): FigureCanvasQTAgg is a real QWidget, and Qt widgets can
only be constructed on the GUI thread, but FigureCanvasAgg has no such
restriction -- matplotlib's Agg backend doesn't touch Qt at all (the same
property pandaplot.services.note_render.latex_markdown_renderer.py already
relies on for headless equation rendering).

Deliberately does NOT implement anything ChartCanvas has for interactive
use only (navigation toolbar, zoom/pan, reset_zoom) -- a headless render
is a one-shot, non-interactive image.
"""
import logging

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.chart_canvas import run_with_mathtext_fallback

logger = logging.getLogger(__name__)


class HeadlessChartCanvas(FigureCanvasAgg):
    """Headless counterpart to ChartCanvas -- see module docstring."""

    def __init__(self, width=10, height=6, dpi=100):
        self.fig = Figure(figsize=(width, height), dpi=dpi, facecolor="none")
        super().__init__(self.fig)
        self.axes = self.fig.add_subplot(111)
        self.axes2 = None  # Secondary Y axis (created via twinx() when needed)

        self.original_xlim = None
        self.original_ylim = None
        self.original_ylim2 = None
        self.original_zlim = None

    def draw(self):
        """Render into the Agg buffer, falling back to literal (non-mathtext)
        labels on invalid mathtext -- same behavior as ChartCanvas.draw()."""
        run_with_mathtext_fallback(self.fig, super().draw)

    @property
    def is_3d(self) -> bool:
        return getattr(self.axes, "name", "") == "3d"

    def set_projection(self, *, projection_3d: bool) -> None:
        """See ChartCanvas.set_projection() -- identical logic, no Qt involved."""
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
        """See ChartCanvas.store_original_limits()."""
        self.original_xlim = self.axes.get_xlim()
        self.original_ylim = self.axes.get_ylim()
        self.original_zlim = self.axes.get_zlim() if self.is_3d else None
        if self.axes2 is not None:
            self.original_ylim2 = self.axes2.get_ylim()

    def set_size(
        self, width, height, pad: float = 2.0, w_pad: float = 2.0, h_pad: float = 2.0,
        top_margin: float = 1.0,
    ):
        """Change the figure size. Unlike ChartCanvas.set_size(), there is
        no widget to resize() afterward -- this canvas is never shown."""
        self.fig.set_size_inches(width, height)
        try:
            run_with_mathtext_fallback(
                self.fig,
                lambda: self.fig.tight_layout(pad=pad, w_pad=w_pad, h_pad=h_pad, rect=(0, 0, 1, top_margin)),
            )
        except Exception:
            logger.debug("tight_layout failed while resizing chart canvas", exc_info=True)
        self.draw()

    def set_dpi(
        self, dpi, pad: float = 2.0, w_pad: float = 2.0, h_pad: float = 2.0, top_margin: float = 1.0,
    ):
        """Change the figure DPI. Unlike ChartCanvas.set_dpi(), there is no
        widget to resize() afterward -- this canvas is never shown."""
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
        self.draw()
