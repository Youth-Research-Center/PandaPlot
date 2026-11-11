"""Tests that value-label arrows are drawn with the styling from the series style (#504)."""
import matplotlib

matplotlib.use("Agg")  # no display needed for these pure-drawing tests
import pytest
from matplotlib.colors import to_rgba
from matplotlib.figure import Figure
from matplotlib.patches import ArrowStyle

from pandaplot.gui.components.tabs.chart.series_data import SeriesData
from pandaplot.gui.components.tabs.chart.series_renderers.line import render_line_series
from pandaplot.gui.components.tabs.chart.series_renderers.scatter import render_scatter_series
from pandaplot.gui.components.tabs.chart.series_renderers.value_labels import annotate_point_labels
from pandaplot.gui.components.tabs.chart.style_maps import ARROWSTYLE_MAP
from pandaplot.models.chart.marker_style import MarkerStyle
from pandaplot.models.chart.series_style import LineSeriesStyle, ScatterSeriesStyle
from pandaplot.models.chart.value_label_arrow import ValueLabelArrowLineStyle, ValueLabelArrowStyle

DATA = SeriesData(
    x_data=[1, 2, 3], y_data=[4.0, 5.0, 6.0],
    x_err=None, y_err=None, x_err_minus=None, y_err_minus=None, error=None,
)

# What matplotlib draws for each arrow style: the shaft only, an open head, a filled head.
ARROWSTYLE_CLASSES = {
    ValueLabelArrowStyle.LINE: ArrowStyle.Curve,
    ValueLabelArrowStyle.ARROW: ArrowStyle.CurveB,
    ValueLabelArrowStyle.FILLED_ARROW: ArrowStyle.CurveFilledB,
}


def _annotate(**kwargs):
    axes = Figure().add_subplot()
    annotate_point_labels(axes, DATA.x_data, DATA.y_data, show_arrow=True, text_color="#d62728", **kwargs)
    return axes.texts


def _arrow(**kwargs):
    return _annotate(**kwargs)[0].arrow_patch


def test_every_arrow_style_has_a_matplotlib_arrowstyle():
    assert set(ARROWSTYLE_MAP) == set(ValueLabelArrowStyle)


def test_default_arrow_keeps_the_historical_look():
    """Before #504 the arrow was a thin, solid, black plain line, faded with the series."""
    arrow = _arrow(alpha=0.7)

    assert type(arrow.get_arrowstyle()) is ArrowStyle.Curve
    assert arrow.get_edgecolor() == pytest.approx(to_rgba("black", 0.7))
    assert arrow.get_linewidth() == 1.0
    assert arrow.get_linestyle() in {"-", "solid"}
    assert arrow.get_alpha() == 0.7


@pytest.mark.parametrize("arrow_style", list(ValueLabelArrowStyle))
def test_arrow_style_selects_the_matplotlib_arrowstyle(arrow_style):
    arrow = _arrow(arrow_style=arrow_style)

    assert type(arrow.get_arrowstyle()) is ARROWSTYLE_CLASSES[arrow_style]


def test_unknown_arrow_style_and_line_style_draw_the_plain_solid_line():
    arrow = _arrow(arrow_style="typo", arrow_line_style="wiggly")

    assert type(arrow.get_arrowstyle()) is ArrowStyle.Curve
    assert arrow.get_linestyle() == "-"


def test_arrow_style_given_as_a_plain_string_is_accepted():
    assert type(_arrow(arrow_style="filled_arrow").get_arrowstyle()) is ArrowStyle.CurveFilledB


def test_arrow_color_is_used_for_the_shaft_and_a_filled_head():
    arrow = _arrow(arrow_style=ValueLabelArrowStyle.FILLED_ARROW, arrow_color="#2ca02c", alpha=0.5)

    assert arrow.get_edgecolor() == pytest.approx(to_rgba("#2ca02c", 0.5))
    assert arrow.get_facecolor() == pytest.approx(to_rgba("#2ca02c", 0.5))


def test_arrow_color_is_independent_of_the_label_text_color():
    text = _annotate(arrow_color="#2ca02c")[0]

    assert text.get_color() == "#d62728"
    assert text.arrow_patch.get_edgecolor()[:3] == pytest.approx(to_rgba("#2ca02c")[:3])


def test_empty_arrow_color_matches_the_label_text_color():
    arrow = _arrow(arrow_color="")

    assert arrow.get_edgecolor()[:3] == pytest.approx(to_rgba("#d62728")[:3])


def test_unusable_arrow_color_falls_back_to_the_label_text_color():
    arrow = _arrow(arrow_color="not-a-color")

    assert arrow.get_edgecolor()[:3] == pytest.approx(to_rgba("#d62728")[:3])


def test_arrow_width_sets_the_line_width():
    assert _arrow(arrow_width=3.5).get_linewidth() == 3.5


@pytest.mark.parametrize("unusable", [0, -1.0, float("nan"), float("inf"), "thick", None])
def test_unusable_arrow_width_draws_the_default_width(unusable):
    assert _arrow(arrow_width=unusable).get_linewidth() == 1.0


