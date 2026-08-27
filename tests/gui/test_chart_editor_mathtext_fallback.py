"""Regression test for issue #194: invalid mathtext in an axis/plot label
(e.g. an incomplete `$\\theta_$`, or any unbalanced `$...$`) raised a
ValueError out of `fig.tight_layout()` inside `apply_layout_with_legend`,
which stopped `update_chart` before it reached `self.chart_canvas.draw()`
and left the preview stuck on a stale/blank render.

`apply_layout_with_legend` now catches the mathtext failure and disables
math parsing for the figure's text artists so they render literally
instead."""
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.chart_canvas import ChartCanvas, set_figure_mathtext_parsing
from pandaplot.gui.components.tabs.chart.chart_editor import apply_layout_with_legend

INVALID_MATHTEXT = r"$\theta_$"


def test_apply_layout_with_legend_falls_back_on_invalid_mathtext_label():
    fig = Figure(figsize=(6, 4))
    axes = fig.add_subplot(111)
    axes.plot([1, 2, 3], [1, 2, 3])
    axes.set_xlabel(INVALID_MATHTEXT)

    # Would raise ValueError from matplotlib's mathtext parser before the fix.
    apply_layout_with_legend(fig, tight_layout_kwargs={}, legend_placed_outside=False)

    canvas = FigureCanvasAgg(fig)
    canvas.draw()  # Must not raise now that mathtext parsing was disabled.
    assert axes.xaxis.label.get_text() == INVALID_MATHTEXT


def test_apply_layout_with_legend_recovers_mathtext_after_label_is_fixed():
    """A label that was invalid but has since been corrected should render as
    math again -- parsing must not stay disabled forever on that Text artist."""
    fig = Figure(figsize=(6, 4))
    axes = fig.add_subplot(111)
    axes.plot([1, 2, 3], [1, 2, 3])
    axes.set_xlabel(INVALID_MATHTEXT)
    apply_layout_with_legend(fig, tight_layout_kwargs={}, legend_placed_outside=False)
    assert axes.xaxis.label.get_parse_math() is False

    axes.set_xlabel(r"$\theta$")
    apply_layout_with_legend(fig, tight_layout_kwargs={}, legend_placed_outside=False)
    assert axes.xaxis.label.get_parse_math() is True


def test_chart_canvas_draw_falls_back_on_invalid_mathtext_title():
    canvas = ChartCanvas()
    canvas.axes.plot([1, 2, 3], [1, 2, 3])
    canvas.axes.set_title(INVALID_MATHTEXT)

    canvas.draw()  # Must not raise; ChartCanvas.draw() should self-heal.
    assert canvas.axes.title.get_text() == INVALID_MATHTEXT


def test_set_figure_mathtext_parsing_toggles_all_text_artists():
    fig = Figure(figsize=(6, 4))
    axes = fig.add_subplot(111)
    axes.plot([1, 2, 3], [1, 2, 3], label="Series One")
    axes.set_xlabel(r"$x$")
    axes.legend()

    set_figure_mathtext_parsing(fig, enabled=False)
    assert axes.xaxis.label.get_parse_math() is False

    set_figure_mathtext_parsing(fig, enabled=True)
    assert axes.xaxis.label.get_parse_math() is True
