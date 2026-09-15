"""HeadlessChartCanvas must expose the same narrow interface
ChartCanvas does for everything render_chart() touches, without any Qt
widget -- so it's safe to construct and use on a background thread."""
from pandaplot.gui.components.tabs.chart.headless_chart_canvas import HeadlessChartCanvas


def test_basic_construction_and_plotting():
    canvas = HeadlessChartCanvas(width=6, height=4, dpi=80)
    assert canvas.axes is not None
    assert canvas.axes2 is None
    assert canvas.is_3d is False

    canvas.axes.plot([1, 2, 3], [4, 5, 6])
    canvas.store_original_limits()
    canvas.draw()  # must not raise, and must not require any Qt/GUI setup

    assert canvas.original_xlim is not None
    assert canvas.original_ylim is not None


def test_set_projection_switches_to_3d_and_back():
    canvas = HeadlessChartCanvas()
    canvas.set_projection(projection_3d=True)
    assert canvas.is_3d is True
    canvas.axes.plot([1, 2], [3, 4], [5, 6])  # 3-D plot call must work

    canvas.set_projection(projection_3d=False)
    assert canvas.is_3d is False


def test_set_size_and_set_dpi_do_not_raise():
    canvas = HeadlessChartCanvas()
    canvas.axes.plot([1, 2, 3], [1, 4, 9])
    canvas.set_size(8, 5)
    canvas.set_dpi(150)
    assert canvas.fig.dpi == 150


def test_savefig_produces_png_bytes():
    import io
    canvas = HeadlessChartCanvas()
    canvas.axes.plot([1, 2, 3], [1, 4, 9])
    canvas.draw()
    buf = io.BytesIO()
    canvas.fig.savefig(buf, format="png", dpi=100)
    assert len(buf.getvalue()) > 0


def test_axes2_branch_in_store_original_limits_and_set_projection():
    """Exercises the axes2 (secondary Y axis) code path in both
    store_original_limits() and set_projection()."""
    canvas = HeadlessChartCanvas()

    # Create a secondary Y axis with twinx()
    canvas.axes2 = canvas.axes.twinx()

    # Plot on both primary and secondary axes
    canvas.axes.plot([1, 2, 3], [4, 5, 6], label="primary")
    canvas.axes2.plot([1, 2, 3], [10, 20, 30], label="secondary", color="orange")

    # Test store_original_limits() with axes2 present
    canvas.store_original_limits()
    assert canvas.original_xlim is not None
    assert canvas.original_ylim is not None
    assert canvas.original_ylim2 is not None  # Must capture axes2's limits

    # Test set_projection() with axes2 present -- it should remove axes2
    canvas.set_projection(projection_3d=True)
    assert canvas.is_3d is True
    assert canvas.axes2 is None  # axes2 must be removed when switching projection

    # After switching to 3D, original_ylim2 should be cleared
    assert canvas.original_ylim2 is None