@pytest.mark.parametrize(
    ("line_style", "expected"),
    [
        (ValueLabelArrowLineStyle.SOLID, "-"),
        (ValueLabelArrowLineStyle.DASHED, "--"),
        (ValueLabelArrowLineStyle.DOTTED, ":"),
    ],
)
def test_arrow_line_style_sets_the_stroke(line_style, expected):
    assert _arrow(arrow_line_style=line_style).get_linestyle() == expected


def test_arrow_fades_with_the_series_alpha():
    assert _arrow(arrow_color="#2ca02c", alpha=0.3).get_alpha() == 0.3


def test_no_arrow_is_drawn_while_the_arrow_is_off_whatever_its_styling():
    axes = Figure().add_subplot()

    annotate_point_labels(
        axes, DATA.x_data, DATA.y_data, show_arrow=False,
        arrow_style=ValueLabelArrowStyle.FILLED_ARROW, arrow_color="#2ca02c", arrow_width=4.0,
    )

    assert axes.texts
    assert all(text.arrow_patch is None for text in axes.texts)


def test_arrow_styling_composes_with_offset_text_and_background_options():
    axes = Figure().add_subplot()

    annotate_point_labels(
        axes, DATA.x_data, DATA.y_data, mode="xy", show_arrow=True, offset_x=5.0, offset_y=-8.0,
        text_color="#d62728", bg_color="#ffff00", bg_alpha=0.5,
        arrow_style=ValueLabelArrowStyle.ARROW, arrow_color="#2ca02c",
    )

    text = axes.texts[0]
    assert text.get_text() == "1, 4"
    assert text.xyann == (5.0, -8.0)
    assert text.get_color() == "#d62728"
    assert text.get_bbox_patch().get_facecolor()[:3] == pytest.approx(to_rgba("#ffff00")[:3])
    assert type(text.arrow_patch.get_arrowstyle()) is ArrowStyle.CurveB


def test_every_labeled_point_gets_the_same_arrow_styling():
    arrows = [text.arrow_patch for text in _annotate(arrow_style="arrow", arrow_width=2.0)]

    assert len(arrows) == 3
    assert all(type(arrow.get_arrowstyle()) is ArrowStyle.CurveB and arrow.get_linewidth() == 2.0 for arrow in arrows)


STYLED_ARROW = {
    "value_label_arrow_style": ValueLabelArrowStyle.FILLED_ARROW,
    "value_label_arrow_color": "#2ca02c",
    "value_label_arrow_width": 2.5,
    "value_label_arrow_line_style": ValueLabelArrowLineStyle.DASHED,
}


def _assert_styled_arrow(arrow, *, alpha):
    assert type(arrow.get_arrowstyle()) is ArrowStyle.CurveFilledB
    assert arrow.get_edgecolor() == pytest.approx(to_rgba("#2ca02c", alpha))
    assert arrow.get_linewidth() == 2.5
    assert arrow.get_linestyle() == "--"
    assert arrow.get_alpha() == alpha


def test_line_series_arrows_use_the_style_fields():
    axes = Figure().add_subplot()
    style = LineSeriesStyle(
        show_value_labels=True, value_label_show_arrow=True, marker=MarkerStyle(marker_style="none", marker_size=1.0),
        **STYLED_ARROW,
    )

    render_line_series(axes, DATA, style, "s", 0.6, visible=True, extra={})

    assert len(axes.texts) == 3
    for text in axes.texts:
        _assert_styled_arrow(text.arrow_patch, alpha=0.6)


def test_scatter_series_arrows_use_the_style_fields():
    axes = Figure().add_subplot()
    style = ScatterSeriesStyle(show_value_labels=True, value_label_show_arrow=True, **STYLED_ARROW)

    render_scatter_series(axes, DATA, style, "s", 0.6, visible=True, extra={})

    assert len(axes.texts) == 3
    for text in axes.texts:
        _assert_styled_arrow(text.arrow_patch, alpha=0.6)


def test_line_series_arrow_matching_the_label_follows_the_series_color_by_default():
    axes = Figure().add_subplot()
    style = LineSeriesStyle(
        color="#9467bd", show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="",
        marker=MarkerStyle(marker_style="none", marker_size=1.0),
    )

    render_line_series(axes, DATA, style, "s", 1.0, visible=True, extra={})

    assert axes.texts[0].arrow_patch.get_edgecolor()[:3] == pytest.approx(to_rgba("#9467bd")[:3])


def test_line_series_arrow_matching_the_label_follows_an_explicit_text_color():
    axes = Figure().add_subplot()
    style = LineSeriesStyle(
        color="#9467bd", show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="",
        value_label_text_color="#d62728", marker=MarkerStyle(marker_style="none", marker_size=1.0),
    )

    render_line_series(axes, DATA, style, "s", 1.0, visible=True, extra={})

    assert axes.texts[0].arrow_patch.get_edgecolor()[:3] == pytest.approx(to_rgba("#d62728")[:3])


def test_scatter_series_arrow_matching_the_label_follows_the_marker_color():
    axes = Figure().add_subplot()
    style = ScatterSeriesStyle(
        show_value_labels=True, value_label_show_arrow=True, value_label_arrow_color="",
        marker=MarkerStyle(marker_color="#8c564b"),
    )

    render_scatter_series(axes, DATA, style, "s", 1.0, visible=True, extra={})

    assert axes.texts[0].arrow_patch.get_edgecolor()[:3] == pytest.approx(to_rgba("#8c564b")[:3])
