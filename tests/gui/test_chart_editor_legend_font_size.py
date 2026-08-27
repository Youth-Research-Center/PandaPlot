"""Regression test for the legend font-size bug in ChartEditor.update_chart:
Matplotlib silently ignores a `.legend(fontsize=...)` kwarg whenever `prop=`
is also passed, so the configured legend font size only takes effect if it's
merged into the `prop` dict alongside `family`. This exercises the real
`build_legend` helper used by `ChartEditorWidget.update_chart` (extracted so
it can be tested without a live QApplication/canvas)."""
from matplotlib.figure import Figure

from pandaplot.gui.components.tabs.chart.chart_editor import build_legend


def _plot_one_series(fig):
    axes = fig.add_subplot(111)
    axes.plot([1, 2, 3], [1, 2, 3], label="Series 1")
    return axes, *axes.get_legend_handles_labels()


def test_build_legend_applies_configured_font_size_with_font_family_set():
    fig = Figure()
    axes, handles, labels = _plot_one_series(fig)
    legend = build_legend(
        axes, handles, labels,
        "DejaVu Sans", 22,
        "#ffffff", show_frame=True, columns=1, bg_alpha=1.0,
        placement_kwargs={"loc": "upper right"},
    )
    assert legend.get_texts()[0].get_fontsize() == 22
    assert legend.get_texts()[0].get_fontfamily() == ["DejaVu Sans"]


def test_build_legend_applies_default_font_size_of_ten():
    fig = Figure()
    axes, handles, labels = _plot_one_series(fig)
    legend = build_legend(
        axes, handles, labels,
        "DejaVu Sans", 10,
        "#ffffff", show_frame=True, columns=1, bg_alpha=1.0,
        placement_kwargs={"loc": "upper right"},
    )
    assert legend.get_texts()[0].get_fontsize() == 10


def test_passing_fontsize_alongside_prop_without_size_is_silently_ignored():
    """Documents the underlying Matplotlib behaviour the fix works around:
    with both `fontsize=` and `prop=` (without `size` in `prop`), the legend
    text falls back to rcParams["legend.fontsize"], not the requested size."""
    fig = Figure()
    axes, handles, labels = _plot_one_series(fig)
    legend = axes.legend(handles, labels, fontsize=22, prop={"family": "DejaVu Sans"})
    assert legend.get_texts()[0].get_fontsize() != 22
